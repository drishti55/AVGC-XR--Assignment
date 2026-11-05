"""SQLite data access. Plain SQL, no ORM — three small tables don't need one.

Each function takes an open connection, so callers (routes, scripts, tests) control
its lifetime and tests can use a temporary database.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import numpy as np

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "schema.sql"

# Columns returned to API clients (everything except the embedding vector).
PASSAGE_COLUMNS = (
    "id, khanda, chapter, chapter_title, verse_ref_en, verse_ref_sa, sanskrit, hindi, english, "
    "sanskrit_source_id, hindi_source_id, english_source_id, page_en, page_sa, keywords, topics, notes"
)


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- knowledge base (write)

def upsert_source(conn: sqlite3.Connection, s: dict) -> None:
    conn.execute(
        """INSERT INTO sources (id, title, translator, publisher, year, languages, url, license_note)
           VALUES (:id, :title, :translator, :publisher, :year, :languages, :url, :license_note)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title, translator=excluded.translator, publisher=excluded.publisher,
             year=excluded.year, languages=excluded.languages, url=excluded.url,
             license_note=excluded.license_note""",
        {k: s.get(k) for k in ("id", "title", "translator", "publisher", "year", "languages", "url", "license_note")},
    )


def upsert_passage(conn: sqlite3.Connection, p: dict, embedding: np.ndarray, model_name: str) -> None:
    row = {k: p.get(k) for k in (
        "id", "khanda", "chapter", "chapter_title", "verse_ref_en", "verse_ref_sa", "sanskrit", "hindi",
        "english", "sanskrit_source_id", "hindi_source_id", "english_source_id", "page_en", "page_sa", "notes",
    )}
    row["keywords"] = json.dumps(p["keywords"], ensure_ascii=False)
    row["topics"] = json.dumps(p["topics"], ensure_ascii=False)
    row["embedding"] = np.asarray(embedding, dtype=np.float32).tobytes()
    row["embedding_model"] = model_name
    cols = ", ".join(row)
    params = ", ".join(f":{c}" for c in row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in row if c != "id")
    conn.execute(f"INSERT INTO passages ({cols}) VALUES ({params}) ON CONFLICT(id) DO UPDATE SET {updates}", row)


def delete_passages_not_in(conn: sqlite3.Connection, keep_ids: list[str]) -> int:
    """Keep the DB an exact mirror of passages.json (removes passages deleted from the JSON)."""
    marks = ",".join("?" * len(keep_ids))
    cur = conn.execute(f"DELETE FROM passages WHERE id NOT IN ({marks})", keep_ids)
    return cur.rowcount


# ---------------------------------------------------------------- knowledge base (read)

def _passage_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["keywords"] = json.loads(d["keywords"])
    d["topics"] = json.loads(d["topics"])
    return d


def list_passages(conn: sqlite3.Connection, topic: str | None = None, chapter: int | None = None) -> list[dict]:
    sql, args = f"SELECT {PASSAGE_COLUMNS} FROM passages WHERE 1=1", []
    if chapter is not None:
        sql += " AND chapter = ?"
        args.append(chapter)
    if topic:
        # topics is a JSON array; json_each lets SQLite filter on its elements.
        sql += " AND EXISTS (SELECT 1 FROM json_each(passages.topics) WHERE json_each.value = ?)"
        args.append(topic)
    sql += " ORDER BY chapter, id"
    return [_passage_row_to_dict(r) for r in conn.execute(sql, args)]


def get_passage(conn: sqlite3.Connection, passage_id: str) -> dict | None:
    row = conn.execute(f"SELECT {PASSAGE_COLUMNS} FROM passages WHERE id = ?", (passage_id,)).fetchone()
    return _passage_row_to_dict(row) if row else None


def get_passages_by_ids(conn: sqlite3.Connection, ids: list[str]) -> list[dict]:
    """Return passages in the same order as `ids` (unknown ids are skipped)."""
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = {r["id"]: _passage_row_to_dict(r)
            for r in conn.execute(f"SELECT {PASSAGE_COLUMNS} FROM passages WHERE id IN ({marks})", ids)}
    return [rows[i] for i in ids if i in rows]


def list_sources(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["id"]: dict(r) for r in conn.execute("SELECT * FROM sources")}


def load_embeddings(conn: sqlite3.Connection) -> tuple[list[str], np.ndarray, str | None]:
    """All passage vectors as one (n, dim) matrix, for in-memory cosine search."""
    rows = conn.execute("SELECT id, embedding, embedding_model FROM passages ORDER BY id").fetchall()
    if not rows:
        return [], np.zeros((0, 0), dtype=np.float32), None
    ids = [r["id"] for r in rows]
    matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    return ids, matrix, rows[0]["embedding_model"]


def count_passages(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
