"""Settings. The dotenv export is not optional.

pydantic-settings reads .env into the Settings object but does NOT export to
os.environ, and the OpenAI SDK reads os.environ directly. Without the explicit
load_dotenv the SDK sees no key while Settings looks correctly populated.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"


def load_env() -> dict[str, bool]:
    """Export .env into os.environ without overriding the shell.

    Returns, per key found in .env, whether this call was the one that set
    it (True) or whether os.environ already had it from the shell (False).
    setdefault semantics are unchanged; this only makes the outcome visible.
    """
    origin_from_file: dict[str, bool] = {}
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return origin_from_file
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        already_present = key in os.environ
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))
        origin_from_file[key] = not already_present
    return origin_from_file


ENV_ORIGIN = load_env()

MODEL = os.environ.get("ISCOPS_MODEL", "gpt-4o-mini")
STEP_BUDGET = int(os.environ.get("ISCOPS_STEP_BUDGET", "8"))


def credential_source(key: str = "OPENAI_API_KEY") -> str:
    """'.env' if this process's load_env() call set it, else 'shell environment'."""
    return ".env" if ENV_ORIGIN.get(key, False) else "shell environment"


def masked(key: str = "OPENAI_API_KEY") -> str:
    value = os.environ.get(key)
    if not value:
        return "<unset>"
    return f"{value[:6]}...{value[-4:]}"


#: USD per 1M tokens, (input, output). Verified against OpenAI's published
#: pricing at the time this was written; not fetched live.
PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """None if the model isn't in PRICING_PER_1M, so callers can say 'unknown'
    instead of printing a wrong number for an unpriced model."""
    rates = PRICING_PER_1M.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return (prompt_tokens / 1_000_000) * input_rate + (completion_tokens / 1_000_000) * output_rate
