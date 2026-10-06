"""Everything the model is shown, as one value.

The system prompt, the tool schemas, and what each read-only tool returns for
each scenario. If this value changes, the agent is being measured on a different
task and earlier live results stop being comparable. Deterministic work on the
engine or the gate must leave it untouched.

    python -m iscops.eval.surface            # print the digest
    python -m iscops.eval.surface --write    # rewrite tests/fixtures/model_surface.json
"""

import hashlib
import json
import sys
from typing import Any

from iscops.agent.loop import SYSTEM
from iscops.config import REPO_ROOT
from iscops.corpus.scenarios import CASES
from iscops.tools.registry import build_registry

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "model_surface.json"


def model_surface() -> dict[str, Any]:
    schemas: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for scenario_id, case in CASES.items():
        registry = build_registry(case)
        schemas = [tool.as_openai_schema() for tool in registry.values()]
        payloads[scenario_id] = {
            tool.name: tool.fn() for tool in registry.values() if tool.read_only
        }
    return {"system": SYSTEM, "tool_schemas": schemas, "payloads": payloads}


def canonical(surface: dict[str, Any]) -> str:
    return json.dumps(surface, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def digest(surface: dict[str, Any] | None = None) -> str:
    text = canonical(model_surface() if surface is None else surface)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--write" in args:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(canonical(model_surface()))
    print(digest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
