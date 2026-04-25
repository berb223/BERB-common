# berb-common

[![CI](https://github.com/berb223/BERB-common/workflows/CI/badge.svg)](https://github.com/berb223/BERB-common/actions)

> Shared Python runtime library: secrets, logging, prompts, Anthropic client, common models. Personal IP.

## What it does

`berb-common` consolidates infrastructure used across Beat's Python projects:

- **`secrets`** — 1Password CLI wrapper
- **`logging`** — structlog configuration with dev/prod renderer split
- **`prompts`** — YAML prompt loader with Jinja2 rendering
- **`anthropic`** — Anthropic SDK client wrapper with retry, timeout, cost logging
- **`models`** — common pydantic models like `LLMResponse`

It is the shared runtime layer (Tier 2) of the FTNT/BERB four-tier portfolio. See [ADR-001](https://github.com/berb223/FTNT-bdm-portfolio/blob/main/docs/adr/001-four-tier-architecture.md) for context.

## Why it exists

Without a shared library, every project re-implements 1Password lookups, structlog setup, prompt loading, and Anthropic client construction. The Phase 0 audit of `FTNT-sales-workbench` found two independent implementations of 1Password and Anthropic in a single repo. Centralizing means: one tested implementation, semver-controlled API changes, and the ability to reuse this library in any non-Fortinet Python project (per [ADR-008](https://github.com/berb223/FTNT-bdm-portfolio/blob/main/docs/adr/008-berb-common-ip-isolation.md)).

## Install

Once published (Phase 2.7), add a `[[tool.uv.index]]` block in your `pyproject.toml` pointing at GitHub Packages, authenticate via `gh auth token`, then:

```bash
uv add "berb-common>=0.1.0,<0.2.0"
```

## Configuration

`berb-common` is dependency-free of any specific runtime config. Each module documents its own inputs.

## Run

`berb-common` is a library, not an application. Import from your project:

```python
from berb_common.secrets import read_op_secret
from berb_common.logging import configure_logging, get_logger
from berb_common.prompts import PromptRegistry
from berb_common.anthropic import AnthropicClient
from berb_common.models import LLMResponse
```

## Test

```bash
uv sync
uv run pytest
```

Coverage threshold is 80% — CI fails below that.

## Deploy

Tagged releases (`v*`) trigger `.github/workflows/publish.yml`, which publishes to GitHub Packages.

## Architecture

See ADRs in [`FTNT-bdm-portfolio`](https://github.com/berb223/FTNT-bdm-portfolio/tree/main/docs/adr):

- ADR-001 — four-tier architecture (this is Tier 2)
- ADR-002 — FTNT/BERB IP boundary
- ADR-008 — `BERB-common` IP isolation rules

## License / Ownership

BERB — Personal IP. Private repo.
