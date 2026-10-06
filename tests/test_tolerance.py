"""The tolerance rule at its edges.

The twelve scenarios pin it at two points only: a difference of 0.20 is inside
and 1.20 is outside, both on a $12.50 part. Every price check in the corpus is on
a part under $25, so the 2% term never decides a case there. These tests decide
it.
"""

from decimal import Decimal as D

import pytest

from iscops.corpus.scenarios import CASES
from iscops.corpus.variants import repriced
from iscops.domain.taxonomy import ExceptionClass
from iscops.eval.engine_audit import TOLERANCE_EDGES, tolerance_violations
from iscops.tools.match import (
    PriceState,
    absorbed_variance,
    detect_exceptions,
    po_line_for,
    price_state,
    price_tolerance,
)


def test_tolerance_rule_holds_at_every_edge():
    assert tolerance_violations() == []


def test_edges_cover_both_terms_of_the_rule_and_their_crossing():
    two_percent = [price * D("0.02") for price, _ in TOLERANCE_EDGES]
    assert any(term < D("0.50") for term in two_percent)
    assert any(term > D("0.50") for term in two_percent)
    assert any(term == D("0.50") for term in two_percent)


@pytest.mark.parametrize(
    ("po_price", "invoice_price", "state"),
    [
        ("12.50", "12.50", PriceState.EXACT),
        ("12.50", "13.00", PriceState.ABSORBED),  # +0.50, on the floor
        ("12.50", "13.01", PriceState.OVER),
        ("12.50", "12.00", PriceState.ABSORBED),  # -0.50
        ("12.50", "11.99", PriceState.UNDER),
        ("100.00", "102.00", PriceState.ABSORBED),  # +2%, above the floor
        ("100.00", "102.01", PriceState.OVER),
        ("100.00", "98.00", PriceState.ABSORBED),
        ("100.00", "97.99", PriceState.UNDER),
    ],
)
def test_price_state_reads_as_the_rule_is_written(po_price, invoice_price, state):
    assert price_state(D(po_price), D(invoice_price)) is state


def test_tolerance_is_not_rounded_to_cents():
    assert price_tolerance(D("33.33")) == D("0.6666")
    assert price_state(D("33.33"), D("33.99")) is PriceState.ABSORBED  # +0.66
    assert price_state(D("33.33"), D("34.00")) is PriceState.OVER  # +0.67


def test_engine_and_price_state_agree_on_every_scenario_line():
    for scenario_id, case in CASES.items():
        states = []
        for inv in case.invoice.lines:
            po = po_line_for(case, inv)
            if po is not None and inv.uom == po.uom:
                states.append(price_state(po.unit_price, inv.unit_price))
        variance = ExceptionClass.PRICE_VARIANCE in detect_exceptions(case)
        assert variance == any(s in (PriceState.OVER, PriceState.UNDER) for s in states), scenario_id
        assert absorbed_variance(case) == any(s is PriceState.ABSORBED for s in states), scenario_id


def test_repriced_refuses_a_multi_line_case():
    with pytest.raises(ValueError):
        repriced(CASES["S01"], D("1.00"), D("1.00"))
