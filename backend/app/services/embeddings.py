"""Multilingual sentence embeddings (intfloat/multilingual-e5-small, runs locally).

e5 models are trained with role prefixes: documents must be embedded as "passage: ..."
and questions as "query: ...". Leaving the prefixes out noticeably hurts retrieval.
Vectors are L2-normalised, so a dot product equals cosine similarity.
"""
from functools import lru_cache

import numpy as np


class Embedder:
    def __init__(self, model_name: str):
        # Imported lazily: loading torch takes a few seconds and tests can avoid it.
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @property
    def max_tokens(self) -> int:
        return self.model.max_seq_length

    def token_count(self, text: str) -> int:
        return len(self.model.tokenizer(text)["input_ids"])

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        return vecs.astype(np.float32)


@lru_cache
def get_embedder(model_name: str) -> Embedder:
    """One shared model instance per process (loading it is the slow part)."""
    return Embedder(model_name)


def passage_embedding_text(p: dict) -> str:
    """What gets embedded for a passage.

    Keywords and chapter title come first so they survive the model's 512-token limit.
    Both translations are included: English matches English questions, and the Hindi
    gives Hindi questions a same-language match. Sanskrit is left out — the model was
    not trained on much Sanskrit, and it would mostly use up tokens.
    """
    return " | ".join([
        ", ".join(p["keywords"]),
        p["chapter_title"],
        p["english"],
        p["hindi"],
    ])
