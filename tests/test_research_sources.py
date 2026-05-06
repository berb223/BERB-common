"""Tests for berb_common.research_sources."""

from __future__ import annotations

import pytest

from berb_common.research_sources import (
    ACTIVITY_SOURCES,
    Activity,
    Tier,
    TierList,
    render_source_hierarchy,
)


class TestCatalog:
    def test_every_activity_has_a_tier_list(self) -> None:
        # Every enum value must have a TierList entry — otherwise rendering fails.
        for activity in Activity:
            assert activity in ACTIVITY_SOURCES, f"{activity} missing from catalog"

    def test_every_tier_has_a_description_and_sources(self) -> None:
        for activity, tier_list in ACTIVITY_SOURCES.items():
            for label, tier in (
                ("tier_1", tier_list.tier_1),
                ("tier_2", tier_list.tier_2),
                ("tier_3", tier_list.tier_3),
            ):
                assert tier.description.strip(), f"{activity}.{label} description is empty"
                assert tier.sources, f"{activity}.{label} sources is empty"

    def test_people_tier_2_includes_linkedin(self) -> None:
        # Sanity check on the catalog's most important specialist source.
        assert "linkedin.com" in ACTIVITY_SOURCES[Activity.PEOPLE].tier_2.sources

    def test_financial_info_tier_3_includes_yahoo_finance(self) -> None:
        sources = ACTIVITY_SOURCES[Activity.FINANCIAL_INFO].tier_3.sources
        assert "finance.yahoo.com" in sources

    def test_cybersecurity_tier_2_includes_fortiguard(self) -> None:
        sources = ACTIVITY_SOURCES[Activity.CYBERSECURITY].tier_2.sources
        assert any("fortiguard" in s for s in sources)


class TestRenderHierarchy:
    def test_substitutes_customer_website_in_tier_1(self) -> None:
        out = render_source_hierarchy(
            Activity.COMPANY_FACTS, customer_website="https://acme.example"
        )
        assert "https://acme.example/about" in out
        assert "{customer_website}" not in out

    def test_strips_trailing_slash_before_substitution(self) -> None:
        out = render_source_hierarchy(
            Activity.COMPANY_FACTS, customer_website="https://acme.example/"
        )
        assert "https://acme.example/about" in out
        # Double slashes shouldn't appear.
        assert "//about" not in out

    def test_leaves_placeholder_when_no_website(self) -> None:
        out = render_source_hierarchy(Activity.COMPANY_FACTS)
        assert "{customer_website}" in out

    def test_includes_all_three_tiers(self) -> None:
        out = render_source_hierarchy(Activity.PEOPLE, customer_website="https://x.example")
        assert "Tier 1" in out
        assert "Tier 2" in out
        assert "Tier 3" in out

    def test_includes_soft_preference_clause(self) -> None:
        out = render_source_hierarchy(Activity.PEOPLE)
        assert "soft preference" in out
        assert "fall back" in out.lower()

    def test_activity_value_in_output(self) -> None:
        out = render_source_hierarchy(Activity.NEWS_MA_DEALS)
        assert "news_ma_deals" in out

    def test_renders_for_every_catalog_entry(self) -> None:
        # Smoke check: every catalog entry must render without raising.
        for activity in Activity:
            out = render_source_hierarchy(activity, customer_website="https://x.example")
            assert out.startswith("SOURCE HIERARCHY")
            assert activity.value in out


class TestTierModels:
    def test_tier_validates_required_fields(self) -> None:
        with pytest.raises(ValueError):
            Tier(description="x")  # type: ignore[call-arg] — sources missing

    def test_tier_list_validates(self) -> None:
        with pytest.raises(ValueError):
            TierList(  # type: ignore[call-arg]
                tier_1=Tier(description="x", sources=["a"]),
                tier_2=Tier(description="y", sources=["b"]),
            )
