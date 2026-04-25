"""Tests for berb_common.models.constants."""

from __future__ import annotations

from berb_common.models import DEFAULT_MODEL, MODEL_HAIKU, MODEL_OPUS, MODEL_SONNET


class TestModelConstants:
    def test_opus_is_string(self) -> None:
        assert isinstance(MODEL_OPUS, str)
        assert MODEL_OPUS.startswith("claude-opus-")

    def test_sonnet_is_string(self) -> None:
        assert isinstance(MODEL_SONNET, str)
        assert MODEL_SONNET.startswith("claude-sonnet-")

    def test_haiku_is_string(self) -> None:
        assert isinstance(MODEL_HAIKU, str)
        assert MODEL_HAIKU.startswith("claude-haiku-")

    def test_default_is_sonnet(self) -> None:
        assert DEFAULT_MODEL == MODEL_SONNET

    def test_constants_are_distinct(self) -> None:
        assert len({MODEL_OPUS, MODEL_SONNET, MODEL_HAIKU}) == 3
