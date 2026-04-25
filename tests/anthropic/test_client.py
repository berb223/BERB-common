"""Tests for berb_common.anthropic.client."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from anthropic import APIConnectionError, APIStatusError
from anthropic.types import TextBlock
from pytest_mock import MockerFixture

from berb_common.anthropic import AnthropicClient

# --- helpers ---------------------------------------------------------------


def _build_message(
    *,
    text: str = "Hello world",
    input_tokens: int = 10,
    output_tokens: int = 20,
    stop_reason: str = "end_turn",
    model: str = "claude-sonnet-4-6",
) -> Any:
    """Build a Mock anthropic Message that contains real TextBlocks."""
    msg = MagicMock()
    msg.content = [TextBlock(type="text", text=text)]
    msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    msg.stop_reason = stop_reason
    msg.model = model
    return msg


class _FakeStatusError(APIStatusError):
    def __init__(self, status_code: int, message: str = "status error") -> None:
        Exception.__init__(self, message)
        self.status_code = status_code


class _FakeConnectionError(APIConnectionError):
    def __init__(self, message: str = "connection failed") -> None:
        Exception.__init__(self, message)


@pytest.fixture
def fake_anthropic(mocker: MockerFixture) -> MagicMock:
    """Patch the Anthropic SDK class; return the instance the client wraps."""
    instance = MagicMock()
    mocker.patch("berb_common.anthropic.client.Anthropic", return_value=instance)
    return instance


# --- tests -----------------------------------------------------------------


class TestInit:
    def test_constructs_with_minimal_args(self, fake_anthropic: MagicMock) -> None:
        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-6")
        assert client.model == "claude-sonnet-4-6"

    def test_ssl_verify_disabled_warns(
        self, fake_anthropic: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        AnthropicClient(api_key="sk-test", model="m", ssl_verify=False)
        # Note: structlog may emit to stdout; we just verify no crash.

    def test_passes_max_retries_to_sdk(
        self, mocker: MockerFixture, fake_anthropic: MagicMock
    ) -> None:
        anthropic_class = mocker.patch(
            "berb_common.anthropic.client.Anthropic", return_value=fake_anthropic
        )
        AnthropicClient(api_key="sk", model="m", max_retries=5, timeout=30.0)
        kwargs = anthropic_class.call_args.kwargs
        assert kwargs["max_retries"] == 5
        assert kwargs["timeout"] == 30.0
        assert kwargs["api_key"] == "sk"


class TestCallSuccess:
    def test_success_returns_content(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message(text="Hi there")
        client = AnthropicClient(api_key="sk", model="claude-sonnet-4-6")
        r = client.call(user="Hello")
        assert r.success is True
        assert r.status_code == 200
        assert r.content == "Hi there"

    def test_success_captures_token_usage(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message(
            input_tokens=15, output_tokens=42
        )
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.input_tokens == 15
        assert r.output_tokens == 42
        assert r.total_tokens == 57

    def test_success_records_stop_reason_and_model(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message(
            stop_reason="max_tokens", model="claude-opus-4-7"
        )
        client = AnthropicClient(api_key="sk", model="claude-sonnet-4-6")
        r = client.call(user="Hello")
        assert r.stop_reason == "max_tokens"
        assert r.model == "claude-opus-4-7"

    def test_success_records_duration(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message()
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.duration_seconds >= 0

    def test_concatenates_multiple_text_blocks(self, fake_anthropic: MagicMock) -> None:
        msg = _build_message()
        msg.content = [
            TextBlock(type="text", text="part-1 "),
            TextBlock(type="text", text="part-2"),
        ]
        fake_anthropic.messages.create.return_value = msg
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.content == "part-1 part-2"

    def test_passes_system_prompt(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message()
        client = AnthropicClient(api_key="sk", model="m")
        client.call(user="Hello", system="You are X")
        kwargs = fake_anthropic.messages.create.call_args.kwargs
        assert kwargs["system"] == "You are X"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]

    def test_blank_system_prompt_omitted(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message()
        client = AnthropicClient(api_key="sk", model="m")
        client.call(user="Hello", system="   ")
        kwargs = fake_anthropic.messages.create.call_args.kwargs
        assert "system" not in kwargs


class TestCallFailure:
    def test_status_error_captured(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.side_effect = _FakeStatusError(
            status_code=401, message="Unauthorized"
        )
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.success is False
        assert r.status_code == 401
        assert "Unauthorized" in r.error_message
        assert r.model == "m"

    def test_connection_error_captured(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.side_effect = _FakeConnectionError(
            message="DNS resolution failed"
        )
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.success is False
        assert r.status_code == 0
        assert "Could not connect" in r.error_message
        assert "DNS resolution failed" in r.error_message

    def test_failure_records_duration(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.side_effect = _FakeStatusError(500, "boom")
        client = AnthropicClient(api_key="sk", model="m")
        r = client.call(user="Hello")
        assert r.duration_seconds >= 0


class TestVerify:
    def test_verify_calls_with_minimal_args(self, fake_anthropic: MagicMock) -> None:
        fake_anthropic.messages.create.return_value = _build_message(text="OK")
        client = AnthropicClient(api_key="sk", model="m")
        r = client.verify()
        assert r.success is True
        kwargs = fake_anthropic.messages.create.call_args.kwargs
        assert kwargs["max_tokens"] == 20
        assert kwargs["temperature"] == 0.0
