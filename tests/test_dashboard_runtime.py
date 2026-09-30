from __future__ import annotations

from datetime import datetime, timezone

from app.dashboard import render_dashboard, summarize_logs


NOW = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)


def sample_logs() -> list[dict]:
    return [
        {
            "ts": "2026-09-30T09:58:00Z",
            "event": "request_received",
            "correlation_id": "req-00000001",
        },
        {
            "ts": "2026-09-30T09:58:01Z",
            "event": "response_sent",
            "correlation_id": "req-00000001",
            "latency_ms": 500,
            "ttft_ms": 100,
            "cost_usd": 0.001,
            "tokens_in": 100,
            "tokens_out": 40,
            "quality_score": 0.8,
            "tool_success": True,
        },
        {
            "ts": "2026-09-30T09:59:00Z",
            "event": "request_received",
            "correlation_id": "req-00000002",
        },
        {
            "ts": "2026-09-30T09:59:01Z",
            "event": "response_sent",
            "correlation_id": "req-00000002",
            "latency_ms": 900,
            "ttft_ms": 150,
            "cost_usd": 0.002,
            "tokens_in": 80,
            "tokens_out": 60,
            "quality_score": 0.6,
            "tool_success": True,
        },
        {
            "ts": "2026-09-30T09:59:02Z",
            "event": "request_received",
            "correlation_id": "req-00000003",
        },
        {
            "ts": "2026-09-30T09:59:03Z",
            "event": "request_failed",
            "correlation_id": "req-00000003",
            "error_type": "RuntimeError",
            "tool_name": "retrieval",
            "tool_success": False,
            "payload": {"message_preview": "learner@example.edu"},
        },
    ]


def test_dashboard_summarizes_recent_logs_for_all_contract_metrics() -> None:
    summary = summarize_logs(sample_logs(), now=NOW, window_minutes=60)

    assert summary["request_count"] == 3
    assert summary["failure_count"] == 1
    assert summary["latency_p50_ms"] == 700
    assert summary["latency_p95_ms"] == 880
    assert summary["latency_p99_ms"] == 896
    assert summary["ttft_p95_ms"] == 147.5
    assert summary["error_rate_pct"] == 100 / 3
    assert summary["retrieval_success_rate_pct"] == 200 / 3
    assert summary["cost_total_usd"] == 0.003
    assert summary["tokens_in_total"] == 180
    assert summary["tokens_out_total"] == 100
    assert summary["quality_avg"] == 0.7
    assert summary["error_types"] == {"RuntimeError": 1}


def test_dashboard_renders_six_readable_panels_without_raw_payload() -> None:
    page = render_dashboard(sample_logs(), now=NOW)

    assert page.count('class="panel"') == 6
    assert "Latency percentiles and TTFT" in page
    assert "Request traffic" in page
    assert "Error rate and retrieval success" in page
    assert "Cost over time" in page
    assert "Input and output tokens" in page
    assert "Quality proxy" in page
    assert "Error types: RuntimeError: 1" in page
    assert "60 minutes" in page
    assert "learner@example.edu" not in page
    assert 'http-equiv="refresh" content="30"' in page
