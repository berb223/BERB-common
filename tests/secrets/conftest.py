"""Auto-reset secret cache between tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from berb_common.secrets import clear_secret_cache


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    clear_secret_cache()
    yield
    clear_secret_cache()
