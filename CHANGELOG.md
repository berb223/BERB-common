# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
