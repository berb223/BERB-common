"""Verified-sources research module — LLM-driven web research with URL validation.

Given a topic + company context, this module:

1. Builds a strict-JSON prompt for the Anthropic API.
2. Calls the model via :class:`berb_common.anthropic.AnthropicClient`.
3. Parses the JSON (with a pipe-style fallback for mis-formatted responses).
4. Probes each cited URL via HTTP HEAD/GET.
5. Returns kept rows (reachable) and dropped rows (unreachable).

Public API:

>>> from berb_common.anthropic import AnthropicClient
>>> from berb_common.verified_sources import (
...     VerifiedSourceRow,
...     VerifiedStepRequest,
...     VerifiedStepResult,
...     run_verified_step,
... )
>>> client = AnthropicClient(api_key="sk-ant-...", model="claude-sonnet-4-6")  # doctest: +SKIP
>>> request = VerifiedStepRequest(                                              # doctest: +SKIP
...     title="Recent News, M&A, deals",
...     focus="Recent news, mergers, acquisitions, divestitures.",
...     category="news_trends_ma",
...     company_name="Acme Corp",
...     country="Switzerland",
...     industry="Manufacturing",
...     website="https://acme.example",
...     max_results=5,
... )
>>> result = run_verified_step(request, client=client)                          # doctest: +SKIP
>>> for row in result.rows:                                                     # doctest: +SKIP
...     print(row.url, row.source_type, row.description)

For advanced consumers that want to wire the pieces together themselves:

>>> from berb_common.verified_sources import (
...     build_system_prompt,
...     build_user_prompt,
...     parse_verified_sources_json,
...     verify_url,
...     verify_urls,
...     filter_dead_rows,
... )
"""

from berb_common.verified_sources.models import (
    VerifiedSourceRow,
    VerifiedStepRequest,
    VerifiedStepResult,
)
from berb_common.verified_sources.parser import (
    parse_pipe_fallback,
    parse_verified_sources_json,
)
from berb_common.verified_sources.prompts import build_system_prompt, build_user_prompt
from berb_common.verified_sources.runner import run_verified_step
from berb_common.verified_sources.verifier import (
    filter_dead_rows,
    verify_url,
    verify_urls,
)

__all__ = [
    "VerifiedSourceRow",
    "VerifiedStepRequest",
    "VerifiedStepResult",
    "build_system_prompt",
    "build_user_prompt",
    "filter_dead_rows",
    "parse_pipe_fallback",
    "parse_verified_sources_json",
    "run_verified_step",
    "verify_url",
    "verify_urls",
]
