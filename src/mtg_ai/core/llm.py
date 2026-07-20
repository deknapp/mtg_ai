"""LLM transport layer.

Agents never talk to a provider SDK directly. They call an `LLM` implementation, which
returns structured (Pydantic) output plus a cost entry. Two backends implement the same
interface:

- `MockLLM`  — deterministic canned intelligence, zero API cost. The Stage 0 default; also
               what the tests run against so the pipeline is exercisable without spending budget.
- `AnthropicLLM` — the real backend, with cost-aware model routing and prompt caching.

The split keeps the *architecture* (agents, typed messages, orchestration) independent of
whether real models are wired in yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings, get_secrets
from .models import CostEntry

T = TypeVar("T", bound=BaseModel)


class LLMFormatError(RuntimeError):
    """Raised when a real model keeps returning output that isn't schema-valid JSON."""


class LLM(ABC):
    """Transport interface shared by every backend."""

    @abstractmethod
    def structured(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user: str,
        context: dict,
        response_model: type[T],
    ) -> tuple[T, CostEntry]:
        """Return a validated `response_model` instance and the call's cost accounting.

        `system` and `user` are the rendered prompts (used by real backends).
        `context` carries the structured payload (and any image bytes) a mock backend needs
        to synthesize schema-valid output without a model call.
        """
        raise NotImplementedError


# --- Mock backend --------------------------------------------------------------------------


class MockLLM(LLM):
    """Deterministic, offline backend. Dispatches per-agent to canned 'intelligence'.

    Handlers are injected by the format that builds the pipeline (draft or sealed), so the core
    transport stays format-agnostic — it knows nothing about any particular agent set.
    """

    def __init__(self, handlers: dict) -> None:
        self._handlers = handlers

    def structured(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user: str,
        context: dict,
        response_model: type[T],
    ) -> tuple[T, CostEntry]:
        handler = self._handlers.get(agent)
        if handler is None:
            raise KeyError(f"MockLLM has no handler for agent {agent!r}")
        output = handler(context)
        if not isinstance(output, response_model):
            output = response_model.model_validate(output)
        cost = CostEntry(
            agent=agent,
            model=f"mock:{model}",
            input_tokens=len(user) // 4,
            output_tokens=len(output.model_dump_json()) // 4,
        )
        return output, cost


# --- Real backend --------------------------------------------------------------------------


class AnthropicLLM(LLM):
    """Real Anthropic backend with model routing + prompt caching.

    Not exercised by the Stage 0 tests. The system prompt (stable across every pick in a
    session) is marked as a cache breakpoint so it is re-read at a large discount.
    """

    def __init__(self, settings: Settings) -> None:
        import anthropic  # imported here so the mock path needs no SDK/credentials

        key = get_secrets().anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the anthropic backend.")
        self._client = anthropic.Anthropic(api_key=key)
        self._settings = settings

    def structured(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user: str,
        context: dict,
        response_model: type[T],
    ) -> tuple[T, CostEntry]:
        schema = response_model.model_json_schema()
        instruction = (
            f"{user}\n\nRespond with ONLY a JSON object matching this schema:\n{schema}"
        )
        content: list[dict] = [{"type": "text", "text": instruction}]
        image_b64 = context.get("image_b64")
        if image_b64:
            content.insert(
                0,
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": context.get("image_media_type", "image/png"),
                        "data": image_b64,
                    },
                },
            )

        # System prompt is stable per session -> cache breakpoint for ~90% off on re-reads.
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        messages: list[dict] = [{"role": "user", "content": content}]

        # Models occasionally answer in prose (e.g. "I don't see any cards...") instead of the
        # requested JSON. Rather than crash the whole pipeline on the parse, retry once with the
        # bad reply fed back and a strict correction. Cost accrues across attempts.
        in_tok = out_tok = cached_tok = 0
        last_text = ""
        for attempt in range(2):
            resp = self._client.messages.create(
                model=model, max_tokens=1024, system=system_blocks, messages=messages
            )
            usage = resp.usage
            in_tok += getattr(usage, "input_tokens", 0)
            out_tok += getattr(usage, "output_tokens", 0)
            cached_tok += getattr(usage, "cache_read_input_tokens", 0) or 0
            last_text = "".join(block.text for block in resp.content if block.type == "text")
            try:
                output = response_model.model_validate_json(_strip_fences(last_text))
                break
            except ValidationError:
                if attempt == 1:
                    raise LLMFormatError(
                        f"{agent} agent: model did not return valid JSON after a retry. "
                        f"Last reply began: {last_text[:120]!r}"
                    )
                messages += [
                    {"role": "assistant", "content": last_text},
                    {
                        "role": "user",
                        "content": (
                            "That was not valid JSON. Respond with ONLY a single JSON object "
                            f"matching the schema, no prose, no code fences:\n{schema}"
                        ),
                    },
                ]

        cost = CostEntry(
            agent=agent,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cached_input_tokens=cached_tok,
        )
        return output, cost


def _strip_fences(text: str) -> str:
    """Tolerate models that wrap JSON in ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def build_llm(settings: Settings, handlers: dict | None = None) -> LLM:
    """Factory: pick a backend from settings. Defaults to the zero-cost mock.

    `handlers` is the format's mock-intelligence registry, used only by the mock backend.
    """
    if settings.llm_backend == "anthropic":
        return AnthropicLLM(settings)
    return MockLLM(handlers or {})
