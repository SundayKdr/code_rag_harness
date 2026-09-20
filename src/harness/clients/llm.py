from dataclasses import dataclass
from typing import Sequence, TypeVar
from pydantic import BaseModel

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from typing import Generic, Sequence, TypeVar

from harness.common.config import Settings


class LlmError(RuntimeError):
    """Ошибка обращения к основной LLM."""


def _strip_json_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        first_newline = text.find("\n")

        if first_newline != -1:
            text = text[first_newline + 1:]

        if text.endswith("```"):
            text = text[:-3]

    return text.strip()

@dataclass(frozen=True, slots=True)
class LlmResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


_RETRYABLE_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

T = TypeVar("T", bound=BaseModel)

@dataclass(frozen=True, slots=True)
class StructuredLlmResult(Generic[T]):
    value: T
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LlmClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_openai_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    async def close(self) -> None:
        await self._client.close()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self._settings.llm_health_url)
                response.raise_for_status()
                return True
        except (httpx.HTTPError, ValueError):
            return False

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_ERRORS),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )

    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmResult:
        completion = await self._client.chat.completions.create(
            model=self._settings.llm_model,
            messages=list(messages),
            temperature=(
                self._settings.llm_temperature
                if temperature is None
                else temperature
            ),
            max_tokens=(
                self._settings.llm_max_tokens
                if max_tokens is None
                else max_tokens
            ),
        )

        text = completion.choices[0].message.content
        if not text:
            raise LlmError("LLM returned an empty response")

        usage = completion.usage

        return LlmResult(
            text=text,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

    async def complete_json(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        response_model: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
	) -> StructuredLlmResult[T]:
        result = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        stripped_text = _strip_json_fence(result.text)
        try:
            value = response_model.model_validate_json(stripped_text)
        except Exception as exc:
            raise LlmError(
	            f"Failed to parse LLM response as "
	            f"{response_model.__name__}: "
	            f"{result.text}"
	        ) from exc

        return StructuredLlmResult(
            value=value,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        )

