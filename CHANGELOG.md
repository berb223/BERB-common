# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-05-06

### Added

- **`berb_common.research_sources` — authoritative-source catalog with per-activity tier lists.** Twelve `Activity` enum values (`COMPANY_FACTS`, `FINANCIAL_INFO`, `VISION_MISSION`, `PEOPLE`, `NEWS_MA_DEALS`, `STRATEGY_DIGITAL`, `TECHNOLOGY_IT`, `CYBERSECURITY`, `PARTNERS_ECOSYSTEM`, `COMPETITORS`, `REGULATORY_COMPLIANCE`, `INDUSTRY_MARKET`), each mapped via `ACTIVITY_SOURCES: dict[Activity, TierList]` to a three-tier preference list (Tier 1 = always check first / first-party; Tier 2 = specialist authority; Tier 3 = aggregator/press fallback). Customer-specific sources use a `{customer_website}` placeholder substituted at render time. New helper `render_source_hierarchy(activity, *, customer_website="")` returns a multi-line prompt fragment with a soft-preference clause — model gets a hint, not a fence (no `allowed_domains` lock-down so the model can still find unexpected legitimate sources).
- **`VerifiedStepRequest.activity: Activity | None`** — when set, the runner appends the rendered tier list to the user prompt (after the first-party-source paragraph). Lets each Verified Sources step bind to a specific activity (e.g., IND_S5 → `Activity.NEWS_MA_DEALS`) so the LLM gets the right authoritative-source ordering.
- LinkedIn is in `Activity.PEOPLE` Tier 2; Yahoo Finance is in `Activity.FINANCIAL_INFO` Tier 3; Fortinet's threat-landscape report and FortiGuard Labs are in `Activity.CYBERSECURITY` Tier 2.

### Changed

- `build_user_prompt` now appends `render_source_hierarchy(...)` when `request.activity is not None`. No-op when activity is unset, so existing callers (BERB-common 0.3.x) keep their current prompt shape.

## [0.3.1] — 2026-05-06

### Changed

- **`build_user_prompt` now adds a "first-party source" instruction when `request.website` is non-empty.** The prompt tells the model to treat the company's own domain as authoritative and explicitly check it (via a `site:<domain>` search when web_search is on, or recall from it when off) for topics plausibly covered there — press releases, IR, partner directories, technical blog, careers, leadership pages. Cross-reference with external sources stays encouraged. No-op when `website` is blank, so consumers passing only a topic + framing don't get extra noise.

## [0.3.0] — 2026-05-06

### Added

- **`AnthropicClient.call` accepts `tools=` for server-side tool use.** Forwarded directly to `messages.create()`. Server tools (e.g. `web_search`) are executed by Anthropic's infrastructure within the same request — the returned `LLMResponse` is the model's final answer after any tool turns.
- **`berb_common.anthropic.web_search_tool(...)`** — canonical builder for Anthropic's `web_search_20250305` server tool. Args: `max_uses` (cost cap, default 5), `allowed_domains` / `blocked_domains` (mutually exclusive), `user_location` (optional approximate geo). Validates the allowed/blocked exclusivity and copies the location dict so caller mutations don't leak.
- **`LLMResponse.web_search_requests`** — count of `web_search` server-tool calls the model made during the turn (parsed from `message.usage.server_tool_use.web_search_requests`). Useful for billing diagnostics — Anthropic charges $10 per 1,000 searches on top of token cost.
- **`berb_common.verified_sources.run_verified_step` defaults `web_search=True`.** When on, the runner builds a `web_search_tool()` and the system prompt instructs the model to cite ONLY URLs that appeared in tool results. This eliminates URL fabrication at source — the model no longer recalls URLs from training data, it cites pages it actually saw. Pass `web_search=False` to keep the pre-0.3.0 memory-only behaviour (cheaper, but URLs are guessed). Additional knobs: `web_search_max_uses=5`, `web_search_allowed_domains`, `web_search_blocked_domains`.
- **`build_system_prompt(request, *, web_search=False)`** — the prompt now branches on the flag. Memory-only path keeps the "Do NOT invent URLs" guardrail. Tool-use path tells the model to cite only URLs from tool-result blocks. Both paths add a new rule 8: "Ground every description in actual content from the cited source — do not invent facts about a company or topic the source does not support."

### Changed

- `berb_common.verified_sources` URL provenance is now two layers, both on by default: (1) **discovery** via `web_search` so the LLM only emits URLs it actually saw, and (2) **post-hoc validation** via `verify_urls` so the renderer never gets a 404. Disable individually for tests / offline runs / cost control.

## [0.2.1] — 2026-05-06

### Changed

- **`parse_pipe_fallback` now defaults `max_rows=10`** — symmetric with `parse_verified_sources_json`, removes the need for consumers to pass the keyword (FTNT-sales-workbench's parsing-package shim wraps it just to add the default; this change retires that wrapper). No behaviour change for callers who pass `max_rows` explicitly.

## [0.2.0] — 2026-05-06

### Added

- **`berb_common.verified_sources` package** — portfolio-wide LLM-driven web research with URL validation. Public API:
  - `VerifiedSourceRow` / `VerifiedStepRequest` / `VerifiedStepResult` (Pydantic models).
  - `parse_verified_sources_json` + `parse_pipe_fallback` (parser, with a recovery path for prose-wrapped or malformed responses).
  - `build_system_prompt` + `build_user_prompt` (strict JSON-only contract; framing parameterised so consumers supply their own role line).
  - `verify_url` / `verify_urls` / `filter_dead_rows` (HTTPS reachability via HEAD-then-GET probes; parallel via `ThreadPoolExecutor`).
  - `run_verified_step` (end-to-end pipeline: prompt → AnthropicClient → parse → validate links → return kept rows + dropped rows).
- Lifted from FTNT-sales-workbench's `account_planning/verified_sources/` (link-verifier, parser, prompts) and `parsing/verified_sources.py`. The Fortinet-specific 8-step research catalogue and Excel writers stay in the consumer.
- `validate_links` defaults to **True** in `run_verified_step` — the named "Verified" promise of the package. Pass `validate_links=False` to skip the network probes.

### Dependencies

- Added `httpx>=0.27` (already used internally by the Anthropic SDK wrapper; promoted to a first-class dependency for the URL verifier).

## [0.1.5] — 2026-05-06

### Changed

- **`berb_common` is now declared as a fully-typed package per [PEP 561](https://peps.python.org/pep-0561/).** The `py.typed` marker file ships in the wheel (it has shipped silently since the v0.1.3 wheel build, but was never announced); v0.1.5 makes the support explicit so downstream projects can pin against it deliberately. Net effect for consumers: `mypy --strict` recognizes types from `berb_common.*` imports without `# type: ignore[import-untyped]` workarounds. No public-API or runtime-behavior changes; safe upgrade from v0.1.3 / v0.1.4.

## [0.1.4] — 2026-05-05

### Changed

- **Publish workflow now uses the reusable workflow from `BERB-workflows`** (`berb223/BERB-workflows/.github/workflows/python-publish.yml@v1`). The previous inline `publish.yml` triggered on `release: published` and required the user to draft the GitHub Release in the UI first; the reusable workflow triggers on `push: tags: ["v*"]` and auto-creates the Release with notes generated from commit history. Adds a `verify-version-matches-tag` guard (on by default) that fails the build if `v<X>.<Y>.<Z>` doesn't match `project.version` in `pyproject.toml`. Wheel + sdist still attached as Release assets; no PyPI upload (per portfolio secrets policy: 1Password is the only secret manager). This release validates the new workflow end-to-end.

## [0.1.3] — 2026-04-26

### Added

- `read_op_secret` now caches resolved secrets through two transparent layers:
  1. **Process cache** (always on) — per-process `dict[ref, value]`. Wiped at process exit and by `clear_op_cache()`. Eliminates repeated `op read` subprocess overhead in long-running services.
  2. **OS keystore disk cache** (default on; opt out with `BERB_OP_DISK_CACHE=0`) — uses the `keyring` library, which delegates to **Credential Manager (DPAPI) on Windows**, **Keychain on macOS**, and **Secret Service on Linux**. TTL defaults to 24 hours; override with `BERB_OP_DISK_CACHE_TTL_SEC`. Cleared per reference via `clear_op_disk_cache(ref)`. Silently no-op when `keyring` is unavailable.
- New exports: `clear_op_cache`, `clear_op_disk_cache`.

### Dependencies

- Added `keyring>=24.0`.

## [0.1.2] — 2026-04-26

### Fixed

- `read_op_secret` now finds the 1Password CLI (`op`) at well-known install locations when it is missing from `PATH`. Previously, processes spawned with a stripped `PATH` (background services, IDE-spawned subprocesses, automation tools) would always raise `OpReadError("not found in PATH")` even when `op` was installed. Locations probed (Windows): `%PROGRAMFILES%\1Password CLI\op.exe`, `%LOCALAPPDATA%\Microsoft\WinGet\Packages\AgileBits.1Password.CLI_*\op.exe`. POSIX: `/usr/local/bin/op`, `/opt/homebrew/bin/op`, `/usr/bin/op`.

## [0.1.1] — 2026-04-26

### Added

- `src/berb_common/py.typed` — PEP 561 marker so consumers' mypy treats `berb_common` as typed. Retires the `follow_imports = "skip"` workaround in `FTNT-sales-workbench` and `FTNT-bdm-operations` (project-local ADR-002 in both repos).

## [0.1.0] — 2026-04-25

First tagged release. Phase 2 of the FTNT/BERB portfolio standardization plan.

### Added

- Initial repo skeleton: `pyproject.toml` (uv, ruff strict, mypy strict, pytest with ≥80% coverage gate), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `README.md`, `.gitattributes`.
- Public top-level package `src/berb_common/` with `__version__`.
- Smoke test verifying the package imports cleanly.
- `berb_common.secrets` module:
  - `read_op_secret(reference, *, timeout_sec=45.0)` — strict 1Password CLI wrapper raising `OpReadError` on any failure.
  - `try_read_op_secret(reference)` — convenience variant returning `None` for missing references.
  - `resolve_secret(*, ref_env, value_env, explicit, cache_key)` — generic precedence resolver (explicit → cache → `op://` via env → plaintext env fallback) with optional in-process caching.
  - `clear_secret_cache()` — clears the in-process cache (tests, sign-out).
- `berb_common.logging` module:
  - `configure_logging(*, debug=False, service_name=None)` — sets up structlog with `ConsoleRenderer` (debug) or `JSONRenderer` (prod), ISO-8601 timestamps, log-level processor, and optional `service` field bound via `structlog.contextvars`.
  - `get_logger(name=None)` — returns a structlog `BoundLogger` for module-scoped logging.
- `berb_common.prompts` module:
  - `PromptRegistry(prompts_dir, *, strict_undefined=False)` — generic YAML + Jinja2 prompt loader. Reads `<dir>/system.yaml` (`system_prompt` key) and `<dir>/<slug>.yaml` (`template` key). Per-instance caching with `clear_cache()`. No project-specific defaults or fields (per ADR-008).
  - Methods: `get_system()`, `render_user(slug, **variables)`, `bundle(slug, **variables)`, `clear_cache()`, `prompts_dir` property.
- `berb_common.models` module:
  - `LLMResponse` — pydantic v2 model: `success`, `status_code`, `content`, `error_message`, `input_tokens`, `output_tokens`, `stop_reason`, `model`, `duration_seconds`, plus `total_tokens` property.
  - `RetryConfig` — pydantic v2 model with `max_retries`, `initial_backoff_seconds`, `backoff_multiplier`, `max_backoff_seconds`, `retryable_status_codes`. Helper methods `backoff_for(attempt)` and `should_retry(status_code, attempt)`.
  - Model ID constants: `MODEL_OPUS = "claude-opus-4-7"`, `MODEL_SONNET = "claude-sonnet-4-6"`, `MODEL_HAIKU = "claude-haiku-4-5-20251001"`, `DEFAULT_MODEL = MODEL_SONNET`.
- `berb_common.anthropic` module:
  - `AnthropicClient(*, api_key, model, timeout=60.0, max_retries=2, ssl_verify=True)` — Anthropic Messages API wrapper. Returns `LLMResponse`; never raises on API errors (status, connection failures captured into `success=False`). Uses the SDK's built-in retry mechanism for transient errors.
  - Methods: `call(*, user, system="", max_tokens=4096, temperature=1.0)`, `verify()`, `model` property.
- `.github/workflows/publish.yml` — on `release: published`, builds wheel + sdist with `uv build` and uploads them as release artifacts.
