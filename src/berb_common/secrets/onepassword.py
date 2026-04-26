"""1Password CLI (`op`) wrapper.

Resolves ``op://vault/item/field`` references at runtime via the 1Password CLI.
Nothing is stored in code or environment files — values come from 1Password
directly.

Prerequisites:

- Install: https://developer.1password.com/docs/cli/get-started/
- Sign in: ``op signin`` (or use the desktop-app integration)

Reference format
----------------

``op://<vault>/<item>/<field>`` — e.g. ``op://Personal/Anthropic/api-key``.

Alternative for shell scripts: ``op run --env-file=...`` substitutes references
in an env file before launching the child process.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from glob import glob


class OpReadError(Exception):
    """Raised when reading a secret via the 1Password CLI fails."""


def _find_op_executable() -> str | None:
    """Locate the 1Password CLI executable.

    First consults ``PATH`` via :func:`shutil.which`. If that fails, falls back
    to a small list of well-known install locations so the CLI is reachable
    even when the launching shell has a stripped ``PATH`` (background services,
    automation tools, IDE-spawned subprocesses).

    Returns:
        Path to the executable, or ``None`` if not found anywhere.
    """
    found = shutil.which("op")
    if found:
        return found

    if sys.platform == "win32":
        candidates: list[str] = []
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        candidates.append(os.path.join(program_files, "1Password CLI", "op.exe"))
        if local_appdata:
            # winget installs under a versioned package directory.
            candidates.extend(
                glob(
                    os.path.join(
                        local_appdata,
                        "Microsoft",
                        "WinGet",
                        "Packages",
                        "AgileBits.1Password.CLI_*",
                        "op.exe",
                    )
                )
            )
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    # POSIX fallbacks for shells where /usr/local/bin or Homebrew aren't on PATH.
    for path in ("/usr/local/bin/op", "/opt/homebrew/bin/op", "/usr/bin/op"):
        if os.path.isfile(path):
            return path
    return None


def read_op_secret(reference: str, *, timeout_sec: float = 45.0) -> str:
    """Read a secret via ``op read <reference>``.

    Args:
        reference: 1Password reference of the form ``op://<vault>/<item>/<field>``.
        timeout_sec: Subprocess timeout. The CLI must complete within this window.

    Returns:
        The secret value with surrounding whitespace stripped.

    Raises:
        OpReadError: If the reference is malformed, the ``op`` binary is missing,
            the call times out, ``op`` returns a non-zero exit code, or the
            output is empty.

    Example:
        >>> from berb_common.secrets import read_op_secret
        >>> key = read_op_secret("op://Personal/Anthropic/api-key")  # doctest: +SKIP
    """
    ref = reference.strip()
    if not ref.startswith("op://"):
        raise OpReadError(f"1Password reference must start with op:// (got: {reference!r})")

    op_exe = _find_op_executable()
    if op_exe is None:
        raise OpReadError(
            "1Password CLI 'op' not found in PATH or known install locations. "
            "Install from https://developer.1password.com/docs/cli/get-started/"
        )

    try:
        proc = subprocess.run(
            [op_exe, "read", ref],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpReadError(f"'op read' timed out after {timeout_sec}s") from exc

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "<no output>"
        raise OpReadError(
            f"'op read' failed (exit {proc.returncode}). {err}\n"
            "Run `op signin` and check the op:// path."
        )

    value = proc.stdout.strip()
    if not value:
        raise OpReadError("'op read' returned an empty value")
    return value


def try_read_op_secret(reference: str | None) -> str | None:
    """Read a secret, returning ``None`` if no reference is given.

    Wraps :func:`read_op_secret` for callers where the reference is optional.
    Errors during the read still raise — only the absent / blank-reference
    path returns ``None``.

    Example:
        >>> from berb_common.secrets import try_read_op_secret
        >>> try_read_op_secret(None) is None
        True
        >>> try_read_op_secret("   ") is None
        True
    """
    if reference is None or not reference.strip():
        return None
    return read_op_secret(reference)
