"""Compact tests for the PoC's business rules, agent loop, and safety gate."""

import json
from decimal import Decimal as D

import pytest

from iscops.agent.client import ModelTurn, ToolCall
from iscops.agent.loop import Termination, run_case
from iscops.approval.gate import GateRejection, Proposal, approve
from iscops.corpus.scenarios import CASES, GOLD
from iscops.domain.records import InvoiceLine
from iscops.domain.taxonomy import (
    CLEAN_EXACT,
    Disposition,
    ExceptionClass,
    permitted_for,
)
from iscops.tools.match import absorbed_variance, detect_exceptions
from iscops.tools.registry import build_registry


def _contains_float(value) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(item) for item in value)
    return False


def test_decimal_arithmetic_and_tool_payload_boundary():
    lines = [
        InvoiceLine(line_number=i, po_line_number=i, part_number="X",
                    quantity=D(3), uom="EA", unit_price=D("0.10"))
        for i in range(1, 4)
    ]
    assert sum(line.extended for line in lines) == D("0.90")

    for name, tool in build_registry(CASES["S01"]).items():
        if name == "write_proposal":
            continue
        payload = tool()
        assert not _contains_float(payload), name
        assert json.loads(json.dumps(payload)) == payload


def test_disposition_policy_intersects_open_exceptions():
    allowed = permitted_for(frozenset({
        ExceptionClass.QUANTITY_OVER_INVOICED,
        ExceptionClass.PRICE_VARIANCE,
    }))
    assert Disposition.RELEASE_WITHIN_TOLERANCE not in allowed
    assert Disposition.REQUEST_CREDIT_MEMO in allowed
    assert permitted_for(frozenset()) == CLEAN_EXACT


def test_all_12_scenarios_match_gold_and_permit_gold_dispositions():
    expected_ids = {f"S{i:02}" for i in range(1, 13)}
    assert set(CASES) == set(GOLD) == expected_ids

    for scenario_id, case in CASES.items():
        actual = detect_exceptions(case)
        gold = GOLD[scenario_id]
        assert actual == gold.exceptions, scenario_id
        allowed = permitted_for(actual, absorbed_variance(case))
        assert gold.disposition in allowed, scenario_id


def test_exact_tolerated_and_real_price_variance_are_distinct():
    assert detect_exceptions(CASES["S01"]) == frozenset()
    assert absorbed_variance(CASES["S01"]) is False

    assert detect_exceptions(CASES["S02"]) == frozenset()
    assert absorbed_variance(CASES["S02"]) is True

    assert detect_exceptions(CASES["S03"]) == frozenset({
        ExceptionClass.PRICE_VARIANCE
    })
    assert absorbed_variance(CASES["S03"]) is False


def test_uom_case_is_not_misclassified_as_price_or_quantity_variance():
    assert detect_exceptions(CASES["S06"]) == {ExceptionClass.UOM_MISMATCH}
    registry = build_registry(CASES["S06"])
    assert registry["compare_prices"]()["lines"][0]["extended_amounts_agree"] is True
    quantities = registry["compare_quantities"]()["lines"][0]
    assert quantities["uom_conversion_factor"] == "12"


def _proposal(disposition, exceptions, rationale="because") -> Proposal:
    return Proposal(
        disposition=disposition,
        exception_classes=frozenset(exceptions),
        rationale=rationale,
    )


def test_gate_accepts_a_correct_proposal():
    proposal = _proposal(
        Disposition.HOLD_PENDING_RECEIPT, {ExceptionClass.SHORT_RECEIPT}
    )
    record = approve(CASES["S05"], proposal)
    assert record.disposition is Disposition.HOLD_PENDING_RECEIPT
    assert record.verified_exception_classes == {ExceptionClass.SHORT_RECEIPT}


@pytest.mark.parametrize(
    ("case_id", "disposition", "exceptions", "rationale", "message"),
    [
        (
            "S06", Disposition.REQUEST_CREDIT_MEMO,
            {ExceptionClass.QUANTITY_OVER_INVOICED}, "because", "do not match verified",
        ),
        (
            "S05", Disposition.REJECT_DUPLICATE,
            {ExceptionClass.SHORT_RECEIPT}, "because", "not permitted",
        ),
        (
            "S05", Disposition.HOLD_PENDING_RECEIPT,
            {ExceptionClass.SHORT_RECEIPT}, "   ", "rationale is empty",
        ),
    ],
)
def test_gate_rejects_invalid_proposals(
    case_id, disposition, exceptions, rationale, message
):
    proposal = _proposal(disposition, exceptions, rationale)
    with pytest.raises(GateRejection, match=message):
        approve(CASES[case_id], proposal)


class ScriptedClient:
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def complete(self, messages, tools):
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        return turn


def _call(name, arguments="{}"):
    return ModelTurn(text=None, tool_calls=(ToolCall(f"c{name}", name, arguments),))


def _batch(*names):
    return ModelTurn(
        text=None, tool_calls=tuple(ToolCall(f"c{name}", name, "{}") for name in names)
    )


def test_batched_agent_run_produces_an_approved_typed_proposal():
    proposal_arguments = json.dumps({
        "disposition": "hold_pending_receipt",
        "exception_classes": ["short_receipt"],
        "rationale": "60 of 100 received",
    })
    client = ScriptedClient([
        _batch("get_po", "get_receipt", "get_invoice"),
        _call("write_proposal", proposal_arguments),
    ])

    result = run_case(CASES["S05"], client)

    assert client.calls == 2
    assert [step.tool for step in result.steps] == [
        "get_po", "get_receipt", "get_invoice", "write_proposal",
    ]
    assert result.termination is Termination.DISPOSITION_REACHED
    assert isinstance(result.proposal, Proposal)
    approved = approve(CASES["S05"], result.proposal)
    assert approved.disposition is Disposition.HOLD_PENDING_RECEIPT


@pytest.mark.parametrize(
    ("turns", "step_budget", "termination", "step_count"),
    [
        ([_call("get_po")], 3, Termination.BUDGET_EXHAUSTED, 3),
        ([ModelTurn(text="I think it is fine.")], 8, Termination.NO_PROGRESS, 0),
    ],
)
def test_agent_stops_without_a_proposal(turns, step_budget, termination, step_count):
    result = run_case(CASES["S01"], ScriptedClient(turns), step_budget=step_budget)
    assert result.termination is termination
    assert result.proposal is None
    assert len(result.steps) == step_count


@pytest.mark.parametrize(
    ("tool_name", "arguments", "detail"),
    [
        ("write_proposal", "{not json", "unparseable arguments"),
        ("delete_everything", "{}", "unknown tool"),
        ("write_proposal", "{}", "bad arguments"),
    ],
)
def test_invalid_tool_calls_terminate_immediately(tool_name, arguments, detail):
    client = ScriptedClient([_call(tool_name, arguments)])
    result = run_case(CASES["S01"], client)
    assert result.termination is Termination.INVALID_TOOL_CALL
    assert detail in result.detail
    assert client.calls == 1
