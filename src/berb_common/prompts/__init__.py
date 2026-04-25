"""YAML + Jinja2 prompt registry.

Projects supply their own ``prompts/`` directory; this library only provides the
loader. Per ADR-008, no project-specific names, defaults, or fields appear here.

See :class:`berb_common.prompts.PromptRegistry`.
"""

from berb_common.prompts.registry import PromptRegistry

__all__ = ["PromptRegistry"]
