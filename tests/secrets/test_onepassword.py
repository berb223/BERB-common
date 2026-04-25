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
        mocker.patch("berb_common.secrets.onepassword.shutil.which", return_value=None)
        with pytest.raises(OpReadError, match="not found in PATH"):
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
