"""Authoritative-source catalog: per-activity tier lists for LLM grounding.

Each :class:`Activity` (people research, financial info, M&A, etc.) maps to a
three-tier preference list of authoritative sources. Consumers render the
tier list into their prompt via :func:`render_source_hierarchy`; the model
gets a soft preference ordering that biases ``web_search`` toward the right
domains without forcing them (``allowed_domains`` is too restrictive — the
catalog is a hint, not a fence).

Tier semantics:
    Tier 1 — always check first; the canonical first-party / regulatory source.
    Tier 2 — check next when Tier 1 is incomplete; specialist authority.
    Tier 3 — fall back to general-press / database aggregators.

Customer-specific URLs use the ``{customer_website}`` placeholder, which
:func:`render_source_hierarchy` substitutes at call time. Pass an empty
``customer_website`` to leave the placeholder visible (useful when the
catalog is rendered before a specific company is known).

The catalog is BERB-common's curated default — consumers can extend or
override entries by mutating :data:`ACTIVITY_SOURCES` at startup, or by
building their own ``TierList`` and rendering it directly.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Activity(StrEnum):
    """Research activities with known authoritative source hierarchies.

    The string value is stable (used as a key in :data:`ACTIVITY_SOURCES` and
    as the ``activity`` value the model sees in prompts).
    """

    COMPANY_FACTS = "company_facts"
    FINANCIAL_INFO = "financial_info"
    VISION_MISSION = "vision_mission"
    PEOPLE = "people"
    NEWS_MA_DEALS = "news_ma_deals"
    STRATEGY_DIGITAL = "strategy_digital"
    TECHNOLOGY_IT = "technology_it"
    CYBERSECURITY = "cybersecurity"
    PARTNERS_ECOSYSTEM = "partners_ecosystem"
    COMPETITORS = "competitors"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    INDUSTRY_MARKET = "industry_market"


class Tier(BaseModel):
    """One tier of preferred sources for an activity.

    Attributes:
        description: Freeform prose for the prompt — explains *why* this tier
            is on the list ("company IR materials", "business databases").
        sources: Canonical strings (URLs / domains / labels). Strings
            containing ``{customer_website}`` are substituted at render time.
    """

    description: str
    sources: list[str]


class TierList(BaseModel):
    """Three-tier preference list for an activity."""

    tier_1: Tier
    tier_2: Tier
    tier_3: Tier


# Sentinel substituted at render time when a customer website is supplied.
_CUSTOMER = "{customer_website}"


ACTIVITY_SOURCES: dict[Activity, TierList] = {
    Activity.COMPANY_FACTS: TierList(
        tier_1=Tier(
            description="Company's own canonical pages and annual report",
            sources=[f"{_CUSTOMER}/about", f"{_CUSTOMER}/contact", "annual report"],
        ),
        tier_2=Tier(description="Wikipedia", sources=["en.wikipedia.org"]),
        tier_3=Tier(
            description="Business databases",
            sources=["crunchbase.com", "opencorporates.com"],
        ),
    ),
    Activity.FINANCIAL_INFO: TierList(
        tier_1=Tier(
            description="Company IR section and annual report",
            sources=[f"{_CUSTOMER}/investor-relations", "annual report"],
        ),
        tier_2=Tier(
            description=(
                "Sectoral regulator (SEC.gov for US; FINMA / BaFin / FCA / etc. by jurisdiction)"
            ),
            sources=["sec.gov", "regulator filings"],
        ),
        tier_3=Tier(
            description="Tier-1 financial press and market data",
            sources=[
                "bloomberg.com",
                "reuters.com",
                "ft.com",
                "wsj.com",
                "finance.yahoo.com",
            ],
        ),
    ),
    Activity.VISION_MISSION: TierList(
        tier_1=Tier(
            description="Company's about / values pages and annual report",
            sources=[f"{_CUSTOMER}/about", f"{_CUSTOMER}/values", "annual report"],
        ),
        tier_2=Tier(description="Recent CEO interviews", sources=["press interviews"]),
        tier_3=Tier(
            description="Wikipedia and press",
            sources=["en.wikipedia.org", "press"],
        ),
    ),
    Activity.PEOPLE: TierList(
        tier_1=Tier(
            description="Company leadership/team page and annual report",
            sources=[f"{_CUSTOMER}/leadership", f"{_CUSTOMER}/team", "annual report"],
        ),
        tier_2=Tier(description="LinkedIn", sources=["linkedin.com"]),
        tier_3=Tier(
            description="Business databases and announcement press releases",
            sources=["crunchbase.com", "bloomberg.com", "press releases"],
        ),
    ),
    Activity.NEWS_MA_DEALS: TierList(
        tier_1=Tier(
            description="Company press room",
            sources=[f"{_CUSTOMER}/press", f"{_CUSTOMER}/news"],
        ),
        tier_2=Tier(
            description="Tier-1 financial press",
            sources=["reuters.com", "ft.com", "wsj.com", "bloomberg.com"],
        ),
        tier_3=Tier(
            description="Deal databases and regulatory filings",
            sources=["crunchbase.com", "pitchbook.com", "regulatory filings"],
        ),
    ),
    Activity.STRATEGY_DIGITAL: TierList(
        tier_1=Tier(
            description="Investor Day decks and annual report",
            sources=[f"{_CUSTOMER}/investor-relations", "annual report"],
        ),
        tier_2=Tier(description="Recent CEO interviews", sources=["press interviews"]),
        tier_3=Tier(
            description="Industry analysts",
            sources=["gartner.com", "forrester.com", "idc.com"],
        ),
    ),
    Activity.TECHNOLOGY_IT: TierList(
        tier_1=Tier(
            description="Company tech blog and careers (job specs leak the stack)",
            sources=[f"{_CUSTOMER}/blog", f"{_CUSTOMER}/careers"],
        ),
        tier_2=Tier(description="GitHub", sources=["github.com"]),
        tier_3=Tier(description="Industry reports", sources=["industry reports"]),
    ),
    Activity.CYBERSECURITY: TierList(
        tier_1=Tier(
            description="Company security/trust pages",
            sources=[f"{_CUSTOMER}/security", f"{_CUSTOMER}/trust"],
        ),
        tier_2=Tier(
            description="Fortinet threat intelligence",
            sources=[
                "fortinet.com/resources/reports/threat-landscape-report",
                "fortinet.com/fortiguard/labs",
            ],
        ),
        tier_3=Tier(
            description="Trust portals, CVE databases, industry reports",
            sources=["cve.mitre.org", "trust portals", "industry reports"],
        ),
    ),
    Activity.PARTNERS_ECOSYSTEM: TierList(
        tier_1=Tier(
            description="Company partners directory",
            sources=[f"{_CUSTOMER}/partners"],
        ),
        tier_2=Tier(
            description="Partner companies' announcements",
            sources=["partner press releases"],
        ),
        tier_3=Tier(description="Trade press", sources=["trade press"]),
    ),
    Activity.COMPETITORS: TierList(
        tier_1=Tier(
            description="Customer's IR materials (segment overlap)",
            sources=[f"{_CUSTOMER}/investor-relations", "annual report"],
        ),
        tier_2=Tier(
            description="Competitor references and analyst quadrants",
            sources=["gartner.com", "forrester.com", "idc.com"],
        ),
        tier_3=Tier(
            description="Competitor leadership pages and press",
            sources=["competitor press"],
        ),
    ),
    Activity.REGULATORY_COMPLIANCE: TierList(
        tier_1=Tier(
            description="Sectoral regulator (SEC, EU regulators, FINMA, BaFin, FCC, etc.)",
            sources=["sec.gov", "regulator filings"],
        ),
        tier_2=Tier(
            description="Customer's compliance/legal page",
            sources=[f"{_CUSTOMER}/legal", f"{_CUSTOMER}/compliance"],
        ),
        tier_3=Tier(description="Trade press", sources=["trade press"]),
    ),
    Activity.INDUSTRY_MARKET: TierList(
        tier_1=Tier(
            description="Trade-association reports",
            sources=["trade associations"],
        ),
        tier_2=Tier(
            description="Industry analysts",
            sources=["gartner.com", "forrester.com", "idc.com"],
        ),
        tier_3=Tier(description="Tier-1 press", sources=["reuters.com", "ft.com"]),
    ),
}


def render_source_hierarchy(activity: Activity, *, customer_website: str = "") -> str:
    """Render the activity's tier list as a multiline prompt fragment.

    Substitutes ``{customer_website}`` in any tier's sources with the value
    supplied. Pass an empty string to leave the placeholder visible.

    The fragment ends with a soft-preference clause: "Prefer sources from
    Tier 1; fall back to Tier 2, then Tier 3 only if higher tiers don't have
    the answer." This is intentional — hard fences via ``allowed_domains``
    prevent the model from finding unexpected but legitimate sources.

    Args:
        activity: One of :class:`Activity`. Raises ``KeyError`` if not in
            :data:`ACTIVITY_SOURCES` (shouldn't happen with the enum).
        customer_website: The customer's homepage URL (or domain). Trailing
            slash is stripped before substitution.
    """
    tier_list = ACTIVITY_SOURCES[activity]
    customer = customer_website.strip().rstrip("/")

    def render_sources(sources: list[str]) -> str:
        if customer:
            return ", ".join(s.replace(_CUSTOMER, customer) for s in sources)
        return ", ".join(sources)

    return "\n".join(
        [
            f"SOURCE HIERARCHY (activity: {activity.value}, soft preference):",
            f"  Tier 1 — {tier_list.tier_1.description}: "
            f"{render_sources(tier_list.tier_1.sources)}",
            f"  Tier 2 — {tier_list.tier_2.description}: "
            f"{render_sources(tier_list.tier_2.sources)}",
            f"  Tier 3 — {tier_list.tier_3.description}: "
            f"{render_sources(tier_list.tier_3.sources)}",
            "Prefer sources from Tier 1; fall back to Tier 2, then Tier 3 only if "
            "higher tiers don't have the answer. This is a soft preference — if a "
            "lower-tier source is materially better for a specific finding, use it "
            "and cite it.",
        ]
    )
