"""Smoke tests: berb-common imports and exposes its version."""

from __future__ import annotations

import berb_common


def test_version_is_set() -> None:
    assert isinstance(berb_common.__version__, str)
    assert berb_common.__version__ == "0.1.2"


def test_package_exports_version_only() -> None:
    assert berb_common.__all__ == ["__version__"]
