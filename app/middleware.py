from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_contextvars()

        supplied_id = request.headers.get("x-request-id", "")
        correlation_id = (
            supplied_id
            if supplied_id.lower() != "missing"
            and re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", supplied_id)
            else f"req-{uuid.uuid4().hex[:8]}"
        )
        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation_id
            response.headers["x-response-time-ms"] = str(
                round((time.perf_counter() - start) * 1000, 2)
            )
            return response
        finally:
            clear_contextvars()
