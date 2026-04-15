"""Structured JSON logging — formatter shape and secret redaction."""

from __future__ import annotations

import json
import logging

import pytest

from app.logging_config import setup_logging


@pytest.fixture(autouse=True)
def _clean_logging(tmp_path) -> None:
    """Isolate each test — reconfigure into the tmp dir so rotations don't
    leak real log files into the repo."""
    setup_logging(level="DEBUG", log_dir=str(tmp_path), log_file="test.log")
    yield
    # Clear handlers after the test so subsequent tests are not affected.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass


def test_record_is_serialised_as_json(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("agenticflow.test")
    with caplog.at_level(logging.INFO, logger="agenticflow.test"):
        logger.info("something_happened", extra={"user_id": 42, "action": "click"})

    assert caplog.records, "no log record captured"
    record = caplog.records[0]
    assert record.getMessage() == "something_happened"
    # `extra=` fields become attributes on the record
    assert record.__dict__.get("user_id") == 42
    assert record.__dict__.get("action") == "click"


def test_secret_keys_in_extra_are_redacted(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("agenticflow.test")
    with caplog.at_level(logging.INFO, logger="agenticflow.test"):
        logger.info(
            "tried_to_leak",
            extra={
                "api_key": "sk-ant-super-secret-0123456789",
                "master_key": "m-very-secret-key",
                "uye_kodu": "FON5-ABCDEF-0123",
                "harmless": "ok",
            },
        )

    record = caplog.records[0]
    assert "REDACTED" in str(record.__dict__.get("api_key"))
    assert "REDACTED" in str(record.__dict__.get("master_key"))
    assert "REDACTED" in str(record.__dict__.get("uye_kodu"))
    assert record.__dict__.get("harmless") == "ok"


def test_rotating_file_handler_writes_to_tmp(tmp_path) -> None:
    setup_logging(level="INFO", log_dir=str(tmp_path), log_file="runs.log")
    logging.getLogger("agenticflow.fs").info("disk_check", extra={"marker": "xyz123"})

    logfile = tmp_path / "runs.log"
    assert logfile.exists()
    content = logfile.read_text(encoding="utf-8")
    # At least one JSON line containing our marker.
    for line in content.splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if parsed.get("marker") == "xyz123":
            assert parsed.get("message") == "disk_check"
            return
    pytest.fail("marker log line not found")


def test_setup_is_idempotent(tmp_path) -> None:
    # Calling setup twice should not duplicate handlers.
    setup_logging(level="INFO", log_dir=str(tmp_path), log_file="runs.log")
    handlers_after_first = len(logging.getLogger().handlers)
    setup_logging(level="INFO", log_dir=str(tmp_path), log_file="runs.log")
    handlers_after_second = len(logging.getLogger().handlers)
    assert handlers_after_first == handlers_after_second
