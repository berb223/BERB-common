"""Tests for berb_common.models.responses."""

from __future__ import annotations

from berb_common.models import LLMResponse


class TestLLMResponseDefaults:
    def test_all_defaults(self) -> None:
        r = LLMResponse()
        assert r.success is False
        assert r.status_code == 0
        assert r.content == ""
        assert r.error_message == ""
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.stop_reason == ""
        assert r.model == ""
        assert r.duration_seconds == 0.0


class TestTotalTokens:
    def test_zero_default(self) -> None:
        assert LLMResponse().total_tokens == 0

    def test_sum(self) -> None:
        assert LLMResponse(input_tokens=10, output_tokens=25).total_tokens == 35

    def test_only_input(self) -> None:
        assert LLMResponse(input_tokens=7).total_tokens == 7

    def test_only_output(self) -> None:
        assert LLMResponse(output_tokens=3).total_tokens == 3


class TestSerialization:
    def test_dict_roundtrip(self) -> None:
        r1 = LLMResponse(
            success=True,
            status_code=200,
            content="hello",
            input_tokens=5,
            output_tokens=10,
            stop_reason="end_turn",
            model="claude-sonnet-4-6",
            duration_seconds=1.23,
        )
        data = r1.model_dump()
        r2 = LLMResponse.model_validate(data)
        assert r1 == r2

    def test_json_roundtrip(self) -> None:
        r1 = LLMResponse(success=True, content="hello", input_tokens=5)
        json_str = r1.model_dump_json()
        r2 = LLMResponse.model_validate_json(json_str)
        assert r2.content == "hello"
        assert r2.input_tokens == 5
        assert r2.success is True

    def test_total_tokens_not_in_dump(self) -> None:
        # `total_tokens` is a property, not a field — should not serialize.
        r = LLMResponse(input_tokens=5, output_tokens=10)
        assert "total_tokens" not in r.model_dump()
