"""Small transformations of a MatchCase.

Each returns a new case and leaves its input alone. They exist so a check can
ask "what does the engine say about this case with one thing changed" without
writing the case out again by hand.
"""

from decimal import Decimal

from iscops.domain.records import MatchCase


def repriced(
    case: MatchCase, po_unit_price: Decimal, invoice_unit_price: Decimal
) -> MatchCase:
    """The same single-line case at different prices.

    Only for cases with exactly one PO line and one invoice line, so there is no
    question about which line moved.
    """
    if len(case.purchase_order.lines) != 1 or len(case.invoice.lines) != 1:
        raise ValueError(f"{case.scenario_id}: repriced() needs a single-line case")
    po_line = case.purchase_order.lines[0].model_copy(update={"unit_price": po_unit_price})
    inv_line = case.invoice.lines[0].model_copy(update={"unit_price": invoice_unit_price})
    return case.model_copy(update={
        "purchase_order": case.purchase_order.model_copy(update={"lines": (po_line,)}),
        "invoice": case.invoice.model_copy(update={"lines": (inv_line,)}),
    })


def reversed_lines(case: MatchCase) -> MatchCase:
    """The same documents with every line list in the opposite order."""
    return case.model_copy(update={
        "purchase_order": case.purchase_order.model_copy(
            update={"lines": tuple(reversed(case.purchase_order.lines))}
        ),
        "goods_receipt": case.goods_receipt.model_copy(
            update={"lines": tuple(reversed(case.goods_receipt.lines))}
        ),
        "invoice": case.invoice.model_copy(
            update={"lines": tuple(reversed(case.invoice.lines))}
        ),
    })


def scaled(case: MatchCase, factor: Decimal) -> MatchCase:
    """Every quantity multiplied by the same positive factor. Prices unchanged."""
    if factor <= 0:
        raise ValueError("scaled() needs a positive factor")
    return case.model_copy(update={
        "purchase_order": case.purchase_order.model_copy(update={"lines": tuple(
            line.model_copy(update={"quantity": line.quantity * factor})
            for line in case.purchase_order.lines
        )}),
        "goods_receipt": case.goods_receipt.model_copy(update={"lines": tuple(
            line.model_copy(update={"quantity_received": line.quantity_received * factor})
            for line in case.goods_receipt.lines
        )}),
        "invoice": case.invoice.model_copy(update={"lines": tuple(
            line.model_copy(update={"quantity": line.quantity * factor})
            for line in case.invoice.lines
        )}),
    })


def _halves(quantity: Decimal) -> tuple[Decimal, Decimal] | None:
    """Two positive parts that sum to the quantity, or None if it cannot be split."""
    first = quantity // 2
    if first <= 0 or first >= quantity:
        return None
    return first, quantity - first


def split_invoice_lines(case: MatchCase) -> MatchCase:
    """Each invoice line billed as two lines against the same PO line.

    The invoice bills the same total for the same goods. Lines are renumbered.
    """
    lines = []
    for line in case.invoice.lines:
        parts = _halves(line.quantity)
        for quantity in parts or (line.quantity,):
            lines.append(line.model_copy(update={"quantity": quantity, "line_number": len(lines) + 1}))
    return case.model_copy(update={
        "invoice": case.invoice.model_copy(update={"lines": tuple(lines)}),
    })


def split_receipt_lines(case: MatchCase) -> MatchCase:
    """Each receipt line recorded as two partial receipts of the same total."""
    lines = []
    for line in case.goods_receipt.lines:
        parts = _halves(line.quantity_received)
        for quantity in parts or (line.quantity_received,):
            lines.append(line.model_copy(update={"quantity_received": quantity}))
    return case.model_copy(update={
        "goods_receipt": case.goods_receipt.model_copy(update={"lines": tuple(lines)}),
    })


def with_invoice_header(case: MatchCase, **fields: str) -> MatchCase:
    """The same case with invoice header fields replaced (po_number, supplier,
    currency). For building cases whose documents do not belong together."""
    return case.model_copy(update={"invoice": case.invoice.model_copy(update=fields)})


def with_receipt_header(case: MatchCase, **fields: str) -> MatchCase:
    return case.model_copy(update={"goods_receipt": case.goods_receipt.model_copy(update=fields)})


def with_receipt_line(case: MatchCase, index: int, **fields: object) -> MatchCase:
    """The same case with one receipt line's fields replaced."""
    lines = list(case.goods_receipt.lines)
    lines[index] = lines[index].model_copy(update=fields)
    return case.model_copy(update={
        "goods_receipt": case.goods_receipt.model_copy(update={"lines": tuple(lines)}),
    })


def with_invoice_line(case: MatchCase, index: int, **fields: object) -> MatchCase:
    """The same case with one invoice line's fields replaced."""
    lines = list(case.invoice.lines)
    lines[index] = lines[index].model_copy(update=fields)
    return case.model_copy(update={
        "invoice": case.invoice.model_copy(update={"lines": tuple(lines)}),
    })


def _changed(value: object) -> object:
    """A value of the same type that is certainly different."""
    if isinstance(value, Decimal):
        return value * 2 + 1
    if isinstance(value, int):
        return value + 100
    if isinstance(value, str):
        return value + "-OTHER"
    if value is None:
        return 100
    raise TypeError(f"no perturbation for {type(value).__name__}")


def field_perturbations(case: MatchCase):
    """Yield (field name, case) with that one field changed everywhere it occurs.

    Covers every leaf field of every record. The field name is
    "<Model>.<field>". Used to ask which fields the engine actually reads.
    """
    po, receipt, invoice = case.purchase_order, case.goods_receipt, case.invoice

    def bumped(obj, field):
        return obj.model_copy(update={field: _changed(getattr(obj, field))})

    yield "MatchCase.scenario_id", bumped(case, "scenario_id")
    yield "MatchCase.prior_invoice_numbers", case.model_copy(update={
        "prior_invoice_numbers": case.prior_invoice_numbers + (invoice.supplier_invoice_number,)
    })
    if case.prior_invoice_numbers:
        yield "MatchCase.prior_invoice_numbers", case.model_copy(update={"prior_invoice_numbers": ()})

    for name, document in (("purchase_order", po), ("goods_receipt", receipt), ("invoice", invoice)):
        for field in type(document).model_fields:
            if field == "lines":
                continue
            yield f"{type(document).__name__}.{field}", case.model_copy(update={name: bumped(document, field)})
        if not document.lines:
            continue
        for field in type(document.lines[0]).model_fields:
            lines = tuple(bumped(line, field) for line in document.lines)
            yield (
                f"{type(document.lines[0]).__name__}.{field}",
                case.model_copy(update={name: document.model_copy(update={"lines": lines})}),
            )


def with_po_line(case: MatchCase, index: int, **fields: object) -> MatchCase:
    """The same case with one PO line's fields replaced."""
    lines = list(case.purchase_order.lines)
    lines[index] = lines[index].model_copy(update=fields)
    return case.model_copy(update={
        "purchase_order": case.purchase_order.model_copy(update={"lines": tuple(lines)}),
    })


def without_receipts(case: MatchCase) -> MatchCase:
    """The same case with nothing received."""
    return case.model_copy(update={
        "goods_receipt": case.goods_receipt.model_copy(update={"lines": ()}),
    })
