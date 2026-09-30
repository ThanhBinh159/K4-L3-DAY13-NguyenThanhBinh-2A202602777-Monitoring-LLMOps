from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def _send_chat(
    *, headers: dict[str, str] | None = None, user_id: str = "student-01"
) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                headers=headers,
                json={
                    "user_id": user_id,
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    return asyncio.run(send_request())


def test_generated_correlation_id_is_returned_and_logged(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = _send_chat(user_id="student@example.com")

    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.headers["x-response-time-ms"]
    assert response.json()["correlation_id"] == correlation_id

    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    received = next(record for record in records if record["event"] == "request_received")
    assert received["correlation_id"] == correlation_id
    assert received["user_id_hash"] != "student@example.com"
    assert received["session_id"] == "session-01"
    assert received["feature"] == "qa"
    assert received["model"]
    assert received["env"]


def test_safe_request_id_is_preserved_and_unsafe_id_is_replaced(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = _send_chat(headers={"x-request-id": "client-123"})
    assert response.headers["x-request-id"] == "client-123"
    assert response.json()["correlation_id"] == "client-123"

    response = _send_chat(headers={"x-request-id": "x" * 65})
    assert re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])


def test_pii_is_scrubbed_before_jsonl_write(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    logging_config.get_logger().info(
        "pii_probe",
        payload={
            "email": "student@vinuni.edu.vn",
            "phone": "090 123 4567",
            "cccd": "079123456789",
            "card": "4111 1111 1111 1111",
        },
    )

    raw = log_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in raw
    assert "090 123 4567" not in raw
    assert "079123456789" not in raw
    assert "4111 1111 1111 1111" not in raw
    assert "REDACTED_EMAIL" in raw
    assert "REDACTED_PHONE_VN" in raw
    assert "REDACTED_CCCD" in raw
    assert "REDACTED_CREDIT_CARD" in raw
