"""Records under three-way match.

Money is Decimal with an explicit currency, never float. Every quantity carries
an explicit UOM. There is no confidence field anywhere: these tools return exact
arithmetic, and judgment is the human approver's job.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    # strict=True is what makes float-for-Decimal raise instead of silently
    # coercing. Without it, 12.30 becomes Decimal('12.30000000000000071...').
    model_config = ConfigDict(frozen=True, strict=True)


class PurchaseOrderLine(_Frozen):
    line_number: int
    part_number: str
    quantity: Decimal
    uom: str
    unit_price: Decimal

    @property
    def extended(self) -> Decimal:
        return self.quantity * self.unit_price


class PurchaseOrder(_Frozen):
    po_number: str
    supplier: str
    currency: str
    lines: tuple[PurchaseOrderLine, ...]


class GoodsReceiptLine(_Frozen):
    po_line_number: int
    part_number: str
    quantity_received: Decimal
    uom: str


class GoodsReceipt(_Frozen):
    receipt_number: str
    po_number: str
    # May be empty: that is how "nothing has been received" is expressed.
    lines: tuple[GoodsReceiptLine, ...]


class InvoiceLine(_Frozen):
    line_number: int
    # None is legal and load-bearing: PART_NOT_ON_PO must be representable.
    po_line_number: int | None
    part_number: str
    quantity: Decimal
    uom: str
    unit_price: Decimal

    @property
    def extended(self) -> Decimal:
        return self.quantity * self.unit_price


class Invoice(_Frozen):
    invoice_id: str
    supplier_invoice_number: str
    po_number: str
    supplier: str
    currency: str
    lines: tuple[InvoiceLine, ...]


class MatchCase(_Frozen):
    scenario_id: str
    purchase_order: PurchaseOrder
    goods_receipt: GoodsReceipt
    invoice: Invoice
    # Invoice numbers already posted against this PO, for duplicate detection.
    prior_invoice_numbers: tuple[str, ...] = ()
