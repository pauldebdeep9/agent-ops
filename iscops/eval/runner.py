"""Scenario runner. Pass/fail against known-correct dispositions.

Deliberately not a metrics framework. With n=12 there is no rate to report: 9/12
is nine named scenarios, and any percentage computed from it will be read by
someone as a capability estimate it cannot support. Failures are named, never
aggregated away.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import iscops.config as config
from iscops.agent.loop import RunResult, Termination, run_case
from iscops.approval.gate import GateRejection, approve
from iscops.corpus.scenarios import CASES, GOLD
from iscops.domain.records import MatchCase


@dataclass
class Outcome:
    scenario_id: str
    passed: bool
    termination: Termination
    proposed: str | None
    expected: str
    steps: int
    note: str = ""


def persist_run(
    case: MatchCase,
    res: RunResult,
    *,
    model: str,
    step_budget: int,
    prompt_tokens: int,
    completion_tokens: int,
    credential_source: str,
    utc_start: str,
    utc_end: str,
) -> Path:
    """Write runs/<trace_id>/{steps.jsonl, approval.json|rejection.json, meta.json}.

    proposal.json is written separately, by the write_proposal tool itself
    (iscops/tools/registry.py) -- that is the one non-read-only tool, and it
    is the thing that actually writes now, not just something the read_only
    flag claims about it.

    A proposal that reaches the gate always leaves a record of the verdict:
    approval.json if it passed, rejection.json if it didn't. Silence is the
    defect this replaces.
    """
    run_dir = config.RUNS_DIR / res.trace_id
    run_dir.mkdir(parents=True, exist_ok=True)

    with (run_dir / "steps.jsonl").open("w") as f:
        for s in res.steps:
            f.write(json.dumps({
                "index": s.index,
                "tool": s.tool,
                "arguments": s.arguments,
                "result": s.result,
                "error": s.error,
            }) + "\n")

    gate_verdict = None
    if res.proposal is not None:
        try:
            record = approve(case, res.proposal)
            (run_dir / "approval.json").write_text(
                json.dumps(record.model_dump(mode="json"), indent=2)
            )
            gate_verdict = "approved"
        except GateRejection as e:
            (run_dir / "rejection.json").write_text(json.dumps({
                "scenario_id": case.scenario_id,
                "trace_id": res.trace_id,
                "reason": str(e),
            }, indent=2))
            gate_verdict = "rejected"

    meta = {
        "scenario_id": case.scenario_id,
        "trace_id": res.trace_id,
        "model": model,
        "step_budget": step_budget,
        "termination": res.termination.value,
        "turns_consumed": res.turns_consumed,
        "tool_calls_dispatched": len(res.steps),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "credential_source": credential_source,
        "gate_verdict": gate_verdict,
        "utc_start": utc_start,
        "utc_end": utc_end,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return run_dir


def run_all(
    client,
    step_budget: int = 8,
    *,
    persist: bool = False,
    model: str = "unknown",
    credential_source: str = "unknown",
) -> list[Outcome]:
    outcomes = []
    for sid, case in CASES.items():
        gold = GOLD[sid]
        prompt_before = getattr(client, "prompt_tokens", 0) or 0
        completion_before = getattr(client, "completion_tokens", 0) or 0
        utc_start = datetime.now(timezone.utc).isoformat()
        res = run_case(case, client, step_budget=step_budget)
        utc_end = datetime.now(timezone.utc).isoformat()
        prompt_after = getattr(client, "prompt_tokens", 0) or 0
        completion_after = getattr(client, "completion_tokens", 0) or 0

        proposed = res.proposal.disposition.value if res.proposal else None
        note = res.detail or ""
        passed = False
        if res.termination is Termination.DISPOSITION_REACHED and res.proposal:
            try:
                approve(case, res.proposal)
                passed = res.proposal.disposition == gold.disposition
                if not passed:
                    note = "gate passed, disposition disagrees with gold"
            except GateRejection as e:
                note = f"gate rejected: {e}"

        if persist:
            persist_run(
                case, res,
                model=model,
                step_budget=step_budget,
                prompt_tokens=prompt_after - prompt_before,
                completion_tokens=completion_after - completion_before,
                credential_source=credential_source,
                utc_start=utc_start,
                utc_end=utc_end,
            )

        outcomes.append(
            Outcome(sid, passed, res.termination, proposed,
                    gold.disposition.value, len(res.steps), note)
        )
    return outcomes


def report(outcomes: list[Outcome]) -> str:
    lines = [f"{sum(o.passed for o in outcomes)}/{len(outcomes)} scenarios passed", ""]
    for o in outcomes:
        mark = "PASS" if o.passed else "FAIL"
        lines.append(
            f"{mark}  {o.scenario_id}  {o.termination.value:<22} "
            f"proposed={o.proposed or '-':<26} expected={o.expected}"
        )
        if o.note:
            lines.append(f"        {o.note}")
    failed = [o.scenario_id for o in outcomes if not o.passed]
    if failed:
        lines += ["", "Failed: " + ", ".join(failed)]
    return "\n".join(lines)
