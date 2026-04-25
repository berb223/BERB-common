"""Tests for berb_common.logging.config."""

from __future__ import annotations

import json
import re

import pytest

from berb_common.logging import configure_logging, get_logger


def _last_json_line(captured: str) -> dict[str, object]:
    """Parse the last non-empty line of captured stdout as JSON."""
    line = captured.strip().splitlines()[-1]
    record = json.loads(line)
    assert isinstance(record, dict)
    return record


class TestConfigureLogging:
    def test_json_renderer_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False)
        log = get_logger("t")
        log.info("hello", key="value")
        record = _last_json_line(capsys.readouterr().out)
        assert record["event"] == "hello"
        assert record["key"] == "value"
        assert record["level"] == "info"
        assert "timestamp" in record

    def test_console_renderer_when_debug(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=True)
        log = get_logger("t")
        log.info("hello-msg")
        out = capsys.readouterr().out
        assert "hello-msg" in out
        # Console output is not parseable as JSON.
        with pytest.raises(json.JSONDecodeError):
            json.loads(out.strip().splitlines()[-1])

    def test_service_name_bound(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False, service_name="sales-workbench")
        log = get_logger("t")
        log.info("event")
        record = _last_json_line(capsys.readouterr().out)
        assert record["service"] == "sales-workbench"

    def test_no_service_name_when_unset(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False)
        log = get_logger("t")
        log.info("event")
        record = _last_json_line(capsys.readouterr().out)
        assert "service" not in record

    def test_idempotent_second_service_name_wins(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False, service_name="first")
        configure_logging(debug=False, service_name="second")
        log = get_logger("t")
        log.info("event")
        record = _last_json_line(capsys.readouterr().out)
        assert record["service"] == "second"

    def test_reconfigure_clears_service_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False, service_name="first")
        configure_logging(debug=False)  # service_name=None clears the binding
        log = get_logger("t")
        log.info("event")
        record = _last_json_line(capsys.readouterr().out)
        assert "service" not in record

    def test_levels_serialized(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False)
        log = get_logger("t")
        log.warning("warn-event")
        log.error("error-event")
        lines = capsys.readouterr().out.strip().splitlines()
        records = [json.loads(line) for line in lines]
        assert records[0]["level"] == "warning"
        assert records[1]["level"] == "error"

    def test_iso_timestamp_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False)
        log = get_logger("t")
        log.info("event")
        record = _last_json_line(capsys.readouterr().out)
        ts = record["timestamp"]
        assert isinstance(ts, str)
        # ISO-8601 prefix YYYY-MM-DDT
        assert re.match(r"^\d{4}-\d{2}-\d{2}T", ts)


class TestGetLogger:
    def test_returns_logger_with_standard_methods(self) -> None:
        configure_logging(debug=False)
        log = get_logger("test")
        assert hasattr(log, "debug")
        assert hasattr(log, "info")
        assert hasattr(log, "warning")
        assert hasattr(log, "error")
        assert hasattr(log, "exception")

    def test_works_without_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(debug=False)
        log = get_logger()
        log.info("nameless-event")
        record = _last_json_line(capsys.readouterr().out)
        assert record["event"] == "nameless-event"
