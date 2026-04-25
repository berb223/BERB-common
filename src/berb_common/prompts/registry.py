"""YAML prompt loader with Jinja2 rendering.

A :class:`PromptRegistry` reads a project's prompts directory:

- ``<dir>/system.yaml`` — top-level key ``system_prompt`` (a string).
- ``<dir>/<slug>.yaml`` — top-level key ``template`` (a Jinja2 string).

Templates are loaded lazily and cached per-instance. Use
:meth:`PromptRegistry.clear_cache` for tests or hot reload.

Errors:
- :class:`FileNotFoundError` if a YAML file is missing.
- :class:`KeyError` if the required top-level key is missing or wrong type.
- ``yaml.YAMLError`` for malformed YAML.
- ``jinja2.TemplateError`` (and subclasses) for rendering failures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, Template


class PromptRegistry:
    """Lazily loads YAML prompt templates from a directory.

    Args:
        prompts_dir: Path to the directory containing prompt YAML files.
        strict_undefined: When True, missing template variables raise
            ``jinja2.UndefinedError``. When False (default), missing variables
            render as empty strings — matches the behavior used by current
            FTNT projects pre-migration.

    Example:
        >>> from pathlib import Path
        >>> from berb_common.prompts import PromptRegistry
        >>> reg = PromptRegistry(Path("prompts"))
        >>> system = reg.get_system()                                 # doctest: +SKIP
        >>> user = reg.render_user("greeting", name="Acme")           # doctest: +SKIP
        >>> system, user = reg.bundle("greeting", name="Acme")        # doctest: +SKIP
    """

    def __init__(self, prompts_dir: Path | str, *, strict_undefined: bool = False) -> None:
        self._dir = Path(prompts_dir)
        env_kwargs: dict[str, Any] = {
            "autoescape": False,
            "trim_blocks": True,
            "lstrip_blocks": True,
        }
        if strict_undefined:
            env_kwargs["undefined"] = StrictUndefined
        self._jinja = Environment(**env_kwargs)
        self._user_cache: dict[str, Template] = {}
        self._system_cache: str | None = None

    @property
    def prompts_dir(self) -> Path:
        """The directory this registry reads from."""
        return self._dir

    def get_system(self) -> str:
        """Return the system prompt from ``<dir>/system.yaml``.

        Cached after first read. The YAML must have a top-level
        ``system_prompt`` key whose value is a string.
        """
        if self._system_cache is None:
            self._system_cache = self._load_string("system.yaml", "system_prompt")
        return self._system_cache

    def render_user(self, slug: str, /, **variables: object) -> str:
        """Render the user prompt for ``<slug>.yaml`` with the given variables.

        The YAML must have a top-level ``template`` key. Returns the rendered
        string with surrounding whitespace stripped.
        """
        template = self._user_template(slug)
        return template.render(**variables).strip()

    def bundle(self, slug: str, /, **variables: object) -> tuple[str, str]:
        """Return ``(system_prompt, rendered_user_prompt)`` as a tuple.

        Convenience for callers that pass both to an LLM in one shot.
        """
        return self.get_system(), self.render_user(slug, **variables)

    def clear_cache(self) -> None:
        """Drop cached system prompt and compiled user templates."""
        self._user_cache.clear()
        self._system_cache = None

    def _user_template(self, slug: str) -> Template:
        if slug not in self._user_cache:
            template_str = self._load_string(f"{slug}.yaml", "template")
            self._user_cache[slug] = self._jinja.from_string(template_str)
        return self._user_cache[slug]

    def _load_string(self, filename: str, key: str) -> str:
        path = self._dir / filename
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise KeyError(f"{path}: expected mapping at top level, got {type(data).__name__}")
        value = data.get(key)
        if not isinstance(value, str):
            raise KeyError(f"{path}: expected string under key {key!r}, got {type(value).__name__}")
        return value.strip()
