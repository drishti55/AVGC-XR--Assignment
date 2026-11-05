"""GET /passages and GET /passages/{id} — browse the knowledge base."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app import db
from app.deps import get_conn
from app.schemas import ErrorOut, PassageList, PassageOut

router = APIRouter(tags=["knowledge base"])


def with_editions(passage: dict, sources: dict[str, dict]) -> dict:
    """Attach the full edition details for each language layer of a passage."""
    return {
        **passage,
        "editions": {
            "sanskrit": sources.get(passage.get("sanskrit_source_id")),
            "hindi": sources[passage["hindi_source_id"]],
            "english": sources[passage["english_source_id"]],
        },
    }


@router.get("/passages", response_model=PassageList, summary="List knowledge-base passages")
def list_passages(
    topic: str | None = Query(None, max_length=40, pattern=r"^[a-z_]+$", examples=["karma"],
                              description="Filter by topic, e.g. karma, soul, afterlife_journey, good_deeds"),
    chapter: int | None = Query(None, ge=1, le=16, description="Saroddhara chapter (1-16)"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    sources = db.list_sources(conn)
    passages = [with_editions(p, sources) for p in db.list_passages(conn, topic=topic, chapter=chapter)]
    return {"count": len(passages), "passages": passages}


@router.get("/passages/{passage_id}", response_model=PassageOut, summary="Get one passage",
            responses={404: {"model": ErrorOut}})
def get_passage(
    passage_id: str = Path(pattern=r"^GPS-\d{2}-\d{3}$", examples=["GPS-02-015"]),
    conn: sqlite3.Connection = Depends(get_conn),
):
    passage = db.get_passage(conn, passage_id)
    if passage is None:
        raise HTTPException(404, f"Passage {passage_id} not found")
    return with_editions(passage, db.list_sources(conn))
