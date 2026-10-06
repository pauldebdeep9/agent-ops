"""The gate, measured over every proposal it can receive.

test_all.py checks a handful of proposals. These tests check all of them: the
proposal space is finite, so nothing here is sampled.
"""

from iscops.corpus.scenarios import CASES, GOLD
from iscops.domain import taxonomy
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.eval import audit as audit_cli
from iscops.eval.gate_audit import Admission, audit, audit_violations, claims, proposal_space
from iscops.tools.match import detect_exceptions


def test_the_space_is_the_full_product_of_both_enums():
    assert len(set(claims())) == 2 ** len(ExceptionClass)
    for case in CASES.values():
        space = list(proposal_space(case))
        assert len(space) == 2 ** len(ExceptionClass) * len(Disposition)
        assert len({(p.exception_classes, p.disposition) for p in space}) == len(space)
    assert audit().enumerated == len(CASES) * 2 ** len(ExceptionClass) * len(Disposition)


def test_gate_admits_only_the_verified_exception_set():
    wrong = [
        (a.scenario_id, sorted(c.value for c in a.claimed))
        for a in audit().admitted
        if a.claimed != detect_exceptions(CASES[a.scenario_id])
    ]
    assert wrong == []


def test_gold_is_admitted_on_every_scenario():
    admitted = {a.scenario_id for a in audit().admitted if a.kind is Admission.GOLD}
    assert admitted == set(GOLD)


def test_escalate_is_admitted_on_every_scenario():
    admitted = {
        a.scenario_id for a in audit().admitted if a.disposition is Disposition.ESCALATE
    }
    assert admitted == set(CASES)


def test_gate_admits_nothing_gold_does_not_accept_except_escalation():
    """The identity the audit exists for. Ten named pairs broke it on main; each
    was closed by a decision recorded in docs/adr/003."""
    assert [(a.scenario_id, a.disposition.value) for a in audit().findings] == []
    assert audit_violations() == []


def test_every_admission_is_gold_acceptable_or_escalation():
    for a in audit().admitted:
        assert a.disposition in GOLD[a.scenario_id].acceptable | {Disposition.ESCALATE}, a
        assert a.kind is not Admission.FINDING, a


def test_strict_exit_code_follows_the_checks(capsys, monkeypatch):
    assert audit_cli.main(["--strict"]) == 0
    assert "admitted" in capsys.readouterr().out

    widened = taxonomy.PERMITTED[ExceptionClass.DUPLICATE_INVOICE] | {Disposition.AUTO_MATCH}
    monkeypatch.setitem(taxonomy.PERMITTED, ExceptionClass.DUPLICATE_INVOICE, widened)
    assert audit_cli.main(["--strict"]) == 1
    assert "RELEASES PAYMENT" in capsys.readouterr().out


def test_without_strict_the_report_never_fails_the_command(monkeypatch, capsys):
    monkeypatch.setattr(audit_cli, "check", lambda: {"audit": ["S00: something is wrong"]})
    assert audit_cli.main([]) == 0
    assert audit_cli.main(["--strict"]) == 1
    assert "S00: something is wrong" in capsys.readouterr().out
