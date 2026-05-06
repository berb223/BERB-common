"""Parse verified-sources LLM output into typed rows.

Tries strict JSON first; falls back to extracting bare ``https://`` URLs from
the response when the model emits markdown/prose around the JSON. Mirrors the
pre-port behaviour from FTNT-sales-workbench so existing fixtures keep parsing
identically.
"""

from __future__ import annotations

import json
from typing import Any

from berb_common.verified_sources.models import VerifiedSourceRow

_BOM = "﻿"
_URL_DELIMS = set(" \"'<>()[]{},;|\t\r\n")


def _strip_bom(text: str) -> str:
    if text.startswith(_BOM):
        return text[1:]
    if len(text) >= 3 and text[:3] == "\xef\xbb\xbf":
        return text[3:]
    return text


def _extract_first_json_object(text: str) -> str:
    """Return the substring spanning the first balanced ``{...}`` block.

    Returns ``text[start:]`` (unbalanced tail) when braces are unmatched,
    so callers can still attempt :func:`json.loads`. Returns the full input
    when no ``{`` is present.
    """
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _item_str(d: dict[str, Any], key: str) -> str:
    """Look up ``d[key]`` case-insensitively, coercing scalars to ``str``."""
    for k, v in d.items():
        if k.lower() == key.lower() and not isinstance(v, dict | list):
            return str(v) if v is not None else ""
    v = d.get(key)
    if v is not None and not isinstance(v, dict | list):
        return str(v)
    return ""


def _results_list(root: dict[str, Any]) -> list[dict[str, Any]] | None:
    for k, v in root.items():
        if k.lower() == "results" and isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    return None


def _extract_url_token(text: str, start_pos: int) -> str:
    for i in range(start_pos, len(text)):
        if text[i] in _URL_DELIMS:
            return text[start_pos:i]
    return text[start_pos:]


def parse_pipe_fallback(text: str, *, max_rows: int) -> list[VerifiedSourceRow]:
    """Recover rows from raw text when JSON parsing fails.

    Walks the input scanning for ``https://`` literals and emits one row per
    unique URL with ``source_type="pipe_extract"``. The runner uses this only
    when the strict JSON path returns nothing — it's a last-resort recovery,
    not a primary path.
    """
    flat = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    seen: set[str] = set()
    out: list[VerifiedSourceRow] = []
    pos = 0
    while len(out) < max_rows:
        p = flat.find("https://", pos)
        if p < 0:
            break
        u = _extract_url_token(flat, p).rstrip(".,);]")
        if u and u not in seen:
            seen.add(u)
            out.append(
                VerifiedSourceRow(
                    url=u,
                    source_type="pipe_extract",
                    deal_parties="",
                    description="",
                )
            )
        pos = p + max(len(u), 4)
    return out


def parse_verified_sources_json(
    response_text: str,
    *,
    max_rows: int = 10,
    append_deal_parties: bool = True,
) -> list[VerifiedSourceRow]:
    """Parse an LLM response into ``VerifiedSourceRow`` objects.

    Args:
        response_text: Verbatim LLM output. May include a leading BOM and/or
            prose around the JSON object.
        max_rows: Cap on the number of rows returned.
        append_deal_parties: When ``True`` (default), suffix each row's
            ``description`` with ``"| Parties: <deal_parties>"`` (or
            ``"Parties: <deal_parties>"`` if description is empty) when
            ``deal_parties`` is non-empty. Set ``False`` to keep the raw
            description.

    Returns:
        A list of :class:`VerifiedSourceRow`. Empty when the response is
        unparseable and the pipe fallback also recovers nothing.
    """
    text = _strip_bom(response_text.strip())
    json_text = _extract_first_json_object(text)
    try:
        root = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return parse_pipe_fallback(response_text, max_rows=max_rows)

    if not isinstance(root, dict):
        return parse_pipe_fallback(response_text, max_rows=max_rows)

    rows_raw = _results_list(root)
    if not rows_raw:
        return parse_pipe_fallback(response_text, max_rows=max_rows)

    out: list[VerifiedSourceRow] = []
    for item in rows_raw[:max_rows]:
        url = _item_str(item, "url")
        st = _item_str(item, "source_type")
        dp = _item_str(item, "deal_parties")
        desc = _item_str(item, "description")
        merged = desc
        if append_deal_parties and dp.strip():
            merged = f"{merged} | Parties: {dp}" if merged.strip() else f"Parties: {dp}"
        out.append(
            VerifiedSourceRow(
                url=url,
                source_type=st,
                deal_parties=dp,
                description=merged,
            )
        )
    return out
