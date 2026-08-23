"""Run a concise live demonstration of the tool-calling agent."""

import argparse

from iscops.agent.client import OpenAIClient
from iscops.agent.loop import run_case
from iscops.approval.gate import GateRejection, approve
from iscops.config import MODEL, STEP_BUDGET
from iscops.corpus.scenarios import CASES, DEMO_CASE_IDS


def _classes(values) -> str:
    return ", ".join(sorted(value.value for value in values)) or "none"


def run_demo(scenario_id: str, client: OpenAIClient) -> None:
    case = CASES[scenario_id]
    print(f"\nScenario: {scenario_id}")

    result = run_case(case, client, step_budget=STEP_BUDGET)
    print("Agent tools:")
    if result.steps:
        for step in result.steps:
            print(f"  {step.tool}")
    else:
        print("  none")

    if result.proposal is None:
        print(f"Termination: {result.termination.value}")
        if result.detail:
            print(f"Detail: {result.detail}")
        return

    proposal = result.proposal
    print("Proposal:")
    print(f"  Exceptions: {_classes(proposal.exception_classes)}")
    print(f"  Disposition: {proposal.disposition.value}")
    print(f"  Rationale: {proposal.rationale}")

    print("Deterministic guard:")
    try:
        record = approve(case, proposal)
    except GateRejection as error:
        print(f"  REJECTED: {error}")
    else:
        print(f"  Verified exceptions: {_classes(record.verified_exception_classes)}")
        print("  APPROVED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ISC agent PoC")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scenario", choices=tuple(CASES))
    selection.add_argument("--all", action="store_true", help="run the demo subset")
    args = parser.parse_args()

    client = OpenAIClient(model=MODEL)
    scenario_ids = DEMO_CASE_IDS if args.all else (args.scenario,)
    for scenario_id in scenario_ids:
        run_demo(scenario_id, client)

    print(f"\nTotal tokens: {client.total_tokens}")


if __name__ == "__main__":
    main()
