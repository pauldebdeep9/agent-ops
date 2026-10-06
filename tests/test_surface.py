"""What the model is shown for the twelve scenarios.

The system prompt, the tool schemas and every read-only tool payload. If this
changes, the agent is being measured on a different task and earlier live
results stop being comparable. Regenerate the fixture only for a deliberate
change, with `python -m iscops.eval.surface --write`, and say so in the log.
"""

import json

from iscops.corpus.scenarios import CASES
from iscops.eval.surface import FIXTURE, canonical, digest, model_surface


def test_model_surface_is_unchanged():
    assert canonical(model_surface()) == FIXTURE.read_text()


def test_fixture_covers_every_scenario_and_every_read_only_tool():
    stored = json.loads(FIXTURE.read_text())
    assert stored["payloads"].keys() == CASES.keys()
    tools = {schema["function"]["name"] for schema in stored["tool_schemas"]}
    for payloads in stored["payloads"].values():
        assert set(payloads) == tools - {"write_proposal"}
    assert len(digest()) == 64
