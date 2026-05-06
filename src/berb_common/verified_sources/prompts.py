"""Build system + user prompts for verified-sources research.

The system prompt enforces strict JSON-only output and the "real https URLs
only — never invent" rule that gives this module its name. The user prompt
relays the topic + company context. Both prompts are derived from the
:class:`VerifiedStepRequest` so consumers don't have to plumb individual
fields through.
"""

from __future__ import annotations

from berb_common.verified_sources.models import VerifiedStepRequest


def build_system_prompt(request: VerifiedStepRequest) -> str:
    """Return the system prompt for one research step.

    The first line is the consumer-supplied ``framing`` (role); the rest is
    the strict JSON output contract. ``request.max_results`` is interpolated
    into the contract so the model knows the per-step cap.
    """
    return f"""{request.framing}

OUTPUT RULES (STRICT):
1) Return ONLY one JSON object. No markdown, no ``` fences, no headings, no commentary before or after JSON.
2) JSON shape (keys required):
   {{"category":"<category_key>","company":"<string>","industry":"<string>","country":"<string>","results":[...]}}
3) results is an array of up to {request.max_results} objects, each:
   {{"url":"https://...","source_type":"<short label>","deal_parties":"<string or empty>","description":"<one or two sentences>"}}
4) Every url MUST start with https:// and be a real, publicly reachable page you are confident about.
5) Do NOT invent URLs, paths, or domains. If you cannot cite a real https URL, omit that result object.
6) source_type examples: company_press_release, business_news, regulatory_filing, industry_report, company_site.
7) Use ASCII-only in JSON strings where possible."""


def build_user_prompt(request: VerifiedStepRequest) -> str:
    """Return the user prompt for one research step."""
    return "\n".join(
        [
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
    )
