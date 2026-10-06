"""States that leave escalation as the only admissible disposition.

Under-billing is the first: an invoice priced below the PO by more than
tolerance. The engine reports it as a price variance, which is true, and every
price remedy assumes the supplier overcharged, which here is false. The rest are
documents that do not belong together.
"""

import ast
from decimal import Decimal as D
from pathlib import Path

import pytest

import iscops
from iscops.approval.gate import GateRejection, Proposal, RejectionCode, approve
from iscops.corpus.scenarios import CASES, GOLD
from iscops.corpus.variants import (
    repriced,
    with_invoice_header,
    with_receipt_header,
    with_receipt_line,
)
from iscops.domain.taxonomy import (
    ESCALATE_ONLY,
    Disposition,
    EscalateOnly,
    ExceptionClass,
    permitted_for,
)
from iscops.tools.match import (
    absorbed_variance,
    detect_exceptions,
    escalate_only_states,
    permitted_dispositions,
)

PV = frozenset({ExceptionClass.PRICE_VARIANCE})
DOCUMENT_TOOLS = ("get_po", "get_receipt", "get_invoice")

#: One way to raise each state that comes from the documents not agreeing.
MISMATCHES = {
    EscalateOnly.PO_NUMBER_MISMATCH: lambda case: with_invoice_header(case, po_number="PO-OTHER"),
    EscalateOnly.CURRENCY_MISMATCH: lambda case: with_invoice_header(case, currency="EUR"),
    EscalateOnly.SUPPLIER_MISMATCH: lambda case: with_invoice_header(case, supplier="Someone Else Ltd"),
    EscalateOnly.RECEIPT_MISMATCH: lambda case: with_receipt_line(case, 0, part_number="GEAR-9999"),
}
#: Scenarios with at least one receipt line, so every mismatch can be built.
RECEIVED = sorted(sid for sid, case in CASES.items() if case.goods_receipt.lines)


def _priced(po_price: str, invoice_price: str):
    return repriced(CASES["S03"], D(po_price), D(invoice_price))


def _proposal(scenario_id: str, disposition: Disposition, exceptions=frozenset()) -> Proposal:
    return Proposal(
        scenario_id=scenario_id, disposition=disposition, exception_classes=exceptions,
        rationale="because", trace_id="t0", evidence=DOCUMENT_TOOLS,
    )


# --- under-billing ----------------------------------------------------------------


def test_over_and_under_billing_are_the_same_class_and_different_states():
    over, under = _priced("12.50", "14.00"), _priced("12.50", "11.00")
    assert detect_exceptions(over) == detect_exceptions(under) == PV
    assert escalate_only_states(over) == frozenset()
    assert escalate_only_states(under) == {EscalateOnly.UNDER_BILLED}
    assert permitted_dispositions(over) == {Disposition.REQUEST_CREDIT_MEMO, Disposition.ESCALATE}
    assert permitted_dispositions(under) == ESCALATE_ONLY


def test_under_billing_inside_tolerance_is_absorbed_not_escalated():
    case = _priced("12.50", "12.30")
    assert detect_exceptions(case) == frozenset()
    assert absorbed_variance(case) is True
    assert escalate_only_states(case) == frozenset()
    assert Disposition.RELEASE_WITHIN_TOLERANCE in permitted_dispositions(case)


def test_under_billing_implies_a_price_variance():
    probes = list(CASES.values()) + [_priced("12.50", p) for p in ("11.00", "11.99", "12.00", "13.01")]
    for case in probes:
        if EscalateOnly.UNDER_BILLED in escalate_only_states(case):
            assert ExceptionClass.PRICE_VARIANCE in detect_exceptions(case), case.scenario_id


def test_s12_is_the_under_billing_scenario_and_admits_only_its_gold():
    assert escalate_only_states(CASES["S12"]) == {EscalateOnly.UNDER_BILLED}
    assert permitted_dispositions(CASES["S12"]) == {GOLD["S12"].disposition}
    assert [sid for sid, case in CASES.items() if sid != "S12" and escalate_only_states(case)] == []


def test_gate_names_the_state_when_it_refuses_a_remedy():
    with pytest.raises(GateRejection, match="escalate only") as caught:
        approve(CASES["S12"], _proposal("S12", Disposition.REQUEST_CREDIT_MEMO, PV))
    assert caught.value.code is RejectionCode.DISPOSITION_NOT_PERMITTED
    assert "under_billed" in str(caught.value)


# --- documents that do not belong together ----------------------------------------


@pytest.mark.parametrize("state", sorted(MISMATCHES, key=lambda s: s.value))
def test_a_mismatch_leaves_only_escalation_and_the_same_exceptions(state):
    for scenario_id in RECEIVED:
        case = CASES[scenario_id]
        broken = MISMATCHES[state](case)
        assert state in escalate_only_states(broken), scenario_id
        assert permitted_dispositions(broken) == ESCALATE_ONLY, scenario_id
        assert detect_exceptions(broken) == detect_exceptions(case), scenario_id


def test_a_receipt_for_another_po_is_a_po_number_mismatch():
    broken = with_receipt_header(CASES["S01"], po_number="PO-OTHER")
    assert escalate_only_states(broken) == {EscalateOnly.PO_NUMBER_MISMATCH}


def test_a_receipt_in_another_unit_or_for_an_unknown_line_is_a_receipt_mismatch():
    for fields in ({"uom": "CS"}, {"po_line_number": 99}):
        broken = with_receipt_line(CASES["S01"], 0, **fields)
        assert escalate_only_states(broken) == {EscalateOnly.RECEIPT_MISMATCH}, fields
        assert permitted_dispositions(broken) == ESCALATE_ONLY, fields


def test_gate_refuses_to_auto_match_documents_in_different_currencies():
    proposal = _proposal("S01", Disposition.AUTO_MATCH)
    approve(CASES["S01"], proposal)
    with pytest.raises(GateRejection, match="currency_mismatch"):
        approve(with_invoice_header(CASES["S01"], currency="EUR"), proposal)


# --- the mechanism ------------------------------------------------------------------


def test_no_scenario_has_mismatched_documents():
    states = set(MISMATCHES)
    assert [sid for sid, case in CASES.items() if escalate_only_states(case) & states] == []


def test_every_escalate_only_state_has_a_case_that_raises_it():
    raised = set(escalate_only_states(CASES["S12"]))
    raised |= {state for state, build in MISMATCHES.items() if state in escalate_only_states(build(CASES["S01"]))}
    assert raised == set(EscalateOnly)


def test_escalate_only_intersects_like_any_other_row():
    for classes in (PV, PV | {ExceptionClass.QUANTITY_OVER_INVOICED}, frozenset()):
        assert permitted_for(classes, escalate_only=True) <= ESCALATE_ONLY
        assert permitted_for(classes, escalate_only=True) <= permitted_for(classes)


def test_permitted_for_has_exactly_one_caller_inside_the_package():
    """The gate, the baseline and the audit must all reach the policy through
    permitted_dispositions(case). A second caller is how a state gets left out."""
    root = Path(iscops.__file__).parent
    callers = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name == "permitted_for":
                    callers.append(path.relative_to(root).as_posix())
    assert callers == ["tools/match.py"]
