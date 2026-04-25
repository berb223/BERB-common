"""Anthropic model ID constants.

Centralizes the canonical model identifiers so projects don't hardcode strings.
Per ADR-008: these are generic Anthropic model IDs, not Fortinet-specific
configuration. Projects pick the model that suits their workload.

References:
    https://docs.anthropic.com/en/docs/about-claude/models
"""

from __future__ import annotations

from typing import Final

# Latest Claude 4.x family (knowledge cutoff: January 2026).
MODEL_OPUS: Final[str] = "claude-opus-4-7"
"""Most capable model — for complex reasoning, long-horizon tasks."""

MODEL_SONNET: Final[str] = "claude-sonnet-4-6"
"""Balanced capability and speed — recommended default for most workloads."""

MODEL_HAIKU: Final[str] = "claude-haiku-4-5-20251001"
"""Fastest and lightest — for high-volume or latency-sensitive paths."""

DEFAULT_MODEL: Final[str] = MODEL_SONNET
"""Recommended default when no specific model is required."""
