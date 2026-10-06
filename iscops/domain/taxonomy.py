"""Exception classes and dispositions for three-way match.

An exception class earns a slot only if it selects a different disposition or
requires different evidence. "Missing receipt" is deliberately absent: it is the
degenerate zero-received case of SHORT_RECEIPT, with the same disposition and the
same evidence, so it does not earn a class of its own.
"""

from enum import Enum


class ExceptionClass(str, Enum):
    """Detection signature is documented per member."""

    PRICE_VARIANCE = "price_variance"
    """Invoice unit price differs from PO unit price beyond tolerance."""

    QUANTITY_OVER_INVOICED = "quantity_over_invoiced"
    """Invoiced quantity exceeds received quantity, same UOM."""

    SHORT_RECEIPT = "short_receipt"
    """Received quantity is below invoiced quantity; zero received is the
    degenerate 'no receipt' case."""

    UOM_MISMATCH = "uom_mismatch"
    """Extended amounts agree while quantity and unit price disagree by a common
    factor. Looks exactly like large over-invoicing; it is a data problem."""

    PART_NOT_ON_PO = "part_not_on_po"
    """Invoice line cites no PO line, cites one the PO does not have, or cites
    one that ordered a different part."""

    DUPLICATE_INVOICE = "duplicate_invoice"
    """Supplier invoice number already seen against the same PO."""


class Disposition(str, Enum):
    AUTO_MATCH = "auto_match"
    RELEASE_WITHIN_TOLERANCE = "release_within_tolerance"
    REQUEST_CREDIT_MEMO = "request_credit_memo"
    HOLD_PENDING_RECEIPT = "hold_pending_receipt"
    REQUEST_PO_AMENDMENT = "request_po_amendment"
    REJECT_DUPLICATE = "reject_duplicate"
    ESCALATE = "escalate"


#: Dispositions that let the invoice go forward to payment. Every other
#: disposition stops it until a person or the supplier acts.
RELEASING: frozenset[Disposition] = frozenset({
    Disposition.AUTO_MATCH,
    Disposition.RELEASE_WITHIN_TOLERANCE,
})

#: Which dispositions each exception class permits. ESCALATE is always permitted:
#: an agent may always decline to decide. No class permits a RELEASING
#: disposition: an open exception never lets the invoice through.
PERMITTED: dict[ExceptionClass, frozenset[Disposition]] = {
    ExceptionClass.PRICE_VARIANCE: frozenset({
        Disposition.REQUEST_CREDIT_MEMO,
        Disposition.ESCALATE,
    }),
    ExceptionClass.QUANTITY_OVER_INVOICED: frozenset({
        Disposition.REQUEST_CREDIT_MEMO,
        Disposition.ESCALATE,
    }),
    ExceptionClass.SHORT_RECEIPT: frozenset({
        Disposition.HOLD_PENDING_RECEIPT,
        Disposition.ESCALATE,
    }),
    ExceptionClass.UOM_MISMATCH: frozenset({
        Disposition.REQUEST_PO_AMENDMENT,
        Disposition.ESCALATE,
    }),
    ExceptionClass.PART_NOT_ON_PO: frozenset({
        Disposition.REQUEST_PO_AMENDMENT,
        Disposition.ESCALATE,
    }),
    ExceptionClass.DUPLICATE_INVOICE: frozenset({
        Disposition.REJECT_DUPLICATE,
        Disposition.ESCALATE,
    }),
}

#: No exception AND no variance at all.
CLEAN_EXACT: frozenset[Disposition] = frozenset({
    Disposition.AUTO_MATCH,
    Disposition.ESCALATE,
})

#: No exception, but a price variance existed and was absorbed by tolerance.
#: This is a third state, not an exception class. Without it AUTO_MATCH and
#: RELEASE_WITHIN_TOLERANCE are indistinguishable to the gate, and the second is
#: unreachable — which is how the missing state was found.
CLEAN_ABSORBED: frozenset[Disposition] = frozenset({
    Disposition.RELEASE_WITHIN_TOLERANCE,
    Disposition.ESCALATE,
})


class EscalateOnly(str, Enum):
    """States in which no remedy is supportable.

    Like an absorbed variance, these are computed from the case and never
    claimed by the agent, so they are not exception classes (ADR-002, ADR-003).
    """

    UNDER_BILLED = "under_billed"
    """A unit price is below the PO price by more than tolerance. Every price
    remedy assumes the supplier overcharged."""

    PO_NUMBER_MISMATCH = "po_number_mismatch"
    """The invoice or the receipt cites a different PO from the one in the case.
    The three documents are not about the same order."""

    CURRENCY_MISMATCH = "currency_mismatch"
    """Invoice and PO are in different currencies. No price comparison between
    them means anything."""

    SUPPLIER_MISMATCH = "supplier_mismatch"
    """The invoice is from a different supplier than the PO was placed with."""

    RECEIPT_MISMATCH = "receipt_mismatch"
    """A receipt line cites a PO line the PO does not have, or records a
    different part or unit of measure from the one ordered. It is not evidence
    that the ordered goods arrived."""


#: What any EscalateOnly state leaves permitted.
ESCALATE_ONLY: frozenset[Disposition] = frozenset({Disposition.ESCALATE})


def permitted_for(
    classes: frozenset[ExceptionClass],
    absorbed_variance: bool = False,
    escalate_only: bool = False,
) -> frozenset[Disposition]:
    """Dispositions permitted given the exceptions actually found.

    Intersection, not union: with two exceptions open, only a disposition that
    both permit is valid. This is what makes a blocking exception dominate a
    releasable one. An EscalateOnly state intersects the same way.

    Call it through tools.match.permitted_dispositions(case), which works the
    two flags out from the case. Nothing else in iscops may call it directly.
    """
    if not classes:
        out = set(CLEAN_ABSORBED if absorbed_variance else CLEAN_EXACT)
    else:
        out = set(Disposition)
        for c in classes:
            out &= PERMITTED[c]
    if escalate_only:
        out &= ESCALATE_ONLY
    return frozenset(out)
