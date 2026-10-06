"""The policy table: what each state permits, and why each permission is there.

The first tests hold for any corpus. The scenario audit can only catch what a
scenario exercises; these catch a bad cell before anyone writes the scenario
that would expose it.
"""

from iscops.corpus.scenarios import CASES, GOLD
from iscops.domain.taxonomy import RELEASING, Disposition
from iscops.eval.gate_audit import audit, policy_rows, policy_violations, witness_violations


def test_policy_table_holds_its_structural_invariants():
    assert policy_violations() == []


def test_releasing_dispositions_are_reachable_only_from_clean_states():
    releasing_rows = {name for name, allowed in policy_rows().items() if allowed & RELEASING}
    assert releasing_rows == {"clean_exact", "clean_absorbed"}
    assert RELEASING == {Disposition.AUTO_MATCH, Disposition.RELEASE_WITHIN_TOLERANCE}


def test_gate_never_releases_payment_where_gold_blocks_it():
    released = [
        (a.scenario_id, a.disposition.value)
        for a in audit().admitted
        if a.releases_payment and a.disposition not in GOLD[a.scenario_id].acceptable
    ]
    assert released == []


def test_releasing_gold_exists_only_for_clean_scenarios():
    assert set(GOLD) == set(CASES)
    for scenario_id, gold in GOLD.items():
        if gold.acceptable & RELEASING:
            assert not gold.exceptions, scenario_id


def test_every_permitted_remedy_is_accepted_by_some_scenario():
    assert witness_violations() == []


def test_gold_accepts_its_own_preferred_disposition():
    for scenario_id, gold in GOLD.items():
        assert gold.acceptable == gold.also_acceptable | {gold.disposition}, scenario_id
