"""Lightweight LLM clients for small (SLLM) and main response generation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

LOGGER = logging.getLogger(__name__)

try:  # Optional dependency
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - allow offline operation
    OpenAI = None  # type: ignore[assignment]


@dataclass(slots=True)
class LLMResponse:
    """Structured LLM response wrapper."""

    text: str
    model: str
    cached: bool = False


class LLMClient:
    """LLM wrapper with graceful fallback when API credentials missing."""

    def __init__(
        self,
        *,
        model_name: str,
        temperature: float = 0.2,
        max_output_tokens: int = 256,
        fallback: Callable[[str], str] | None = None,
    ) -> None:
        self._model_name = model_name
        self._temperature = temperature
        self._max_tokens = max_output_tokens
        self._fallback = fallback or (lambda prompt: "")
        self._enabled = False
        self._client: OpenAI | None = None

        api_key = os.getenv("OPENAI_API_KEY")
        if OpenAI is not None and api_key:
            try:
                self._client = OpenAI(api_key=api_key)
                self._enabled = True
            except Exception as exc:  # pragma: no cover - network conditions
                LOGGER.warning("OpenAI client init failed (%s); using fallback for %s", exc, model_name)
        else:
            LOGGER.debug("OpenAI client unavailable; using fallback for %s", model_name)

    # ------------------------------------------------------------------
    def complete(self, prompt: str) -> LLMResponse:
        if not self._enabled or self._client is None:
            return LLMResponse(text=self._fallback(prompt), model=self._model_name, cached=True)

        try:  # pragma: no cover - external API
            response = self._client.responses.create(
                model=self._model_name,
                input=prompt,
                max_output_tokens=self._max_tokens,
                temperature=self._temperature,
            )
            text = "".join(part.text for part in response.output_text if hasattr(part, "text"))
            if not text.strip() and response.output:
                text = response.output[0].content[0].text  # type: ignore[index]
            return LLMResponse(text=text.strip(), model=self._model_name, cached=False)
        except Exception as exc:  # pragma: no cover - external API
            LOGGER.warning("LLM completion failed (%s); using fallback for %s", exc, self._model_name)
            return LLMResponse(text=self._fallback(prompt), model=self._model_name, cached=True)


# ----------------------------------------------------------------------
# Factory helpers

def _default_small_fallback(prompt: str) -> str:
    return prompt.strip()


def _default_main_fallback(prompt: str) -> str:
    return "일반적인 생활습관 가이드를 참고하시고 필요 시 담당 의사와 상의해 주세요."


def get_small_llm() -> LLMClient:
    """Return configured small LLM client."""

    model = os.getenv("SLLM_CHOICE", "gpt-5-nano")
    return LLMClient(model_name=model, temperature=0.1, max_output_tokens=256, fallback=_default_small_fallback)


def get_main_llm() -> LLMClient:
    """Return configured main LLM client."""

    model = os.getenv("LLM_CHOICE", "gpt-5-mini")
    return LLMClient(model_name=model, temperature=0.2, max_output_tokens=512, fallback=_default_main_fallback)


__all__ = ["LLMClient", "LLMResponse", "get_small_llm", "get_main_llm"]
