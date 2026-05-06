"""Build system + user prompts for verified-sources research.

The system prompt enforces strict JSON-only output and the "real https URLs
only — never invent" rule that gives this module its name. The user prompt
relays the topic + company context. Both prompts are derived from the
:class:`VerifiedStepRequest` so consumers don't have to plumb individual
fields through.
"""

from __future__ import annotations

from berb_common.research_sources import render_source_hierarchy
from berb_common.verified_sources.models import VerifiedStepRequest


def build_system_prompt(request: VerifiedStepRequest, *, web_search: bool = False) -> str:
    """Return the system prompt for one research step.

    The first line is the consumer-supplied ``framing`` (role); the rest is
    the strict JSON output contract. ``request.max_results`` is interpolated
    into the contract so the model knows the per-step cap.

    Args:
        request: The step request (drives the ``max_results`` interpolation
            and the ``framing`` first line).
        web_search: When ``True``, the prompt instructs the model to use the
            ``web_search`` tool and cite ONLY URLs that appeared in tool
            results. When ``False`` (default), the prompt asks the model to
            recall real URLs from training data without inventing — the
            pre-tool-use behaviour. Set ``True`` whenever the runner is
            invoked with ``tools=[web_search_tool()]``.
    """
    if web_search:
        url_rules = (
            "4) Use the web_search tool to find sources. Cite ONLY URLs that appeared in your "
            "tool-result blocks; do NOT output URLs you did not see in search results.\n"
            "5) If web_search returned no usable URL for an entry, omit that result object. "
            "Better to return fewer results than to include an unverified URL."
        )
    else:
        url_rules = (
            "4) Every url MUST start with https:// and be a real, publicly reachable page you "
            "are confident about.\n"
            "5) Do NOT invent URLs, paths, or domains. If you cannot cite a real https URL, "
            "omit that result object."
        )
    return f"""{request.framing}

OUTPUT RULES (STRICT):
1) Return ONLY one JSON object. No markdown, no ``` fences, no headings, no commentary before or after JSON.
2) JSON shape (keys required):
   {{"category":"<category_key>","company":"<string>","industry":"<string>","country":"<string>","results":[...]}}
3) results is an array of up to {request.max_results} objects, each:
   {{"url":"https://...","source_type":"<short label>","deal_parties":"<string or empty>","description":"<one or two sentences>"}}
{url_rules}
6) source_type examples: company_press_release, business_news, regulatory_filing, industry_report, company_site.
7) Use ASCII-only in JSON strings where possible.
8) Ground every description in actual content from the cited source — do not invent facts about a company or topic the source does not support."""


def build_user_prompt(request: VerifiedStepRequest) -> str:
    """Return the user prompt for one research step.

    When ``request.website`` is supplied, the prompt also asks the model to
    treat that domain as an authoritative first-party source — explicitly
    check it (via ``site:<domain>`` search when web_search is on, or recall
    from it when off) for topics the company's own pages plausibly cover
    (press releases, IR, partner directories, technical blog, etc.). The
    model still cross-references with external sources for breadth.
    """
    lines = [
        f"Verified Sources task: {request.title}",
        "",
        f"Company: {request.company_name}",
        f"Country: {request.country}",
        f"Industry: {request.industry}",
        f"Website: {request.website}",
        "",
        "Research focus:",
        request.focus,
        "",
        f'Set JSON field "category" exactly to: {request.category}',
        "",
        f"Return up to {request.max_results} results in the results array.",
    ]
    if request.website.strip():
        lines.extend(
            [
                "",
                f"First-party source: the company's own domain is {request.website}.",
                "When the topic is plausibly covered there (press releases, investor "
                "relations, partner directories, official statements, technical blog "
                "posts, careers pages, leadership pages), explicitly check that "
                "domain — for example, with a site:-restricted search — and include "
                "at least one results entry whose URL lives on that domain when one "
                "is available. Cross-reference with external sources for breadth.",
            ]
        )
    if request.activity is not None:
        lines.extend(
            [
                "",
                render_source_hierarchy(
                    request.activity, customer_website=request.website
                ),
            ]
        )
    return "\n".join(lines)
