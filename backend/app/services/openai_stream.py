"""
OpenAI streaming client service.

This module provides a thin wrapper around the official OpenAI SDK v1.x to
perform streamed chat completions and yield token deltas suitable for SSE.

It also includes a simple retry mechanism for transient errors.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Iterable, Optional, Dict

import httpx
from openai import AsyncOpenAI
from openai._exceptions import APIError, APIStatusError, RateLimitError

from ..core.settings import get_settings


class OpenAIStreamClient:
    """High-level streaming client for OpenAI Chat Completions.

    Usage:
        async for delta in client.stream_chat(messages=[...]):
            yield delta
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model or (settings.openai_model or "gpt-3.5-turbo")
        # Share httpx client for connection reuse
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        client_kwargs = {
            "api_key": self.api_key,
            "http_client": self._http_client,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        if extra_headers:
            client_kwargs["default_headers"] = extra_headers
        self._client = AsyncOpenAI(**client_kwargs)

    async def close(self) -> None:
        await self._http_client.aclose()

    async def stream_chat(
        self,
        messages: Iterable[dict],
        max_retries: int = 2,
        retry_delay_seconds: float = 0.8,
    ) -> AsyncIterator[str]:
        """Stream assistant tokens for the given chat messages.

        Yields plain text chunks (no role/content wrappers). The caller can
        format into SSE events or concatenate as needed.
        """

        attempt = 0
        while True:
            try:
                stream = await self._client.chat.completions.create(
                    model=self.model,
                    messages=list(messages),
                    stream=True,
                )
                async for event in stream:
                    # New SDK returns chunks with choices[].delta.content
                    for choice in event.choices:
                        delta = getattr(choice.delta, "content", None)
                        if delta:
                            yield delta
                break
            except (RateLimitError, APIStatusError, APIError) as exc:
                attempt += 1
                if attempt > max_retries:
                    raise exc
                await asyncio.sleep(retry_delay_seconds)


