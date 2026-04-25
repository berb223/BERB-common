"""Generic secret resolution with optional in-process caching.

Resolves a single secret via a precedence chain:

1. Explicit caller-provided value (highest priority — for tests, request headers, ...).
2. In-process cache (if ``cache_key`` is supplied).
3. ``$<ref_env>`` → :func:`berb_common.secrets.read_op_secret` → cached.
4. ``$<value_env>`` plaintext env var (legacy fallback).

Errors raised by the 1Password CLI propagate — callers wishing to fall back to
``value_env`` after an op-read failure should catch :class:`OpReadError`.
"""

from __future__ import annotations

import os
from threading import Lock

from berb_common.secrets.onepassword import read_op_secret

_cache: dict[str, str] = {}
_lock = Lock()


def resolve_secret(
    *,
    ref_env: str | None = None,
    value_env: str | None = None,
    explicit: str | None = None,
    cache_key: str | None = None,
) -> str | None:
    """Resolve a secret using the precedence chain documented at module level.

    Args:
        ref_env: Name of an environment variable holding an ``op://`` reference.
        value_env: Name of an environment variable holding the plaintext value
            (legacy fallback).
        explicit: Caller-provided override — takes precedence over everything.
            Pass an empty string to force "no value" (useful in tests).
        cache_key: If set, results from the ``op read`` path are cached under
            this key for the process lifetime. Subsequent calls with the same
            ``cache_key`` skip the CLI round-trip.

    Returns:
        The secret string, or ``None`` if no source produced one.

    Raises:
        OpReadError: If the ``ref_env`` path produces a reference but the CLI
            read fails. Plaintext ``value_env`` is **not** consulted in that
            case — the failure is surfaced.

    Example:
        >>> import os
        >>> from berb_common.secrets import resolve_secret, clear_secret_cache
        >>> os.environ["MY_KEY"] = "abc"
        >>> resolve_secret(value_env="MY_KEY")
        'abc'
        >>> clear_secret_cache()
    """
    if explicit is not None:
        return explicit.strip() or None

    if cache_key is not None:
        with _lock:
            cached = _cache.get(cache_key)
            if cached is not None:
                return cached

    ref = (os.environ.get(ref_env) or "").strip() if ref_env else ""
    if ref:
        value = read_op_secret(ref)
        if cache_key is not None:
            with _lock:
                _cache[cache_key] = value
        return value

    raw = (os.environ.get(value_env) or "").strip() if value_env else ""
    return raw or None


def clear_secret_cache() -> None:
    """Clear the in-process secret cache.

    Use in tests, or after the user signs out of 1Password and a stale value
    might still be cached.
    """
    with _lock:
        _cache.clear()
