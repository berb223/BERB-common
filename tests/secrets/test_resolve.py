"""Tests for berb_common.secrets.resolve."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from berb_common.secrets import OpReadError, resolve_secret


class TestExplicit:
    def test_explicit_value_wins(self) -> None:
        assert resolve_secret(explicit="from-arg") == "from-arg"

    def test_explicit_strips_whitespace(self) -> None:
        assert resolve_secret(explicit="  trimmed  ") == "trimmed"

    def test_explicit_empty_returns_none(self) -> None:
        assert resolve_secret(explicit="") is None

    def test_explicit_whitespace_only_returns_none(self) -> None:
        assert resolve_secret(explicit="   ") is None

    def test_explicit_overrides_other_sources(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_REF", "op://Vault/Item/field")
        monkeypatch.setenv("MY_VAL", "from-env")
        # If explicit is honored, read_op_secret must NOT be called.
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret")
        result = resolve_secret(explicit="explicit-wins", ref_env="MY_REF", value_env="MY_VAL")
        assert result == "explicit-wins"
        op.assert_not_called()


class TestOpRefPath:
    def test_op_ref_resolved(self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_REF", "op://Vault/Item/field")
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret", return_value="secret")
        assert resolve_secret(ref_env="MY_REF") == "secret"
        op.assert_called_once_with("op://Vault/Item/field")

    def test_op_ref_blank_falls_through_to_value_env(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_REF", "   ")
        monkeypatch.setenv("MY_VAL", "fallback")
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret")
        result = resolve_secret(ref_env="MY_REF", value_env="MY_VAL")
        assert result == "fallback"
        op.assert_not_called()

    def test_op_ref_unset_falls_through_to_value_env(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MY_REF", raising=False)
        monkeypatch.setenv("MY_VAL", "fallback")
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret")
        result = resolve_secret(ref_env="MY_REF", value_env="MY_VAL")
        assert result == "fallback"
        op.assert_not_called()

    def test_op_error_propagates(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_REF", "op://Vault/Item/field")
        monkeypatch.setenv("MY_VAL", "would-be-fallback")
        mocker.patch(
            "berb_common.secrets.resolve.read_op_secret",
            side_effect=OpReadError("not signed in"),
        )
        with pytest.raises(OpReadError, match="not signed in"):
            resolve_secret(ref_env="MY_REF", value_env="MY_VAL")


class TestValueEnv:
    def test_value_env_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_VAL", "plain-value")
        assert resolve_secret(value_env="MY_VAL") == "plain-value"

    def test_value_env_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_VAL", "  trimmed  ")
        assert resolve_secret(value_env="MY_VAL") == "trimmed"

    def test_value_env_unset_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MY_VAL", raising=False)
        assert resolve_secret(value_env="MY_VAL") is None

    def test_no_sources_returns_none(self) -> None:
        assert resolve_secret() is None


class TestCache:
    def test_cache_hit_skips_op_call(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_REF", "op://Vault/Item/field")
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret", return_value="cached")
        first = resolve_secret(ref_env="MY_REF", cache_key="my-key")
        second = resolve_secret(ref_env="MY_REF", cache_key="my-key")
        assert first == "cached"
        assert second == "cached"
        op.assert_called_once()

    def test_cache_keys_isolated(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REF_A", "op://Vault/A/field")
        monkeypatch.setenv("REF_B", "op://Vault/B/field")
        mocker.patch("berb_common.secrets.resolve.read_op_secret", side_effect=["alpha", "beta"])
        a = resolve_secret(ref_env="REF_A", cache_key="key-a")
        b = resolve_secret(ref_env="REF_B", cache_key="key-b")
        assert a == "alpha"
        assert b == "beta"

    def test_cache_only_caches_op_path(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        # value_env results are not cached — each call re-reads the env.
        monkeypatch.setenv("MY_VAL", "first")
        first = resolve_secret(value_env="MY_VAL", cache_key="key")
        monkeypatch.setenv("MY_VAL", "second")
        second = resolve_secret(value_env="MY_VAL", cache_key="key")
        assert first == "first"
        assert second == "second"

    def test_clear_cache(self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        from berb_common.secrets import clear_secret_cache

        monkeypatch.setenv("MY_REF", "op://Vault/Item/field")
        op = mocker.patch("berb_common.secrets.resolve.read_op_secret", side_effect=["one", "two"])
        first = resolve_secret(ref_env="MY_REF", cache_key="my-key")
        clear_secret_cache()
        second = resolve_secret(ref_env="MY_REF", cache_key="my-key")
        assert first == "one"
        assert second == "two"
        assert op.call_count == 2
