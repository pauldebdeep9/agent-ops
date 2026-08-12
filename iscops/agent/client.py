"""Minimal chat client. ~50 lines, written rather than imported.

No structured outputs, so no strict-mode schema hardening: tool calling accepts
ordinary JSON Schema and validation happens on our side of the boundary.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string; parsed and validated by the loop


@dataclass(frozen=True)
class ModelTurn:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


class ChatClient(Protocol):
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...


class OpenAIClient:
    """Thin wrapper. Deliberately not a retry/backoff layer — a transport failure
    should surface as a failure, not as a quiet extra step against the budget."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0) -> None:
        from openai import OpenAI  # imported lazily so the rest of the repo

        self._client = OpenAI()  # runs without the SDK installed
        self.model = model
        self.temperature = temperature
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            temperature=self.temperature,
        )
        if resp.usage:
            self.prompt_tokens += resp.usage.prompt_tokens
            self.completion_tokens += resp.usage.completion_tokens
        msg = resp.choices[0].message
        calls = tuple(
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
            for c in (msg.tool_calls or [])
        )
        return ModelTurn(text=msg.content, tool_calls=calls)
