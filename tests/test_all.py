"""Minimal test suite. Not coverage-driven — each test exists because it pins an
invariant that would otherwise fail silently.
"""

import json
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

import iscops.config as config
from iscops.agent.client import ModelTurn, ToolCall
from iscops.agent.loop import Termination, run_case
from iscops.approval.gate import GateRejection, Proposal, approve
from iscops.corpus.scenarios import CASES, GOLD
from iscops.domain.records import InvoiceLine, PurchaseOrderLine
from iscops.domain.taxonomy import (
    CLEAN_EXACT,
    PERMITTED,
    Disposition,
    ExceptionClass,
    permitted_for,
)
from iscops.eval.runner import persist_run
from iscops.tools.match import absorbed_variance, detect_exceptions
from iscops.tools.registry import build_registry


@pytest.fixture(autouse=True)
def _isolate_runs_dir(tmp_path, monkeypatch):
    """write_proposal and persist_run write to config.RUNS_DIR. Redirect it so
    make test never touches the repo's real runs/ directory."""
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)


# --- domain -----------------------------------------------------------------


def test_every_exception_permits_escalate_and_one_remedy():
    for cls, allowed in PERMITTED.items():
        assert Disposition.ESCALATE in allowed, cls
        assert len(allowed) >= 2, cls


def test_money_rejects_float():
    with pytest.raises(ValidationError):
        PurchaseOrderLine(
            line_number=1, part_number="X", quantity=D(1), uom="EA", unit_price=12.5
        )


def test_decimal_arithmetic_exact_at_the_cent():
    lines = [
        InvoiceLine(line_number=i, po_line_number=i, part_number="X",
                    quantity=D(3), uom="EA", unit_price=D("0.10"))
        for i in range(1, 4)
    ]
    assert sum(ln.extended for ln in lines) == D("0.90")


def test_part_not_on_po_is_representable():
    ln = InvoiceLine(line_number=1, po_line_number=None, part_number="FRT",
                     quantity=D(1), uom="EA", unit_price=D("10.00"))
    assert ln.po_line_number is None


def test_permitted_intersects_rather_than_unions():
    both = permitted_for(frozenset({
        ExceptionClass.QUANTITY_OVER_INVOICED, ExceptionClass.PRICE_VARIANCE
    }))
    # release_within_tolerance is fine for a price variance alone; it must not
    # survive once an over-invoiced quantity is also open.
    assert Disposition.RELEASE_WITHIN_TOLERANCE not in both
    assert Disposition.REQUEST_CREDIT_MEMO in both
    assert permitted_for(frozenset()) == CLEAN_EXACT


# --- corpus and match engine -------------------------------------------------


def test_detector_agrees_with_gold_on_every_scenario():
    diffs = {
        sid: (sorted(x.value for x in detect_exceptions(c)),
              sorted(x.value for x in GOLD[sid].exceptions))
        for sid, c in CASES.items()
        if detect_exceptions(c) != GOLD[sid].exceptions
    }
    assert not diffs, diffs


def test_gold_dispositions_are_all_permitted():
    for sid, g in GOLD.items():
        allowed = permitted_for(g.exceptions, absorbed_variance(CASES[sid]))
        assert g.disposition in allowed, (sid, sorted(d.value for d in allowed))


def test_uom_case_has_agreeing_extended_amounts():
    # If this stops holding, S06 is no longer the trap it was built to be.
    reg = build_registry(CASES["S06"])
    row = reg["compare_prices"].fn()["lines"][0]
    assert row["extended_amounts_agree"] is True
    assert reg["compare_quantities"].fn()["lines"][0]["uom_conversion_factor"] == "12"


def test_absorbed_variance_separates_s01_from_s02():
    assert absorbed_variance(CASES["S01"]) is False   # nothing differed
    assert absorbed_variance(CASES["S02"]) is True    # differed, inside tolerance
    assert absorbed_variance(CASES["S03"]) is False   # differed, outside tolerance


def test_corpus_composition():
    assert len(CASES) == 12
    assert sum(1 for g in GOLD.values() if not g.exceptions) == 2
    assert sum(1 for g in GOLD.values() if g.disposition is Disposition.ESCALATE) == 2
    assert {c for g in GOLD.values() for c in g.exceptions} == set(ExceptionClass)


# --- tools -------------------------------------------------------------------


def test_exactly_one_non_read_only_tool():
    reg = build_registry(CASES["S01"])
    assert [t.name for t in reg.values() if not t.read_only] == ["write_proposal"]


def test_tool_output_is_json_serialisable_and_free_of_floats():
    for tool in build_registry(CASES["S01"]).values():
        if tool.name == "write_proposal":
            continue
        blob = json.dumps(tool.fn())
        assert "e-" not in blob  # no float exponent notation leaking in
        json.loads(blob)


def test_write_proposal_actually_writes_proposal_json(tmp_path):
    # read_only=False on this tool is supposed to mean something. Before this,
    # nothing did: the tool returned a dict and touched no disk.
    reg = build_registry(CASES["S05"], trace_id="t-write-test", observed=[])
    reg["write_proposal"].fn(
        disposition="hold_pending_receipt",
        exception_classes=["short_receipt"],
        rationale="because",
    )
    payload = json.loads((tmp_path / "t-write-test" / "proposal.json").read_text())
    assert payload["scenario_id"] == "S05"
    assert payload["trace_id"] == "t-write-test"
    assert payload["disposition"] == "hold_pending_receipt"


# --- approval gate -----------------------------------------------------------


def _proposal(sid, disposition, exceptions, evidence=("get_po", "get_receipt", "get_invoice")):
    return Proposal(
        scenario_id=sid, disposition=disposition,
        exception_classes=frozenset(exceptions), rationale="because",
        trace_id="t0", evidence=evidence,
    )


def test_gate_accepts_a_correct_proposal():
    rec = approve(CASES["S05"], _proposal(
        "S05", Disposition.HOLD_PENDING_RECEIPT, {ExceptionClass.SHORT_RECEIPT}))
    assert rec.applied is False
    assert rec.verified_exception_classes == {ExceptionClass.SHORT_RECEIPT}
    assert rec.timestamp_utc.endswith("+00:00")


def test_gate_rejects_disposition_unsupported_by_verified_facts():
    """The P1 finding transposed: naming real exception classes is not the same
    as proposing a disposition those facts support."""
    with pytest.raises(GateRejection, match="not permitted"):
        approve(CASES["S05"], _proposal(
            "S05", Disposition.REJECT_DUPLICATE, {ExceptionClass.SHORT_RECEIPT}))


def test_gate_rejects_claimed_exceptions_that_are_not_present():
    # The naive answer to the UOM case. Real class, real evidence, wrong facts.
    with pytest.raises(GateRejection, match="do not match verified"):
        approve(CASES["S06"], _proposal(
            "S06", Disposition.REQUEST_CREDIT_MEMO,
            {ExceptionClass.QUANTITY_OVER_INVOICED}))


def test_gate_rejects_proposal_with_unobserved_evidence():
    with pytest.raises(GateRejection, match="never observed"):
        approve(CASES["S05"], _proposal(
            "S05", Disposition.HOLD_PENDING_RECEIPT,
            {ExceptionClass.SHORT_RECEIPT}, evidence=("get_po",)))


def test_gate_rejects_cross_case_proposal():
    with pytest.raises(GateRejection, match="targets"):
        approve(CASES["S01"], _proposal(
            "S05", Disposition.HOLD_PENDING_RECEIPT, {ExceptionClass.SHORT_RECEIPT}))


# --- agent loop (scripted client; see docs/LIMITATIONS.md) -------------------


class ScriptedClient:
    """Replays fixed turns. This exercises loop mechanics and nothing else — it
    cannot tell us whether a real model behaves this way."""

    def __init__(self, turns): self._turns, self.calls = list(turns), 0

    def complete(self, messages, tools):
        turn = self._turns[min(self.calls, len(self._turns) - 1)]
        self.calls += 1
        return turn


def _call(name, args="{}"):
    return ModelTurn(text=None, tool_calls=(ToolCall(f"c{name}", name, args),))


def test_loop_reaches_disposition():
    proposal_args = json.dumps({
        "disposition": "hold_pending_receipt",
        "exception_classes": ["short_receipt"],
        "rationale": "60 of 100 received",
    })
    client = ScriptedClient([
        _call("get_po"), _call("get_receipt"), _call("get_invoice"),
        _call("write_proposal", proposal_args),
    ])
    res = run_case(CASES["S05"], client)
    assert res.termination is Termination.DISPOSITION_REACHED
    assert approve(CASES["S05"], res.proposal).disposition is Disposition.HOLD_PENDING_RECEIPT


def test_loop_exhausts_budget_without_special_casing():
    res = run_case(CASES["S01"], ScriptedClient([_call("get_po")]), step_budget=3)
    assert res.termination is Termination.BUDGET_EXHAUSTED
    assert res.proposal is None
    assert len(res.steps) == 3


def test_silent_stop_is_not_recorded_as_success():
    """A turn with no tool call must be distinguishable from a resolved case."""
    res = run_case(CASES["S01"], ScriptedClient([ModelTurn(text="I think it's fine.")]))
    assert res.termination is Termination.NO_PROGRESS
    assert res.proposal is None


def test_malformed_arguments_surface_on_first_occurrence():
    client = ScriptedClient([_call("write_proposal", "{not json")])
    res = run_case(CASES["S01"], client)
    assert res.termination is Termination.INVALID_TOOL_CALL
    assert client.calls == 1  # not retried until the budget drained


def test_unknown_tool_terminates():
    res = run_case(CASES["S01"], ScriptedClient([_call("delete_everything")]))
    assert res.termination is Termination.INVALID_TOOL_CALL


# --- audit trail persistence --------------------------------------------------


def _batch(*names):
    return ModelTurn(text=None, tool_calls=tuple(ToolCall(f"c{n}", n, "{}") for n in names))


def test_rejected_proposal_produces_rejection_json():
    """A gate that silently discards is worse than no gate: reject_duplicate is
    not permitted for short_receipt, and that rejection must leave a record."""
    proposal_args = json.dumps({
        "disposition": "reject_duplicate",
        "exception_classes": ["short_receipt"],
        "rationale": "wrong on purpose",
    })
    client = ScriptedClient([
        _call("get_po"), _call("get_receipt"), _call("get_invoice"),
        _call("write_proposal", proposal_args),
    ])
    res = run_case(CASES["S05"], client)
    assert res.termination is Termination.DISPOSITION_REACHED

    run_dir = persist_run(
        CASES["S05"], res, model="test", step_budget=8,
        prompt_tokens=0, completion_tokens=0,
        credential_source="test", utc_start="t0", utc_end="t1",
    )
    assert (run_dir / "proposal.json").exists()  # written by the tool itself
    assert not (run_dir / "approval.json").exists()
    rejection = json.loads((run_dir / "rejection.json").read_text())
    assert rejection["scenario_id"] == "S05"
    assert "not permitted" in rejection["reason"]
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["gate_verdict"] == "rejected"


def test_approved_proposal_produces_approval_json():
    proposal_args = json.dumps({
        "disposition": "hold_pending_receipt",
        "exception_classes": ["short_receipt"],
        "rationale": "60 of 100 received",
    })
    client = ScriptedClient([
        _call("get_po"), _call("get_receipt"), _call("get_invoice"),
        _call("write_proposal", proposal_args),
    ])
    res = run_case(CASES["S05"], client)

    run_dir = persist_run(
        CASES["S05"], res, model="test", step_budget=8,
        prompt_tokens=0, completion_tokens=0,
        credential_source="test", utc_start="t0", utc_end="t1",
    )
    assert not (run_dir / "rejection.json").exists()
    approval = json.loads((run_dir / "approval.json").read_text())
    assert approval["disposition"] == "hold_pending_receipt"
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["gate_verdict"] == "approved"


def test_steps_jsonl_has_one_line_per_dispatch_and_no_float_exponents():
    client = ScriptedClient([_call("get_po"), _call("get_receipt"), _call("get_invoice")])
    res = run_case(CASES["S05"], client, step_budget=3)
    run_dir = persist_run(
        CASES["S05"], res, model="test", step_budget=3,
        prompt_tokens=0, completion_tokens=0,
        credential_source="test", utc_start="t0", utc_end="t1",
    )
    lines = (run_dir / "steps.jsonl").read_text().splitlines()
    assert len(lines) == len(res.steps) == 3
    for line in lines:
        assert "e-" not in line
        row = json.loads(line)
        assert set(row) == {"index", "tool", "arguments", "result", "error"}


def test_turns_consumed_and_tool_calls_dispatched_differ_under_batching():
    """Budget bounds turns, not tool calls: one batched turn can dispatch
    several. meta.json must not conflate the two."""
    proposal_args = json.dumps({
        "disposition": "hold_pending_receipt",
        "exception_classes": ["short_receipt"],
        "rationale": "60 of 100 received",
    })
    client = ScriptedClient([
        _batch("get_po", "get_receipt", "get_invoice"),
        _call("write_proposal", proposal_args),
    ])
    res = run_case(CASES["S05"], client)
    assert res.turns_consumed == 2
    assert len(res.steps) == 4

    run_dir = persist_run(
        CASES["S05"], res, model="test", step_budget=8,
        prompt_tokens=10, completion_tokens=5,
        credential_source="test", utc_start="t0", utc_end="t1",
    )
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["turns_consumed"] == 2
    assert meta["tool_calls_dispatched"] == 4
    assert meta["prompt_tokens"] == 10
    assert meta["completion_tokens"] == 5
    assert meta["credential_source"] == "test"
