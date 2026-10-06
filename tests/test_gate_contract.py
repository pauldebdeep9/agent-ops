"""The gate's five conditions, checked over every proposal that can be built.

README.md states the contract: approve() raises unless the proposal targets this
case, the three document tools were observed, the claimed exception classes match
what the engine verifies, the disposition is permitted, and a rationale is
present. gate_audit.expected_rejection is that sentence written as code,
independently of gate.py. approve() must agree with it on every proposal in the
space, so no condition can be deleted, reordered or inverted without a failure.
"""

import pytest
from pydantic import ValidationError

from iscops.approval.gate import GateRejection, Proposal, RejectionCode, approve
from iscops.corpus.scenarios import CASES
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.eval.gate_audit import (
    actual_rejection,
    contract_violations,
    expected_rejection,
    full_proposal_space,
)

DOCUMENT_TOOLS = ("get_po", "get_receipt", "get_invoice")


@pytest.mark.parametrize("scenario_id", sorted(CASES))
def test_gate_agrees_with_its_contract_on_every_proposal(scenario_id):
    other = next(sid for sid in sorted(CASES) if sid != scenario_id)
    case = CASES[scenario_id]
    space = list(full_proposal_space(case, other))
    assert len(space) == 2 ** len(ExceptionClass) * len(Disposition) * 8 * 2 * 3
    wrong = [
        p.model_dump(mode="json")
        for p in space
        if expected_rejection(case, p) != actual_rejection(case, p)
    ]
    assert wrong[:5] == []


def test_contract_check_is_clean_and_reaches_every_rejection_code():
    assert contract_violations() == []


def test_a_rejection_always_says_why():
    case = CASES["S05"]
    for proposal in full_proposal_space(case, "S01"):
        try:
            approve(case, proposal)
        except GateRejection as rejection:
            assert str(rejection).strip()
            assert isinstance(rejection.code, RejectionCode)


def _proposal(**overrides):
    fields = dict(
        scenario_id="S05",
        disposition=Disposition.HOLD_PENDING_RECEIPT,
        exception_classes=frozenset({ExceptionClass.SHORT_RECEIPT}),
        rationale="60 of 100 received",
        trace_id="t0",
        evidence=DOCUMENT_TOOLS,
    )
    return Proposal(**{**fields, **overrides})


def test_blank_rationale_is_rejected():
    with pytest.raises(GateRejection, match="rationale is empty") as caught:
        approve(CASES["S05"], _proposal(rationale="   "))
    assert caught.value.code is RejectionCode.RATIONALE_EMPTY


def test_proposal_does_not_coerce_strings_into_enums():
    with pytest.raises(ValidationError):
        _proposal(disposition="hold_pending_receipt")


def test_proposal_cannot_be_edited_after_construction():
    proposal = _proposal()
    with pytest.raises(ValidationError):
        proposal.disposition = Disposition.AUTO_MATCH


def test_approval_record_cannot_be_marked_applied():
    record = approve(CASES["S05"], _proposal())
    assert record.applied is False
    with pytest.raises(ValidationError):
        record.applied = True
    with pytest.raises(ValidationError):
        type(record)(**{**record.model_dump(), "disposition": "hold_pending_receipt"})


def test_a_mismatch_rejection_names_what_was_claimed_and_what_was_verified():
    """The reason is what the reviewer reads and what rejection.json keeps."""
    with pytest.raises(GateRejection) as caught:
        approve(CASES["S06"], _proposal(
            scenario_id="S06", disposition=Disposition.REQUEST_CREDIT_MEMO,
            exception_classes=frozenset({ExceptionClass.QUANTITY_OVER_INVOICED}),
        ))
    assert str(caught.value) == (
        "claimed exceptions ['quantity_over_invoiced'] do not match verified ['uom_mismatch']"
    )
    with pytest.raises(GateRejection) as caught:
        approve(CASES["S08"], _proposal(
            scenario_id="S08", disposition=Disposition.AUTO_MATCH, exception_classes=frozenset(),
        ))
    assert str(caught.value) == (
        "claimed exceptions ['<none>'] do not match verified ['duplicate_invoice']"
    )
    with pytest.raises(GateRejection) as caught:
        approve(CASES["S01"], _proposal(scenario_id="S01", disposition=Disposition.AUTO_MATCH))
    assert str(caught.value) == (
        "claimed exceptions ['short_receipt'] do not match verified ['<none>']"
    )


def test_a_not_permitted_rejection_names_the_verified_classes_and_what_is_allowed():
    with pytest.raises(GateRejection) as caught:
        approve(CASES["S05"], _proposal(disposition=Disposition.REJECT_DUPLICATE))
    assert str(caught.value) == (
        "disposition reject_duplicate not permitted given ['short_receipt']; "
        "allowed: ['escalate', 'hold_pending_receipt']"
    )
    with pytest.raises(GateRejection) as caught:
        approve(CASES["S01"], _proposal(
            scenario_id="S01", disposition=Disposition.REQUEST_CREDIT_MEMO,
            exception_classes=frozenset(),
        ))
    assert str(caught.value) == (
        "disposition request_credit_memo not permitted given ['<none>']; "
        "allowed: ['auto_match', 'escalate']"
    )
