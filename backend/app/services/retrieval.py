"""Hybrid retrieval over the knowledge base: BM25 keywords + semantic embeddings, fused by RRF.

Why both:
  * semantic (e5 embeddings) matches meaning and works across languages — a Hindi question
    finds English text, "soul" finds "jīva" / "the Self";
  * BM25 matches exact rare words — proper names like Vaitaraṇī, Yama, Bahubhīti.
Reciprocal Rank Fusion combines the two ranked lists using ranks only, so we never have to
balance cosine scores (~0.7-0.9) against BM25 scores (0-20+).

The relevance gate decides whether the knowledge base covers the question at all. If it does
not, the API answers "not in the knowledge base" without calling the LLM.
"""
from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np
from rank_bm25 import BM25Okapi

from app.services.embeddings import passage_embedding_text
from app.services.language import tokenize

Mode = Literal["bm25", "semantic", "hybrid"]
RRF_K = 60  # standard constant from the RRF paper (Cormack et al., 2009)


@dataclass
class ScoredPassage:
    id: str
    score: float            # score used for the final ranking (RRF for hybrid)
    cosine: float           # semantic similarity, always reported
    bm25: float             # keyword score, always reported
    semantic_rank: int
    bm25_rank: int | None   # None = no keyword overlap at all


@dataclass
class RetrievalResult:
    query: str
    mode: Mode
    passages: list[ScoredPassage]
    best_cosine: float
    best_bm25: float
    relevant: bool                          # passed the relevance gate?
    reason: str = ""
    all_ranked: list[ScoredPassage] = field(default_factory=list, repr=False)

    @property
    def ids(self) -> list[str]:
        return [p.id for p in self.passages]


class Retriever:
    def __init__(self, passages: list[dict], matrix: np.ndarray, embed_query: Callable[[str], np.ndarray],
                 semantic_threshold: float, bm25_threshold: float, top_k: int = 4,
                 strong_semantic_threshold: float = 0.85):
        """passages: dicts with id/keywords/chapter_title/english/hindi, in the same order as matrix rows."""
        self.ids = [p["id"] for p in passages]
        self.matrix = matrix
        self.embed_query = embed_query
        self.semantic_threshold = semantic_threshold
        self.strong_semantic_threshold = strong_semantic_threshold
        self.bm25_threshold = bm25_threshold
        self.top_k = top_k
        # BM25 indexes the same text that was embedded (keywords + title + English + Hindi).
        self.bm25 = BM25Okapi([tokenize(passage_embedding_text(p)) for p in passages])

    def search(self, query: str, mode: Mode = "hybrid", top_k: int | None = None) -> RetrievalResult:
        k = top_k or self.top_k
        cos = self.matrix @ self.embed_query(query)                      # cosine (vectors are normalised)
        terms = tokenize(query)
        bm = np.asarray(self.bm25.get_scores(terms)) if terms else np.zeros(len(self.ids))

        sem_order = np.argsort(-cos)
        sem_rank = {int(i): r for r, i in enumerate(sem_order, start=1)}
        bm_order = [int(i) for i in np.argsort(-bm) if bm[i] > 0]       # only docs sharing a term
        bm_rank = {i: r for r, i in enumerate(bm_order, start=1)}

        if mode == "semantic":
            score = cos
        elif mode == "bm25":
            score = bm
        else:
            score = np.array([1 / (RRF_K + sem_rank[i]) + (1 / (RRF_K + bm_rank[i]) if i in bm_rank else 0)
                              for i in range(len(self.ids))])

        ranked = [ScoredPassage(id=self.ids[i], score=float(score[i]), cosine=float(cos[i]), bm25=float(bm[i]),
                                semantic_rank=sem_rank[i], bm25_rank=bm_rank.get(i))
                  for i in np.argsort(-score)]
        if mode == "bm25":
            ranked = [p for p in ranked if p.bm25 > 0]

        best_cos, best_bm = float(cos.max()), float(bm.max(initial=0.0))
        relevant, reason = self._gate(best_cos, best_bm)
        return RetrievalResult(query=query, mode=mode, passages=ranked[:k] if relevant else [],
                               best_cosine=best_cos, best_bm25=best_bm, relevant=relevant, reason=reason,
                               all_ranked=ranked)

    @classmethod
    def from_db(cls, conn, embed_query: Callable[[str], np.ndarray], semantic_threshold: float,
                bm25_threshold: float, top_k: int = 4, strong_semantic_threshold: float = 0.85) -> "Retriever":
        from app import db

        ids, matrix, _ = db.load_embeddings(conn)
        passages = db.get_passages_by_ids(conn, ids)          # same order as the matrix rows
        return cls(passages, matrix, embed_query, semantic_threshold, bm25_threshold, top_k, strong_semantic_threshold)

    def _gate(self, best_cos: float, best_bm: float) -> tuple[bool, str]:
        """Does the knowledge base cover this question at all?

        e5 gives fairly high similarity to *any* short text in the same language (an off-topic
        Hindi question scores ~0.83 against Hindi passages), so a borderline semantic score
        only counts when at least one meaningful keyword is shared too.
        """
        if best_cos >= self.strong_semantic_threshold:
            return True, f"strong semantic match {best_cos:.3f} >= {self.strong_semantic_threshold}"
        if best_bm >= self.bm25_threshold:
            return True, f"strong keyword match {best_bm:.2f} >= {self.bm25_threshold}"
        if best_cos >= self.semantic_threshold and best_bm > 0:
            return True, f"semantic match {best_cos:.3f} >= {self.semantic_threshold} with keyword support"
        return False, (f"no passage is close enough (best cosine {best_cos:.3f}, best keyword score {best_bm:.2f})")
