"""Small cases at the edges of the engine that no scenario reaches.

Each one was a change to the engine that the suite did not notice until the
mutation pass (scripts/mutate.py) pointed at it.
"""

from decimal import Decimal as D

from iscops.corpus.scenarios import CASES
from iscops.corpus.variants import with_invoice_line, with_po_line, without_receipts
from iscops.domain.taxonomy import ExceptionClass
from iscops.tools.match import detect_exceptions, uom_factor


def test_one_unit_ordered_and_billed_with_nothing_received_is_a_short_receipt():
    case = without_receipts(CASES["S05"])
    case = with_po_line(case, 0, quantity=D(1))
    case = with_invoice_line(case, 0, quantity=D(1))
    assert detect_exceptions(case) == {ExceptionClass.SHORT_RECEIPT}


def test_uom_factor_is_none_whenever_any_quantity_or_the_po_price_is_zero():
    assert uom_factor(D(0), D(0), D("1.00"), D("1.00")) is None
    assert uom_factor(D(0), D(5), D("1.00"), D(0)) is None
    assert uom_factor(D(5), D(0), D(0), D("1.00")) is None
    assert uom_factor(D(10), D(120), D("150.00"), D("12.50")) == D(12)
    assert uom_factor(D(10), D(10), D("150.00"), D("150.00")) is None
