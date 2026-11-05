"""Unit tests for language handling and hybrid retrieval (fake embedder, no model)."""
import numpy as np
import pytest

from app.services.language import detect_language, tokenize
from app.services.retrieval import Retriever


# ---------------------------------------------------------------- language

@pytest.mark.parametrize("text, lang", [
    ("What does Garuda Purana explain about karma?", "en"),
    ("गरुड़ पुराण में कर्म के बारे में क्या बताया गया है?", "hi"),
    ("Garuda Purana में कर्म क्या है?", "hi"),            # mixed, mostly Devanagari
    ("garuda puran mein karma kya hai", "en"),           # romanised Hindi -> treated as English
    ("?!", "en"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_tokenize_keeps_devanagari_words_whole():
    # \w+ would split "कर्म" at the vowel sign / virama — the tokenizer must not.
    assert "कर्म" in tokenize("कर्म")
    assert "आत्मा" in tokenize("आत्मा अजर-अमर है")


def test_tokenize_strips_joined_hindi_postpositions():
    assert tokenize("कर्मोंके") == ["कर्म"]
    assert tokenize("कर्मफलका") == ["कर्मफल"]


def test_tokenize_splits_on_danda_and_drops_verse_numbers():
    assert tokenize("शुभाशुभम्॥ ५७॥") == ["शुभाशुभम्"]


def test_tokenize_english_light_stemming_and_stopwords():
    assert tokenize("Why do people suffer?") == ["people", "suffer"]
    assert tokenize("must be suffered") == ["must", "suffer"]
    assert tokenize("the deeds") == ["deed"]
    assert tokenize("What does the Garuda Purana say?") == []


def test_tokenize_ignores_zero_width_characters():
    assert tokenize("भगवान्‌ने") == tokenize("भगवान्ने")


# ---------------------------------------------------------------- retrieval

PASSAGES = [
    {"id": "A", "keywords": ["vaitarani", "river"], "chapter_title": "The Way of Yama",
     "english": "The Vaitarani river of blood.", "hindi": "वैतरणी नदी"},
    {"id": "B", "keywords": ["karma"], "chapter_title": "Signs of Sins",
     "english": "Karma must be suffered.", "hindi": "कर्म का फल"},
    {"id": "C", "keywords": ["liberation"], "chapter_title": "The Law for Liberation",
     "english": "Liberation is by knowledge alone.", "hindi": "ज्ञान से मोक्ष"},
]
# Orthonormal passage vectors: a query vector's cosine with each passage = its component.
MATRIX = np.eye(3, dtype=np.float32)


def make(query_vectors: dict[str, list[float]], **kw) -> Retriever:
    def embed(q: str) -> np.ndarray:
        v = np.asarray(query_vectors[q], dtype=np.float32)
        return v / np.linalg.norm(v)
    return Retriever(PASSAGES, MATRIX, embed, semantic_threshold=kw.get("t", 0.80),
                     bm25_threshold=kw.get("bm", 6.0), top_k=2, strong_semantic_threshold=kw.get("strong", 0.85))


def test_semantic_mode_orders_by_cosine():
    r = make({"q": [0.2, 0.9, 0.1]}, t=0.0, strong=0.0)
    assert r.search("q", mode="semantic").ids[0] == "B"


def test_bm25_mode_only_returns_passages_sharing_a_term():
    r = make({"vaitarani": [0.1, 0.1, 0.99]})
    res = r.search("vaitarani", mode="bm25", top_k=3)
    assert [p.id for p in res.all_ranked] == ["A"]


def test_hybrid_combines_both_signals():
    # Semantic prefers C slightly, but only A contains the keyword: RRF puts A first.
    r = make({"vaitarani": [0.85, 0.1, 0.9]}, t=0.0, strong=0.0)   # ranking test: gate disabled
    res = r.search("vaitarani", mode="hybrid")
    assert res.ids[0] == "A"
    assert res.passages[0].bm25 > 0 and res.passages[0].bm25_rank == 1


def test_top_k_limits_results():
    r = make({"karma": [0.6, 0.9, 0.5]}, t=0.0, strong=0.0)
    assert len(r.search("karma").passages) == 2


def test_gate_refuses_borderline_semantic_without_keywords():
    # Like the real Hindi weather question: cosine 0.83 (borderline) but no shared keyword.
    r = make({"weather today": [0.83, 0.40, 0.39]})
    res = r.search("weather today")
    assert 0.80 <= res.best_cosine < 0.85 and res.best_bm25 == 0
    assert not res.relevant and res.passages == []


def test_gate_accepts_borderline_semantic_with_keyword_support():
    r = make({"karma": [0.45, 0.83, 0.33]})
    res = r.search("karma")
    assert 0.80 <= res.best_cosine < 0.85 and res.best_bm25 > 0
    assert res.relevant and res.ids[0] == "B"


def test_gate_accepts_strong_semantic_alone():
    r = make({"why do beings suffer": [0.1, 0.99, 0.1]})
    res = r.search("why do beings suffer")
    assert res.best_cosine >= 0.85 and res.relevant


def test_gate_refuses_clearly_unrelated():
    r = make({"cricket world cup": [0.55, 0.55, 0.55]})
    res = r.search("cricket world cup")
    assert not res.relevant and res.passages == [] and "no passage" in res.reason
