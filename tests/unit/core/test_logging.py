"""Tests for core.logging module — formatters, timer, setup."""

import importlib
import json
import logging
import tempfile
from pathlib import Path

from credit_risk_server.core.logging import (
    CorrelationFilter,
    DevFormatter,
    JSONFormatter,
    Timer,
    correlation_id,
)


class TestCorrelationFilter:
    def test_injects_correlation_id(self):
        filt = CorrelationFilter()
        correlation_id.set("test-123")
        record = logging.LogRecord("test", 0, "", 0, "msg", (), None)
        filt.filter(record)
        assert record.correlation_id == "test-123"

    def test_empty_correlation_id_injected(self):
        filt = CorrelationFilter()
        correlation_id.set("")
        record = logging.LogRecord("test", 0, "", 0, "msg", (), None)
        filt.filter(record)
        assert record.correlation_id == ""


def _make_record(**kwargs):
    """Create a LogRecord and inject correlation_id via CorrelationFilter."""
    from credit_risk_server.core.logging import CorrelationFilter

    record = logging.LogRecord("test.logger", logging.INFO, "", 0, "hello", (), None)
    for k, v in kwargs.items():
        setattr(record, k, v)
    filt = CorrelationFilter()
    filt.filter(record)
    return record


class TestDevFormatter:
    def test_format_with_extras(self):
        correlation_id.set("corr-1")
        fmt = DevFormatter(DevFormatter._DEV_FMT)
        record = _make_record(source_type="csv", data_path="data/")
        output = fmt.format(record)
        assert "source_type=csv" in output
        assert "data_path=data/" in output

    def test_format_without_extras(self):
        correlation_id.set("")
        fmt = DevFormatter(DevFormatter._DEV_FMT)
        record = _make_record()
        output = fmt.format(record)
        assert "hello" in output


class TestJSONFormatter:
    def test_format_with_correlation_id(self):
        correlation_id.set("corr-2")
        fmt = JSONFormatter()
        record = _make_record()
        output = fmt.format(record)
        data = json.loads(output)
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello"
        assert data["correlation_id"] == "corr-2"

    def test_format_without_correlation_id(self):
        correlation_id.set("")
        fmt = JSONFormatter()
        record = _make_record()
        output = fmt.format(record)
        data = json.loads(output)
        assert "message" in data
        assert "logger" in data
        assert "timestamp" in data

    def test_format_with_extras(self):
        fmt = JSONFormatter()
        record = logging.LogRecord("test.logger", logging.INFO, "", 0, "hello", (), None)
        record.extra_key = "extra_value"
        output = fmt.format(record)
        data = json.loads(output)
        assert data["extra_key"] == "extra_value"

    def test_format_with_exception(self):
        fmt = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record = logging.LogRecord("test.logger", logging.ERROR, "", 0, "fail", (), None)
            record.exc_info = sys.exc_info()
            output = fmt.format(record)
            data = json.loads(output)
            assert "exception" in data


class TestTimer:
    def test_timer_logs_success(self, caplog):
        logger = logging.getLogger("test.timer_success")
        with caplog.at_level(logging.INFO):
            with Timer(logger, "test_action", key="val"):
                pass
        assert any("test_action completed" in r.message for r in caplog.records)

    def test_timer_logs_warning_on_exception(self, caplog):
        logger = logging.getLogger("test.timer_exc")
        with caplog.at_level(logging.WARNING):
            try:
                with Timer(logger, "fail_action"):
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
        assert any("fail_action failed" in r.message for r in caplog.records)


class TestSetupLogging:
    def test_setup_configures_handlers(self):
        from credit_risk_server.core.logging import setup_logging

        logging_mod = importlib.import_module("credit_risk_server.core.logging")
        original_configured = logging_mod._CONFIGURED
        logging_mod._CONFIGURED = False

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                log_path = Path(tmpdir) / "test.log"
                setup_logging("DEBUG", "dev", log_path)
                logger = logging.getLogger()
                assert any(isinstance(h.formatter, DevFormatter) for h in logger.handlers)
        finally:
            logging_mod._CONFIGURED = original_configured

    def test_setup_prod_mode_with_json(self):
        from credit_risk_server.core.logging import setup_logging

        logging_mod = importlib.import_module("credit_risk_server.core.logging")
        original_configured = logging_mod._CONFIGURED
        logging_mod._CONFIGURED = False

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                log_path = Path(tmpdir) / "test_prod.log"
                setup_logging("INFO", "prod", log_path)
                logger = logging.getLogger()
                assert any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers)
        finally:
            logging_mod._CONFIGURED = original_configured

    def test_idempotent(self):
        from credit_risk_server.core.logging import setup_logging

        logging_mod = importlib.import_module("credit_risk_server.core.logging")
        logging_mod._CONFIGURED = True

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test2.log"
            handler_count = len(logging.getLogger().handlers)
            setup_logging("DEBUG", "prod", log_path)
            assert len(logging.getLogger().handlers) == handler_count
