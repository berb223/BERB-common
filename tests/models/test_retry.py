"""Tests for berb_common.models.retry."""

from __future__ import annotations

import pytest

from berb_common.models import RetryConfig


class TestDefaults:
    def test_default_values(self) -> None:
        c = RetryConfig()
        assert c.max_retries == 2
        assert c.initial_backoff_seconds == 1.0
        assert c.backoff_multiplier == 2.0
        assert c.max_backoff_seconds == 60.0
        assert 429 in c.retryable_status_codes
        assert 500 in c.retryable_status_codes
        assert 504 in c.retryable_status_codes

    def test_validation_rejects_negative_max_retries(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(max_retries=-1)

    def test_validation_rejects_zero_initial_backoff(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(initial_backoff_seconds=0.0)

    def test_validation_rejects_multiplier_below_one(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(backoff_multiplier=0.5)


class TestBackoffFor:
    def test_attempt_zero_is_initial(self) -> None:
        c = RetryConfig(initial_backoff_seconds=0.5, backoff_multiplier=2.0)
        assert c.backoff_for(0) == 0.5

    def test_exponential_growth(self) -> None:
        c = RetryConfig(initial_backoff_seconds=1.0, backoff_multiplier=2.0)
        assert c.backoff_for(1) == 2.0
        assert c.backoff_for(2) == 4.0
        assert c.backoff_for(3) == 8.0

    def test_capped_at_max(self) -> None:
        c = RetryConfig(
            initial_backoff_seconds=1.0,
            backoff_multiplier=10.0,
            max_backoff_seconds=5.0,
        )
        assert c.backoff_for(0) == 1.0
        assert c.backoff_for(1) == 5.0  # would be 10, capped
        assert c.backoff_for(5) == 5.0

    def test_negative_attempt_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            RetryConfig().backoff_for(-1)


class TestShouldRetry:
    def test_retries_on_known_codes(self) -> None:
        c = RetryConfig(max_retries=3)
        assert c.should_retry(status_code=500, attempt=0) is True
        assert c.should_retry(status_code=429, attempt=1) is True
        assert c.should_retry(status_code=503, attempt=2) is True

    def test_does_not_retry_4xx_other_than_429(self) -> None:
        c = RetryConfig(max_retries=3)
        assert c.should_retry(status_code=400, attempt=0) is False
        assert c.should_retry(status_code=401, attempt=0) is False
        assert c.should_retry(status_code=404, attempt=0) is False

    def test_does_not_retry_2xx(self) -> None:
        c = RetryConfig(max_retries=3)
        assert c.should_retry(status_code=200, attempt=0) is False

    def test_stops_at_max_retries(self) -> None:
        c = RetryConfig(max_retries=2)
        assert c.should_retry(status_code=500, attempt=1) is True
        assert c.should_retry(status_code=500, attempt=2) is False  # at max
        assert c.should_retry(status_code=500, attempt=3) is False

    def test_max_retries_zero_means_no_retry(self) -> None:
        c = RetryConfig(max_retries=0)
        assert c.should_retry(status_code=500, attempt=0) is False

    def test_custom_retryable_codes(self) -> None:
        c = RetryConfig(
            max_retries=3,
            retryable_status_codes=frozenset({418}),
        )
        assert c.should_retry(status_code=418, attempt=0) is True
        assert c.should_retry(status_code=500, attempt=0) is False
