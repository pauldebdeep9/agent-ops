"""Run all 12 scenarios against a live model. Requires OPENAI_API_KEY.

    python -m iscops.eval.cli
"""

from iscops.agent.client import OpenAIClient
from iscops.config import MODEL, STEP_BUDGET, credential_source, estimate_cost_usd, masked
from iscops.eval.runner import report, run_all


def main() -> None:
    cred_source = credential_source()
    print(f"model: {MODEL}  OPENAI_API_KEY: {masked()} (from {cred_source})")
    client = OpenAIClient(model=MODEL)
    outcomes = run_all(
        client, step_budget=STEP_BUDGET,
        persist=True, model=MODEL, credential_source=cred_source,
    )
    print(report(outcomes))
    print(
        f"\nprompt tokens: {client.prompt_tokens}  "
        f"completion tokens: {client.completion_tokens}  "
        f"total: {client.total_tokens}"
    )
    cost = estimate_cost_usd(MODEL, client.prompt_tokens, client.completion_tokens)
    print(f"estimated cost: ${cost:.6f}" if cost is not None else "estimated cost: unknown (no pricing for this model)")
    counts: dict[str, int] = {}
    for o in outcomes:
        counts[o.termination.value] = counts.get(o.termination.value, 0) + 1
    print("terminations: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
