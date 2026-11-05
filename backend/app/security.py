"""Small security helpers: per-IP rate limiting, request-size limit, security headers.

The rate limiter keeps timestamps in this process's memory — fine for one local server.
With several servers it would move to Redis so all instances share the counts.
"""
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

UNITS = {"second": 1, "minute": 60, "hour": 3600}


def parse_rate(rate: str) -> tuple[int, int]:
    """'10/minute' -> (10, 60)."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(second|minute|hour)\s*", rate)
    if not m:
        raise ValueError(f"RATE_LIMIT must look like '10/minute', got {rate!r}")
    return int(m.group(1)), UNITS[m.group(2)]


class RateLimiter:
    """Sliding window: at most `max_requests` per `window` seconds for each client key."""

    def __init__(self, max_requests: int, window: int):
        self.max_requests, self.window = max_requests, window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()          # endpoints run in a thread pool

    def check(self, key: str) -> int | None:
        """Record a request. Returns None if allowed, else seconds until the next slot frees up."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return int(self.window - (now - hits[0])) + 1
            hits.append(now)
            return None


def rate_limit(request: Request) -> None:
    """FastAPI dependency for endpoints that call the LLM (they cost quota)."""
    limiter: RateLimiter = request.app.state.rate_limiter
    client = request.client.host if request.client else "unknown"
    retry_after = limiter.check(client)
    if retry_after is not None:
        raise HTTPException(429, f"Too many questions. Please wait {retry_after} s and try again.",
                            headers={"Retry-After": str(retry_after)})


class BodySizeLimit(BaseHTTPMiddleware):
    """Reject oversized request bodies before they are read (a question is at most 500 chars)."""

    def __init__(self, app, max_bytes: int = 16_384):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self.max_bytes:
            return JSONResponse({"error": "payload_too_large", "message": "Request body is too large."},
                                status_code=413)
        return await call_next(request)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response
