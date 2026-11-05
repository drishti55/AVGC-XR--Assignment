"""POST /ask — answer a question from the knowledge base."""
import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app import db
from app.deps import get_conn
from app.routes.passages import with_editions
from app.schemas import AskRequest, AskResponse, ErrorOut

router = APIRouter(tags=["question answering"])

ANSWER_LABELS = {
    "en": {True: "AI interpretation — generated from the cited passages, not part of the scripture",
           False: "Not found in the knowledge base"},
    "hi": {True: "एआई व्याख्या — उद्धृत अंशोंके आधार पर बनायी गयी, यह मूल ग्रन्थका भाग नहीं है",
           False: "ज्ञानकोशमें उपलब्ध नहीं"},
}


@router.post("/ask", response_model=AskResponse, summary="Ask a question (English or Hindi)",
             responses={422: {"model": ErrorOut}, 503: {"model": ErrorOut}})
def ask(body: AskRequest, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    service = request.app.state.answer_service
    if service is None:
        raise HTTPException(503, "Question answering is not ready (knowledge base or models not loaded).")

    conversation_id = body.conversation_id or str(uuid.uuid4())
    history = db.recent_messages(conn, conversation_id, max_turns=3)
    result = service.answer(conn, body.question, history)

    # Save both turns in one transaction (chat history is part of the assignment's DB use).
    with conn:
        db.ensure_conversation(conn, conversation_id)
        db.add_message(conn, conversation_id, "user", body.question, language=result.language)
        db.add_message(conn, conversation_id, "assistant", result.answer, language=result.language,
                       cited_ids=result.cited_ids, model_used=result.model, answerable=result.answerable,
                       latency_ms=result.latency_ms)

    sources = db.list_sources(conn)
    cosine = {r["id"]: r["cosine"] for r in result.retrieval["retrieved"]}

    def cards(ids: list[str]) -> list[dict]:
        return [{**with_editions(p, sources), "relevance": cosine.get(p["id"])}
                for p in db.get_passages_by_ids(conn, ids)]

    label = ANSWER_LABELS[result.language][result.answerable]
    if result.notice == "llm_unavailable":
        label = "Relevant passages (AI unavailable)" if result.language == "en" else "प्रासंगिक अंश (एआई उपलब्ध नहीं)"

    return {
        "conversation_id": conversation_id,
        "language": result.language,
        "answerable": result.answerable,
        "answer": result.answer,
        "answer_label": label,
        "sources": cards(result.cited_ids),
        "related_passages": cards(result.related_ids),
        "model": result.model,
        "notice": result.notice,
        "latency_ms": result.latency_ms,
        "retrieval": result.retrieval,
    }
