"""Changes to a case that must not change what the engine concludes.

Reordering lines, scaling every quantity, billing one line as two, or recording
one receipt as two partial receipts: the documents describe the same goods and
the same money, so everything the engine concludes must come out the same. The
right answer is inherited from the original scenario, not recomputed.
"""

import pytest

from iscops.approval.gate import GateRejection, Proposal, approve
from iscops.corpus.scenarios import CASES
from iscops.corpus.variants import reversed_lines, split_invoice_lines, split_receipt_lines
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.eval.engine_audit import VARIANTS, conclusions, variant_violations
from iscops.tools.match import detect_exceptions
from iscops.tools.registry import build_registry


def test_no_variant_changes_any_conclusion():
    assert variant_violations() == []


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_engine_conclusions_survive_the_variant(name):
    changed = [
        scenario_id
        for scenario_id, case in CASES.items()
        if conclusions(VARIANTS[name](case)) != conclusions(case)
    ]
    assert changed == []


def test_variants_keep_the_totals_they_claim_to_keep():
    for scenario_id, case in CASES.items():
        billed = sum(line.extended for line in case.invoice.lines)
        received = sum(line.quantity_received for line in case.goods_receipt.lines)
        assert sum(l.extended for l in split_invoice_lines(case).invoice.lines) == billed, scenario_id
        assert sum(l.quantity_received for l in split_receipt_lines(case).goods_receipt.lines) == received, scenario_id
        assert reversed_lines(reversed_lines(case)) == case, scenario_id


def test_splitting_actually_splits_something():
    assert any(len(split_invoice_lines(c).invoice.lines) > len(c.invoice.lines) for c in CASES.values())
    assert any(len(split_receipt_lines(c).goods_receipt.lines) > len(c.goods_receipt.lines) for c in CASES.values())


def _auto_match(case) -> Proposal:
    return Proposal(
        scenario_id=case.scenario_id, disposition=Disposition.AUTO_MATCH,
        exception_classes=frozenset(), rationale="because", trace_id="t0",
        evidence=("get_po", "get_receipt", "get_invoice"),
    )


def test_over_invoicing_billed_as_two_lines_is_still_over_invoicing():
    case = split_invoice_lines(CASES["S04"])  # 120 EA against a PO line of 100, as 60 + 60
    assert len(case.invoice.lines) == 2
    assert detect_exceptions(case) == {ExceptionClass.QUANTITY_OVER_INVOICED}
    with pytest.raises(GateRejection):
        approve(case, _auto_match(case))


def test_a_full_receipt_recorded_in_two_parts_is_not_a_short_receipt():
    case = split_receipt_lines(CASES["S01"])
    assert detect_exceptions(case) == frozenset()
    approve(case, _auto_match(case))


def test_compare_quantities_reports_the_received_total_per_po_line():
    case = split_receipt_lines(CASES["S05"])  # 60 received, as 30 + 30
    rows = build_registry(case)["compare_quantities"].fn()["lines"]
    assert [row["received"] for row in rows] == ["60"]
