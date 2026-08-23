"""The agent loop: a while over tool dispatch. No framework.

Termination is an enum, never a boolean. The failure this guards against is
silent termination — the model stops calling tools, the loop exits, and the run
records as complete with no disposition, indistinguishable in the results from a
case genuinely resolved. That is the same shape as P1's auto_accept_error_rate,
where the failure most likely to go unnoticed was structurally excluded from the
metric meant to catch it.
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from iscops.approval.gate import Proposal
from iscops.domain.records import MatchCase
from iscops.domain.taxonomy import Disposition, ExceptionClass
from iscops.tools.registry import TOOL_SCHEMAS, build_registry


class Termination(str, Enum):
    DISPOSITION_REACHED = "disposition_reached"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_TOOL_CALL = "invalid_tool_call"
    NO_PROGRESS = "no_progress"  # a turn with neither a tool call nor a proposal


SYSTEM = """You resolve purchase-order invoice exceptions by three-way match.

Call tools to gather facts. Never compute from memory; the tools return exact
figures. When you have enough evidence, call write_proposal exactly once.

Exception classes: price_variance, quantity_over_invoiced, short_receipt,
uom_mismatch, part_not_on_po, duplicate_invoice.

Dispositions: auto_match, release_within_tolerance, request_credit_memo,
hold_pending_receipt, request_po_amendment, reject_duplicate, escalate.

Rules:
- Unit-price tolerance is 2% of the PO price, floored at $0.50. Inside it, no
  price exception exists.
- If invoice UOM differs from PO UOM and the extended amounts agree, this is
  uom_mismatch, a data problem. It is not over-invoicing and no money is owed.
- Choose escalate when the evidence does not support any remedy.
- You propose. You never execute."""


@dataclass
class Step:
    index: int
    tool: str | None
    arguments: dict[str, Any] | None
    result: Any
    error: str | None = None


@dataclass
class RunResult:
    scenario_id: str
    trace_id: str
    termination: Termination
    steps: list[Step] = field(default_factory=list)
    proposal: Proposal | None = None
    tools_observed: tuple[str, ...] = ()
    detail: str | None = None
    #: Turns (LLM API calls) actually made, out of step_budget. Not the same
    #: as len(steps): a turn can dispatch several tool calls at once.
    turns_consumed: int = 0


def run_case(
    case: MatchCase, client, step_budget: int = 8
) -> RunResult:
    trace_id = uuid.uuid4().hex[:12]
    observed: list[str] = []
    registry = build_registry(case, trace_id, observed)
    schemas = TOOL_SCHEMAS
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Resolve case {case.scenario_id}."},
    ]
    result = RunResult(case.scenario_id, trace_id, Termination.BUDGET_EXHAUSTED)

    for i in range(step_budget):
        turn = client.complete(messages, schemas)
        result.turns_consumed = i + 1

        if not turn.tool_calls:
            result.termination = Termination.NO_PROGRESS
            result.detail = (turn.text or "")[:200]
            return result

        messages.append({
            "role": "assistant",
            "content": turn.text,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments},
                }
                for c in turn.tool_calls
            ],
        })

        for call in turn.tool_calls:
            if call.name not in registry:
                result.termination = Termination.INVALID_TOOL_CALL
                result.detail = f"unknown tool {call.name!r}"
                result.steps.append(Step(i, call.name, None, None, result.detail))
                return result
            try:
                args = json.loads(call.arguments or "{}")
            except json.JSONDecodeError as e:
                # Surface on first occurrence with the payload, not on the fifth
                # after the budget has drained.
                result.termination = Termination.INVALID_TOOL_CALL
                result.detail = f"{call.name}: unparseable arguments: {e}"
                result.steps.append(Step(i, call.name, None, None, call.arguments[:200]))
                return result

            try:
                out = registry[call.name](**args)
            except TypeError as e:
                result.termination = Termination.INVALID_TOOL_CALL
                result.detail = f"{call.name}: bad arguments: {e}"
                result.steps.append(Step(i, call.name, args, None, str(e)))
                return result

            result.steps.append(Step(i, call.name, args, out))
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(out),
            })

            if call.name == "write_proposal":
                try:
                    proposal = Proposal(
                        scenario_id=case.scenario_id,
                        disposition=Disposition(args["disposition"]),
                        exception_classes=frozenset(
                            ExceptionClass(c) for c in args["exception_classes"]
                        ),
                        rationale=args["rationale"],
                        trace_id=trace_id,
                        evidence=tuple(dict.fromkeys(observed)),
                    )
                except (ValueError, KeyError) as e:
                    result.termination = Termination.INVALID_TOOL_CALL
                    result.detail = f"write_proposal: {e}"
                    return result
                result.proposal = proposal
                result.termination = Termination.DISPOSITION_REACHED
                result.tools_observed = proposal.evidence
                return result

    result.tools_observed = tuple(dict.fromkeys(observed))
    return result  # BUDGET_EXHAUSTED, set at construction. No special case.
