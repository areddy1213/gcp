"""Thin wrapper around the Anthropic SDK for JSON-schema-constrained calls."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """A call failed for this input; other inputs may still succeed."""


class LLMRefusal(LLMError):
    def __init__(self, category: str | None, explanation: str | None = None):
        super().__init__(f"model declined (category={category or 'unspecified'})")
        self.category = category
        self.explanation = explanation


class LLMTruncated(LLMError):
    def __init__(self, partial_text: str):
        super().__init__("response hit max_tokens before the JSON was complete")
        self.partial_text = partial_text


class FatalLLMError(LLMError):
    """Bad credentials, missing permissions or unknown model: stop the run."""


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class JSONModel(Protocol):
    """What extraction, dedupe and reporting need from a model. Tests pass a fake."""

    model: str

    def call(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 32_000) -> LLMResult: ...


class ClaudeJSON:
    """Calls Claude with structured outputs (output_config.format = json_schema).

    - Streams every request so large outputs don't hit HTTP timeouts.
    - The SDK retries 408/409/429/5xx and connection errors with exponential backoff.
    - Server-side fallbacks ("default") re-run a declined request on Anthropic's recommended
      fallback model. Interview-prep security content can occasionally trip a safety classifier.
      Disable with IQBANK_FALLBACKS=0 (e.g. on platforms that don't support it).
    """

    def __init__(self, model: str, effort: str = "medium", *, use_fallbacks: bool = True, max_retries: int = 5):
        self.model = model
        self.effort = effort
        self.use_fallbacks = use_fallbacks
        self.max_retries = max_retries
        self._client = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls = 0

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(max_retries=self.max_retries)
        return self._client

    def call(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 32_000) -> LLMResult:
        import anthropic

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            # Stable instructions first, marked cacheable; the per-document text goes in `messages`.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }
        if self.use_fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"

        try:
            with self.client.beta.messages.stream(**kwargs) as stream:
                message = stream.get_final_message()
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise FatalLLMError(f"Anthropic auth failed ({exc.status_code}): check ANTHROPIC_API_KEY") from exc
        except anthropic.NotFoundError as exc:
            raise FatalLLMError(f"model {self.model!r} not found: set IQBANK_MODEL") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"bad request: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("rate limited after retries") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"connection error: {exc}") from exc

        self.calls += 1
        usage = message.usage
        in_tok = (
            (usage.input_tokens or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        )
        out_tok = usage.output_tokens or 0
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        log.debug(
            "claude call: model=%s in=%d out=%d stop=%s request_id=%s",
            message.model,
            in_tok,
            out_tok,
            message.stop_reason,
            getattr(message, "_request_id", None),
        )

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise LLMRefusal(getattr(details, "category", None), getattr(details, "explanation", None))

        text = "".join(block.text for block in message.content if block.type == "text")
        if message.stop_reason == "max_tokens":
            raise LLMTruncated(text)
        return LLMResult(text=text, model=message.model, input_tokens=in_tok, output_tokens=out_tok)

    def usage_summary(self) -> str:
        return (
            f"{self.calls} Claude call(s), {self.total_input_tokens:,} input / "
            f"{self.total_output_tokens:,} output tokens"
        )
