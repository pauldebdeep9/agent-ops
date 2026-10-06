"""Every check is broken on purpose and required to notice.

A check that has never failed on a real defect proves nothing. Fail-first shows
that once, by hand. This file does it on every run: it damages the policy table,
the tolerance constants, the gate and the engine one piece at a time, and
requires the named check to report a violation each time.
"""

from decimal import Decimal as D

import pytest

from iscops.approval import gate
from iscops.domain import taxonomy
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.eval.audit import CHECKS, check
from iscops.eval.gate_audit import policy_rows
from iscops.tools import match

# --- the policy table, one cell at a time -------------------------------------------

POLICY_CELLS = [(row, disposition) for row in policy_rows() for disposition in Disposition]
POLICY_CHECKS = ("policy", "witness", "audit")  # cheapest first


def _flip(monkeypatch, row: str, disposition: Disposition) -> None:
    current = policy_rows()[row]
    flipped = current - {disposition} if disposition in current else current | {disposition}
    if row == "clean_exact":
        monkeypatch.setattr(taxonomy, "CLEAN_EXACT", flipped)
    elif row == "clean_absorbed":
        monkeypatch.setattr(taxonomy, "CLEAN_ABSORBED", flipped)
    elif row == "escalate_only":
        monkeypatch.setattr(taxonomy, "ESCALATE_ONLY", flipped)
    else:
        monkeypatch.setitem(taxonomy.PERMITTED, ExceptionClass(row), flipped)


def test_the_cells_are_the_whole_table():
    rows = policy_rows()
    assert set(rows) == {c.value for c in ExceptionClass} | {
        "clean_exact", "clean_absorbed", "escalate_only",
    }
    assert len(POLICY_CELLS) == len(rows) * len(Disposition)
    assert all(CHECKS[name]() == [] for name in POLICY_CHECKS)


@pytest.mark.parametrize(
    ("row", "disposition"), POLICY_CELLS, ids=[f"{r}:{d.value}" for r, d in POLICY_CELLS]
)
def test_flipping_any_one_policy_cell_is_noticed(monkeypatch, row, disposition):
    _flip(monkeypatch, row, disposition)
    assert any(CHECKS[name]() for name in POLICY_CHECKS), (row, disposition.value)


# --- the tolerance constants ----------------------------------------------------------

TOLERANCE_CHANGES = [
    ("PRICE_TOLERANCE_PCT", D("0")),
    ("PRICE_TOLERANCE_PCT", D("0.01")),
    ("PRICE_TOLERANCE_PCT", D("0.04")),
    ("PRICE_TOLERANCE_FLOOR", D("0")),
    ("PRICE_TOLERANCE_FLOOR", D("0.25")),
    ("PRICE_TOLERANCE_FLOOR", D("1.00")),
]


@pytest.mark.parametrize(("constant", "value"), TOLERANCE_CHANGES)
def test_changing_a_tolerance_constant_is_noticed(monkeypatch, constant, value):
    assert CHECKS["tolerance"]() == []
    assert getattr(match, constant) != value
    monkeypatch.setattr(match, constant, value)
    assert CHECKS["tolerance"]() != []


# --- one deliberate break per check -----------------------------------------------------


def _credit_memo_for_short_receipt(monkeypatch):
    _flip(monkeypatch, ExceptionClass.SHORT_RECEIPT.value, Disposition.REQUEST_CREDIT_MEMO)


def _auto_match_for_duplicates(monkeypatch):
    _flip(monkeypatch, ExceptionClass.DUPLICATE_INVOICE.value, Disposition.AUTO_MATCH)


def _evidence_not_required(monkeypatch):
    monkeypatch.setattr(gate, "REQUIRED_EVIDENCE", ())


def _no_floor(monkeypatch):
    monkeypatch.setattr(match, "PRICE_TOLERANCE_FLOOR", D("0"))


def _last_receipt_line_wins(monkeypatch):
    def last_wins(case):
        return {line.po_line_number: line.quantity_received for line in case.goods_receipt.lines}

    monkeypatch.setattr(match, "received_by_po_line", last_wins)


def _part_number_ignored(monkeypatch):
    def by_line_number_only(case, inv):
        for line in case.purchase_order.lines:
            if line.line_number == inv.po_line_number:
                return line
        return None

    monkeypatch.setattr(match, "po_line_for", by_line_number_only)


BREAKS = {
    "audit": _credit_memo_for_short_receipt,
    "policy": _auto_match_for_duplicates,
    "witness": _credit_memo_for_short_receipt,
    "contract": _evidence_not_required,
    "tolerance": _no_floor,
    "variants": _last_receipt_line_wins,
    "fields": _part_number_ignored,
}


def test_every_check_has_a_break_that_must_turn_it_red():
    assert set(BREAKS) == set(CHECKS)
    assert all(violations == [] for violations in check().values())


@pytest.mark.parametrize("name", sorted(BREAKS))
def test_each_check_goes_red_on_its_break(monkeypatch, name):
    BREAKS[name](monkeypatch)
    assert CHECKS[name]() != []
