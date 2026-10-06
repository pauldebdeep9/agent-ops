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
from enum import Enum

from pydantic import BaseModel, ConfigDict

from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.tools.match import (
    detect_exceptions,
    escalate_only_states,
    permitted_dispositions,
)


class Proposal(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    scenario_id: str
    disposition: Disposition
    exception_classes: frozenset[ExceptionClass]
    rationale: str
    trace_id: str
    # Names of tools whose output the agent actually observed.
    evidence: tuple[str, ...]


class RejectionCode(str, Enum):
    """Which condition failed. Declared in the order approve() checks them, so a
    proposal that breaks several is reported under the first."""

    WRONG_CASE = "wrong_case"
    EVIDENCE_MISSING = "evidence_missing"
    EXCEPTIONS_MISMATCH = "exceptions_mismatch"
    DISPOSITION_NOT_PERMITTED = "disposition_not_permitted"
    RATIONALE_EMPTY = "rationale_empty"


class GateRejection(Exception):
    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code


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
            RejectionCode.WRONG_CASE,
            f"proposal targets {proposal.scenario_id}, case is {case.scenario_id}",
        )

    missing = [t for t in REQUIRED_EVIDENCE if t not in proposal.evidence]
    if missing:
        raise GateRejection(
            RejectionCode.EVIDENCE_MISSING,
            f"evidence never observed: {', '.join(missing)}",
        )

    verified = detect_exceptions(case)

    # Claimed vs actual. Not "did the agent name a real class" but "are these the
    # classes that are actually present".
    if proposal.exception_classes != verified:
        claimed = sorted(c.value for c in proposal.exception_classes) or ["<none>"]
        actual = sorted(c.value for c in verified) or ["<none>"]
        raise GateRejection(
            RejectionCode.EXCEPTIONS_MISMATCH,
            f"claimed exceptions {claimed} do not match verified {actual}",
        )

    allowed = permitted_dispositions(case)
    if proposal.disposition not in allowed:
        forced = sorted(s.value for s in escalate_only_states(case))
        raise GateRejection(
            RejectionCode.DISPOSITION_NOT_PERMITTED,
            f"disposition {proposal.disposition.value} not permitted given "
            f"{sorted(c.value for c in verified) or ['<none>']}; "
            f"allowed: {sorted(d.value for d in allowed)}"
            + (f"; escalate only: {forced}" if forced else ""),
        )

    if not proposal.rationale.strip():
        raise GateRejection(RejectionCode.RATIONALE_EMPTY, "rationale is empty")

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
