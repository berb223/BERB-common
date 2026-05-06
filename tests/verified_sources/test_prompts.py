"""Tests for berb_common.verified_sources.prompts."""

from __future__ import annotations

from berb_common.research_sources import Activity
from berb_common.verified_sources.models import VerifiedStepRequest
from berb_common.verified_sources.prompts import build_system_prompt, build_user_prompt


def _request(**overrides: object) -> VerifiedStepRequest:
    base: dict[str, object] = {
        "title": "Recent News, M&A",
        "focus": "Recent deals.",
        "category": "news_trends_ma",
        "company_name": "Acme Corp",
        "country": "Switzerland",
        "industry": "Manufacturing",
        "website": "https://acme.example",
        "max_results": 5,
    }
    base.update(overrides)
    return VerifiedStepRequest(**base)  # type: ignore[arg-type]


class TestSystemPrompt:
    def test_starts_with_framing(self) -> None:
        request = _request(framing="You are a senior analyst.")
        out = build_system_prompt(request)
        assert out.startswith("You are a senior analyst.")

    def test_default_framing_is_generic(self) -> None:
        out = build_system_prompt(_request())
        assert "Fortinet" not in out
        assert "business analyst" in out.lower()

    def test_interpolates_max_results(self) -> None:
        out = build_system_prompt(_request(max_results=7))
        assert "up to 7 objects" in out
        assert "up to 7 results" not in out  # only the array sentence mentions count

    def test_strict_url_rule_present(self) -> None:
        out = build_system_prompt(_request())
        assert "https://" in out
        assert "Do NOT invent URLs" in out

    def test_web_search_variant_references_tool(self) -> None:
        out = build_system_prompt(_request(), web_search=True)
        assert "web_search" in out
        assert "tool-result" in out or "search results" in out

    def test_web_search_variant_drops_memory_only_phrasing(self) -> None:
        out = build_system_prompt(_request(), web_search=True)
        # Memory-only wording should not appear when tool use is enabled.
        assert "Do NOT invent URLs" not in out

    def test_default_is_memory_mode(self) -> None:
        out = build_system_prompt(_request())
        assert "web_search" not in out

    def test_grounding_clause_in_both_variants(self) -> None:
        # Rule 8 ("ground every description in actual content") applies to both
        # modes — it's the second guardrail beyond URL provenance.
        for ws in (False, True):
            assert "Ground every description" in build_system_prompt(_request(), web_search=ws)


class TestUserPrompt:
    def test_includes_topic_and_company(self) -> None:
        out = build_user_prompt(_request())
        assert "Recent News, M&A" in out
        assert "Acme Corp" in out
        assert "Switzerland" in out
        assert "Manufacturing" in out
        assert "https://acme.example" in out

    def test_includes_focus_and_category(self) -> None:
        out = build_user_prompt(_request())
        assert "Recent deals." in out
        assert "news_trends_ma" in out

    def test_relays_max_results(self) -> None:
        out = build_user_prompt(_request(max_results=3))
        assert "up to 3 results" in out

    def test_first_party_source_instruction_when_website_supplied(self) -> None:
        out = build_user_prompt(_request(website="https://acme.example"))
        assert "First-party source" in out
        assert "https://acme.example" in out
        # Cues both web_search and memory-only paths cover.
        assert "site:" in out
        assert "press releases" in out

    def test_no_first_party_instruction_when_website_blank(self) -> None:
        out = build_user_prompt(_request(website=""))
        assert "First-party source" not in out

    def test_no_first_party_instruction_when_website_whitespace(self) -> None:
        out = build_user_prompt(_request(website="   "))
        assert "First-party source" not in out

    def test_activity_renders_source_hierarchy(self) -> None:
        out = build_user_prompt(
            _request(activity=Activity.PEOPLE, website="https://acme.example")
        )
        assert "SOURCE HIERARCHY" in out
        assert "linkedin.com" in out
        # Customer-website substitution applies inside the hierarchy too.
        assert "https://acme.example/leadership" in out

    def test_no_activity_no_hierarchy(self) -> None:
        out = build_user_prompt(_request(activity=None))
        assert "SOURCE HIERARCHY" not in out
