"""structlog configuration with dev/prod renderer split.

Per ``CONVENTIONS.md`` "Logging":

- ``debug=True`` (development): ``ConsoleRenderer`` — human-readable, colored.
- Otherwise (production, CI, container): ``JSONRenderer`` — one JSON object per line.

Configures structlog at process startup. Call once before logging begins.
"""

from __future__ import annotations

from typing import Any

import structlog


def configure_logging(*, debug: bool = False, service_name: str | None = None) -> None:
    """Configure structlog for this process.

    Args:
        debug: Use ``ConsoleRenderer`` with colors when True; ``JSONRenderer`` otherwise.
        service_name: If set, every subsequent log entry includes ``service=<name>``
            as a top-level field, bound via :mod:`structlog.contextvars`.

    The function is idempotent — re-calling it replaces the prior configuration
    and re-binds ``service_name`` (or clears it if ``None``). Call once at
    process startup.

    Example:
        >>> from berb_common.logging import configure_logging, get_logger
        >>> configure_logging(debug=True, service_name="my-service")
        >>> log = get_logger(__name__)
        >>> log.info("started", account="Acme")  # doctest: +SKIP
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if debug:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(processors=processors)

    structlog.contextvars.clear_contextvars()
    if service_name:
        structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger.

    Pass ``__name__`` for module-scoped logging. After :func:`configure_logging`
    has run, log entries include the configured renderer's output (Console or
    JSON) plus any context variables bound via ``structlog.contextvars``.

    Returns:
        A structlog ``BoundLogger`` with ``.debug``, ``.info``, ``.warning``,
        ``.error``, ``.exception``, ``.critical``.

    Example:
        >>> log = get_logger(__name__)
        >>> log.info("event", key="value")  # doctest: +SKIP
    """
    return structlog.get_logger(name)
