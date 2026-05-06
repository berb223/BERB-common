"""Tests for berb_common.anthropic.tools.web_search_tool."""

from __future__ import annotations

import pytest

from berb_common.anthropic import WEB_SEARCH_TOOL_TYPE, web_search_tool


class TestWebSearchTool:
    def test_default_shape(self) -> None:
        out = web_search_tool()
        assert out == {
            "type": WEB_SEARCH_TOOL_TYPE,
            "name": "web_search",
            "max_uses": 5,
        }

    def test_max_uses_override(self) -> None:
        assert web_search_tool(max_uses=2)["max_uses"] == 2

    def test_allowed_domains(self) -> None:
        out = web_search_tool(allowed_domains=["example.com", "anthropic.com"])
        assert out["allowed_domains"] == ["example.com", "anthropic.com"]
        assert "blocked_domains" not in out

    def test_blocked_domains(self) -> None:
        out = web_search_tool(blocked_domains=["bad.example"])
        assert out["blocked_domains"] == ["bad.example"]
        assert "allowed_domains" not in out

    def test_allowed_and_blocked_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="at most one"):
            web_search_tool(
                allowed_domains=["a.example"],
                blocked_domains=["b.example"],
            )

    def test_user_location(self) -> None:
        loc = {"type": "approximate", "city": "Zurich", "country": "CH"}
        out = web_search_tool(user_location=loc)  # type: ignore[arg-type]
        assert out["user_location"] == loc
        # Returned dict is a copy — caller mutating the input must not leak.
        loc["city"] = "Berne"
        assert out["user_location"]["city"] == "Zurich"

    def test_pinned_tool_type(self) -> None:
        # Pinning ensures consumers don't have to remember the dated suffix.
        assert WEB_SEARCH_TOOL_TYPE == "web_search_20250305"
