"""Approval gate and audit trail.

Nothing is applied. A proposal becomes an ApprovalRecord only if it survives the
gate, and an ApprovalRecord is a recommendation awaiting a human.

The check that matters is the third one. P1 found that a citation which resolves
is not a citation that supports: binding verified that [n] pointed at a real
chunk, and nothing verified that the sentence described what was in it. The same
shape applies here. A proposal can name real exception classes, cite real tool
output, and still propose a disposition those facts do not support. The gate
therefore re-derives the exceptions itself and compares, rather than trusting the
agent's account of them.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import Disposition, ExceptionClass, permitted_for
from iscops.tools.match import absorbed_variance, detect_exceptions


class Proposal(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    scenario_id: str
    disposition: Disposition
    exception_classes: frozenset[ExceptionClass]
    rationale: str
    trace_id: str
    # Names of tools whose output the agent actually observed.
    evidence: tuple[str, ...]


class GateRejection(Exception):
    pass


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    scenario_id: str
    actor: str
    timestamp_utc: str
    disposition: Disposition
    exception_classes: frozenset[ExceptionClass]
    rationale: str
    trace_id: str
    evidence: tuple[str, ...]
    #: What the deterministic engine found, recorded alongside what was claimed.
    verified_exception_classes: frozenset[ExceptionClass]
    applied: bool = False  # never set True anywhere in this repo


#: Tools whose output must have been observed before any proposal is admissible.
REQUIRED_EVIDENCE = ("get_po", "get_receipt", "get_invoice")


def approve(
    case: MatchCase, proposal: Proposal, actor: str = "pending_human_review"
) -> ApprovalRecord:
    """Raise GateRejection, or return an unapplied ApprovalRecord."""

    if proposal.scenario_id != case.scenario_id:
        raise GateRejection(
            f"proposal targets {proposal.scenario_id}, case is {case.scenario_id}"
        )

    missing = [t for t in REQUIRED_EVIDENCE if t not in proposal.evidence]
    if missing:
        raise GateRejection(f"evidence never observed: {', '.join(missing)}")

    verified = detect_exceptions(case)

    # Claimed vs actual. Not "did the agent name a real class" but "are these the
    # classes that are actually present".
    if proposal.exception_classes != verified:
        claimed = sorted(c.value for c in proposal.exception_classes) or ["<none>"]
        actual = sorted(c.value for c in verified) or ["<none>"]
        raise GateRejection(
            f"claimed exceptions {claimed} do not match verified {actual}"
        )

    allowed = permitted_for(verified, absorbed_variance(case))
    if proposal.disposition not in allowed:
        raise GateRejection(
            f"disposition {proposal.disposition.value} not permitted given "
            f"{sorted(c.value for c in verified) or ['<none>']}; "
            f"allowed: {sorted(d.value for d in allowed)}"
        )

    if not proposal.rationale.strip():
        raise GateRejection("rationale is empty")

    return ApprovalRecord(
        scenario_id=case.scenario_id,
        actor=actor,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        disposition=proposal.disposition,
        exception_classes=proposal.exception_classes,
        rationale=proposal.rationale,
        trace_id=proposal.trace_id,
        evidence=proposal.evidence,
        verified_exception_classes=verified,
    )
