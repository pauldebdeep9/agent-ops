"""Deterministically verify an agent's proposed business decision."""

from pydantic import BaseModel

from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import Disposition, ExceptionClass, permitted_for
from iscops.tools.match import absorbed_variance, detect_exceptions


class Proposal(BaseModel):
    disposition: Disposition
    exception_classes: frozenset[ExceptionClass]
    rationale: str


class GateRejection(Exception):
    pass


class ApprovalRecord(BaseModel):
    disposition: Disposition
    verified_exception_classes: frozenset[ExceptionClass]


def approve(case: MatchCase, proposal: Proposal) -> ApprovalRecord:
    """Raise GateRejection, or return the independently verified decision."""

    actual = detect_exceptions(case)

    if proposal.exception_classes != actual:
        claimed = sorted(c.value for c in proposal.exception_classes) or ["<none>"]
        verified = sorted(c.value for c in actual) or ["<none>"]
        raise GateRejection(
            f"claimed exceptions {claimed} do not match verified {verified}"
        )

    allowed = permitted_for(actual, absorbed_variance(case))
    if proposal.disposition not in allowed:
        raise GateRejection(
            f"disposition {proposal.disposition.value} not permitted given "
            f"{sorted(c.value for c in actual) or ['<none>']}; "
            f"allowed: {sorted(d.value for d in allowed)}"
        )

    if not proposal.rationale.strip():
        raise GateRejection("rationale is empty")

    return ApprovalRecord(
        disposition=proposal.disposition,
        verified_exception_classes=actual,
    )
