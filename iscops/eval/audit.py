"""Every deterministic check on the gate and the engine. No LLM, no key required.

    python -m iscops.eval.audit            # report
    python -m iscops.eval.audit --strict   # exit 1 if any check is violated

Each check returns a list of violations and reads the policy table, the
tolerance constants and the gate at call time. That is what lets
tests/test_falsifiability.py break one of them on purpose and require the check
to notice: a check that cannot be made to fail is not checking anything.
"""

import sys
from typing import Callable

from iscops.eval import engine_audit, gate_audit

#: name -> check. Looked up through the module at call time, on purpose.
CHECKS: dict[str, Callable[[], list[str]]] = {
    "audit": lambda: gate_audit.audit_violations(),
    "policy": lambda: gate_audit.policy_violations(),
    "witness": lambda: gate_audit.witness_violations(),
    "contract": lambda: gate_audit.contract_violations(),
    "tolerance": lambda: engine_audit.tolerance_violations(),
    "variants": lambda: engine_audit.variant_violations(),
    "fields": lambda: engine_audit.field_violations(),
}


def check() -> dict[str, list[str]]:
    return {name: run() for name, run in CHECKS.items()}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(gate_audit.render(gate_audit.audit()))
    results = check()
    print()
    for name, violations in results.items():
        print(f"check {name:<10} {'ok' if not violations else f'{len(violations)} violated'}")
        for violation in violations:
            print(f"  {violation}")
    return 1 if "--strict" in args and any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
