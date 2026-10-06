"""Which record fields the engine reads.

Change one field at a time, on every scenario, and see whether anything the
engine concludes changes. A field that never matters is either an identifier or
a hole. On main, 15 of 27 fields never mattered and only 4 are identifiers; the
other 11 included the part number on all three documents.
"""

import pytest

from iscops.approval.gate import GateRejection, Proposal, approve
from iscops.corpus.scenarios import CASES
from iscops.corpus.variants import field_perturbations, with_invoice_line
from iscops.domain import records
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.eval.engine_audit import UNREAD_BY_DESIGN, field_reading, field_violations
from iscops.tools.match import detect_exceptions
from iscops.tools.registry import build_registry

MODELS = (
    records.MatchCase, records.PurchaseOrder, records.PurchaseOrderLine,
    records.GoodsReceipt, records.GoodsReceiptLine, records.Invoice, records.InvoiceLine,
)
NESTED = {"purchase_order", "goods_receipt", "invoice", "lines"}
LEAF_FIELDS = {f"{m.__name__}.{f}" for m in MODELS for f in m.model_fields if f not in NESTED}


def test_every_field_of_every_record_is_perturbed():
    perturbed = {field for case in CASES.values() for field, _ in field_perturbations(case)}
    assert perturbed == LEAF_FIELDS


def test_a_perturbation_always_changes_the_case():
    for case in CASES.values():
        for field, changed in field_perturbations(case):
            assert changed != case, field


def test_the_engine_reads_every_field_that_is_not_an_identifier():
    assert field_violations() == []
    unread = {field for field, count in field_reading().items() if count == 0}
    assert unread == UNREAD_BY_DESIGN
    assert UNREAD_BY_DESIGN < LEAF_FIELDS


def test_billing_a_different_part_against_a_po_line_is_part_not_on_po():
    case = with_invoice_line(CASES["S01"], 0, part_number="GEAR-9999")
    assert detect_exceptions(case) == {ExceptionClass.PART_NOT_ON_PO}
    auto_match = Proposal(
        scenario_id="S01", disposition=Disposition.AUTO_MATCH,
        exception_classes=frozenset(), rationale="because", trace_id="t0",
        evidence=("get_po", "get_receipt", "get_invoice"),
    )
    with pytest.raises(GateRejection):
        approve(case, auto_match)


def test_an_invoice_line_citing_a_po_line_that_does_not_exist_is_part_not_on_po():
    case = with_invoice_line(CASES["S01"], 0, po_line_number=99)
    assert detect_exceptions(case) == {ExceptionClass.PART_NOT_ON_PO}


def test_tools_and_engine_agree_on_which_lines_are_on_the_po():
    case = with_invoice_line(CASES["S01"], 0, part_number="GEAR-9999")
    registry = build_registry(case)
    assert [row["on_po"] for row in registry["compare_quantities"].fn()["lines"]] == [False, True]
    assert [row["on_po"] for row in registry["compare_prices"].fn()["lines"]] == [False, True]
