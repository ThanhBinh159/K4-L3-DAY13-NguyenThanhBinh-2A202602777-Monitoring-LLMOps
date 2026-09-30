from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
CONFIG_PATH = ROOT / "config" / "dashboard.yaml"

STYLE = """
:root { color-scheme: dark; --bg:#0b1220; --card:#152136; --text:#f8fafc;
  --muted:#cbd5e1; --border:#334155; --blue:#60a5fa; --green:#34d399;
  --amber:#fbbf24; --red:#f87171; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
  font:16px/1.5 system-ui,Segoe UI,sans-serif; }
main { max-width:1500px; margin:auto; padding:24px; }
h1 { font-size:clamp(24px,3vw,34px); margin:0 0 6px; }
h2 { font-size:18px; margin:0; }
.meta,.unit,.target-text { color:var(--muted); }
.meta { margin:0 0 8px; }
.panel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:22px; }
.panel { min-width:0; background:var(--card); border:1px solid var(--border);
  border-radius:12px; padding:18px; }
.panel-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.unit,.target-text { font-size:13px; margin:4px 0; }
.status { font-size:12px; font-weight:700; border-radius:999px; padding:4px 8px; white-space:nowrap; }
.status.good { color:var(--green); background:#15372e; }
.status.bad { color:var(--red); background:#43212b; }
.status.empty { color:var(--amber); background:#392b14; }
svg { width:100%; height:auto; display:block; margin:12px 0; }
.gridline { stroke:var(--border); stroke-width:1; }
.axis { fill:var(--muted); font-size:12px; }
.threshold-line { stroke:var(--amber); stroke-width:2; stroke-dasharray:6 5; }
.stats { display:flex; flex-wrap:wrap; gap:8px; margin:0; }
.stat { flex:1 1 120px; background:#1c2c45; border-radius:8px; padding:9px 11px; }
.stat dt { color:var(--muted); font-size:12px; }
.stat dd { margin:2px 0 0; font:600 17px/1.4 Consolas,monospace; }
@media(max-width:800px) { .panel-grid { grid-template-columns:1fr; } main { padding:16px; } }
"""


def load_logs(path: Path = LOG_PATH) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number} of {path.name}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected JSON object at line {line_number} of {path.name}")
            records.append(record)
    return records


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _number(record: dict[str, Any], key: str) -> float | None:
    value = record.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def summarize_logs(
    records: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_minutes: int = 60,
) -> dict[str, Any]:
    if window_minutes < 1:
        raise ValueError("window_minutes must be positive")
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    start = now - timedelta(minutes=window_minutes)
    buckets = [
        {"requests": 0, "failures": 0, "attempts": 0, "successes": 0,
         "latency": [], "ttft": [], "cost": [], "tokens_in": [],
         "tokens_out": [], "quality": []}
        for _ in range(window_minutes)
    ]
    error_types: Counter[str] = Counter()
    for record in records:
        timestamp = _timestamp(record.get("ts"))
        if timestamp is None or not start <= timestamp <= now:
            continue
        index = min(window_minutes - 1, int((timestamp - start).total_seconds() // 60))
        bucket = buckets[index]
        event = record.get("event")
        if event == "request_received":
            bucket["requests"] += 1
        elif event == "request_failed":
            bucket["failures"] += 1
            if isinstance(record.get("error_type"), str):
                error_types[record["error_type"]] += 1
        if isinstance(record.get("tool_success"), bool):
            bucket["attempts"] += 1
            bucket["successes"] += int(record["tool_success"])
        if event == "response_sent":
            for field, target in (
                ("latency_ms", "latency"), ("ttft_ms", "ttft"),
                ("cost_usd", "cost"), ("tokens_in", "tokens_in"),
                ("tokens_out", "tokens_out"), ("quality_score", "quality"),
            ):
                value = _number(record, field)
                if value is not None:
                    bucket[target].append(value)

    def all_values(key: str) -> list[float]:
        return [value for bucket in buckets for value in bucket[key]]

    requests = sum(bucket["requests"] for bucket in buckets)
    failures = sum(bucket["failures"] for bucket in buckets)
    attempts = sum(bucket["attempts"] for bucket in buckets)
    successes = sum(bucket["successes"] for bucket in buckets)
    quality = all_values("quality")
    series = {
        "latency": [_percentile(bucket["latency"], 95) for bucket in buckets],
        "traffic": [bucket["requests"] for bucket in buckets],
        "errors": [100 * bucket["failures"] / bucket["requests"]
                   if bucket["requests"] else None for bucket in buckets],
        "retrieval": [100 * bucket["successes"] / bucket["attempts"]
                      if bucket["attempts"] else None for bucket in buckets],
        "cost": [sum(bucket["cost"]) for bucket in buckets],
        "tokens_in": [sum(bucket["tokens_in"]) for bucket in buckets],
        "tokens_out": [sum(bucket["tokens_out"]) for bucket in buckets],
        "quality": [mean(bucket["quality"]) if bucket["quality"] else None
                    for bucket in buckets],
    }
    return {
        "start": start, "end": now, "window_minutes": window_minutes,
        "request_count": requests, "failure_count": failures,
        "requests_per_minute": requests / window_minutes,
        "latency_p50_ms": _percentile(all_values("latency"), 50),
        "latency_p95_ms": _percentile(all_values("latency"), 95),
        "latency_p99_ms": _percentile(all_values("latency"), 99),
        "ttft_p95_ms": _percentile(all_values("ttft"), 95),
        "error_rate_pct": 100 * failures / requests if requests else None,
        "retrieval_success_rate_pct": 100 * successes / attempts if attempts else None,
        "cost_total_usd": sum(all_values("cost")),
        "tokens_in_total": sum(all_values("tokens_in")),
        "tokens_out_total": sum(all_values("tokens_out")),
        "quality_avg": mean(quality) if quality else None,
        "error_types": dict(error_types),
        "series": series,
    }


def _format(value: float | None, unit: str) -> str:
    if value is None:
        return "No data"
    if unit == "ms":
        return f"{value:,.0f} ms"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "usd":
        return f"{value:.4f} USD"
    if unit == "tokens":
        return f"{value:,.0f}"
    if unit == "score_0_to_1":
        return f"{value:.2f}"
    if unit == "requests_per_minute":
        return f"{value:.2f} req/min"
    return f"{value:,.0f}"


def _panel_data(panel_id: str, summary: dict[str, Any]):
    s = summary
    definitions = {
        "latency": (s["latency_p95_ms"],
                    [("P50", s["latency_p50_ms"], "ms"), ("P95", s["latency_p95_ms"], "ms"),
                     ("P99", s["latency_p99_ms"], "ms"), ("TTFT P95", s["ttft_p95_ms"], "ms")],
                    [("P95 latency", s["series"]["latency"])]),
        "traffic": (s["requests_per_minute"],
                    [("Requests", s["request_count"], "count"),
                     ("Average rate", s["requests_per_minute"], "requests_per_minute")],
                    [("Requests/min", s["series"]["traffic"])]),
        "errors": (s["error_rate_pct"],
                   [("Error rate", s["error_rate_pct"], "percent"),
                    ("Retrieval success", s["retrieval_success_rate_pct"], "percent"),
                    ("Failures", s["failure_count"], "count")],
                   [("Error rate", s["series"]["errors"]),
                    ("Retrieval success", s["series"]["retrieval"])]),
        "cost": (s["cost_total_usd"],
                 [("Window total", s["cost_total_usd"], "usd")],
                 [("Cost/min", s["series"]["cost"])]),
        "tokens": (s["tokens_in_total"] + s["tokens_out_total"],
                   [("Input", s["tokens_in_total"], "tokens"),
                    ("Output", s["tokens_out_total"], "tokens")],
                   [("Input", s["series"]["tokens_in"]),
                    ("Output", s["series"]["tokens_out"])]),
        "quality": (s["quality_avg"],
                    [("Mean score", s["quality_avg"], "score_0_to_1")],
                    [("Quality mean", s["series"]["quality"])]),
    }
    return definitions[panel_id]


def _chart(
    panel_id: str,
    series: list[tuple[str, list[float | None]]],
    start: datetime,
    end: datetime,
    threshold: float | None,
) -> str:
    width, height, left, top, plot_width, plot_height = 600, 200, 50, 14, 530, 135
    numbers = [value for _, values in series for value in values if value is not None]
    if threshold is not None:
        numbers.append(threshold)
    scale = max(numbers, default=1) or 1
    scale *= 1.08
    length = max((len(values) for _, values in series), default=1)

    def x(index: int) -> float:
        return left + plot_width * index / max(length - 1, 1)

    def y(value: float) -> float:
        return top + plot_height * (1 - value / scale)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(panel_id)} trend in the last hour">'
    ]
    for value in (0, scale / 2, scale):
        position = y(value)
        parts.append(
            f'<line class="gridline" x1="{left}" y1="{position:.1f}" '
            f'x2="{left+plot_width}" y2="{position:.1f}"/>'
            f'<text class="axis" x="2" y="{position+4:.1f}">{value:.2g}</text>'
        )
    if threshold is not None:
        parts.append(
            f'<line class="threshold-line" x1="{left}" y1="{y(threshold):.1f}" '
            f'x2="{left+plot_width}" y2="{y(threshold):.1f}"/>'
        )
    colors = ("#60a5fa", "#34d399")
    for group, (label, values) in enumerate(series):
        points = [(index, value) for index, value in enumerate(values) if value is not None]
        if points:
            coordinates = " ".join(f"{x(index):.1f},{y(value):.1f}" for index, value in points)
            dash = ' stroke-dasharray="7 4"' if group else ""
            parts.append(
                f'<polyline points="{coordinates}" fill="none" stroke="{colors[group]}" '
                f'stroke-width="2.5"{dash}/>'
            )
            index, value = points[-1]
            parts.append(
                f'<circle cx="{x(index):.1f}" cy="{y(value):.1f}" r="4" '
                f'fill="{colors[group]}"><title>{escape(label)}: {value:.3g}</title></circle>'
            )
    for index, time in ((0, start), (length - 1, end)):
        parts.append(
            f'<text class="axis" x="{x(index):.1f}" y="169" text-anchor="middle">'
            f'{time.strftime("%H:%M")} UTC</text>'
        )
    for group, (label, _) in enumerate(series):
        parts.append(
            f'<text class="axis" x="{left+group*225}" y="190" '
            f'fill="{colors[group]}">{escape(label)}'
            f'{" (dashed)" if group else " (solid)"}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_dashboard(
    records: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    config_path: Path = CONFIG_PATH,
) -> str:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = payload.get("dashboard") if isinstance(payload, dict) else None
    if not isinstance(config, dict) or not isinstance(config.get("panels"), list):
        raise ValueError("Invalid dashboard contract")
    summary = summarize_logs(
        records,
        now=now,
        window_minutes=int(config.get("time_range_minutes", 60)),
    )
    title = escape(str(config.get("title", "Monitoring dashboard")))
    refresh = int(config.get("refresh_seconds", 30))
    cards = []
    for panel in config["panels"]:
        panel_id = str(panel["id"])
        value, stats, series = _panel_data(panel_id, summary)
        rule = panel["threshold"]
        target = float(rule["value"])
        operator = rule["operator"]
        passed = None if value is None else value <= target if operator == "lte" else value >= target
        status = "No samples" if passed is None else "Within threshold" if passed else "Threshold breached"
        status_class = "empty" if passed is None else "good" if passed else "bad"
        rule_sign = "≤" if operator == "lte" else "≥"
        unit = str(panel["unit"])
        stats_html = "".join(
            f'<div class="stat"><dt>{escape(label)}</dt><dd>{escape(_format(metric, metric_unit))}</dd></div>'
            for label, metric, metric_unit in stats
        )
        breakdown = ""
        if panel_id == "errors":
            details = ", ".join(
                f"{escape(name)}: {count}"
                for name, count in sorted(summary["error_types"].items())
            ) or "No errors"
            breakdown = f'<p class="target-text">Error types: {details}</p>'
        chart_target = target if panel_id in {"latency", "traffic", "errors", "quality"} else None
        cards.append(
            '<article class="panel">'
            f'<div class="panel-head"><div><h2>{escape(str(panel["title"]))}</h2>'
            f'<p class="unit">Unit: {escape(unit.replace("_", " "))}</p></div>'
            f'<span class="status {status_class}">{status}</span></div>'
            f'<p class="target-text">Target: {escape(str(rule["aggregation"]))} {rule_sign} '
            f'{escape(_format(target, unit))}</p>'
            + _chart(panel_id, series, summary["start"], summary["end"], chart_target)
            + f'<dl class="stats">{stats_html}</dl>{breakdown}</article>'
        )
    range_text = (
        f'{summary["start"].strftime("%Y-%m-%d %H:%M")}–'
        f'{summary["end"].strftime("%Y-%m-%d %H:%M")} UTC'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="refresh" content="{refresh}"><title>{title}</title>'
        f'<style>{STYLE}</style></head><body><main><header><h1>{title}</h1>'
        f'<p class="meta">Source: data/logs.jsonl · Last {summary["window_minutes"]} minutes'
        f' · Refresh: {refresh}s</p><p class="meta">Time range: {range_text}</p>'
        f'<p class="meta">Requests: {summary["request_count"]}; failures: {summary["failure_count"]}</p>'
        f'</header><section class="panel-grid" aria-label="Six monitoring panels">'
        + "".join(cards) + "</section></main></body></html>"
    )


def dashboard_page(log_path: Path = LOG_PATH, config_path: Path = CONFIG_PATH) -> str:
    try:
        return render_dashboard(load_logs(log_path), config_path=config_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<title>Dashboard unavailable</title><body><main>'
            '<h1>Dashboard unavailable</h1>'
            f'<p role="alert">Could not load dashboard data: {escape(str(exc))}</p>'
            '</main></body></html>'
        )
