"""Helpers for building Anthropic tool definitions.

Currently exposes :func:`web_search_tool` — the canonical config block for
the ``web_search`` server tool. Other server tools (computer use, code
execution, etc.) can grow here without polluting the client module.
"""

from __future__ import annotations

from typing import Any, TypedDict


class _UserLocation(TypedDict, total=False):
    type: str
    city: str
    region: str
    country: str
    timezone: str


# Tool type identifier as documented in Anthropic's API. Pinning the string
# here means the SDK consumer doesn't have to remember the dated suffix.
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


def web_search_tool(
    *,
    max_uses: int = 5,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    user_location: _UserLocation | None = None,
) -> dict[str, Any]:
    """Build the ``web_search`` server-tool definition for Anthropic's API.

    Pass the result inside the ``tools=`` argument of
    :meth:`berb_common.anthropic.AnthropicClient.call`.

    Args:
        max_uses: Cap on the number of search calls the model may make per
            turn. Anthropic bills per search ($10 / 1000 as of 2026), so this
            doubles as a cost cap.
        allowed_domains: When set, the tool only returns results from these
            domains. Mutually exclusive with ``blocked_domains`` per the API.
        blocked_domains: When set, the tool excludes these domains.
        user_location: Optional approximate location for geographically
            relevant results — ``{"type": "approximate", "city": "...",
            "country": "..."}``.

    Returns:
        A dict matching Anthropic's ``web_search_20250305`` tool schema.

    Example:
        >>> tool = web_search_tool(max_uses=3)
        >>> tool["type"]
        'web_search_20250305'
        >>> tool["max_uses"]
        3
    """
    if allowed_domains and blocked_domains:
        raise ValueError("web_search_tool: pass at most one of allowed_domains / blocked_domains")
    out: dict[str, Any] = {
        "type": WEB_SEARCH_TOOL_TYPE,
        "name": "web_search",
        "max_uses": max_uses,
    }
    if allowed_domains:
        out["allowed_domains"] = list(allowed_domains)
    if blocked_domains:
        out["blocked_domains"] = list(blocked_domains)
    if user_location:
        out["user_location"] = dict(user_location)
    return out
