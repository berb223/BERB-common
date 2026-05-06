"""Tests for berb_common.verified_sources.verifier."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from berb_common.verified_sources.models import VerifiedSourceRow
from berb_common.verified_sources.verifier import (
    filter_dead_rows,
    verify_url,
    verify_urls,
)


def _mock_httpx_client(
    mocker: MockerFixture,
    *,
    head_status: int | None = None,
    head_raises: Exception | None = None,
    get_status: int | None = None,
    get_raises: Exception | None = None,
) -> MagicMock:
    """Patch the verifier's httpx.Client with a context-manager mock.

    Set ``head_status`` / ``get_status`` to drive response codes; set the
    ``_raises`` variants to make a method raise an httpx exception.
    """
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=None)
    if head_raises is not None:
        client.head = MagicMock(side_effect=head_raises)
    elif head_status is not None:
        client.head = MagicMock(return_value=MagicMock(status_code=head_status))
    else:
        client.head = MagicMock(return_value=MagicMock(status_code=200))
    if get_raises is not None:
        client.get = MagicMock(side_effect=get_raises)
    elif get_status is not None:
        client.get = MagicMock(return_value=MagicMock(status_code=get_status))
    else:
        client.get = MagicMock(return_value=MagicMock(status_code=200))
    mocker.patch("berb_common.verified_sources.verifier.httpx.Client", return_value=client)
    return client


class TestVerifyUrl:
    def test_head_2xx_returns_true(self, mocker: MockerFixture) -> None:
        c = _mock_httpx_client(mocker, head_status=200)
        assert verify_url("https://example.com") is True
        c.head.assert_called_once()
        c.get.assert_not_called()

    def test_head_3xx_after_redirect_returns_true(self, mocker: MockerFixture) -> None:
        # follow_redirects=True means the SDK already followed; final 200 returned.
        _mock_httpx_client(mocker, head_status=200)
        assert verify_url("https://example.com") is True

    def test_head_4xx_falls_back_to_get(self, mocker: MockerFixture) -> None:
        c = _mock_httpx_client(mocker, head_status=405, get_status=200)
        assert verify_url("https://example.com") is True
        c.head.assert_called_once()
        c.get.assert_called_once()

    def test_head_raises_falls_back_to_get(self, mocker: MockerFixture) -> None:
        c = _mock_httpx_client(
            mocker,
            head_raises=httpx.ConnectError("boom"),
            get_status=200,
        )
        assert verify_url("https://example.com") is True
        c.get.assert_called_once()

    def test_both_fail_returns_false(self, mocker: MockerFixture) -> None:
        _mock_httpx_client(mocker, head_status=500, get_status=500)
        assert verify_url("https://example.com") is False

    def test_get_raises_returns_false(self, mocker: MockerFixture) -> None:
        _mock_httpx_client(
            mocker,
            head_raises=httpx.ConnectError("boom"),
            get_raises=httpx.ReadTimeout("timeout"),
        )
        assert verify_url("https://example.com") is False

    def test_unexpected_exception_returns_false(self, mocker: MockerFixture) -> None:
        # An unexpected (non-httpx) error in the client init or anywhere else
        # must be swallowed — verify_url never raises.
        mocker.patch(
            "berb_common.verified_sources.verifier.httpx.Client",
            side_effect=RuntimeError("unexpected"),
        )
        assert verify_url("https://example.com") is False

    @pytest.mark.parametrize("bad", ["", "   ", "http://insecure.example", "ftp://x"])
    def test_non_https_returns_false_without_network(self, mocker: MockerFixture, bad: str) -> None:
        client_class = mocker.patch("berb_common.verified_sources.verifier.httpx.Client")
        assert verify_url(bad) is False
        client_class.assert_not_called()


class TestVerifyUrls:
    def test_empty_iterable_returns_empty_dict(self, mocker: MockerFixture) -> None:
        client_class = mocker.patch("berb_common.verified_sources.verifier.httpx.Client")
        assert verify_urls([]) == {}
        client_class.assert_not_called()

    def test_dedupes_input(self, mocker: MockerFixture) -> None:
        # Same URL twice should be probed once (the result map has one key).
        _mock_httpx_client(mocker, head_status=200)
        out = verify_urls(["https://a.example", "https://a.example"])
        assert out == {"https://a.example": True}

    def test_mixed_results(self, mocker: MockerFixture) -> None:
        # Drive different responses by URL via a side_effect on head.
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=None)

        def head_for(url: str, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(status_code=200 if "good" in url else 500)

        client.head = MagicMock(side_effect=head_for)
        client.get = MagicMock(return_value=MagicMock(status_code=500))
        mocker.patch("berb_common.verified_sources.verifier.httpx.Client", return_value=client)

        out = verify_urls(["https://good.example", "https://bad.example"])
        assert out == {"https://good.example": True, "https://bad.example": False}


class TestFilterDeadRows:
    def test_empty_input(self) -> None:
        kept, dropped = filter_dead_rows([])
        assert kept == []
        assert dropped == []

    def test_splits_kept_and_dropped(self, mocker: MockerFixture) -> None:
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=None)

        def head_for(url: str, *args: Any, **kwargs: Any) -> MagicMock:
            return MagicMock(status_code=200 if "good" in url else 404)

        client.head = MagicMock(side_effect=head_for)
        client.get = MagicMock(return_value=MagicMock(status_code=404))
        mocker.patch("berb_common.verified_sources.verifier.httpx.Client", return_value=client)

        rows = [
            VerifiedSourceRow(url="https://good.example/1", description="A"),
            VerifiedSourceRow(url="https://bad.example/2", description="B"),
            VerifiedSourceRow(url="https://good.example/3", description="C"),
        ]
        kept, dropped = filter_dead_rows(rows)
        assert [r.url for r in kept] == ["https://good.example/1", "https://good.example/3"]
        assert [r.url for r in dropped] == ["https://bad.example/2"]

    def test_empty_url_rows_go_to_dropped(self, mocker: MockerFixture) -> None:
        # Empty / non-https URL rows are dropped without a network call.
        client_class = mocker.patch("berb_common.verified_sources.verifier.httpx.Client")
        rows = [VerifiedSourceRow(url=""), VerifiedSourceRow(url="http://insecure.example")]
        kept, dropped = filter_dead_rows(rows)
        assert kept == []
        assert len(dropped) == 2
        client_class.assert_not_called()
