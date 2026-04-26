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
        from berb_common.secrets.onepassword import _find_op_executable

        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        mocker.patch("berb_common.secrets.onepassword.sys.platform", "win32")
        mocker.patch.dict(
            "berb_common.secrets.onepassword.os.environ",
            {"PROGRAMFILES": r"C:\Program Files", "LOCALAPPDATA": r"C:\Users\u\AppData\Local"},
            clear=False,
        )
        mocker.patch(
            "berb_common.secrets.onepassword.os.path.isfile",
            side_effect=lambda p: p == r"C:\Program Files\1Password CLI\op.exe",
        )
        mocker.patch("berb_common.secrets.onepassword.glob", return_value=[])
        assert _find_op_executable() == r"C:\Program Files\1Password CLI\op.exe"

    def test_windows_fallback_winget(self, mocker: MockerFixture) -> None:
        from berb_common.secrets.onepassword import _find_op_executable

        winget_path = (
            r"C:\Users\u\AppData\Local\Microsoft\WinGet\Packages\AgileBits.1Password.CLI_x\op.exe"  # noqa: E501
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
