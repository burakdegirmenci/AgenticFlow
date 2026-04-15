"""In-process metrics counters + Prometheus text rendering."""

from __future__ import annotations

import pytest

from app.metrics import (
    EXECUTIONS_TOTAL,
    REQUESTS_TOTAL,
    STEPS_TOTAL,
    render_prometheus,
    reset_all_for_tests,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_all_for_tests()


def test_zero_counter_renders_as_single_line() -> None:
    text = render_prometheus()
    assert "agenticflow_requests_total 0" in text
    assert "# HELP agenticflow_requests_total" in text
    assert "# TYPE agenticflow_requests_total counter" in text


def test_labeled_counter_increments_and_renders() -> None:
    REQUESTS_TOTAL.increment(method="GET", status="2xx")
    REQUESTS_TOTAL.increment(method="GET", status="2xx")
    REQUESTS_TOTAL.increment(method="POST", status="4xx")

    text = render_prometheus()

    # Two distinct label sets, one line each.
    assert 'agenticflow_requests_total{method="GET",status="2xx"} 2' in text
    assert 'agenticflow_requests_total{method="POST",status="4xx"} 1' in text


def test_labels_are_sorted_alphabetically() -> None:
    REQUESTS_TOTAL.increment(status="2xx", method="GET")  # kwargs order reversed
    text = render_prometheus()
    # method should come before status in output (sorted by key).
    line = next(line for line in text.splitlines() if "agenticflow_requests_total{" in line)
    assert line.index("method") < line.index("status")


def test_executions_counter_tracks_trigger_and_status() -> None:
    EXECUTIONS_TOTAL.increment(status="SUCCESS", trigger="MANUAL")
    EXECUTIONS_TOTAL.increment(status="ERROR", trigger="SCHEDULE")

    text = render_prometheus()
    assert 'agenticflow_executions_total{status="SUCCESS",trigger="MANUAL"} 1' in text
    assert 'agenticflow_executions_total{status="ERROR",trigger="SCHEDULE"} 1' in text


def test_steps_counter_is_per_node_type() -> None:
    STEPS_TOTAL.increment(node_type="transform.filter", status="SUCCESS")
    STEPS_TOTAL.increment(node_type="transform.filter", status="SUCCESS")
    STEPS_TOTAL.increment(node_type="output.log", status="ERROR")

    text = render_prometheus()
    assert (
        'agenticflow_execution_steps_total{node_type="transform.filter",status="SUCCESS"} 2' in text
    )


def test_label_values_escaped() -> None:
    REQUESTS_TOTAL.increment(method='weird"one', status="2xx")
    text = render_prometheus()
    # Literal backslash-quote in the rendered label value
    assert 'method="weird\\"one"' in text


def test_increment_by_arbitrary_amount() -> None:
    REQUESTS_TOTAL.increment(by=5, method="GET", status="2xx")
    text = render_prometheus()
    assert 'agenticflow_requests_total{method="GET",status="2xx"} 5' in text
