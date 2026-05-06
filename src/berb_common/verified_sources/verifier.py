"""Verify HTTPS URL reachability via HEAD/GET probes.

Three public functions:

- :func:`verify_url` — probe one URL, return ``True``/``False``.
- :func:`verify_urls` — probe many URLs in parallel, return ``{url: bool}``.
- :func:`filter_dead_rows` — split a list of ``VerifiedSourceRow`` into
  ``(kept, dropped)`` based on URL reachability.

The probe sends HEAD first (cheap; no body transfer), and falls back to GET
for servers that block HEAD or return ``405 Method Not Allowed``. A response
status of ``< 400`` (after redirects) counts as reachable.

Non-https URLs and empty strings always fail the probe — the prompts already
require https, so this is a defensive double-check.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

import httpx

from berb_common.logging import get_logger
from berb_common.verified_sources.models import VerifiedSourceRow

_log = get_logger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "berb-common-verified-sources/1.0 (link check)",
    "Accept": "*/*",
}


def verify_url(url: str, *, timeout: float = 12.0) -> bool:
    """Return ``True`` when ``url`` is a reachable ``https://`` resource.

    Uses HEAD then GET. Any exception (DNS, TLS, timeout, connection reset)
    counts as unreachable. Status codes ``< 400`` after redirects count as
    reachable.
    """
    u = (url or "").strip()
    if not u.startswith("https://"):
        return False

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            verify=True,
            headers=_DEFAULT_HEADERS,
        ) as client:
            try:
                r = client.head(u)
                if r.status_code < 400:
                    return True
            except httpx.HTTPError as ex:
                _log.debug("verify_url_head_failed", url=u[:200], error=str(ex))
            try:
                r = client.get(u)
                return r.status_code < 400
            except httpx.HTTPError as ex:
                _log.debug("verify_url_get_failed", url=u[:200], error=str(ex))
                return False
    except Exception as ex:
        # Defensive: a probe must never propagate. Any unexpected error
        # (DNS resolver crash, threading issue, etc.) becomes "unreachable".
        _log.debug("verify_url_unexpected_error", url=u[:200], error=str(ex))
        return False


def verify_urls(
    urls: Iterable[str],
    *,
    timeout: float = 12.0,
    max_workers: int = 10,
) -> dict[str, bool]:
    """Probe each URL in parallel; return ``{url: reachable}``.

    Duplicate URLs in ``urls`` are de-duplicated — the returned dict has one
    entry per unique input. Order is not guaranteed.

    Args:
        urls: URLs to probe. Empty / non-https entries return ``False``
            without a network call.
        timeout: Per-request timeout in seconds.
        max_workers: Thread pool size. The probes are network-bound, so
            scaling above 10 helps when many URLs are in play.
    """
    unique = list({u for u in urls if u})
    if not unique:
        return {}
    out: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = pool.map(lambda u: (u, verify_url(u, timeout=timeout)), unique)
        for u, ok in results:
            out[u] = ok
    return out


def filter_dead_rows(
    rows: Sequence[VerifiedSourceRow],
    *,
    timeout: float = 12.0,
    max_workers: int = 10,
) -> tuple[list[VerifiedSourceRow], list[VerifiedSourceRow]]:
    """Split rows into ``(kept, dropped)`` by URL reachability.

    Rows whose URL is empty or non-https go straight into ``dropped`` without
    a network call. Rows with the same URL are probed once and the result
    applied to every occurrence.
    """
    if not rows:
        return [], []
    reachability = verify_urls(
        (r.url for r in rows if r.url),
        timeout=timeout,
        max_workers=max_workers,
    )
    kept: list[VerifiedSourceRow] = []
    dropped: list[VerifiedSourceRow] = []
    for row in rows:
        if reachability.get(row.url, False):
            kept.append(row)
        else:
            dropped.append(row)
    return kept, dropped
