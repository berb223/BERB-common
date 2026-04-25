"""Tests for berb_common.prompts.registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError

from berb_common.prompts import PromptRegistry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def registry() -> PromptRegistry:
    return PromptRegistry(FIXTURES)


@pytest.fixture
def strict_registry() -> PromptRegistry:
    return PromptRegistry(FIXTURES, strict_undefined=True)


class TestGetSystem:
    def test_reads_system_prompt(self, registry: PromptRegistry) -> None:
        assert registry.get_system() == "You are a helpful assistant."

    def test_caches_after_first_read(self, registry: PromptRegistry) -> None:
        first = registry.get_system()
        second = registry.get_system()
        assert first is second  # cached identity

    def test_strips_whitespace(self, registry: PromptRegistry) -> None:
        # Fixture has a trailing newline from YAML's | block scalar.
        assert not registry.get_system().endswith("\n")


class TestRenderUser:
    def test_renders_with_variables(self, registry: PromptRegistry) -> None:
        out = registry.render_user("greeting", name="Acme", current_year=2026)
        assert out == "Hello, Acme! Year is 2026."

    def test_default_filter_works(self, registry: PromptRegistry) -> None:
        out = registry.render_user("with_default", name="Beat")
        assert out == "Greeting: Hi, Name: Beat."

    def test_provides_variable(self, registry: PromptRegistry) -> None:
        out = registry.render_user("with_default", name="Beat", greeting="Yo")
        assert out == "Greeting: Yo, Name: Beat."

    def test_missing_variable_renders_empty_in_lax_mode(self, registry: PromptRegistry) -> None:
        # `name` is not provided; lax mode renders it as empty.
        out = registry.render_user("greeting", current_year=2026)
        assert out == "Hello, ! Year is 2026."

    def test_missing_variable_raises_in_strict_mode(self, strict_registry: PromptRegistry) -> None:
        with pytest.raises(UndefinedError):
            strict_registry.render_user("greeting", current_year=2026)

    def test_missing_template_file_raises(self, registry: PromptRegistry) -> None:
        with pytest.raises(FileNotFoundError):
            registry.render_user("nonexistent")

    def test_caches_compiled_template(self, registry: PromptRegistry) -> None:
        first = registry.render_user("greeting", name="A", current_year=2026)
        second = registry.render_user("greeting", name="B", current_year=2026)
        assert first == "Hello, A! Year is 2026."
        assert second == "Hello, B! Year is 2026."


class TestBundle:
    def test_returns_system_and_user(self, registry: PromptRegistry) -> None:
        system, user = registry.bundle("greeting", name="Acme", current_year=2026)
        assert system == "You are a helpful assistant."
        assert user == "Hello, Acme! Year is 2026."


class TestClearCache:
    def test_clears_system_cache(self, registry: PromptRegistry, tmp_path: Path) -> None:
        # Use a writable copy to test cache clearing under file changes.
        tmp_dir = tmp_path / "prompts"
        tmp_dir.mkdir()
        (tmp_dir / "system.yaml").write_text("system_prompt: original", encoding="utf-8")
        reg = PromptRegistry(tmp_dir)
        assert reg.get_system() == "original"
        # Modify file. Cache still returns original.
        (tmp_dir / "system.yaml").write_text("system_prompt: updated", encoding="utf-8")
        assert reg.get_system() == "original"
        # Clear and re-read.
        reg.clear_cache()
        assert reg.get_system() == "updated"

    def test_clears_user_cache(self, tmp_path: Path) -> None:
        tmp_dir = tmp_path / "prompts"
        tmp_dir.mkdir()
        (tmp_dir / "greet.yaml").write_text("template: Hi {{ name }}", encoding="utf-8")
        reg = PromptRegistry(tmp_dir)
        assert reg.render_user("greet", name="A") == "Hi A"
        (tmp_dir / "greet.yaml").write_text("template: Hello {{ name }}", encoding="utf-8")
        assert reg.render_user("greet", name="B") == "Hi B"  # still cached
        reg.clear_cache()
        assert reg.render_user("greet", name="C") == "Hello C"


class TestErrorPaths:
    def test_bad_root_type(self, registry: PromptRegistry) -> None:
        with pytest.raises(KeyError, match="expected mapping at top level"):
            registry.render_user("bad_root")

    def test_missing_required_key(self, registry: PromptRegistry) -> None:
        with pytest.raises(KeyError, match="expected string under key 'template'"):
            registry.render_user("missing_key")

    def test_wrong_value_type(self, registry: PromptRegistry) -> None:
        with pytest.raises(KeyError, match="expected string under key 'template'"):
            registry.render_user("wrong_type")


class TestPromptsDir:
    def test_exposes_path(self) -> None:
        reg = PromptRegistry(FIXTURES)
        assert reg.prompts_dir == FIXTURES

    def test_accepts_string_path(self) -> None:
        reg = PromptRegistry(str(FIXTURES))
        assert reg.prompts_dir == FIXTURES
        assert reg.get_system() == "You are a helpful assistant."
