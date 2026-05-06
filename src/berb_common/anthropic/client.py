"""Anthropic Messages API client wrapper.

Wraps the official ``anthropic`` SDK to:

- Provide a consistent :class:`berb_common.models.LLMResponse` return type.
- Centralize timeout, retry, and SSL-verification configuration.
- Log success/failure events via ``berb_common.logging``.

Errors from the API are captured into the ``LLMResponse`` (``success=False``,
``error_message=...``) — :meth:`AnthropicClient.call` does not raise on API
failures. Programming errors (e.g. ``TypeError``) propagate unchanged.

The SDK's own retry mechanism handles transient errors (connection failures,
``5xx`` responses); we expose the count via the ``max_retries`` parameter.
``4xx`` responses are not retried by the SDK and surface as ``LLMResponse``
failures.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from anthropic import Anthropic, APIConnectionError, APIStatusError
from anthropic.types import Message, TextBlock

from berb_common.logging import get_logger
from berb_common.models import LLMResponse

_log = get_logger(__name__)


class AnthropicClient:
    """Anthropic Messages API wrapper.

    Args:
        api_key: Anthropic API key.
        model: Model identifier (e.g. ``"claude-sonnet-4-6"``).
        timeout: Request timeout in seconds.
        max_retries: SDK-level retry count for transient errors (connection,
            5xx). 4xx responses are not retried.
        ssl_verify: When False, disables SSL certificate verification — only
            for use behind a corporate proxy with a self-signed certificate.
            Not recommended for production.

    Example:
        >>> from berb_common.anthropic import AnthropicClient
        >>> client = AnthropicClient(api_key="sk-ant-...", model="claude-sonnet-4-6")
        >>> response = client.call(user="Hello")                 # doctest: +SKIP
        >>> if response.success:                                 # doctest: +SKIP
        ...     print(response.content)
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        ssl_verify: bool = True,
    ) -> None:
        if not ssl_verify:
            _log.warning("anthropic_ssl_verify_disabled")
        http_client = httpx.Client(verify=ssl_verify, timeout=timeout)
        self._client = Anthropic(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self._model = model

    @property
    def model(self) -> str:
        """The configured model identifier."""
        return self._model

    def call(
        self,
        *,
        user: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a single request to the Anthropic Messages API.

        Args:
            user: User-role message content.
            system: Optional system prompt. Empty string omits the field.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            tools: Optional list of tool definitions to forward to the API.
                Server-side tools (e.g. ``web_search``) are executed by
                Anthropic's infrastructure within the same request — the
                returned :class:`LLMResponse` is the model's final answer
                after any tool turns. Use :func:`web_search_tool` to build
                the canonical web-search definition.

        Returns:
            :class:`LLMResponse`. API errors (status, connection) are captured
            with ``success=False``; the call never raises for API failures.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user}],
        }
        if system.strip():
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        t0 = time.perf_counter()
        try:
            message: Message = self._client.messages.create(**kwargs)
        except APIStatusError as exc:
            elapsed = time.perf_counter() - t0
            status = int(getattr(exc, "status_code", 0) or 0)
            _log.warning("anthropic_api_error", status_code=status, error=str(exc))
            return LLMResponse(
                success=False,
                status_code=status,
                error_message=str(exc),
                duration_seconds=elapsed,
                model=self._model,
                web_search_requests=0,
            )
        except APIConnectionError as exc:
            elapsed = time.perf_counter() - t0
            _log.error("anthropic_connection_error", error=str(exc))
            return LLMResponse(
                success=False,
                status_code=0,
                error_message=f"Could not connect to the Anthropic API: {exc}",
                duration_seconds=elapsed,
                model=self._model,
                web_search_requests=0,
            )

        elapsed = time.perf_counter() - t0
        content = self._extract_text(message)
        input_tokens = int(getattr(message.usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(message.usage, "output_tokens", 0) or 0)
        response_model = str(getattr(message, "model", "") or self._model)
        web_search_requests = self._extract_web_search_count(message)

        _log.info(
            "anthropic_ok",
            model=response_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            web_search_requests=web_search_requests,
            duration_seconds=round(elapsed, 3),
            content_chars=len(content),
        )

        return LLMResponse(
            success=True,
            status_code=200,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=str(getattr(message, "stop_reason", "") or ""),
            model=response_model,
            duration_seconds=elapsed,
            web_search_requests=web_search_requests,
        )

    def verify(self) -> LLMResponse:
        """Send a minimal request to verify credentials and connectivity.

        Returns:
            :class:`LLMResponse`. Use ``response.success`` as a boolean health
            indicator.
        """
        return self.call(user="Say 'OK'.", max_tokens=20, temperature=0.0)

    @staticmethod
    def _extract_text(message: Message) -> str:
        """Concatenate the ``text`` of every ``TextBlock`` in the message.

        When server-side tools (e.g. ``web_search``) are used, the message
        content interleaves ``server_tool_use`` and tool-result blocks with
        ``TextBlock`` blocks. This skips the non-text blocks; the returned
        string is the model's narrative + final answer.
        """
        return "".join(b.text for b in message.content if isinstance(b, TextBlock))

    @staticmethod
    def _extract_web_search_count(message: Message) -> int:
        """Read the ``server_tool_use.web_search_requests`` count from usage.

        Anthropic exposes this on ``message.usage.server_tool_use``. Returns
        ``0`` when the field is missing (no tool used, older SDK, or the
        provider-specific shape changes).
        """
        usage = getattr(message, "usage", None)
        if usage is None:
            return 0
        server_tool_use = getattr(usage, "server_tool_use", None)
        if server_tool_use is None:
            return 0
        return int(getattr(server_tool_use, "web_search_requests", 0) or 0)
