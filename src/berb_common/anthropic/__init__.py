"""Anthropic SDK client wrapper.

See :class:`berb_common.anthropic.AnthropicClient` for the public API. The
client also accepts a ``tools=`` argument; build canonical tool definitions
via helpers in :mod:`berb_common.anthropic.tools` (currently
:func:`web_search_tool`).
"""

from berb_common.anthropic.client import AnthropicClient
from berb_common.anthropic.tools import WEB_SEARCH_TOOL_TYPE, web_search_tool

__all__ = ["WEB_SEARCH_TOOL_TYPE", "AnthropicClient", "web_search_tool"]
