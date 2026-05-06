"""Tests for berb_common.verified_sources.parser."""

from __future__ import annotations

from berb_common.verified_sources.parser import (
    parse_pipe_fallback,
    parse_verified_sources_json,
)

_ONE_RESULT = """
{
  "category": "news_trends_ma",
  "company": "Acme Corp",
  "industry": "Manufacturing",
  "country": "Switzerland",
  "results": [
    {
      "url": "https://example.com/news/1",
      "source_type": "business_news",
      "deal_parties": "",
      "description": "Acme acquires Beta."
    }
  ]
}
"""

_TWO_RESULTS = """
{"results": [
  {"url": "https://a.example/x", "source_type": "company_press_release", "deal_parties": "Acme, Beta", "description": "Press release."},
  {"url": "https://b.example/y", "source_type": "regulatory_filing", "deal_parties": "", "description": "Filing."}
]}
"""


class TestStrictJson:
    def test_single_row_round_trip(self) -> None:
        rows = parse_verified_sources_json(_ONE_RESULT, max_rows=5)
        assert len(rows) == 1
        r = rows[0]
        assert r.url == "https://example.com/news/1"
        assert r.source_type == "business_news"
        assert r.deal_parties == ""
        assert r.description == "Acme acquires Beta."

    def test_multiple_rows(self) -> None:
        rows = parse_verified_sources_json(_TWO_RESULTS, max_rows=5)
        assert [r.url for r in rows] == ["https://a.example/x", "https://b.example/y"]

    def test_max_rows_caps_results(self) -> None:
        rows = parse_verified_sources_json(_TWO_RESULTS, max_rows=1)
        assert len(rows) == 1
        assert rows[0].url == "https://a.example/x"

    def test_deal_parties_appended_to_description_when_present(self) -> None:
        rows = parse_verified_sources_json(_TWO_RESULTS, max_rows=5)
        assert rows[0].description == "Press release. | Parties: Acme, Beta"
        # second row has empty deal_parties — no suffix
        assert rows[1].description == "Filing."

    def test_deal_parties_only_when_description_empty(self) -> None:
        text = """{"results":[{"url":"https://a.example","source_type":"x","deal_parties":"X, Y","description":""}]}"""
        rows = parse_verified_sources_json(text, max_rows=5)
        assert rows[0].description == "Parties: X, Y"

    def test_append_deal_parties_off_keeps_raw_description(self) -> None:
        rows = parse_verified_sources_json(_TWO_RESULTS, max_rows=5, append_deal_parties=False)
        assert rows[0].description == "Press release."
        assert rows[0].deal_parties == "Acme, Beta"

    def test_strips_utf8_bom(self) -> None:
        rows = parse_verified_sources_json("﻿" + _ONE_RESULT, max_rows=5)
        assert len(rows) == 1

    def test_extracts_from_prose_wrapped_json(self) -> None:
        prose = "Here are the results:\n" + _ONE_RESULT + "\nLet me know if you need more."
        rows = parse_verified_sources_json(prose, max_rows=5)
        assert len(rows) == 1
        assert rows[0].url == "https://example.com/news/1"

    def test_case_insensitive_field_lookup(self) -> None:
        text = """{"Results":[{"URL":"https://a.example","Source_Type":"x","Deal_Parties":"","Description":"D"}]}"""
        rows = parse_verified_sources_json(text, max_rows=5)
        assert len(rows) == 1
        assert rows[0].url == "https://a.example"
        assert rows[0].source_type == "x"
        assert rows[0].description == "D"


class TestFallback:
    def test_invalid_json_falls_back_to_pipe(self) -> None:
        text = "not JSON at all but here is a link https://recovered.example/page yes"
        rows = parse_verified_sources_json(text, max_rows=5)
        assert len(rows) == 1
        assert rows[0].url == "https://recovered.example/page"
        assert rows[0].source_type == "pipe_extract"

    def test_root_not_dict_falls_back(self) -> None:
        rows = parse_verified_sources_json('["not", "a", "dict"]', max_rows=5)
        assert rows == []

    def test_no_results_array_falls_back(self) -> None:
        text = '{"category":"x","results":"not an array"}'
        rows = parse_verified_sources_json(text, max_rows=5)
        assert rows == []

    def test_pipe_fallback_dedupes_urls(self) -> None:
        text = "https://a.example/x and again https://a.example/x and a new one https://b.example/y"
        rows = parse_pipe_fallback(text, max_rows=5)
        assert [r.url for r in rows] == ["https://a.example/x", "https://b.example/y"]

    def test_pipe_fallback_strips_trailing_punctuation(self) -> None:
        rows = parse_pipe_fallback("see https://a.example/x.", max_rows=5)
        assert rows[0].url == "https://a.example/x"

    def test_pipe_fallback_respects_max_rows(self) -> None:
        text = " ".join(f"https://e.example/{i}" for i in range(20))
        rows = parse_pipe_fallback(text, max_rows=3)
        assert len(rows) == 3
