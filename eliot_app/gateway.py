"""Bounded asynchronous Chat Completions transport for compatible providers."""
from __future__ import annotations

import asyncio
import codecs
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os

import httpx

from .config import Provider


class ProviderError(Exception):
    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass
class Reply:
    text: str = ""
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)


def retry_delay(header: str | None, attempt: int) -> float:
    try:
        delay = float(header)
    except (ValueError, TypeError):
        try:
            delay = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            delay = 2 ** attempt
    return max(0, delay)


class Gateway:
    def __init__(self, transport=None):
        self.transport = transport
        self.runtime_keys: dict[str, str] = {}

    def has_key(self, provider: Provider):
        return provider.auth == "none" or bool(self.runtime_keys.get(provider.id) or os.getenv(provider.api_key_env))

    async def complete(self, provider: Provider, messages: list[dict], on_delta=None) -> Reply:
        key = self.runtime_keys.get(provider.id) or os.getenv(provider.api_key_env, "")
        if provider.auth == "bearer" and not key:
            raise ProviderError("missing_key", f"Set {provider.api_key_env} or supply a temporary key in Providers.")
        headers = {"Content-Type": "application/json"}
        if provider.auth == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        body = {"model": provider.model, "messages": messages, "stream": provider.streaming, **provider.parameters}
        url = provider.base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=provider.timeout_seconds, transport=self.transport, follow_redirects=False, trust_env=False) as client:
            for attempt in range(provider.max_retries + 1):
                try:
                    async with client.stream("POST", url, json=body, headers=headers) as response:
                        code = response.status_code
                        if code == 429 or code in {500, 502, 503, 504}:
                            if attempt < provider.max_retries:
                                delay = retry_delay(response.headers.get("retry-after"), attempt)
                                if delay <= 10:
                                    await asyncio.sleep(delay)
                                    continue
                        if code >= 300:
                            kind, message = {
                                401: ("invalid_key", "The provider rejected the API key."),
                                403: ("forbidden", "The provider denied access to this model or account."),
                                404: ("not_found", "The model or endpoint was not found. Check the base URL and exact model ID."),
                                429: ("rate_limited", "The provider is rate limited or has exhausted quota. Try again later."),
                            }.get(code, ("provider_error", f"Provider request failed (HTTP {code}). Check endpoint settings and model parameters."))
                            # Provider response bodies can echo credentials; never surface them.
                            raise ProviderError(kind, message)
                        if not provider.streaming:
                            payload = bytearray()
                            async for chunk in response.aiter_bytes():
                                payload.extend(chunk)
                                if len(payload) > 2_000_000:
                                    raise ProviderError("response_limit", "The provider response exceeded the size limit.")
                            return self._response(json.loads(payload))
                        if "text/event-stream" not in response.headers.get("content-type", ""):
                            raise ProviderError("protocol", "The provider did not return an event stream. Disable streaming for this profile.")
                        reply = Reply()
                        async for line in self._lines(response):
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                return self._finished(reply)
                            if not data:
                                continue
                            item = json.loads(data)
                            if item.get("error"):
                                raise ProviderError("provider_error", "The provider returned an error during streaming.")
                            if isinstance(item.get("usage"), dict):
                                reply.usage = self._usage(item["usage"])
                            choices = item.get("choices", [])
                            if not choices:
                                continue
                            choice = choices[0]
                            delta = choice.get("delta", {})
                            if delta.get("tool_calls") or delta.get("function_call"):
                                raise ProviderError("unsupported_tools", "This provider requested a tool. Tool execution is not enabled in this chat release.")
                            text = delta.get("content") or ""
                            if not isinstance(text, str):
                                raise ValueError("Invalid content")
                            reply.text += text
                            if len(reply.text) > 100_000:
                                raise ProviderError("response_limit", "The response reached Eliot's character limit.")
                            if text and on_delta:
                                await on_delta(text)
                            if choice.get("finish_reason"):
                                reply.finish_reason = choice["finish_reason"]
                        return self._finished(reply)
                except ProviderError:
                    raise
                except httpx.TimeoutException:
                    # Retrying a partially received chat could duplicate output or charges.
                    raise ProviderError("timeout", "The provider timed out. The request was stopped locally.") from None
                except httpx.HTTPError:
                    raise ProviderError("connection", "Could not reach the provider, or its connection was interrupted.") from None
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    raise ProviderError("protocol", "The provider returned an invalid Chat Completions response.") from None
        raise ProviderError("provider_error", "The provider request failed.")

    @staticmethod
    async def _lines(response):
        decoder = codecs.getincrementaldecoder("utf-8")()
        buffer, received = "", 0
        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > 2_000_000:
                raise ProviderError("response_limit", "The provider response exceeded the size limit.")
            buffer += decoder.decode(chunk)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                yield line.rstrip("\r")
        buffer += decoder.decode(b"", final=True)
        if buffer:
            yield buffer.rstrip("\r")

    @staticmethod
    def _usage(usage):
        # Keep measured counts only; never persist arbitrary provider data.
        return {key: value for key, value in usage.items() if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(value) is int and value >= 0}

    @staticmethod
    def _finished(reply):
        if reply.finish_reason in {"tool_calls", "function_call"}:
            raise ProviderError("unsupported_tools", "Tool execution is not enabled in this chat release.")
        if reply.finish_reason not in {"stop", "length", "content_filter"}:
            raise ProviderError("interrupted", "The provider stream ended before reporting completion.")
        if not reply.text:
            raise ProviderError("empty_response", "The provider returned no text. Check the selected model.")
        return reply

    def _response(self, item):
        choice = item["choices"][0]
        message = choice["message"]
        if message.get("tool_calls") or message.get("function_call"):
            raise ProviderError("unsupported_tools", "Tool execution is not enabled in this chat release.")
        text = message.get("content")
        if not isinstance(text, str):
            raise ValueError("Invalid text")
        if len(text) > 100_000:
            raise ProviderError("response_limit", "The response reached Eliot's character limit.")
        usage = item.get("usage") or {}
        if not isinstance(usage, dict):
            raise ValueError("Invalid usage")
        return self._finished(Reply(text, choice.get("finish_reason"), self._usage(usage)))
