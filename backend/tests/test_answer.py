"""Tests for the /ask pipeline: grounding, citation validation, fallback, input validation.

Fake retriever + fake LLM providers: no model, no network, no API quota.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.answer import NOT_FOUND, AnswerService, validate_citations
from app.services.llm.base import LLMError, LLMResult, parse_result
from app.services.llm.router import AllProvidersFailed, LLMRouter
from app.services.prompts import build_system_prompt, build_user_prompt
from app.services.retrieval import RetrievalResult, ScoredPassage

RETRIEVED = ["GPS-05-055", "GPS-01-046", "GPS-08-101"]


class FakeRetriever:
    def __init__(self, ids=RETRIEVED, relevant=True):
        self.ids, self.relevant = ids, relevant

    def search(self, query, mode="hybrid", top_k=None):
        passages = [ScoredPassage(id=i, score=1.0, cosine=0.83, bm25=2.0, semantic_rank=n, bm25_rank=n)
                    for n, i in enumerate(self.ids, start=1)] if self.relevant else []
        return RetrievalResult(query=query, mode="hybrid", passages=passages, best_cosine=0.83 if self.relevant else 0.7,
                               best_bm25=2.0 if self.relevant else 0.0, relevant=self.relevant,
                               reason="test")


class FakeLLM:
    def __init__(self, name="gemini", result=None, error=None):
        self.name, self.result, self.error, self.calls = name, result, error, 0
        self.last_prompt = None

    def generate(self, system, user):
        self.calls += 1
        self.last_prompt = (system, user)
        if self.error:
            raise LLMError(self.name, self.error)
        return self.result


def ok_result(answer="Karma must be experienced [GPS-05-055].", ids=("GPS-05-055",), model="gemini/test"):
    return LLMResult(True, answer, list(ids), model)


def make_client(settings, retriever=None, providers=None):
    service = AnswerService(retriever or FakeRetriever(), LLMRouter(providers or [FakeLLM(result=ok_result())]))
    return TestClient(create_app(settings, answer_service=service))


# ---------------------------------------------------------------- happy path

def test_ask_returns_grounded_answer_with_verbatim_sources(settings, kb):
    r = make_client(settings).post("/ask", json={"question": "What does Garuda Purana explain about karma?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answerable"] is True and body["language"] == "en"
    assert body["model"] == "gemini/test" and body["notice"] is None
    assert [s["id"] for s in body["sources"]] == ["GPS-05-055"]
    original = next(p for p in kb["passages"] if p["id"] == "GPS-05-055")
    src = body["sources"][0]
    assert src["sanskrit"] == original["sanskrit"] and src["english"] == original["english"]   # from DB, verbatim
    assert src["editions"]["english"]["id"] == "wood1911"
    assert body["answer_label"].startswith("AI interpretation")
    assert len(body["conversation_id"]) == 36


def test_conversation_id_is_echoed(settings):
    cid = "123e4567-e89b-12d3-a456-426614174000"
    body = make_client(settings).post("/ask", json={"question": "karma?", "conversation_id": cid}).json()
    assert body["conversation_id"] == cid


# ---------------------------------------------------------------- grounding layers

def test_gate_refusal_never_calls_the_llm(settings):
    llm = FakeLLM(result=ok_result())
    client = make_client(settings, retriever=FakeRetriever(relevant=False), providers=[llm])
    body = client.post("/ask", json={"question": "Who won the 2011 Cricket World Cup?"}).json()
    assert body["answerable"] is False and body["sources"] == [] and body["model"] is None
    assert body["answer"] == NOT_FOUND["en"]
    assert llm.calls == 0


def test_not_found_message_in_hindi(settings):
    client = make_client(settings, retriever=FakeRetriever(relevant=False))
    body = client.post("/ask", json={"question": "भारत की राजधानी क्या है?"}).json()
    assert body["language"] == "hi" and body["answer"] == NOT_FOUND["hi"]


def test_llm_saying_unanswerable_is_respected(settings):
    llm = FakeLLM(result=LLMResult(False, "Not in the passages.", [], "gemini/test"))
    body = make_client(settings, providers=[llm]).post("/ask", json={"question": "karma and quantum?"}).json()
    assert body["answerable"] is False and body["sources"] == []


def test_invented_citation_is_removed(settings):
    llm = FakeLLM(result=ok_result("Karma persists [GPS-05-055]. Also [GPS-12-345] says more.",
                                   ids=["GPS-05-055", "GPS-12-345"]))
    body = make_client(settings, providers=[llm]).post("/ask", json={"question": "karma?"}).json()
    assert "GPS-12-345" not in body["answer"]
    assert [s["id"] for s in body["sources"]] == ["GPS-05-055"]


def test_answer_with_only_invented_citations_is_rejected(settings):
    llm = FakeLLM(result=ok_result("Yama rules [GPS-12-345].", ids=["GPS-12-345"]))
    body = make_client(settings, providers=[llm]).post("/ask", json={"question": "karma?"}).json()
    assert body["answerable"] is False and body["sources"] == []


def test_answer_with_no_citations_is_rejected(settings):
    llm = FakeLLM(result=ok_result("Karma is important.", ids=[]))
    body = make_client(settings, providers=[llm]).post("/ask", json={"question": "karma?"}).json()
    assert body["answerable"] is False


def test_validate_citations_handles_grouped_brackets():
    text, valid, rejected = validate_citations(
        "A [GPS-05-055, GPS-01-046]. B [GPS-99-001]. C [GPS-08-101; GPS-77-777].", ["GPS-05-055"], RETRIEVED)
    assert text == "A [GPS-05-055, GPS-01-046]. B. C [GPS-08-101]."
    assert valid == ["GPS-05-055", "GPS-01-046", "GPS-08-101"]
    assert rejected == ["GPS-77-777", "GPS-99-001"]


def test_validate_citations_adds_inline_ids_missing_from_list():
    _, valid, _ = validate_citations("X [GPS-08-101].", [], RETRIEVED)
    assert valid == ["GPS-08-101"]


# ---------------------------------------------------------------- fallback

def test_fallback_to_second_provider(settings):
    gemini = FakeLLM("gemini", error="unavailable")
    ollama = FakeLLM("ollama", result=ok_result(model="ollama/qwen2.5:7b"))
    body = make_client(settings, providers=[gemini, ollama]).post("/ask", json={"question": "karma?"}).json()
    assert body["answerable"] is True
    assert body["model"] == "ollama/qwen2.5:7b"
    assert body["notice"] == "fallback_used:gemini:unavailable"
    assert gemini.calls == 1 and ollama.calls == 1


def test_all_providers_down_still_returns_passages(settings):
    providers = [FakeLLM("gemini", error="rate_limited"), FakeLLM("ollama", error="unavailable")]
    r = make_client(settings, providers=providers).post("/ask", json={"question": "karma?"})
    assert r.status_code == 200
    body = r.json()
    assert body["notice"] == "llm_unavailable" and body["answerable"] is False
    assert [p["id"] for p in body["related_passages"]] == RETRIEVED and body["sources"] == []


def test_router_raises_when_everything_fails():
    with pytest.raises(AllProvidersFailed) as e:
        LLMRouter([FakeLLM("a", error="timeout"), FakeLLM("b", error="unavailable")]).generate("s", "u")
    assert [x.kind for x in e.value.errors] == ["timeout", "unavailable"]


def test_parse_result_rejects_malformed_json():
    with pytest.raises(LLMError) as e:
        parse_result({"answer": "x"}, "m", "gemini")
    assert e.value.kind == "bad_output"


def test_service_unavailable_when_not_loaded(settings):
    r = TestClient(create_app(settings)).post("/ask", json={"question": "karma?"})   # no lifespan, no service
    assert r.status_code == 503 and r.json()["error"] == "service_unavailable"


# ---------------------------------------------------------------- input validation

@pytest.mark.parametrize("payload", [
    {},
    {"question": ""},
    {"question": "   "},
    {"question": "a"},
    {"question": "x" * 501},
    {"question": "karma\x00?"},
    {"question": 42},
    {"question": "karma?", "conversation_id": "not-a-uuid"},
])
def test_invalid_input_rejected(settings, payload):
    r = make_client(settings).post("/ask", json=payload)
    assert r.status_code == 422 and r.json()["error"] == "invalid_request"


def test_question_is_trimmed(settings):
    llm = FakeLLM(result=ok_result())
    make_client(settings, providers=[llm]).post("/ask", json={"question": "   karma?   "})
    assert "<<<\nkarma?\n>>>" in llm.last_prompt[1]


# ---------------------------------------------------------------- prompt

def test_prompt_contents(kb):
    passages = kb["passages"][:2]
    user_en = build_user_prompt("What is karma?", "en", passages)
    assert all(f"[{p['id']}]" in user_en for p in passages)
    assert "Hindi translation" not in user_en                     # English answer: no Hindi context
    assert "<<<\nWhat is karma?\n>>>" in user_en                   # question is fenced off as data
    assert "Hindi translation" in build_user_prompt("कर्म?", "hi", passages)
    system = build_system_prompt("hi")
    assert "Hindi" in system and "Never write chapter or verse numbers" in system
