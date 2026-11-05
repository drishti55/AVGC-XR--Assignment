"""API tests for /health and /passages (temporary DB, no network, no model)."""
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_ok(client, kb):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok"
    assert body["passages"] == len(kb["passages"])
    assert body["llm"] == {"gemini": "configured", "ollama": "unreachable"}
    assert body["status"] == "ok"                     # Gemini alone is enough


def test_health_never_exposes_the_key(client):
    assert "test-key" not in client.get("/health").text


def test_health_degraded_without_database(tmp_path):
    s = Settings(_env_file=None, database_path=str(tmp_path / "missing.db"), gemini_api_key="",
                 ollama_base_url="http://127.0.0.1:9")
    body = TestClient(create_app(s)).get("/health").json()
    assert body["status"] == "degraded" and body["database"] == "missing"


def test_list_passages(client, kb):
    r = client.get("/passages")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(kb["passages"]) == len(body["passages"])
    p = body["passages"][0]
    for field in ("sanskrit", "hindi", "english", "chapter", "verse_ref_en", "keywords", "editions"):
        assert field in p
    assert p["editions"]["english"]["translator"] == "Ernest Wood and S. V. Subrahmanyam"
    assert "embedding" not in p


def test_filter_by_topic(client):
    body = client.get("/passages", params={"topic": "soul"}).json()
    assert body["count"] > 0 and all("soul" in p["topics"] for p in body["passages"])


def test_filter_by_chapter(client):
    body = client.get("/passages", params={"chapter": 2}).json()
    assert body["count"] > 0 and all(p["chapter"] == 2 for p in body["passages"])


def test_invalid_filters_rejected(client):
    for params in ({"chapter": 17}, {"chapter": "abc"}, {"topic": "DROP TABLE"}):
        r = client.get("/passages", params=params)
        assert r.status_code == 422 and r.json()["error"] == "invalid_request"


def test_get_one_passage(client):
    r = client.get("/passages/GPS-02-015")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "GPS-02-015" and "वैतरणी" in body["sanskrit"]
    assert body["editions"]["sanskrit"]["id"] == "gitapress1416"


def test_unknown_passage_404(client):
    r = client.get("/passages/GPS-99-999")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found", "message": "Passage GPS-99-999 not found"}


def test_malformed_passage_id_422(client):
    assert client.get("/passages/../../etc").status_code in (404, 422)
    assert client.get("/passages/not-an-id").status_code == 422


def test_cors_allows_only_frontend(client):
    ok = client.options("/passages", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/passages", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
