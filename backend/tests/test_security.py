"""Hardening tests: rate limiting, body size, headers, error hygiene, secrets."""
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import RateLimiter, parse_rate
from tests.test_answer import FakeLLM, FakeRetriever, make_client, ok_result

REPO = Path(__file__).resolve().parents[2]


def test_ask_is_rate_limited(settings):
    s = settings.model_copy(update={"rate_limit": "3/minute"})
    client = make_client(s)
    codes = [client.post("/ask", json={"question": "karma?"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = client.post("/ask", json={"question": "karma?"})
    assert r.json()["error"] == "rate_limited" and int(r.headers["Retry-After"]) > 0


def test_read_endpoints_are_not_rate_limited(settings):
    client = make_client(settings.model_copy(update={"rate_limit": "1/minute"}))
    assert all(client.get("/passages").status_code == 200 for _ in range(5))


def test_rate_limiter_window_and_keys(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.security.time.monotonic", lambda: now[0])
    rl = RateLimiter(2, 60)
    assert rl.check("a") is None and rl.check("a") is None
    assert rl.check("a") == 61                       # third within the window is blocked
    assert rl.check("b") is None                     # other clients unaffected
    now[0] += 60
    assert rl.check("a") is None                     # window passed


@pytest.mark.parametrize("rate, expected", [("10/minute", (10, 60)), (" 5 / second ", (5, 1)), ("100/hour", (100, 3600))])
def test_parse_rate(rate, expected):
    assert parse_rate(rate) == expected


def test_parse_rate_rejects_garbage():
    with pytest.raises(ValueError):
        parse_rate("lots")


def test_oversized_body_rejected(settings):
    r = make_client(settings).post("/ask", content=b'{"question": "' + b"x" * 20_000 + b'"}',
                                   headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"] == "payload_too_large"


def test_security_headers(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_unexpected_error_is_generic(settings):
    class Boom(FakeRetriever):
        def search(self, *a, **k):
            raise RuntimeError("secret internal detail at /Users/someone/app.py line 42")
    client = TestClient(make_client(settings, retriever=Boom()).app, raise_server_exceptions=False)
    r = client.post("/ask", json={"question": "karma?"})
    assert r.status_code == 500
    assert r.json() == {"error": "internal_error", "message": "Something went wrong. Please try again."}
    assert "secret internal detail" not in r.text and "Traceback" not in r.text


def test_wrong_method_uses_error_shape(client):
    r = client.get("/ask")
    assert r.status_code == 405 and r.json()["error"] == "method_not_allowed"


def test_api_key_never_in_any_response(settings):
    s = settings.model_copy(update={"gemini_api_key": "SUPER-SECRET-KEY-123"})
    client = make_client(s, providers=[FakeLLM("gemini", error="unavailable"), FakeLLM("ollama", result=ok_result())])
    for r in (client.get("/health"), client.get("/passages"), client.post("/ask", json={"question": "karma?"})):
        assert "SUPER-SECRET-KEY-123" not in r.text


def test_frontend_source_contains_no_secrets():
    pattern = re.compile(r"AIza[0-9A-Za-z_-]{20,}|AQ\.[0-9A-Za-z_-]{20,}|GEMINI_API_KEY", re.I)
    for f in (REPO / "frontend" / "src").rglob("*"):
        if f.is_file():
            assert not pattern.search(f.read_text(encoding="utf-8")), f"possible secret in {f}"


def test_env_files_are_not_tracked_by_git():
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    assert not [f for f in tracked if Path(f).name == ".env"]
    assert "backend/.env.example" in tracked


def test_cors_rejects_unknown_origin_on_post(tmp_path, db_path):
    s = Settings(_env_file=None, database_path=str(db_path), cors_origins="http://localhost:5173")
    r = TestClient(create_app(s)).options("/ask", headers={"Origin": "http://evil.example",
                                                           "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
