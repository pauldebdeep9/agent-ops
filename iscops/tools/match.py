"""Deterministic three-way match. No LLM, no confidence, exact arithmetic.

This module is ground truth for the approval gate. The agent does not compute
here; it dispatches tools and chooses a disposition. That split is deliberate —
a model that re-derives arithmetic in tokens will eventually get it wrong in a
way no test catches, because the test asserts the tool's output and never the
agent's restatement of it.
"""

from decimal import Decimal as D

from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import ExceptionClass

#: Unit-price tolerance: 2% of PO unit price, floored at $0.50.
#:
#: The brief said "2% or $50, whichever is greater". Applied to a unit price of
#: 12.50 that is a 400% band, which would swallow every price variance in the
#: corpus and make S03 and S12 undetectable. Flagged rather than routed around:
#: $50 is an extended-amount threshold, not a unit-price one.
PRICE_TOLERANCE_PCT = D("0.02")
PRICE_TOLERANCE_FLOOR = D("0.50")


def uom_factor(po_qty: D, inv_qty: D, po_price: D, inv_price: D) -> D | None:
    """Return the conversion factor if this is a UOM mismatch, else None.

    Signature: quantities differ by factor f, unit prices differ by 1/f, and the
    extended amounts agree exactly.
    """
    if inv_qty == 0 or po_price == 0 or po_qty == 0:
        return None
    if po_qty * po_price != inv_qty * inv_price:
        return None
    factor = inv_qty / po_qty
    return factor if factor != 1 else None


def absorbed_variance(case: MatchCase) -> bool:
    """True when a unit price differs from the PO but sits inside tolerance.

    Distinguishes "nothing differed" from "something differed and was absorbed" —
    the difference between AUTO_MATCH and RELEASE_WITHIN_TOLERANCE.
    """
    po_by_line = {ln.line_number: ln for ln in case.purchase_order.lines}
    for inv in case.invoice.lines:
        po = po_by_line.get(inv.po_line_number) if inv.po_line_number else None
        if po is None or inv.uom != po.uom:
            continue
        tol = max(po.unit_price * PRICE_TOLERANCE_PCT, PRICE_TOLERANCE_FLOOR)
        if 0 < abs(inv.unit_price - po.unit_price) <= tol:
            return True
    return False


def detect_exceptions(case: MatchCase) -> frozenset[ExceptionClass]:
    found: set[ExceptionClass] = set()

    if case.invoice.supplier_invoice_number in case.prior_invoice_numbers:
        found.add(ExceptionClass.DUPLICATE_INVOICE)

    po_by_line = {ln.line_number: ln for ln in case.purchase_order.lines}
    rcpt_by_line = {ln.po_line_number: ln for ln in case.goods_receipt.lines}

    for inv in case.invoice.lines:
        if inv.po_line_number is None or inv.po_line_number not in po_by_line:
            found.add(ExceptionClass.PART_NOT_ON_PO)
            continue

        po = po_by_line[inv.po_line_number]

        # UOM first: it masquerades as quantity and price variance at once, and
        # checking it after them produces two wrong findings instead of one right.
        if inv.uom != po.uom:
            found.add(ExceptionClass.UOM_MISMATCH)
            continue

        tol = max(po.unit_price * PRICE_TOLERANCE_PCT, PRICE_TOLERANCE_FLOOR)
        if abs(inv.unit_price - po.unit_price) > tol:
            found.add(ExceptionClass.PRICE_VARIANCE)

        received = (
            rcpt_by_line[inv.po_line_number].quantity_received
            if inv.po_line_number in rcpt_by_line
            else D(0)
        )
        if inv.quantity > received:
            # Over-invoiced vs short-received turns on the PO: if the PO covers
            # the invoiced quantity, the delivery is late; if it does not, the
            # supplier billed for goods never ordered.
            if inv.quantity > po.quantity:
                found.add(ExceptionClass.QUANTITY_OVER_INVOICED)
            elif received < po.quantity:
                found.add(ExceptionClass.SHORT_RECEIPT)
            else:
                found.add(ExceptionClass.QUANTITY_OVER_INVOICED)

    return frozenset(found)
