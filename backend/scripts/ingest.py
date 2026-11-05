"""Load data/passages.json into SQLite and compute passage embeddings.

Run from backend/:  uv run python scripts/ingest.py
Safe to run repeatedly: rows are upserted and the DB mirrors the JSON exactly.
"""
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services.embeddings import get_embedder, passage_embedding_text  # noqa: E402
from validate_kb import KB_PATH, validate  # noqa: E402  (sibling script)


def main() -> int:
    settings = get_settings()
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))

    errors = validate(kb)
    if errors:
        print("Knowledge base is invalid — fix these first (see scripts/validate_kb.py):")
        for e in errors:
            print("  -", e)
        return 1

    passages = kb["passages"]
    print(f"Loading embedding model {settings.embedding_model} ...")
    t0 = time.time()
    embedder = get_embedder(settings.embedding_model)

    texts = [passage_embedding_text(p) for p in passages]
    for p, text in zip(passages, texts):
        n = embedder.token_count("passage: " + text)
        if n > embedder.max_tokens:
            print(f"  note: {p['id']} is {n} tokens; the model reads the first {embedder.max_tokens} "
                  "(keywords, title and English come first, so only the end of the Hindi is cut)")
    vectors = embedder.embed_passages(texts)

    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    with db.connection(settings.db_file) as conn:
        db.init_schema(conn)
        with conn:  # one transaction: all-or-nothing
            for s in kb["sources"]:
                db.upsert_source(conn, s)
            for p, vec in zip(passages, vectors):
                db.upsert_passage(conn, p, vec, settings.embedding_model)
            removed = db.delete_passages_not_in(conn, [p["id"] for p in passages])
        total = db.count_passages(conn)

    print(f"Ingested {len(passages)} passages ({vectors.shape[1]}-dim vectors), removed {removed} stale, "
          f"{total} in DB -> {settings.db_file}  [{time.time() - t0:.1f}s]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
