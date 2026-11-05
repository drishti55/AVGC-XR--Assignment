"""Database layer tests — temporary SQLite file, fake vectors (no model loading)."""
import json

import numpy as np
import pytest

from app import db
from scripts.validate_kb import KB_PATH, validate


@pytest.fixture
def kb():
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def conn(tmp_path, kb):
    c = db.connect(tmp_path / "test.db")
    db.init_schema(c)
    for s in kb["sources"]:
        db.upsert_source(c, s)
    for i, p in enumerate(kb["passages"]):
        vec = np.zeros(8, dtype=np.float32)
        vec[i % 8] = 1.0
        db.upsert_passage(c, p, vec, "fake-model")
    c.commit()
    yield c
    c.close()


def test_real_knowledge_base_is_valid(kb):
    assert validate(kb) == []


def test_all_passages_loaded(conn, kb):
    assert db.count_passages(conn) == len(kb["passages"])


def test_upsert_is_idempotent(conn, kb):
    p = kb["passages"][0]
    db.upsert_passage(conn, p, np.ones(8, dtype=np.float32), "fake-model")
    assert db.count_passages(conn) == len(kb["passages"])


def test_get_passage_roundtrip(conn, kb):
    original = kb["passages"][0]
    got = db.get_passage(conn, original["id"])
    assert got["english"] == original["english"]
    assert got["sanskrit"] == original["sanskrit"]
    assert got["keywords"] == original["keywords"]      # JSON decoded back to a list
    assert "embedding" not in got                       # vectors never leak into API data


def test_get_unknown_passage_returns_none(conn):
    assert db.get_passage(conn, "GPS-99-999") is None


def test_filter_by_topic_and_chapter(conn):
    soul = db.list_passages(conn, topic="soul")
    assert soul and all("soul" in p["topics"] for p in soul)
    ch2 = db.list_passages(conn, chapter=2)
    assert ch2 and all(p["chapter"] == 2 for p in ch2)


def test_get_by_ids_keeps_order_and_skips_unknown(conn, kb):
    a, b = kb["passages"][3]["id"], kb["passages"][1]["id"]
    got = db.get_passages_by_ids(conn, [a, "GPS-99-999", b])
    assert [p["id"] for p in got] == [a, b]


def test_load_embeddings_matrix(conn, kb):
    ids, matrix, model = db.load_embeddings(conn)
    assert len(ids) == len(kb["passages"])
    assert matrix.shape == (len(kb["passages"]), 8) and matrix.dtype == np.float32
    assert model == "fake-model"


def test_delete_passages_not_in(conn, kb):
    keep = [p["id"] for p in kb["passages"][:5]]
    removed = db.delete_passages_not_in(conn, keep)
    assert removed == len(kb["passages"]) - 5
    assert db.count_passages(conn) == 5
