"""Shared fixtures: a temporary database built from the real passages.json (fake vectors)."""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import Settings
from app.main import create_app
from scripts.validate_kb import KB_PATH


@pytest.fixture
def kb():
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def db_path(tmp_path, kb):
    path = tmp_path / "test.db"
    with db.connection(path) as c:
        db.init_schema(c)
        for s in kb["sources"]:
            db.upsert_source(c, s)
        for i, p in enumerate(kb["passages"]):
            vec = np.zeros(8, dtype=np.float32)
            vec[i % 8] = 1.0
            db.upsert_passage(c, p, vec, "fake-model")
        c.commit()
    return path


@pytest.fixture
def conn(db_path):
    c = db.connect(db_path)
    yield c
    c.close()


@pytest.fixture
def settings(db_path):
    # Port 9 (discard) is never an Ollama server, so health sees it as unreachable.
    return Settings(_env_file=None, database_path=str(db_path), gemini_api_key="test-key",
                    ollama_base_url="http://127.0.0.1:9")


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))
