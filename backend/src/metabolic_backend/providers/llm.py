"""LLM provider using LangChain-OpenAI directly without wrapper."""

from __future__ import annotations

import logging
import os
from typing import Optional

LOGGER = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
    LOGGER.warning("langchain-openai not installed; LLM features will be unavailable")


def get_small_llm() -> Optional[ChatOpenAI]:
    """Return configured small LLM (gpt-5-nano) for quick tasks like classification.

    Returns:
        ChatOpenAI instance or None if not available
    """
    if ChatOpenAI is None:
        LOGGER.debug("ChatOpenAI not available (langchain-openai not installed)")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        LOGGER.debug("OPENAI_API_KEY not set; LLM features disabled")
        return None

    model = os.getenv("SLLM_CHOICE", "gpt-5-nano")

    try:
        # Configure model_kwargs for gpt-5 series
        model_kwargs = {}
        if "gpt-5" in model.lower() or "o1" in model.lower() or "o3" in model.lower():
            model_kwargs["reasoning_effort"] = "minimal"

        llm = ChatOpenAI(
            model=model,
            temperature=0.1,
            max_tokens=256,
            api_key=api_key,
            model_kwargs=model_kwargs if model_kwargs else None,
        )

        LOGGER.info(f"Small LLM initialized: {model}")
        return llm

    except Exception as exc:
        LOGGER.warning(f"Failed to initialize small LLM ({model}): {exc}")
        return None


def get_main_llm() -> Optional[ChatOpenAI]:
    """Return configured main LLM (gpt-5-mini) for primary response generation.

    Returns:
        ChatOpenAI instance or None if not available
    """
    if ChatOpenAI is None:
        LOGGER.debug("ChatOpenAI not available (langchain-openai not installed)")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        LOGGER.debug("OPENAI_API_KEY not set; LLM features disabled")
        return None

    model = os.getenv("LLM_CHOICE", "gpt-5-mini")

    try:
        # Configure model_kwargs for gpt-5 series
        model_kwargs = {}
        if "gpt-5" in model.lower() or "o1" in model.lower() or "o3" in model.lower():
            model_kwargs["reasoning_effort"] = "minimal"

        llm = ChatOpenAI(
            model=model,
            temperature=0.2,
            max_tokens=512,
            api_key=api_key,
            model_kwargs=model_kwargs if model_kwargs else None,
        )

        LOGGER.info(f"Main LLM initialized: {model}")
        return llm

    except Exception as exc:
        LOGGER.warning(f"Failed to initialize main LLM ({model}): {exc}")
        return None


__all__ = ["get_small_llm", "get_main_llm"]
