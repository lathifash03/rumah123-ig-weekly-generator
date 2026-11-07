"""Thin OpenAI wrapper: structured JSON output plus token accounting.

The model name is always supplied from configuration. Nothing here defaults to
a model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from openai import OpenAI

from .config import Env, env


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, usage) -> None:
        self.calls += 1
        if usage is None:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.total_tokens += getattr(usage, "total_tokens", 0) or 0

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLM:
    """Structured-output client. Pass a stub in tests instead of this."""

    settings: Env = field(default_factory=lambda: env(require_api_key=True))
    usage: Usage = field(default_factory=Usage)
    _client: OpenAI | None = None

    def __post_init__(self) -> None:
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.api_key)

    @property
    def model(self) -> str:
        return self.settings.model

    def json(self, system: str, user: str, schema: dict) -> dict:
        """One call returning JSON that conforms to schema.

        Raises on a refusal or unparseable body rather than returning
        something fabricated.
        """
        resp = self._client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_schema", "json_schema": schema},
        )
        self.usage.add(getattr(resp, "usage", None))
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise RuntimeError(f"model refused: {choice.message.refusal}")
        content = choice.message.content
        if not content:
            raise RuntimeError("model returned an empty body")
        return json.loads(content)


def list_models(api_key: str) -> list[str]:
    """Every model id the key can see, for the model-selection step."""
    client = OpenAI(api_key=api_key)
    return sorted(m.id for m in client.models.list().data)
