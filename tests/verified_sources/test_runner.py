"""Tests for berb_common.verified_sources.runner."""

from __future__ import annotations

from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from berb_common.models import LLMResponse
from berb_common.verified_sources.models import (
    VerifiedSourceRow,
    VerifiedStepRequest,
)
from berb_common.verified_sources.runner import run_verified_step

_GOOD_JSON = """
{"category":"news_trends_ma","results":[
  {"url":"https://a.example/x","source_type":"business_news","deal_parties":"","description":"A"},
  {"url":"https://b.example/y","source_type":"company_press_release","deal_parties":"","description":"B"}
]}
"""


def _request(**overrides: object) -> VerifiedStepRequest:
    base: dict[str, object] = {
        "title": "Recent News, M&A",
        "focus": "Recent deals.",
        "category": "news_trends_ma",
        "company_name": "Acme Corp",
        "max_results": 5,
    }
    base.update(overrides)
    return VerifiedStepRequest(**base)  # type: ignore[arg-type]


def _client_returning(content: str) -> MagicMock:
    """Build a MagicMock AnthropicClient whose .call() returns a successful LLMResponse."""
    client = MagicMock()
    client.call = MagicMock(
        return_value=LLMResponse(
            success=True,
            status_code=200,
            content=content,
            input_tokens=100,
            output_tokens=50,
            stop_reason="end_turn",
            model="claude-sonnet-4-6",
        )
    )
    return client


def _client_failing(error: str) -> MagicMock:
    client = MagicMock()
    client.call = MagicMock(
        return_value=LLMResponse(
            success=False,
            status_code=500,
            content="",
            error_message=error,
            model="claude-sonnet-4-6",
        )
    )
    return client


class TestSuccessPath:
    def test_validate_links_off_keeps_all_parsed_rows(self) -> None:
        client = _client_returning(_GOOD_JSON)
        result = run_verified_step(_request(), client=client, validate_links=False)
        assert result.success is True
        assert len(result.rows) == 2
        assert result.dropped_rows == []
        assert result.error_message == ""
        assert result.raw_response == _GOOD_JSON
        assert result.llm_response.input_tokens == 100

    def test_validate_links_on_filters_dead_rows(self, mocker: MockerFixture) -> None:
        # Mock filter_dead_rows to return one kept + one dropped — exercising
        # the wiring without doing real network calls.
        kept = [VerifiedSourceRow(url="https://a.example/x", description="A")]
        dropped = [VerifiedSourceRow(url="https://b.example/y", description="B")]
        mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            return_value=(kept, dropped),
        )
        client = _client_returning(_GOOD_JSON)
        result = run_verified_step(_request(), client=client, validate_links=True)
        assert result.success is True
        assert result.rows == kept
        assert result.dropped_rows == dropped

    def test_validate_links_on_by_default(self, mocker: MockerFixture) -> None:
        # The point of this whole package — link validation must be the default.
        spy = mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            return_value=([], []),
        )
        run_verified_step(_request(), client=_client_returning(_GOOD_JSON))
        spy.assert_called_once()

    def test_user_prompt_prefix_is_prepended(self, mocker: MockerFixture) -> None:
        client = _client_returning(_GOOD_JSON)
        mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            return_value=([], []),
        )
        run_verified_step(
            _request(),
            client=client,
            user_prompt_prefix="ACCOUNT CONTEXT: new prospect.",
        )
        call_kwargs = client.call.call_args.kwargs
        assert call_kwargs["user"].startswith("ACCOUNT CONTEXT: new prospect.")
        # The base prompt is still appended after a blank line separator.
        assert "Verified Sources task:" in call_kwargs["user"]

    def test_empty_prefix_does_not_pad_the_prompt(self, mocker: MockerFixture) -> None:
        client = _client_returning(_GOOD_JSON)
        mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            return_value=([], []),
        )
        run_verified_step(_request(), client=client, user_prompt_prefix="   ")
        # Whitespace-only prefix should not show up at the start of the prompt.
        assert client.call.call_args.kwargs["user"].startswith("Verified Sources task:")

    def test_passes_max_tokens_and_temperature_to_client(self, mocker: MockerFixture) -> None:
        client = _client_returning(_GOOD_JSON)
        mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            return_value=([], []),
        )
        run_verified_step(_request(), client=client, max_tokens=1024, temperature=0.2)
        kw = client.call.call_args.kwargs
        assert kw["max_tokens"] == 1024
        assert kw["temperature"] == 0.2


class TestFailurePath:
    def test_llm_failure_returns_unsuccessful_result(self) -> None:
        client = _client_failing("rate limited")
        result = run_verified_step(_request(), client=client)
        assert result.success is False
        assert result.error_message == "rate limited"
        assert result.rows == []
        assert result.dropped_rows == []
        assert result.llm_response.success is False

    def test_empty_error_message_falls_back_to_default(self) -> None:
        client = MagicMock()
        client.call = MagicMock(
            return_value=LLMResponse(success=False, status_code=500, error_message="")
        )
        result = run_verified_step(_request(), client=client)
        assert result.error_message == "LLM call failed"


class TestRequestPlumbing:
    def test_max_results_drives_parser_cap(self, mocker: MockerFixture) -> None:
        # Long results array — cap should apply.
        many = ", ".join(
            f'{{"url":"https://e{i}.example","source_type":"x","deal_parties":"","description":"d"}}'
            for i in range(20)
        )
        client = _client_returning(f'{{"results":[{many}]}}')
        mocker.patch(
            "berb_common.verified_sources.runner.filter_dead_rows",
            side_effect=lambda rows, **kw: (list(rows), []),
        )
        result = run_verified_step(_request(max_results=3), client=client)
        assert len(result.rows) == 3
