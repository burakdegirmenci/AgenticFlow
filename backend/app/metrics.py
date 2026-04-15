"""In-process counters exposed via ``GET /metrics`` (plaintext, Prometheus-ish).

No Prometheus client dep — we emit the minimum viable format by hand so a
scraper or a curl-friendly operator can read it. When we outgrow that,
switch to `prometheus_client` behind the same counter API.

Thread-safety: writers are rare (once per HTTP request / execution step),
and concurrent increments on a single dict key in CPython are atomic
enough for this use case. A lock is used defensively.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping


class _LabeledCounter:
    """A monotonically increasing counter keyed by sorted label tuples."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self._values: dict[tuple[tuple[str, str], ...], int] = {}
        self._lock = threading.Lock()

    def increment(self, by: int = 1, **labels: str) -> None:
        key = tuple(sorted((str(k), str(v)) for k, v in labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0) + by

    def snapshot(self) -> Mapping[tuple[tuple[str, str], ...], int]:
        with self._lock:
            return dict(self._values)


# ---------------------------------------------------------------------------
# Registry — add new counters here.
# ---------------------------------------------------------------------------
REQUESTS_TOTAL = _LabeledCounter(
    "agenticflow_requests_total",
    "HTTP requests served, labeled by method and status class (2xx, 4xx, ...).",
)

EXECUTIONS_TOTAL = _LabeledCounter(
    "agenticflow_executions_total",
    "Workflow executions finished, labeled by trigger and final status.",
)

STEPS_TOTAL = _LabeledCounter(
    "agenticflow_execution_steps_total",
    "ExecutionStep transitions, labeled by final status (SUCCESS / ERROR / SKIPPED).",
)

_COUNTERS: list[_LabeledCounter] = [REQUESTS_TOTAL, EXECUTIONS_TOTAL, STEPS_TOTAL]


def render_prometheus() -> str:
    """Serialise every counter to the Prometheus text exposition format."""
    lines: list[str] = []
    for counter in _COUNTERS:
        lines.append(f"# HELP {counter.name} {counter.description}")
        lines.append(f"# TYPE {counter.name} counter")
        snap = counter.snapshot()
        if not snap:
            lines.append(f"{counter.name} 0")
            continue
        for label_key, value in snap.items():
            if label_key:
                label_str = ",".join(f'{k}="{_escape_label(v)}"' for k, v in label_key)
                lines.append(f"{counter.name}{{{label_str}}} {value}")
            else:
                lines.append(f"{counter.name} {value}")
    return "\n".join(lines) + "\n"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def reset_all_for_tests() -> None:
    """Clear all counters. Intended only for unit-test isolation."""
    for counter in _COUNTERS:
        with counter._lock:  # noqa: SLF001
            counter._values.clear()  # noqa: SLF001
