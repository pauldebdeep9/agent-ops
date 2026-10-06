"""The match engine, measured as the case changes. No LLM, no key.

gate_audit holds a case still and varies the proposal. This module does the
opposite. It changes the case in ways whose effect is known in advance and
checks that the engine concludes what it should:

  tolerance   at the edges of the price band, the right side of each edge
  variants    rewriting a case without changing goods or money changes nothing
  fields      every field that is not an identifier is read by the engine

Run it with `python -m iscops.eval.audit`.
"""

from decimal import Decimal as D
from typing import Callable, Mapping

from iscops.corpus.scenarios import CASES
from iscops.corpus.variants import (
    field_perturbations,
    repriced,
    reversed_lines,
    scaled,
    split_invoice_lines,
    split_receipt_lines,
)
from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import ExceptionClass
from iscops.tools.match import (
    PriceState,
    absorbed_variance,
    detect_exceptions,
    escalate_only_states,
    permitted_dispositions,
    price_state,
    price_tolerance,
)


def conclusions(case: MatchCase) -> tuple[object, ...]:
    """Everything the engine concludes about a case."""
    return (
        detect_exceptions(case),
        absorbed_variance(case),
        escalate_only_states(case),
        permitted_dispositions(case),
    )


# --- tolerance ------------------------------------------------------------------------

#: (PO unit price, tolerance), written out by hand from the rule in
#: docs/LIMITATIONS.md: 2% of the PO unit price, floored at $0.50. This table
#: is the oracle, so nothing in it is computed. It has rows on both sides of
#: $25.00, where the two terms cross, and one where 2% is not a whole number of
#: cents.
TOLERANCE_EDGES: tuple[tuple[D, D], ...] = (
    (D("3.75"), D("0.50")),  # floor binds
    (D("12.50"), D("0.50")),  # floor binds
    (D("25.00"), D("0.50")),  # the two terms are equal
    (D("33.33"), D("0.6666")),  # 2% binds, and is not rounded to cents
    (D("100.00"), D("2.00")),  # 2% binds
    (D("150.00"), D("3.00")),  # 2% binds
)

_CENT = D("0.01")
#: The single-line scenario the edge probes are built from.
_EDGE_BASE = "S03"


def tolerance_violations() -> list[str]:
    """The tolerance rule at its edges, in both directions.

    At each edge the largest whole-cent difference inside the band is absorbed
    and one cent more is a price variance. Checked on price_state() directly and
    again through the engine on a real case, so the engine cannot stop using it.
    """
    out: list[str] = []
    for po_price, tolerance in TOLERANCE_EDGES:
        if price_tolerance(po_price) != tolerance:
            out.append(f"PO {po_price}: tolerance {price_tolerance(po_price)}, expected {tolerance}")
        inside = tolerance.quantize(_CENT, rounding="ROUND_DOWN")
        probes = [(D(0), PriceState.EXACT)]
        for sign, beyond in ((1, PriceState.OVER), (-1, PriceState.UNDER)):
            probes += [(sign * inside, PriceState.ABSORBED), (sign * (inside + _CENT), beyond)]
        for delta, expected in probes:
            invoice_price = po_price + delta
            got = price_state(po_price, invoice_price)
            if got is not expected:
                out.append(f"PO {po_price}, invoice {invoice_price}: {got.value}, expected {expected.value}")
            probe = repriced(CASES[_EDGE_BASE], po_price, invoice_price)
            engine = (
                ExceptionClass.PRICE_VARIANCE in detect_exceptions(probe),
                absorbed_variance(probe),
            )
            want = (expected in (PriceState.OVER, PriceState.UNDER), expected is PriceState.ABSORBED)
            if engine != want:
                out.append(
                    f"PO {po_price}, invoice {invoice_price}: engine says variance={engine[0]} "
                    f"absorbed={engine[1]}, expected variance={want[0]} absorbed={want[1]}"
                )
    return out


# --- variants ---------------------------------------------------------------------------

#: Rewritings that keep the goods and the money the same. The right answer for a
#: variant is the original scenario's, inherited rather than recomputed.
VARIANTS: dict[str, Callable[[MatchCase], MatchCase]] = {
    "reversed_lines": reversed_lines,
    "scaled_x3": lambda case: scaled(case, D(3)),
    "split_invoice_lines": split_invoice_lines,
    "split_receipt_lines": split_receipt_lines,
    "split_both": lambda case: split_receipt_lines(split_invoice_lines(case)),
}


def variant_violations(cases: Mapping[str, MatchCase] = CASES) -> list[str]:
    """Rewriting a case without changing the goods or the money must not change
    what the engine concludes."""
    return [
        f"{scenario_id}: conclusions change under {name}"
        for name, transform in VARIANTS.items()
        for scenario_id, case in cases.items()
        if conclusions(transform(case)) != conclusions(case)
    ]


# --- fields ---------------------------------------------------------------------------------

#: Fields the engine deliberately ignores: identifiers that name a document or
#: a line and say nothing about the goods or the money.
UNREAD_BY_DESIGN = frozenset({
    "MatchCase.scenario_id",
    "GoodsReceipt.receipt_number",
    "Invoice.invoice_id",
    "InvoiceLine.line_number",
})


def field_reading(cases: Mapping[str, MatchCase] = CASES) -> dict[str, int]:
    """For every record field, on how many scenarios changing it changes what the
    engine concludes. Zero means the engine never reads it."""
    hits: dict[str, set[str]] = {}
    for scenario_id, case in cases.items():
        before = conclusions(case)
        for field, changed in field_perturbations(case):
            hits.setdefault(field, set())
            if conclusions(changed) != before:
                hits[field].add(scenario_id)
    return {field: len(scenarios) for field, scenarios in hits.items()}


def field_violations(cases: Mapping[str, MatchCase] = CASES) -> list[str]:
    """A field that can change without any conclusion changing is a field the
    match does not depend on. That is right for an identifier and wrong for
    anything else."""
    unread = {field for field, count in field_reading(cases).items() if count == 0}
    return [
        f"{field}: never read by the engine" for field in sorted(unread - UNREAD_BY_DESIGN)
    ] + [
        f"{field}: listed as unread by design, but the engine reads it"
        for field in sorted(UNREAD_BY_DESIGN - unread)
    ]
