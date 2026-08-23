"""Twelve hand-constructed scenarios with known-correct dispositions.

No RNG. The corpus is written out literally, so determinism is by construction
rather than by seed — there is no wall-clock or hash-ordering surface to leak
through. That is a simplification against P1's convention and is recorded in
docs/LIMITATIONS.md.

Composition, with numerators rather than rates:
  2/12 clean or within-tolerance
  6/12 single exception, one per ExceptionClass
  2/12 co-occurring exceptions with a determinate answer
  2/12 genuinely insufficient evidence -> ESCALATE
"""

from decimal import Decimal as D

from pydantic import BaseModel, ConfigDict

from iscops.domain.records import (
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    MatchCase,
    PurchaseOrder,
    PurchaseOrderLine,
)
from iscops.domain.taxonomy import Disposition, ExceptionClass


class Gold(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    scenario_id: str
    exceptions: frozenset[ExceptionClass]
    disposition: Disposition
    rationale: str


def _case(
    sid: str,
    po_lines: list[tuple[int, str, str, str, str]],
    rcpt_lines: list[tuple[int, str, str, str]],
    inv_lines: list[tuple[int, int | None, str, str, str, str]],
    *,
    supplier_invoice_number: str = "SIN-0001",
    prior: tuple[str, ...] = (),
) -> MatchCase:
    return MatchCase(
        scenario_id=sid,
        purchase_order=PurchaseOrder(
            po_number=f"PO-{sid}",
            supplier="Vantage Bearings Pte Ltd",
            currency="USD",
            lines=tuple(
                PurchaseOrderLine(
                    line_number=n, part_number=p, quantity=D(q), uom=u, unit_price=D(pr)
                )
                for n, p, q, u, pr in po_lines
            ),
        ),
        goods_receipt=GoodsReceipt(
            receipt_number=f"GR-{sid}",
            po_number=f"PO-{sid}",
            lines=tuple(
                GoodsReceiptLine(
                    po_line_number=n, part_number=p, quantity_received=D(q), uom=u
                )
                for n, p, q, u in rcpt_lines
            ),
        ),
        invoice=Invoice(
            invoice_id=f"INV-{sid}",
            supplier_invoice_number=supplier_invoice_number,
            po_number=f"PO-{sid}",
            supplier="Vantage Bearings Pte Ltd",
            currency="USD",
            lines=tuple(
                InvoiceLine(
                    line_number=n,
                    po_line_number=pl,
                    part_number=p,
                    quantity=D(q),
                    uom=u,
                    unit_price=D(pr),
                )
                for n, pl, p, q, u, pr in inv_lines
            ),
        ),
        prior_invoice_numbers=prior,
    )


CASES: dict[str, MatchCase] = {
    # --- 2 clean / within tolerance -------------------------------------
    "S01": _case(
        "S01",
        [(1, "BRG-6204", "100", "EA", "12.50"), (2, "SEA-2210", "40", "EA", "3.75")],
        [(1, "BRG-6204", "100", "EA"), (2, "SEA-2210", "40", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "12.50"), (2, 2, "SEA-2210", "40", "EA", "3.75")],
    ),
    "S02": _case(  # +1.6% on unit price: inside the 2% band
        "S02",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "12.70")],
    ),
    # --- 6 single exception, one per class -------------------------------
    "S03": _case(  # +9.6%, well outside tolerance
        "S03",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "13.70")],
    ),
    "S04": _case(  # invoiced 120, received 100
        "S04",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "120", "EA", "12.50")],
    ),
    "S05": _case(  # received 60 of 100 invoiced; nothing wrong with the invoice yet
        "S05",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "60", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "12.50")],
    ),
    "S06": _case(  # PO in cases of 12, invoice in eaches. Extended amounts agree.
        "S06",
        [(1, "BRG-6204", "10", "CS", "150.00")],
        [(1, "BRG-6204", "10", "CS")],
        [(1, 1, "BRG-6204", "120", "EA", "12.50")],
    ),
    "S07": _case(  # line 2 of the invoice is not on the PO at all
        "S07",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [
            (1, 1, "BRG-6204", "100", "EA", "12.50"),
            (2, None, "FRT-EXP", "1", "EA", "220.00"),
        ],
    ),
    "S08": _case(  # same supplier invoice number already posted
        "S08",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "12.50")],
        supplier_invoice_number="SIN-8891",
        prior=("SIN-8891",),
    ),
    # --- 2 co-occurring, determinate -------------------------------------
    "S09": _case(  # over-invoiced quantity AND price outside tolerance
        "S09",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "120", "EA", "13.90")],
    ),
    "S10": _case(  # short receipt on line 1, clean line 2
        "S10",
        [(1, "BRG-6204", "100", "EA", "12.50"), (2, "SEA-2210", "40", "EA", "3.75")],
        [(1, "BRG-6204", "55", "EA"), (2, "SEA-2210", "40", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "12.50"), (2, 2, "SEA-2210", "40", "EA", "3.75")],
    ),
    # --- 2 escalate --------------------------------------------------------
    "S11": _case(  # unreferenced line AND nothing received: no basis to decide
        "S11",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [],
        [
            (1, 1, "BRG-6204", "100", "EA", "12.50"),
            (2, None, "TOOL-KIT", "2", "EA", "480.00"),
        ],
    ),
    "S12": _case(  # invoice is 12% BELOW the PO. Under-billing; no policy covers it.
        "S12",
        [(1, "BRG-6204", "100", "EA", "12.50")],
        [(1, "BRG-6204", "100", "EA")],
        [(1, 1, "BRG-6204", "100", "EA", "11.00")],
    ),
}


DEMO_CASE_IDS = ("S01", "S02", "S03", "S05", "S06", "S08")


GOLD: dict[str, Gold] = {
    "S01": Gold(
        scenario_id="S01",
        exceptions=frozenset(),
        disposition=Disposition.AUTO_MATCH,
        rationale="Both lines agree on quantity, UOM and price across all three documents.",
    ),
    "S02": Gold(
        scenario_id="S02",
        exceptions=frozenset(),
        disposition=Disposition.RELEASE_WITHIN_TOLERANCE,
        rationale="Unit price is 1.6% over PO, inside the 2% band, so no exception is raised.",
    ),
    "S03": Gold(
        scenario_id="S03",
        exceptions=frozenset({ExceptionClass.PRICE_VARIANCE}),
        disposition=Disposition.REQUEST_CREDIT_MEMO,
        rationale="Unit price 9.6% over PO with goods fully received; supplier owes the difference.",
    ),
    "S04": Gold(
        scenario_id="S04",
        exceptions=frozenset({ExceptionClass.QUANTITY_OVER_INVOICED}),
        disposition=Disposition.REQUEST_CREDIT_MEMO,
        rationale="Invoiced 120 EA against 100 EA received; 20 EA were never delivered.",
    ),
    "S05": Gold(
        scenario_id="S05",
        exceptions=frozenset({ExceptionClass.SHORT_RECEIPT}),
        disposition=Disposition.HOLD_PENDING_RECEIPT,
        rationale="Only 60 of 100 received. The invoice may be correct once the balance arrives.",
    ),
    "S06": Gold(
        scenario_id="S06",
        exceptions=frozenset({ExceptionClass.UOM_MISMATCH}),
        disposition=Disposition.REQUEST_PO_AMENDMENT,
        rationale=(
            "PO is in CS, invoice in EA, factor 12. Extended amounts agree exactly at "
            "1500.00, so nothing is owed either way. The trap: this presents as 12x "
            "over-invoicing and the naive answer is a credit memo."
        ),
    ),
    "S07": Gold(
        scenario_id="S07",
        exceptions=frozenset({ExceptionClass.PART_NOT_ON_PO}),
        disposition=Disposition.REQUEST_PO_AMENDMENT,
        rationale="Freight line is legitimate but unreferenced; the PO needs a line for it.",
    ),
    "S08": Gold(
        scenario_id="S08",
        exceptions=frozenset({ExceptionClass.DUPLICATE_INVOICE}),
        disposition=Disposition.REJECT_DUPLICATE,
        rationale="Supplier invoice number SIN-8891 is already posted against this PO.",
    ),
    "S09": Gold(
        scenario_id="S09",
        exceptions=frozenset(
            {ExceptionClass.QUANTITY_OVER_INVOICED, ExceptionClass.PRICE_VARIANCE}
        ),
        disposition=Disposition.REQUEST_CREDIT_MEMO,
        rationale="Both errors overcharge and both are settled by one credit memo.",
    ),
    "S10": Gold(
        scenario_id="S10",
        exceptions=frozenset({ExceptionClass.SHORT_RECEIPT}),
        disposition=Disposition.HOLD_PENDING_RECEIPT,
        rationale=(
            "Line 1 short by 45 EA, line 2 clean. One open line blocks the invoice; a "
            "clean second line does not release it."
        ),
    ),
    "S11": Gold(
        scenario_id="S11",
        exceptions=frozenset(
            {ExceptionClass.PART_NOT_ON_PO, ExceptionClass.SHORT_RECEIPT}
        ),
        disposition=Disposition.ESCALATE,
        rationale=(
            "Nothing received and an unreferenced 960.00 line. Neither a hold nor an "
            "amendment is supportable without knowing whether goods shipped at all."
        ),
    ),
    "S12": Gold(
        scenario_id="S12",
        exceptions=frozenset({ExceptionClass.PRICE_VARIANCE}),
        disposition=Disposition.ESCALATE,
        rationale=(
            "Invoice is 12% BELOW PO. Tolerance logic fires, but every remedy assumes "
            "the supplier overcharged. Under-billing is out of policy."
        ),
    ),
}
