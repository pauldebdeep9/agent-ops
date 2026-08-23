"""Load local environment settings used by the live demo."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Export .env without overriding values already set in the shell."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(
            key.strip(), value.strip().strip('"').strip("'")
        )


load_env()

MODEL = os.environ.get("ISCOPS_MODEL", "gpt-4o-mini")
STEP_BUDGET = int(os.environ.get("ISCOPS_STEP_BUDGET", "8"))
