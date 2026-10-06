"""The approval gate, measured over every proposal it can receive. No LLM, no key.

A proposal is a claimed set of exception classes plus one disposition. Both come
from closed enums, so for any case the proposal space is finite: every subset of
ExceptionClass times every Disposition. This module pushes that whole space
through approve() and reports what the gate admits, measured against gold.

It measures the gate, not the agent. Nothing here says what a model will
propose. It says what the gate would let through if a model proposed it.

Run it with `python -m iscops.eval.audit`.
"""

from dataclasses import dataclass
from enum import Enum
from itertools import combinations, product
from typing import Iterator, Mapping

from iscops.approval.gate import (
    REQUIRED_EVIDENCE,
    GateRejection,
    Proposal,
    RejectionCode,
    approve,
)
from iscops.corpus.scenarios import CASES, GOLD, Gold
from iscops.domain import taxonomy
from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.tools.match import absorbed_variance, detect_exceptions, permitted_dispositions

# --- the proposal space -----------------------------------------------------------


class Admission(str, Enum):
    """What an admitted proposal is, relative to gold."""

    GOLD = "gold"
    ACCEPTABLE = "acceptable"  # not the preferred answer, but gold accepts it
    ESCALATION = "escalation"  # declined to decide where gold names a remedy
    FINDING = "finding"  # a remedy the gate admits and gold does not accept


@dataclass(frozen=True)
class Admitted:
    scenario_id: str
    claimed: frozenset[ExceptionClass]
    disposition: Disposition
    kind: Admission

    @property
    def releases_payment(self) -> bool:
        return self.disposition in taxonomy.RELEASING


@dataclass(frozen=True)
class AuditReport:
    scenarios: int
    enumerated: int
    admitted: tuple[Admitted, ...]

    @property
    def findings(self) -> tuple[Admitted, ...]:
        return tuple(a for a in self.admitted if a.kind is Admission.FINDING)


def claims() -> tuple[frozenset[ExceptionClass], ...]:
    """Every subset of ExceptionClass, in a fixed order."""
    classes = tuple(ExceptionClass)
    return tuple(
        frozenset(subset)
        for size in range(len(classes) + 1)
        for subset in combinations(classes, size)
    )


def proposal_space(case: MatchCase) -> Iterator[Proposal]:
    """Every (claimed exception set, disposition) pair for one case.

    Everything else about the proposal is held valid, so the only reasons left
    for the gate to reject are the claim and the disposition.
    """
    for claimed in claims():
        for disposition in Disposition:
            yield Proposal(
                scenario_id=case.scenario_id,
                disposition=disposition,
                exception_classes=claimed,
                rationale="audit",
                trace_id="audit",
                evidence=REQUIRED_EVIDENCE,
            )


def admits(case: MatchCase, proposal: Proposal) -> bool:
    try:
        approve(case, proposal)
    except GateRejection:
        return False
    return True


def classify(gold: Gold, disposition: Disposition) -> Admission:
    if disposition is gold.disposition:
        return Admission.GOLD
    if disposition in gold.also_acceptable:
        return Admission.ACCEPTABLE
    if disposition is Disposition.ESCALATE:
        return Admission.ESCALATION
    return Admission.FINDING


def audit(
    cases: Mapping[str, MatchCase] = CASES, gold: Mapping[str, Gold] = GOLD
) -> AuditReport:
    enumerated = 0
    admitted: list[Admitted] = []
    for scenario_id, case in cases.items():
        for proposal in proposal_space(case):
            enumerated += 1
            if admits(case, proposal):
                admitted.append(
                    Admitted(
                        scenario_id,
                        proposal.exception_classes,
                        proposal.disposition,
                        classify(gold[scenario_id], proposal.disposition),
                    )
                )
    return AuditReport(len(cases), enumerated, tuple(admitted))


def render(report: AuditReport, gold: Mapping[str, Gold] = GOLD) -> str:
    """Counts with their denominators and every finding by name. No rate."""

    def scenarios(kind: Admission) -> int:
        return len({a.scenario_id for a in report.admitted if a.kind is kind})

    findings = report.findings
    lines = [
        f"Gate audit: {report.scenarios} scenarios x {len(claims())} claimed exception "
        f"sets x {len(Disposition)} dispositions = {report.enumerated} proposals",
        f"admitted {len(report.admitted)}/{report.enumerated}",
        f"  gold disposition admitted   {scenarios(Admission.GOLD)}/{report.scenarios} scenarios",
        f"  escalation instead of gold  {scenarios(Admission.ESCALATION)}/{report.scenarios} scenarios",
        f"  findings                    {len(findings)} in "
        f"{scenarios(Admission.FINDING)}/{report.scenarios} scenarios",
    ]
    if findings:
        lines += ["", f"{'ID':<5}{'gold':<26}admitted, not accepted by gold"]
        lines += [
            f"{a.scenario_id:<5}{gold[a.scenario_id].disposition.value:<26}{a.disposition.value}"
            f"{'   <-- RELEASES PAYMENT' if a.releases_payment else ''}"
            for a in findings
        ]
    return "\n".join(lines)


def audit_violations(
    cases: Mapping[str, MatchCase] = CASES, gold: Mapping[str, Gold] = GOLD
) -> list[str]:
    """Nothing admitted that gold does not accept, other than escalation. Gold
    and escalate admitted on every scenario. No claim admitted but the verified
    one."""
    report = audit(cases, gold)
    out = [
        f"{a.scenario_id}: admits {a.disposition.value}, which gold does not accept"
        + (" and which releases payment" if a.releases_payment else "")
        for a in report.findings
    ]
    for scenario_id, case in cases.items():
        mine = [a for a in report.admitted if a.scenario_id == scenario_id]
        if not any(a.kind is Admission.GOLD for a in mine):
            out.append(f"{scenario_id}: gold {gold[scenario_id].disposition.value} is not admitted")
        if not any(a.disposition is Disposition.ESCALATE for a in mine):
            out.append(f"{scenario_id}: escalate is not admitted")
        if any(a.claimed != detect_exceptions(case) for a in mine):
            out.append(f"{scenario_id}: a claim other than the verified exception set is admitted")
    return out


# --- the policy table ---------------------------------------------------------------


def policy_rows() -> dict[str, frozenset[Disposition]]:
    """Every row of the policy table, read at call time."""
    rows = {cls.value: allowed for cls, allowed in taxonomy.PERMITTED.items()}
    rows["clean_exact"] = taxonomy.CLEAN_EXACT
    rows["clean_absorbed"] = taxonomy.CLEAN_ABSORBED
    rows["escalate_only"] = taxonomy.ESCALATE_ONLY
    return rows


def policy_violations() -> list[str]:
    """Structural invariants of the policy table. They hold whatever the corpus
    contains, which is the point: a corpus can only show the cases it has."""
    out = [
        f"{name}: escalate is not permitted"
        for name, allowed in policy_rows().items()
        if Disposition.ESCALATE not in allowed
    ]
    for cls in ExceptionClass:
        allowed = taxonomy.PERMITTED.get(cls)
        if allowed is None:
            out.append(f"{cls.value}: no policy row")
            continue
        for disposition in sorted(allowed & taxonomy.RELEASING, key=lambda d: d.value):
            out.append(f"{cls.value}: permits {disposition.value}, which releases payment")
        if not allowed - {Disposition.ESCALATE}:
            out.append(f"{cls.value}: permits no remedy")
    # ADR-002: the two clean states, exactly.
    if taxonomy.CLEAN_EXACT != {Disposition.AUTO_MATCH, Disposition.ESCALATE}:
        out.append("clean_exact: must be exactly auto_match and escalate")
    if taxonomy.CLEAN_ABSORBED != {Disposition.RELEASE_WITHIN_TOLERANCE, Disposition.ESCALATE}:
        out.append("clean_absorbed: must be exactly release_within_tolerance and escalate")
    # ADR-003: an escalate-only state leaves escalation and nothing else.
    if taxonomy.ESCALATE_ONLY != {Disposition.ESCALATE}:
        out.append("escalate_only: must be exactly escalate")
    return out


def witness_violations(
    cases: Mapping[str, MatchCase] = CASES, gold: Mapping[str, Gold] = GOLD
) -> list[str]:
    """Every remedy the policy permits must be the accepted answer somewhere.

    A cell of the table that no scenario accepts is a permission nobody has
    examined. The witness has to isolate the row: a scenario whose verified
    exception set is that class alone, or a clean scenario in that clean state.
    """
    rows = policy_rows()
    accepted: dict[str, set[Disposition]] = {name: set() for name in rows}
    for scenario_id, case in cases.items():
        verified = detect_exceptions(case)
        if not verified:
            row = "clean_absorbed" if absorbed_variance(case) else "clean_exact"
        elif len(verified) == 1:
            row = next(iter(verified)).value
        else:
            continue
        accepted[row] |= gold[scenario_id].acceptable
    return [
        f"{name}: permits {disposition.value}, accepted by no scenario"
        for name, allowed in rows.items()
        for disposition in sorted(allowed - {Disposition.ESCALATE}, key=lambda d: d.value)
        if disposition not in accepted[name]
    ]


# --- the gate's contract ------------------------------------------------------------

# The five conditions in README.md, written out independently of gate.py. The
# tool names are literals on purpose: this is the oracle, not a second reader of
# gate.REQUIRED_EVIDENCE.
_DOCUMENT_TOOLS = ("get_po", "get_receipt", "get_invoice")
_EVIDENCE_SETS = tuple(
    subset
    for size in range(len(_DOCUMENT_TOOLS) + 1)
    for subset in combinations(_DOCUMENT_TOOLS, size)
)
_RATIONALES = ("because", "", " \t\n")


def expected_rejection(case: MatchCase, proposal: Proposal) -> RejectionCode | None:
    """The first condition the proposal breaks, or None if it breaks none."""
    if proposal.scenario_id != case.scenario_id:
        return RejectionCode.WRONG_CASE
    if not set(_DOCUMENT_TOOLS) <= set(proposal.evidence):
        return RejectionCode.EVIDENCE_MISSING
    if proposal.exception_classes != detect_exceptions(case):
        return RejectionCode.EXCEPTIONS_MISMATCH
    if proposal.disposition not in permitted_dispositions(case):
        return RejectionCode.DISPOSITION_NOT_PERMITTED
    if not proposal.rationale.strip():
        return RejectionCode.RATIONALE_EMPTY
    return None


def actual_rejection(case: MatchCase, proposal: Proposal) -> RejectionCode | None:
    try:
        approve(case, proposal)
    except GateRejection as rejection:
        return rejection.code
    return None


def full_proposal_space(case: MatchCase, other_scenario_id: str) -> Iterator[Proposal]:
    """Every proposal that can be built: claim x disposition x evidence observed
    x which case it names x rationale."""
    for claimed, disposition, evidence, scenario_id, rationale in product(
        claims(), Disposition, _EVIDENCE_SETS, (case.scenario_id, other_scenario_id), _RATIONALES
    ):
        yield Proposal(
            scenario_id=scenario_id,
            disposition=disposition,
            exception_classes=claimed,
            rationale=rationale,
            trace_id="contract",
            evidence=evidence,
        )


def contract_violations(cases: Mapping[str, MatchCase] = CASES) -> list[str]:
    """approve() must agree with the five README conditions, and report the first
    one broken, on every proposal that can be built. Every rejection code must
    be produced by something."""
    out: list[str] = []
    produced: set[RejectionCode | None] = set()
    scenario_ids = list(cases)
    for scenario_id, case in cases.items():
        other = next(sid for sid in scenario_ids if sid != scenario_id)
        disagreements = 0
        for proposal in full_proposal_space(case, other):
            got = actual_rejection(case, proposal)
            produced.add(got)
            disagreements += got != expected_rejection(case, proposal)
        if disagreements:
            out.append(f"{scenario_id}: gate disagrees with its contract on {disagreements} proposals")
    out += [
        f"rejection code {code.value} is never produced"
        for code in RejectionCode
        if code not in produced
    ]
    return out
