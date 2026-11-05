"""Pydantic models for API requests and responses.

They validate input (bad requests get a 422 before reaching our code) and document the
API in the auto-generated /docs page.
"""
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceOut(BaseModel):
    id: str
    title: str
    translator: str | None = None
    publisher: str | None = None
    year: int | None = None
    languages: str
    url: str | None = None
    license_note: str | None = None


class Editions(BaseModel):
    """Which edition each language layer of a passage comes from."""
    sanskrit: SourceOut | None = None
    hindi: SourceOut
    english: SourceOut


class PassageOut(BaseModel):
    id: str = Field(examples=["GPS-02-015"])
    khanda: str
    chapter: int
    chapter_title: str
    verse_ref_en: str | None = None
    verse_ref_sa: str | None = None
    sanskrit: str | None = Field(None, description="Original Sanskrit, verbatim from the source edition")
    hindi: str = Field(description="Hindi translation, verbatim from the source edition")
    english: str = Field(description="English translation, verbatim from the source edition")
    page_en: str | None = None
    page_sa: str | None = None
    keywords: list[str]
    topics: list[str]
    notes: str | None = None
    editions: Editions


class PassageList(BaseModel):
    count: int
    passages: list[PassageOut]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "missing", "error"]
    passages: int
    llm: dict[str, str] = Field(examples=[{"gemini": "configured", "ollama": "reachable"}])


class ErrorOut(BaseModel):
    error: str
    message: str


# ---------------------------------------------------------------- POST /ask

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500, examples=["What does Garuda Purana explain about karma?"])
    conversation_id: str | None = Field(None, pattern=r"^[0-9a-fA-F-]{36}$",
                                        description="UUID from a previous response, to continue a conversation")

    @field_validator("question")
    @classmethod
    def clean_question(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("question is too short")
        if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in v):
            raise ValueError("question contains control characters")
        return v


class SourcePassage(PassageOut):
    relevance: float | None = Field(None, description="Cosine similarity between question and passage")


class RetrievalInfo(BaseModel):
    mode: str
    passed_gate: bool
    reason: str
    best_cosine: float
    best_bm25: float
    retrieved: list[dict]


class AskResponse(BaseModel):
    conversation_id: str
    language: Literal["en", "hi"]
    answerable: bool = Field(description="false = the knowledge base does not cover the question")
    answer: str = Field(description="AI-generated interpretation (or a 'not found' / 'unavailable' message)")
    answer_label: str = Field(description="How the UI should label the answer, e.g. 'AI interpretation'")
    sources: list[SourcePassage] = Field(description="Passages the answer cites (verbatim from the database)")
    related_passages: list[SourcePassage] = Field(description="Shown only when the AI service is down")
    model: str | None = Field(None, description="Which LLM produced the answer, e.g. gemini/gemini-3.5-flash")
    notice: str | None = Field(None, description="fallback_used:... or llm_unavailable")
    latency_ms: int
    retrieval: RetrievalInfo
