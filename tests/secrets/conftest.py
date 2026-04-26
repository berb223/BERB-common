"""Auto-reset secret caches between tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from berb_common.secrets import clear_op_cache, clear_secret_cache


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    clear_secret_cache()
    clear_op_cache()
    yield
    clear_secret_cache()
    clear_op_cache()


@pytest.fixture(autouse=True)
def _disable_disk_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not touch the user's real OS keystore. Disk cache off by default;
    individual tests opt back in via ``monkeypatch.setenv`` plus a mocked ``keyring``.
    """
    monkeypatch.setenv("BERB_OP_DISK_CACHE", "0")
