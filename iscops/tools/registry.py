"""Tool protocol, registry, and the six tools.

Every tool returns structured data, never prose. Exactly one tool is not
read-only. That invariant is one assertion (see tests/test_all.py) and it is
the enforceable form of "this agent does not move money".

Schemas are hand-written dicts rather than generated from Pydantic. Tool calling
does not require strict mode, so none of P1's schema-hardening problems
(additionalProperties on every $def, every property in required) arise here.
"""

import json
from dataclasses import dataclass
from decimal import Decimal as D
from typing import Any, Callable

import iscops.config as config
from iscops.domain.records import MatchCase
from iscops.tools.match import po_line_for, received_by_po_line, uom_factor


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., dict[str, Any]]
    read_only: bool = True

    def as_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_NO_ARGS = {"type": "object", "properties": {}, "required": []}


def _s(v: D) -> str:
    """Decimals cross the tool boundary as strings. JSON floats would reintroduce
    the imprecision the Decimal models exist to prevent."""
    return str(v)


def build_registry(
    case: MatchCase, trace_id: str = "adhoc", observed: list[str] | None = None
) -> dict[str, Tool]:
    """One registry per case. The case is closed over rather than passed as a
    tool argument, so the agent cannot address a different case by accident.

    trace_id and observed exist so write_proposal can record what it needs to:
    which run it belongs to, and what evidence preceded it. observed is the
    same list the loop uses for Proposal.evidence -- tools append their own
    name on call, rather than the loop tracking dispatch separately.
    """
    if observed is None:
        observed = []

    def get_po() -> dict[str, Any]:
        observed.append("get_po")
        return {
            "po_number": case.purchase_order.po_number,
            "supplier": case.purchase_order.supplier,
            "currency": case.purchase_order.currency,
            "lines": [
                {
                    "line_number": ln.line_number,
                    "part_number": ln.part_number,
                    "quantity": _s(ln.quantity),
                    "uom": ln.uom,
                    "unit_price": _s(ln.unit_price),
                    "extended": _s(ln.extended),
                }
                for ln in case.purchase_order.lines
            ],
        }

    def get_receipt() -> dict[str, Any]:
        observed.append("get_receipt")
        return {
            "receipt_number": case.goods_receipt.receipt_number,
            "line_count": len(case.goods_receipt.lines),
            "lines": [
                {
                    "po_line_number": ln.po_line_number,
                    "part_number": ln.part_number,
                    "quantity_received": _s(ln.quantity_received),
                    "uom": ln.uom,
                }
                for ln in case.goods_receipt.lines
            ],
        }

    def get_invoice() -> dict[str, Any]:
        observed.append("get_invoice")
        return {
            "invoice_id": case.invoice.invoice_id,
            "supplier_invoice_number": case.invoice.supplier_invoice_number,
            "prior_invoice_numbers_on_this_po": list(case.prior_invoice_numbers),
            "lines": [
                {
                    "line_number": ln.line_number,
                    "po_line_number": ln.po_line_number,
                    "part_number": ln.part_number,
                    "quantity": _s(ln.quantity),
                    "uom": ln.uom,
                    "unit_price": _s(ln.unit_price),
                    "extended": _s(ln.extended),
                }
                for ln in case.invoice.lines
            ],
        }

    def compare_quantities() -> dict[str, Any]:
        observed.append("compare_quantities")
        received = received_by_po_line(case)
        rows = []
        for inv in case.invoice.lines:
            po = po_line_for(case, inv)
            rc = received.get(inv.po_line_number) if po else None
            rows.append({
                "invoice_line": inv.line_number,
                "po_line": inv.po_line_number,
                "on_po": po is not None,
                "invoiced": _s(inv.quantity),
                "invoiced_uom": inv.uom,
                "ordered": _s(po.quantity) if po else None,
                "ordered_uom": po.uom if po else None,
                "received": _s(rc) if rc is not None else "0",
                "uom_conversion_factor": (
                    _s(f)
                    if po
                    and (f := uom_factor(po.quantity, inv.quantity, po.unit_price, inv.unit_price))
                    else None
                ),
            })
        return {"lines": rows}

    def compare_prices() -> dict[str, Any]:
        observed.append("compare_prices")
        rows = []
        for inv in case.invoice.lines:
            po = po_line_for(case, inv)
            if po is None:
                rows.append({
                    "invoice_line": inv.line_number,
                    "on_po": False,
                    "invoiced_unit_price": _s(inv.unit_price),
                })
                continue
            delta = inv.unit_price - po.unit_price
            rows.append({
                "invoice_line": inv.line_number,
                "on_po": True,
                "po_unit_price": _s(po.unit_price),
                "invoiced_unit_price": _s(inv.unit_price),
                "delta": _s(delta),
                "po_extended": _s(po.extended),
                "invoiced_extended": _s(inv.extended),
                "extended_amounts_agree": po.extended == inv.extended,
            })
        return {"lines": rows}

    def write_proposal(
        disposition: str, exception_classes: list[str], rationale: str
    ) -> dict[str, Any]:
        # The gate, not this tool, decides whether the proposal is admissible.
        # This writes what the agent claimed, unvalidated -- the raw attempt,
        # which is what "as submitted" means. Validation and evidence-checked
        # approval/rejection are the gate's job, recorded separately.
        observed.append("write_proposal")
        run_dir = config.RUNS_DIR / trace_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "proposal.json").write_text(json.dumps({
            "scenario_id": case.scenario_id,
            "trace_id": trace_id,
            "disposition": disposition,
            "exception_classes": exception_classes,
            "rationale": rationale,
            "evidence": list(dict.fromkeys(observed)),
        }, indent=2))
        return {
            "recorded": True,
            "disposition": disposition,
            "exception_classes": exception_classes,
            "rationale": rationale,
        }

    tools = [
        Tool("get_po", "Retrieve the purchase order and its lines.", _NO_ARGS, get_po),
        Tool("get_receipt", "Retrieve the goods receipt. May have zero lines.", _NO_ARGS, get_receipt),
        Tool("get_invoice", "Retrieve the invoice and prior invoice numbers on this PO.", _NO_ARGS, get_invoice),
        Tool("compare_quantities", "Per-line ordered vs received vs invoiced, with UOM and any conversion factor.", _NO_ARGS, compare_quantities),
        Tool("compare_prices", "Per-line PO vs invoiced unit price and extended amounts.", _NO_ARGS, compare_prices),
        Tool(
            "write_proposal",
            "Record a proposed disposition. Proposes only; nothing is executed.",
            {
                "type": "object",
                "properties": {
                    "disposition": {"type": "string"},
                    "exception_classes": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["disposition", "exception_classes", "rationale"],
            },
            write_proposal,
            read_only=False,
        ),
    ]
    return {t.name: t for t in tools}
