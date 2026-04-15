"""Structured JSON logging for AgenticFlow.

One configuration entry point, called once from ``app.main.lifespan``.
Every log record is emitted as a single JSON line with ISO-8601 timestamps,
logger name, level, and any ``extra=`` fields the call site supplied.

Output destinations (both active by default):
- stdout — for container / systemd aggregation.
- ``logs/agenticflow.log`` (rotating) — so a self-hosted operator has a
  local trail to grep even without a central sink.

Redaction: a top-level filter strips any key whose name matches a known
secret pattern (API keys, Fernet tokens, uye_kodu). That is an extra safety
net; callers should never pass a raw secret in the first place.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter

_SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|uye[_-]?kodu|master[_-]?key|sentry[_-]?dsn)"
)
_SECRET_VALUE_LEN = 6  # leave a redaction hint but not the full value


class _RedactSecretsFilter(logging.Filter):
    """Redact values whose key name looks like a secret.

    Scans both the record's ``extra`` (attached as attributes) and any dict
    argument passed as ``%s`` formatting. Irreversible — we never unmask.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            if _SECRET_KEY_RE.search(key):
                value = record.__dict__[key]
                if isinstance(value, str) and len(value) > _SECRET_VALUE_LEN:
                    record.__dict__[key] = value[:3] + "…REDACTED"
                elif value is not None:
                    record.__dict__[key] = "…REDACTED"
        if isinstance(record.args, Mapping):
            record.args = _redact_mapping(record.args)
        return True


def _redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(k, str) and _SECRET_KEY_RE.search(k):
            out[k] = "…REDACTED"
        elif isinstance(v, Mapping):
            out[k] = _redact_mapping(v)
        else:
            out[k] = v
    return out


def _make_formatter() -> JsonFormatter:
    # Fields on every record. Extra keys supplied via ``logger.info(..., extra={})``
    # land in the output automatically.
    return JsonFormatter(
        "{asctime}{levelname}{name}{message}",
        style="{",
        rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        timestamp=True,
    )


def setup_logging(
    *,
    level: str = "INFO",
    log_dir: str | os.PathLike[str] | None = "logs",
    log_file: str = "agenticflow.log",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> None:
    """Configure the root logger. Idempotent.

    - Removes any handlers set by previous calls (uvicorn installs its own;
      those are replaced so all records — app + uvicorn — share one format).
    - Adds a stdout handler and a rotating file handler.
    - Installs the secret-redaction filter on both.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Wipe existing handlers so repeated calls don't duplicate output and
    # uvicorn's default plain formatter is replaced with ours.
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    formatter = _make_formatter()
    redact = _RedactSecretsFilter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(redact)
    root.addHandler(stdout_handler)

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redact)
        root.addHandler(file_handler)

    # Tame the noisier third-party loggers by default.
    for name in ("zeep", "urllib3", "apscheduler.executors.default"):
        logging.getLogger(name).setLevel(max(logging.WARNING, root.level))


def get_logger(name: str) -> logging.Logger:
    """Thin wrapper to standardise logger acquisition across the app."""
    return logging.getLogger(name)
