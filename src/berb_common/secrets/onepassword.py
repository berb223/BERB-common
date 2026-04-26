"""1Password CLI (`op`) wrapper with optional OS-keystore caching.

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

Caching layers
--------------

Two cache layers sit in front of the ``op read`` subprocess. Both are
transparent to callers — the public API stays ``read_op_secret(ref) -> str``.

1. **Process cache** (always on)
   - Per-process ``dict[ref, value]``. Wiped at process exit and by
     :func:`clear_op_cache`. Saves repeated subprocess overhead in long-running
     services (Streamlit, FastAPI).

2. **OS keystore disk cache** (default on; opt out with
   ``BERB_OP_DISK_CACHE=0``)
   - Stored via the ``keyring`` library:
     - **Windows**: Credential Manager (DPAPI-protected, bound to the user's
       login session).
     - **macOS**: Keychain.
     - **Linux**: Secret Service (KWallet / GNOME Keyring).
   - TTL gate (default 24 hours; override via
     ``BERB_OP_DISK_CACHE_TTL_SEC``) prevents stale keys from being reused.
   - Cleared by :func:`clear_op_disk_cache`.
   - Silently skipped if ``keyring`` is missing or the OS backend is
     unavailable (headless Linux without Secret Service, etc.).

Threat-model notes
------------------

- The process cache is plain memory: a debugger attached to this process can
  recover the value. This is unavoidable for any in-memory cache; the
  alternative (no caching) means hitting ``op read`` and the 1Password app
  on every API call.
- The keystore entry is encrypted by the OS using a user-bound key. On
  Windows that is DPAPI behind your Windows account credentials. The 24h
  TTL limits how long a leaked machine state can replay the key.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import sys
import time
from glob import glob
from typing import Final

_log = logging.getLogger(__name__)


class OpReadError(Exception):
    """Raised when reading a secret via the 1Password CLI fails."""


# --- Process cache ----------------------------------------------------------

_process_cache: dict[str, str] = {}


def _clear_process_cache() -> None:
    _process_cache.clear()


atexit.register(_clear_process_cache)


def clear_op_cache() -> None:
    """Drop the in-process cache. Does NOT touch the OS keystore."""
    _clear_process_cache()


# --- OS keystore disk cache -------------------------------------------------

KEYRING_SERVICE: Final[str] = "berb-common"
KEYRING_USER_PREFIX: Final[str] = "op-secret"
DEFAULT_DISK_TTL_SEC: Final[int] = 86_400  # 24 hours


def _disk_cache_enabled() -> bool:
    """Default-on; opt out with ``BERB_OP_DISK_CACHE=0|false|no``."""
    raw = os.environ.get("BERB_OP_DISK_CACHE", "").strip().lower()
    return raw not in {"0", "false", "no"}


def _disk_cache_ttl_sec() -> int:
    raw = os.environ.get("BERB_OP_DISK_CACHE_TTL_SEC", "").strip()
    if not raw:
        return DEFAULT_DISK_TTL_SEC
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_DISK_TTL_SEC


def _keyring_user_for_ref(ref: str) -> str:
    """One keystore entry per ``op://`` reference."""
    return f"{KEYRING_USER_PREFIX}::{ref}"


def _disk_cache_get(ref: str) -> str | None:
    if not _disk_cache_enabled():
        return None
    try:
        import keyring
    except ImportError:
        return None
    try:
        raw = keyring.get_password(KEYRING_SERVICE, _keyring_user_for_ref(ref))
    except Exception as e:
        _log.debug("op disk cache: read failed: %s", e)
        return None
    if not raw or "|" not in raw:
        return None
    ts_str, secret = raw.split("|", 1)
    try:
        ts = float(ts_str)
    except ValueError:
        return None
    age = time.time() - ts
    if age < 0 or age > _disk_cache_ttl_sec():
        return None
    return secret or None


def _disk_cache_set(ref: str, secret: str) -> None:
    if not _disk_cache_enabled():
        return
    try:
        import keyring
    except ImportError:
        return
    blob = f"{time.time()}|{secret}"
    try:
        keyring.set_password(KEYRING_SERVICE, _keyring_user_for_ref(ref), blob)
    except Exception as e:
        _log.debug("op disk cache: write failed: %s", e)


def clear_op_disk_cache(ref: str | None = None) -> None:
    """Drop OS keystore entries.

    With ``ref=None`` (default), clears entries for any reference currently in
    the in-process cache. To wipe every ``berb-common`` entry on the machine,
    open the OS credential UI (Credential Manager on Windows, Keychain Access
    on macOS) or call this with each ``ref`` explicitly.
    """
    try:
        import keyring
        import keyring.errors as keyring_errors
    except ImportError:
        return
    refs = [ref] if ref else list(_process_cache.keys())
    for r in refs:
        try:
            keyring.delete_password(KEYRING_SERVICE, _keyring_user_for_ref(r))
        except keyring_errors.PasswordDeleteError:
            pass
        except Exception as e:
            _log.debug("op disk cache: delete failed for %s: %s", r, e)


# --- `op` discovery ---------------------------------------------------------


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


# --- Public API -------------------------------------------------------------


def read_op_secret(reference: str, *, timeout_sec: float = 45.0) -> str:
    """Read a secret via ``op read <reference>``, with caching.

    Lookup order: in-process cache → OS keystore (if enabled) →
    ``op read`` shell-out. The result is written back to whichever caches
    are enabled.

    Args:
        reference: 1Password reference of the form ``op://<vault>/<item>/<field>``.
        timeout_sec: Subprocess timeout for the underlying ``op read`` call.

    Returns:
        The secret value with surrounding whitespace stripped.

    Raises:
        OpReadError: If the reference is malformed, the ``op`` binary is
            missing, the call times out, ``op`` returns a non-zero exit code,
            or the output is empty.

    Example:
        >>> from berb_common.secrets import read_op_secret
        >>> key = read_op_secret("op://Personal/Anthropic/api-key")  # doctest: +SKIP
    """
    ref = reference.strip()
    if not ref.startswith("op://"):
        raise OpReadError(f"1Password reference must start with op:// (got: {reference!r})")

    cached = _process_cache.get(ref)
    if cached is not None:
        return cached

    cached = _disk_cache_get(ref)
    if cached is not None:
        _process_cache[ref] = cached
        return cached

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

    _process_cache[ref] = value
    _disk_cache_set(ref, value)
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
