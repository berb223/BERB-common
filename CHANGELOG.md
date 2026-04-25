# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial repo skeleton: `pyproject.toml` (uv, ruff strict, mypy strict, pytest with ≥80% coverage gate), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `README.md`, `.gitattributes`.
- Public top-level package `src/berb_common/` with `__version__`.
- Smoke test verifying the package imports cleanly.
