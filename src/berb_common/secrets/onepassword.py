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

import shutil
import subprocess


class OpReadError(Exception):
    """Raised when reading a secret via the 1Password CLI fails."""


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

    op_exe = shutil.which("op")
    if op_exe is None:
        raise OpReadError(
            "1Password CLI 'op' not found in PATH. "
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
