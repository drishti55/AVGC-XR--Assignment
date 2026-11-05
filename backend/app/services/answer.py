"""The question-answering pipeline behind POST /ask.

    question -> language -> hybrid retrieval -> relevance gate
             -> LLM (Gemini, fallback Ollama) -> citation check -> response

Three layers keep answers grounded:
  1. the relevance gate refuses before the LLM is even called;
  2. the prompt restricts the model to the passages;
  3. citation validation here, in code: cited IDs must be among the retrieved passages.
"""
import logging
import re
import sqlite3
import time
from dataclasses import dataclass

from app import db
from app.services.language import detect_language
from app.services.llm.router import AllProvidersFailed, LLMRouter
from app.services.prompts import build_system_prompt, build_user_prompt
from app.services.retrieval import Retriever

logger = logging.getLogger("garuda.answer")

NOT_FOUND = {
    "en": "The knowledge base does not contain information to answer this question. "
          "It currently holds 18 passages from the Garuda Purana Saroddhara (on death, karma, the "
          "journey after death, good deeds and liberation).",
    "hi": "इस प्रश्नका उत्तर देनेके लिये ज्ञानकोशमें जानकारी उपलब्ध नहीं है। इसमें अभी गरुडपुराण-सारोद्धारके "
          "18 अंश हैं (मृत्यु, कर्म, मृत्युके बाद की यात्रा, सत्कर्म और मोक्षके विषयमें)।",
}
LLM_DOWN = {
    "en": "The AI service is temporarily unavailable, so no interpretation could be generated. "
          "The most relevant passages from the knowledge base are shown below.",
    "hi": "एआई सेवा अभी उपलब्ध नहीं है, इसलिये व्याख्या नहीं बन सकी। ज्ञानकोशके सबसे प्रासंगिक अंश नीचे दिये गये हैं।",
}
PASSAGE_ID = re.compile(r"GPS-\d{2}-\d{3}")
# A bracket holding one or more passage IDs: "[GPS-05-055]" or "[GPS-05-055, GPS-01-046]"
CITATION_GROUP = re.compile(r"\[\s*(GPS-\d{2}-\d{3}(?:\s*[,;]\s*GPS-\d{2}-\d{3})*)\s*\]")


@dataclass
class Answer:
    language: str
    answerable: bool
    answer: str
    cited_ids: list[str]
    related_ids: list[str]          # shown when the LLM is down (retrieved, not cited)
    model: str | None
    notice: str | None
    retrieval: dict
    latency_ms: int


def validate_citations(answer: str, cited: list[str], retrieved: list[str]) -> tuple[str, list[str], list[str]]:
    """Keep only citations of passages that were actually retrieved.

    Returns (cleaned answer text, valid cited ids in order, rejected ids).
      * inline markers like [GPS-05-055] or [GPS-05-055, GPS-01-046] are checked ID by ID;
        unknown IDs are dropped from the marker, and an empty marker is removed;
      * IDs used inline but missing from the model's list are added, so text and list agree.
    """
    allowed = set(retrieved)
    inline: list[str] = []

    def rewrite(m: re.Match) -> str:
        ids = PASSAGE_ID.findall(m.group(1))
        inline.extend(ids)
        kept = [i for i in ids if i in allowed]
        return f"[{', '.join(kept)}]" if kept else ""

    cleaned = CITATION_GROUP.sub(rewrite, answer)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:।])", r"\1", cleaned).strip()
    rejected = sorted({i for i in [*cited, *inline] if i not in allowed})
    valid: list[str] = []
    for i in [*cited, *inline]:
        if i in allowed and i not in valid:
            valid.append(i)
    return cleaned, valid, rejected


class AnswerService:
    def __init__(self, retriever: Retriever, llm: LLMRouter):
        self.retriever = retriever
        self.llm = llm

    def answer(self, conn: sqlite3.Connection, question: str, history: list[dict] | None = None) -> Answer:
        start = time.perf_counter()
        language = detect_language(question)
        result = self.retriever.search(question)
        retrieval = {"mode": result.mode, "passed_gate": result.relevant, "reason": result.reason,
                     "best_cosine": round(result.best_cosine, 3), "best_bm25": round(result.best_bm25, 2),
                     "retrieved": [{"id": p.id, "cosine": round(p.cosine, 3), "bm25": round(p.bm25, 2)}
                                   for p in result.passages]}

        def done(**kw) -> Answer:
            return Answer(language=language, retrieval=retrieval,
                          latency_ms=int((time.perf_counter() - start) * 1000), **kw)

        # Layer 1: nothing relevant -> refuse without calling the LLM.
        if not result.relevant:
            return done(answerable=False, answer=NOT_FOUND[language], cited_ids=[], related_ids=[],
                        model=None, notice=None)

        passages = db.get_passages_by_ids(conn, result.ids)
        system = build_system_prompt(language)
        user = build_user_prompt(question, language, passages, history)

        # Layer 2: grounded generation, Gemini first, local Ollama as fallback.
        try:
            llm_result, failures = self.llm.generate(system, user)
        except AllProvidersFailed as e:
            logger.error("All LLM providers failed: %s", e)
            return done(answerable=False, answer=LLM_DOWN[language], cited_ids=[], related_ids=result.ids,
                        model=None, notice="llm_unavailable")

        # Layer 3: citations must point at retrieved passages.
        text, cited, rejected = validate_citations(llm_result.answer, llm_result.cited_passage_ids, result.ids)
        if language == "hi":
            text = re.sub(r"(?<=[\u0900-\u097F\]])\s*\|", "।", text)   # ASCII "|" used as danda
        if rejected:
            logger.warning("Removed citations of non-retrieved passages: %s", rejected)
        notice = f"fallback_used:{failures[0].provider}:{failures[0].kind}" if failures else None

        if not llm_result.is_answerable or not cited:
            # An answer with no valid source is not allowed to stand.
            return done(answerable=False, answer=NOT_FOUND[language], cited_ids=[], related_ids=[],
                        model=llm_result.model, notice=notice)
        return done(answerable=True, answer=text, cited_ids=cited, related_ids=[],
                    model=llm_result.model, notice=notice)
