"""Retry configuration model.

Captures the parameters callers can use to tune retry behavior on flaky
external dependencies (LLM APIs, secret stores, etc.). Library wrappers may
accept a :class:`RetryConfig` to centralize the choice rather than spreading
magic numbers across call sites.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Knobs for retry behavior.

    The Anthropic SDK has its own retry mechanism configured via
    ``max_retries`` on the client; ``RetryConfig`` is here for callers
    implementing their own retry loops, or for a future BERB-common helper
    that wraps non-SDK calls (e.g. ``httpx``-based fetches).

    Attributes:
        max_retries: Maximum retry attempts after the initial call. ``0`` means
            "do not retry".
        initial_backoff_seconds: First sleep duration before retry attempt 1.
        backoff_multiplier: Factor applied to the previous backoff for each
            subsequent attempt (exponential backoff).
        max_backoff_seconds: Cap on any single sleep duration.
        retryable_status_codes: HTTP status codes that should trigger a retry.
            ``5xx`` plus ``429`` (rate limit) by default.

    Example:
        >>> RetryConfig().max_retries
        2
        >>> RetryConfig(max_retries=5, initial_backoff_seconds=0.5).backoff_for(0)
        0.5
        >>> RetryConfig(max_retries=5, initial_backoff_seconds=0.5).backoff_for(2)
        2.0
    """

    max_retries: int = Field(default=2, ge=0)
    initial_backoff_seconds: float = Field(default=1.0, gt=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float = Field(default=60.0, gt=0)
    retryable_status_codes: frozenset[int] = Field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )

    def backoff_for(self, attempt: int) -> float:
        """Return the sleep duration before retry attempt ``attempt`` (0-indexed).

        Attempt 0 sleeps ``initial_backoff_seconds``; subsequent attempts
        multiply by ``backoff_multiplier``, capped at ``max_backoff_seconds``.
        """
        if attempt < 0:
            raise ValueError(f"attempt must be non-negative, got {attempt}")
        delay = self.initial_backoff_seconds * (self.backoff_multiplier**attempt)
        return min(delay, self.max_backoff_seconds)

    def should_retry(self, *, status_code: int, attempt: int) -> bool:
        """Return True if a call should be retried after a status-code response.

        Retries occur up to (but not exceeding) ``max_retries`` total attempts.
        """
        if attempt >= self.max_retries:
            return False
        return status_code in self.retryable_status_codes
