"""Deterministic three-way match. No LLM, no confidence, exact arithmetic.

This module is ground truth for the approval gate. The agent does not compute
here; it dispatches tools and chooses a disposition. That split is deliberate —
a model that re-derives arithmetic in tokens will eventually get it wrong in a
way no test catches, because the test asserts the tool's output and never the
agent's restatement of it.
"""

from decimal import Decimal as D
from enum import Enum

from iscops.domain.records import InvoiceLine, MatchCase, PurchaseOrderLine
from iscops.domain.taxonomy import (
    Disposition,
    EscalateOnly,
    ExceptionClass,
    permitted_for,
)

#: Unit-price tolerance: 2% of PO unit price, floored at $0.50.
#:
#: The brief said "2% or $50, whichever is greater". Applied to a unit price of
#: 12.50 that is a 400% band, which would swallow every price variance in the
#: corpus and make S03 and S12 undetectable. Flagged rather than routed around:
#: $50 is an extended-amount threshold, not a unit-price one.
PRICE_TOLERANCE_PCT = D("0.02")
PRICE_TOLERANCE_FLOOR = D("0.50")


class PriceState(str, Enum):
    """Where an invoiced unit price sits relative to the PO unit price."""

    EXACT = "exact"
    ABSORBED = "absorbed"  # differs, inside tolerance
    OVER = "over"  # above the PO price by more than tolerance
    UNDER = "under"  # below the PO price by more than tolerance


def price_tolerance(po_unit_price: D) -> D:
    """The tolerance band for one PO unit price. The rule is written here once."""
    return max(po_unit_price * PRICE_TOLERANCE_PCT, PRICE_TOLERANCE_FLOOR)


def price_state(po_unit_price: D, invoice_unit_price: D) -> PriceState:
    """The single place a price is compared against tolerance. The band is
    closed: a difference exactly equal to the tolerance is absorbed."""
    delta = invoice_unit_price - po_unit_price
    if delta == 0:
        return PriceState.EXACT
    if abs(delta) <= price_tolerance(po_unit_price):
        return PriceState.ABSORBED
    return PriceState.OVER if delta > 0 else PriceState.UNDER


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


def po_line_for(case: MatchCase, inv: InvoiceLine) -> PurchaseOrderLine | None:
    """The PO line an invoice line is billing, or None.

    None when the line cites no PO line, cites one the PO does not have, or
    cites one that ordered a different part. In all three the PO does not cover
    what is being billed, which is PART_NOT_ON_PO. The tools ask the same
    question through this function, so the agent and the gate cannot disagree
    about which lines are on the PO.
    """
    for line in case.purchase_order.lines:
        if line.line_number == inv.po_line_number:
            return line if line.part_number == inv.part_number else None
    return None


def absorbed_variance(case: MatchCase) -> bool:
    """True when a unit price differs from the PO but sits inside tolerance.

    Distinguishes "nothing differed" from "something differed and was absorbed" —
    the difference between AUTO_MATCH and RELEASE_WITHIN_TOLERANCE.
    """
    for inv in case.invoice.lines:
        po = po_line_for(case, inv)
        if po is None or inv.uom != po.uom:
            continue
        if price_state(po.unit_price, inv.unit_price) is PriceState.ABSORBED:
            return True
    return False


def escalate_only_states(case: MatchCase) -> frozenset[EscalateOnly]:
    """States that leave escalation as the only admissible disposition."""
    found: set[EscalateOnly] = set()
    po, receipt, invoice = case.purchase_order, case.goods_receipt, case.invoice
    if invoice.po_number != po.po_number or receipt.po_number != po.po_number:
        found.add(EscalateOnly.PO_NUMBER_MISMATCH)
    if invoice.currency != po.currency:
        found.add(EscalateOnly.CURRENCY_MISMATCH)
    if invoice.supplier != po.supplier:
        found.add(EscalateOnly.SUPPLIER_MISMATCH)
    po_by_line = {ln.line_number: ln for ln in po.lines}
    for line in receipt.lines:
        ordered = po_by_line.get(line.po_line_number)
        if ordered is None or line.part_number != ordered.part_number or line.uom != ordered.uom:
            found.add(EscalateOnly.RECEIPT_MISMATCH)
    for inv in invoice.lines:
        ordered = po_line_for(case, inv)
        if ordered is None or inv.uom != ordered.uom:
            continue
        if price_state(ordered.unit_price, inv.unit_price) is PriceState.UNDER:
            found.add(EscalateOnly.UNDER_BILLED)
    return frozenset(found)


def permitted_dispositions(case: MatchCase) -> frozenset[Disposition]:
    """What the policy permits for this case. The one caller of permitted_for:
    the gate, the baseline and the audit all come through here, so none of them
    can leave a state out."""
    return permitted_for(
        detect_exceptions(case),
        absorbed_variance(case),
        bool(escalate_only_states(case)),
    )


def received_by_po_line(case: MatchCase) -> dict[int, D]:
    """Quantity received against each PO line, summed over every receipt line.

    Partial deliveries are the ordinary case, so one PO line can have several
    receipt lines. The compare_quantities tool reads this too: the agent is
    shown the same figure the gate uses.
    """
    received: dict[int, D] = {}
    for line in case.goods_receipt.lines:
        received[line.po_line_number] = received.get(line.po_line_number, D(0)) + line.quantity_received
    return received


def detect_exceptions(case: MatchCase) -> frozenset[ExceptionClass]:
    found: set[ExceptionClass] = set()

    if case.invoice.supplier_invoice_number in case.prior_invoice_numbers:
        found.add(ExceptionClass.DUPLICATE_INVOICE)

    po_by_line = {ln.line_number: ln for ln in case.purchase_order.lines}
    invoiced: dict[int, D] = {}

    for inv in case.invoice.lines:
        po = po_line_for(case, inv)
        if po is None:
            found.add(ExceptionClass.PART_NOT_ON_PO)
            continue

        # UOM first: it masquerades as quantity and price variance at once, and
        # checking it after them produces two wrong findings instead of one right.
        if inv.uom != po.uom:
            found.add(ExceptionClass.UOM_MISMATCH)
            continue

        # Price is a property of each invoice line.
        if price_state(po.unit_price, inv.unit_price) in (PriceState.OVER, PriceState.UNDER):
            found.add(ExceptionClass.PRICE_VARIANCE)

        # Quantity is a property of the PO line: several invoice lines may bill it.
        invoiced[po.line_number] = invoiced.get(po.line_number, D(0)) + inv.quantity

    received = received_by_po_line(case)
    for line_number, quantity in invoiced.items():
        if quantity > received.get(line_number, D(0)):
            # Over-invoiced vs short-received turns on the PO: if the PO covers
            # the invoiced quantity, the delivery is late; if it does not, the
            # supplier billed for goods never ordered.
            if quantity > po_by_line[line_number].quantity:
                found.add(ExceptionClass.QUANTITY_OVER_INVOICED)
            else:
                found.add(ExceptionClass.SHORT_RECEIPT)

    return frozenset(found)
