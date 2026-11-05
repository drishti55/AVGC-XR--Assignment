"""Pydantic models for API requests and responses.

They validate input (bad requests get a 422 before reaching our code) and document the
API in the auto-generated /docs page.
"""
from typing import Literal

from pydantic import BaseModel, Field


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
