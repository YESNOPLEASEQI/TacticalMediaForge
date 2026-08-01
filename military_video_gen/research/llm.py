"""Retry helpers for evidence-bounded structured LLM calls."""

import asyncio
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel

from military_video_gen.services.llm_service import LLMService

T = TypeVar("T", bound=BaseModel)


async def generate_structured_with_retries(
    llm: LLMService,
    *,
    messages: Sequence[dict[str, str]],
    response_type: type[T],
    max_retries: int = 2,
    max_tokens: int = 2000,
    model: str | None = None,
) -> T:
    """Retry invalid structured responses at deterministic temperature."""
    last_error: Exception | None = None
    for _attempt in range(max_retries + 1):
        try:
            return await llm.generate_structured(
                messages=list(messages),
                response_type=response_type,
                temperature=0,
                max_tokens=max_tokens,
                model=model,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            last_error = error
            if _attempt < max_retries:
                await asyncio.sleep(0.5 * (2**_attempt))
    assert last_error is not None
    raise last_error
