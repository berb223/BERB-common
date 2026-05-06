"""Run one verified-sources research step end-to-end.

The runner wires together the four pieces of the package:

    request → prompts → AnthropicClient (optional web_search) → parser → verifier → result

Two layers of URL grounding, both on by default:

1. ``web_search=True`` — the LLM gets Anthropic's ``web_search`` server tool
   and the prompt tells it to cite only URLs that appeared in tool results.
   This eliminates URL fabrication at source — the LLM no longer recalls
   URLs from training data, it cites pages it actually saw.
2. ``validate_links=True`` — every URL the parser returns is HEAD/GET-probed
   and unreachable rows are moved to ``dropped_rows``. Defence-in-depth: a
   page might 404 between when the model searched it and when the AP run
   completes; this catches that.

Both layers compose. Disable individually for tests / cost control / offline
runs.
"""

from __future__ import annotations

from berb_common.anthropic import AnthropicClient, web_search_tool
from berb_common.logging import get_logger
from berb_common.verified_sources.models import (
    VerifiedSourceRow,
    VerifiedStepRequest,
    VerifiedStepResult,
)
from berb_common.verified_sources.parser import parse_verified_sources_json
from berb_common.verified_sources.prompts import build_system_prompt, build_user_prompt
from berb_common.verified_sources.verifier import filter_dead_rows

_log = get_logger(__name__)


def run_verified_step(
    request: VerifiedStepRequest,
    *,
    client: AnthropicClient,
    validate_links: bool = True,
    link_timeout: float = 12.0,
    link_max_workers: int = 10,
    user_prompt_prefix: str = "",
    max_tokens: int = 4096,
    temperature: float = 1.0,
    append_deal_parties: bool = True,
    web_search: bool = True,
    web_search_max_uses: int = 5,
    web_search_allowed_domains: list[str] | None = None,
    web_search_blocked_domains: list[str] | None = None,
) -> VerifiedStepResult:
    """Run one research step and return kept rows + diagnostics.

    Args:
        request: Topic + company context + per-step caps + role framing.
        client: Configured Anthropic client (caller controls model + auth).
        validate_links: When ``True`` (default), every parsed URL is
            HEAD/GET-probed and unreachable rows are moved to
            ``dropped_rows``. Set ``False`` to skip the probes.
        link_timeout: Per-URL probe timeout in seconds.
        link_max_workers: Thread-pool size for the parallel probe phase.
        user_prompt_prefix: Optional prose to prepend to the user prompt
            (separated by a blank line). Lets consumers inject account-context
            preambles or other shared framing without rebuilding the prompt.
        max_tokens: Cap on LLM output tokens.
        temperature: LLM sampling temperature.
        append_deal_parties: Forwarded to the parser — see
            :func:`berb_common.verified_sources.parser.parse_verified_sources_json`.
        web_search: When ``True`` (default), the request is sent with the
            ``web_search`` server tool enabled and the prompt instructs the
            model to cite only URLs from tool results. Set ``False`` to fall
            back to memory-only behaviour (cheaper, but URLs are guessed).
        web_search_max_uses: Cap on how many ``web_search`` calls the model
            may make per turn. Doubles as a cost cap.
        web_search_allowed_domains: Optional whitelist passed to the tool.
        web_search_blocked_domains: Optional blacklist passed to the tool.

    Returns:
        A :class:`VerifiedStepResult` with ``rows`` (kept), ``dropped_rows``
        (unreachable when ``validate_links`` was on), ``success``,
        ``error_message``, ``raw_response``, and ``llm_response``. The
        :attr:`LLMResponse.web_search_requests` count surfaces how many
        searches the model performed (``0`` when ``web_search=False``).
    """
    system_prompt = build_system_prompt(request, web_search=web_search)
    base_user_prompt = build_user_prompt(request)
    user_prompt = (
        f"{user_prompt_prefix}\n\n{base_user_prompt}"
        if user_prompt_prefix.strip()
        else base_user_prompt
    )

    tools = (
        [
            web_search_tool(
                max_uses=web_search_max_uses,
                allowed_domains=web_search_allowed_domains,
                blocked_domains=web_search_blocked_domains,
            )
        ]
        if web_search
        else None
    )

    llm_response = client.call(
        user=user_prompt,
        system=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools,
    )

    if not llm_response.success:
        return VerifiedStepResult(
            rows=[],
            dropped_rows=[],
            success=False,
            error_message=llm_response.error_message or "LLM call failed",
            raw_response=llm_response.content,
            llm_response=llm_response,
        )

    parsed: list[VerifiedSourceRow] = parse_verified_sources_json(
        llm_response.content,
        max_rows=request.max_results,
        append_deal_parties=append_deal_parties,
    )

    if not validate_links:
        return VerifiedStepResult(
            rows=parsed,
            dropped_rows=[],
            success=True,
            error_message="",
            raw_response=llm_response.content,
            llm_response=llm_response,
        )

    kept, dropped = filter_dead_rows(
        parsed,
        timeout=link_timeout,
        max_workers=link_max_workers,
    )
    if dropped:
        _log.info(
            "verified_sources_dropped_unreachable",
            category=request.category,
            company=request.company_name,
            kept=len(kept),
            dropped=len(dropped),
        )
    return VerifiedStepResult(
        rows=kept,
        dropped_rows=dropped,
        success=True,
        error_message="",
        raw_response=llm_response.content,
        llm_response=llm_response,
    )
