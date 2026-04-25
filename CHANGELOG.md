# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
