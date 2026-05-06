"""Pydantic models for the verified-sources research module.

Three public shapes:

- :class:`VerifiedSourceRow` — one cited source (URL + metadata).
- :class:`VerifiedStepRequest` — the input to one research step (topic +
  company context + framing + caps).
- :class:`VerifiedStepResult` — the output of one research step (kept rows,
  dropped rows, raw LLM response, success flag).

The runner (:mod:`berb_common.verified_sources.runner`) takes a request and
returns a result. Consumers convert between their own per-project step
catalogue and ``VerifiedStepRequest`` at the call site — the BERB-common
package itself has no opinion about which research topics matter for any
particular project.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from berb_common.models import LLMResponse
from berb_common.research_sources import Activity


class VerifiedSourceRow(BaseModel):
    """One cited source row.

    Shape mirrors the JSON object the LLM is instructed to emit (see
    :func:`berb_common.verified_sources.prompts.build_system_prompt`):
    ``{"url", "source_type", "deal_parties", "description"}``.

    Attributes:
        url: Reachable ``https://`` URL the LLM is confident about. Empty
            string only after parsing recovers a row from a malformed
            response — runners should treat empty-URL rows as invalid.
        source_type: Short label, e.g. ``"company_press_release"``,
            ``"regulatory_filing"``.
        deal_parties: Names of parties involved when the source documents a
            deal/M&A; empty otherwise.
        description: One- or two-sentence summary of why this source is
            relevant.
    """

    url: str = ""
    source_type: str = ""
    deal_parties: str = ""
    description: str = ""


class VerifiedStepRequest(BaseModel):
    """Input to one verified-sources research step.

    Attributes:
        title: Human-readable topic title (e.g. ``"Recent News, M&A, deals"``).
        focus: One- or two-sentence brief telling the LLM what to research.
        category: JSON ``"category"`` value the LLM must echo back. Used by
            consumers to round-trip rows back to their internal step catalogue.
        company_name: Company being researched.
        country: Country of operation.
        industry: Industry classification.
        website: Company website (helps the LLM disambiguate similarly-named
            companies).
        max_results: Maximum result rows the LLM may return for this step.
        framing: First line of the system prompt — the role the LLM plays.
            Defaults to a generic business-analyst framing; consumers can
            override (e.g. ``"You are a senior business analyst preparing
            Fortinet account plans."``).
    """

    title: str
    focus: str
    category: str
    company_name: str
    country: str = ""
    industry: str = ""
    website: str = ""
    max_results: int = Field(default=5, ge=1, le=50)
    framing: str = "You are a senior business analyst conducting account research."
    activity: Activity | None = Field(
        default=None,
        description=(
            "Optional research-activity tag. When set, the runner renders the "
            "matching tier list from berb_common.research_sources into the user "
            "prompt as a soft source preference."
        ),
    )


class VerifiedStepResult(BaseModel):
    """Output of one verified-sources research step.

    Attributes:
        rows: Kept rows. Each has a non-empty URL. When ``validate_links`` was
            on at the runner, every URL was reachable at the time of the call.
        dropped_rows: Rows the LLM emitted that were dropped because their URL
            failed the reachability probe. Empty when ``validate_links`` was off
            or every URL was reachable. Useful for diagnostics ("the LLM
            invented X URLs that we filtered out").
        success: ``True`` when the LLM call returned a usable response and
            parsing produced at least zero rows. ``False`` only when the LLM
            call itself failed.
        error_message: Human-readable failure message; empty on success.
        raw_response: Verbatim LLM output. Useful for diagnostics when the
            parser falls back or returns nothing.
        llm_response: The underlying :class:`LLMResponse` from the Anthropic
            client (token usage, duration, model, etc.).
    """

    rows: list[VerifiedSourceRow] = Field(default_factory=list)
    dropped_rows: list[VerifiedSourceRow] = Field(default_factory=list)
    success: bool = False
    error_message: str = ""
    raw_response: str = ""
    llm_response: LLMResponse = Field(
        # Pydantic-mypy plugin does not pick up the positional default on
        # ``LLMResponse.duration_seconds`` (declared as ``Field(0.0, ...)``);
        # same applies to ``web_search_requests``. Pass both explicitly.
        default_factory=lambda: LLMResponse(duration_seconds=0.0, web_search_requests=0),
    )
