"""Deterministic baseline: no LLM, no key required.

Runs the match engine and the gate across all 12 scenarios. This is the layer the
agent is measured against, and it is worth being able to run on its own — if the
baseline disagrees with gold, an agent failure tells you nothing.

    python -m iscops.eval.baseline
"""

from iscops.corpus.scenarios import CASES, GOLD
from iscops.tools.match import detect_exceptions, permitted_dispositions


def main() -> None:
    agree = 0
    print(f"{'ID':<5}{'verified exceptions':<44}{'gold disposition':<26}permitted")
    print("-" * 108)
    for sid, case in CASES.items():
        found = detect_exceptions(case)
        gold = GOLD[sid]
        allowed = permitted_dispositions(case)
        ok = found == gold.exceptions and gold.disposition in allowed
        agree += ok
        print(
            f"{sid:<5}{','.join(sorted(c.value for c in found)) or '-':<44}"
            f"{gold.disposition.value:<26}{len(allowed)} permitted"
            f"{'' if ok else '   <-- DISAGREES WITH GOLD'}"
        )
    print("-" * 108)
    print(f"{agree}/{len(CASES)} scenarios: engine agrees with gold and gold is permitted")


if __name__ == "__main__":
    main()
