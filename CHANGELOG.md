# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
