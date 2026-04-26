"""Tests for berb_common.secrets.onepassword."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest
from pytest_mock import MockerFixture

from berb_common.secrets import OpReadError, read_op_secret, try_read_op_secret


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[Any]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestReadOpSecret:
    def test_invalid_reference_raises(self) -> None:
        with pytest.raises(OpReadError, match="must start with op://"):
            read_op_secret("not-a-reference")

    def test_blank_reference_raises(self) -> None:
        with pytest.raises(OpReadError, match="must start with op://"):
            read_op_secret("   ")

    def test_missing_op_binary_raises(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword._find_op_executable", return_value=None)
        with pytest.raises(OpReadError, match="not found"):
            read_op_secret("op://Vault/Item/field")

    def test_success_returns_value(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="secret-value\n"),
        )
        assert read_op_secret("op://Vault/Item/field") == "secret-value"

    def test_nonzero_exit_raises(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(1, stderr="not signed in"),
        )
        with pytest.raises(OpReadError, match="exit 1"):
            read_op_secret("op://Vault/Item/field")

    def test_nonzero_exit_falls_back_to_stdout(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(2, stdout="path not found"),
        )
        with pytest.raises(OpReadError, match="path not found"):
            read_op_secret("op://Vault/Item/field")

    def test_nonzero_exit_no_output(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(3, stdout="", stderr=""),
        )
        with pytest.raises(OpReadError, match="<no output>"):
            read_op_secret("op://Vault/Item/field")

    def test_empty_output_raises(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="   \n"),
        )
        with pytest.raises(OpReadError, match="empty value"):
            read_op_secret("op://Vault/Item/field")

    def test_timeout_raises(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="op", timeout=45.0),
        )
        with pytest.raises(OpReadError, match="timed out"):
            read_op_secret("op://Vault/Item/field", timeout_sec=45.0)


class TestFindOpExecutable:
    """Cross-system discovery: PATH first, then well-known install locations.

    Important when the launching shell has a stripped PATH (background
    services, IDE-spawned processes, automation tools) but the CLI is still
    installed on the machine.
    """

    def test_returns_path_when_on_path(self, mocker: MockerFixture) -> None:
        from berb_common.secrets.onepassword import _find_op_executable

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        assert _find_op_executable() == "/usr/bin/op"

    def test_windows_fallback_program_files(self, mocker: MockerFixture) -> None:
        # `os.path.join` resolves separators per the host OS, so build the
        # expected path the same way the production code does to stay
        # platform-agnostic in CI.
        import os.path as _osp

        from berb_common.secrets.onepassword import _find_op_executable

        expected = _osp.join(r"C:\Program Files", "1Password CLI", "op.exe")

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        mocker.patch("berb_common.secrets.onepassword.sys.platform", "win32")
        mocker.patch.dict(
            "berb_common.secrets.onepassword.os.environ",
            {"PROGRAMFILES": r"C:\Program Files", "LOCALAPPDATA": r"C:\Users\u\AppData\Local"},
            clear=False,
        )
        mocker.patch(
            "berb_common.secrets.onepassword.os.path.isfile",
            side_effect=lambda p: p == expected,
        )
        mocker.patch("berb_common.secrets.onepassword.glob", return_value=[])
        assert _find_op_executable() == expected

    def test_windows_fallback_winget(self, mocker: MockerFixture) -> None:
        from berb_common.secrets.onepassword import _find_op_executable

        winget_path = (
            r"C:\Users\u\AppData\Local\Microsoft\WinGet\Packages\AgileBits.1Password.CLI_x\op.exe"
        )
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        mocker.patch("berb_common.secrets.onepassword.sys.platform", "win32")
        mocker.patch.dict(
            "berb_common.secrets.onepassword.os.environ",
            {"PROGRAMFILES": r"C:\Program Files", "LOCALAPPDATA": r"C:\Users\u\AppData\Local"},
            clear=False,
        )
        mocker.patch("berb_common.secrets.onepassword.glob", return_value=[winget_path])
        # Program Files install absent; only the winget copy exists.
        mocker.patch(
            "berb_common.secrets.onepassword.os.path.isfile",
            side_effect=lambda p: p == winget_path,
        )
        assert _find_op_executable() == winget_path

    def test_posix_fallback_homebrew(self, mocker: MockerFixture) -> None:
        from berb_common.secrets.onepassword import _find_op_executable

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        mocker.patch("berb_common.secrets.onepassword.sys.platform", "linux")
        mocker.patch(
            "berb_common.secrets.onepassword.os.path.isfile",
            side_effect=lambda p: p == "/opt/homebrew/bin/op",
        )
        assert _find_op_executable() == "/opt/homebrew/bin/op"

    def test_returns_none_when_nowhere(self, mocker: MockerFixture) -> None:
        from berb_common.secrets.onepassword import _find_op_executable

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        mocker.patch("berb_common.secrets.onepassword.sys.platform", "linux")
        mocker.patch("berb_common.secrets.onepassword.os.path.isfile", return_value=False)
        assert _find_op_executable() is None


class TestTryReadOpSecret:
    def test_none_returns_none(self) -> None:
        assert try_read_op_secret(None) is None

    def test_blank_returns_none(self) -> None:
        assert try_read_op_secret("   ") is None

    def test_valid_delegates(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="value"),
        )
        assert try_read_op_secret("op://Vault/Item/field") == "value"


class TestProcessCache:
    """In-process cache: always on, hit on second call within the same process."""

    def test_second_call_skips_subprocess(self, mocker: MockerFixture) -> None:
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        run = mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="value-1"),
        )
        assert read_op_secret("op://V/I/f") == "value-1"
        assert read_op_secret("op://V/I/f") == "value-1"
        assert run.call_count == 1

    def test_clear_op_cache_forces_resubprocess(self, mocker: MockerFixture) -> None:
        from berb_common.secrets import clear_op_cache

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        run = mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            side_effect=[_proc(0, stdout="value-1"), _proc(0, stdout="value-2")],
        )
        assert read_op_secret("op://V/I/f") == "value-1"
        clear_op_cache()
        assert read_op_secret("op://V/I/f") == "value-2"
        assert run.call_count == 2


class TestDiskCache:
    """OS keystore cache: opt-out via env, 24h TTL by default, keyring-backed."""

    @pytest.fixture
    def fake_keyring(self, mocker: MockerFixture) -> Any:
        """Replace `keyring` with an in-memory shim that records reads/writes."""
        import sys
        import types

        store: dict[tuple[str, str], str] = {}

        class _Errors(types.ModuleType):
            class PasswordDeleteError(Exception):
                pass

        errors_mod = _Errors("keyring.errors")

        keyring_mod = types.ModuleType("keyring")
        keyring_mod.errors = errors_mod  # type: ignore[attr-defined]
        keyring_mod.get_password = (  # type: ignore[attr-defined]
            lambda service, user: store.get((service, user))
        )
        keyring_mod.set_password = (  # type: ignore[attr-defined]
            lambda service, user, value: store.__setitem__((service, user), value)
        )

        def _delete(service: str, user: str) -> None:
            if (service, user) not in store:
                raise errors_mod.PasswordDeleteError(f"missing: {user}")
            del store[(service, user)]

        keyring_mod.delete_password = _delete  # type: ignore[attr-defined]
        mocker.patch.dict(sys.modules, {"keyring": keyring_mod, "keyring.errors": errors_mod})
        return store

    def test_disk_cache_disabled_does_not_touch_keyring(
        self, mocker: MockerFixture, fake_keyring: Any
    ) -> None:
        # Default conftest sets BERB_OP_DISK_CACHE=0
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="value"),
        )
        assert read_op_secret("op://V/I/f") == "value"
        assert fake_keyring == {}, "no entry should be written when disk cache is off"

    def test_disk_cache_writes_then_reads(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, fake_keyring: Any
    ) -> None:
        from berb_common.secrets import clear_op_cache

        monkeypatch.setenv("BERB_OP_DISK_CACHE", "1")
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        run = mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="value-1"),
        )
        assert read_op_secret("op://V/I/f") == "value-1"
        assert len(fake_keyring) == 1, "first call writes to keyring"

        clear_op_cache()  # drop process cache; keyring is the only source now
        run.return_value = _proc(0, stdout="value-2")
        assert read_op_secret("op://V/I/f") == "value-1", "served from keyring, op not called"
        assert run.call_count == 1, "subprocess only ran once"

    def test_disk_cache_respects_ttl_expiry(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, fake_keyring: Any
    ) -> None:
        from berb_common.secrets import clear_op_cache

        monkeypatch.setenv("BERB_OP_DISK_CACHE", "1")
        monkeypatch.setenv("BERB_OP_DISK_CACHE_TTL_SEC", "60")
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        run = mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            side_effect=[_proc(0, stdout="value-1"), _proc(0, stdout="value-2")],
        )
        # First call seeds the cache.
        time_mock = mocker.patch("berb_common.secrets.onepassword.time.time", return_value=1000.0)
        assert read_op_secret("op://V/I/f") == "value-1"

        # Advance well past TTL; the keyring entry must be ignored.
        clear_op_cache()
        time_mock.return_value = 1000.0 + 120  # 60s past 60s TTL
        assert read_op_secret("op://V/I/f") == "value-2"
        assert run.call_count == 2

    def test_clear_op_disk_cache_removes_keyring_entry(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, fake_keyring: Any
    ) -> None:
        from berb_common.secrets import clear_op_disk_cache

        monkeypatch.setenv("BERB_OP_DISK_CACHE", "1")
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="v"),
        )
        read_op_secret("op://V/I/f")
        assert len(fake_keyring) == 1
        clear_op_disk_cache("op://V/I/f")
        assert fake_keyring == {}

    def test_keyring_unavailable_degrades_silently(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If `keyring` import raises, read_op_secret still works (no caching)."""
        import sys

        monkeypatch.setenv("BERB_OP_DISK_CACHE", "1")
        # Force `import keyring` to ImportError inside the cache helpers.
        monkeypatch.setitem(sys.modules, "keyring", None)
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value="/usr/bin/op")
        mocker.patch(
            "berb_common.secrets.onepassword.subprocess.run",
            return_value=_proc(0, stdout="value"),
        )
        assert read_op_secret("op://V/I/f") == "value"
