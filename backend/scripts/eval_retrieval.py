"""Compare BM25 vs semantic vs hybrid retrieval and calibrate the relevance gate.

Run from backend/:  uv run python scripts/eval_retrieval.py [--write]
  --write  also saves the report to docs/EVAL_RETRIEVAL.md

Metrics (in-scope questions):
  hit@1  - the top passage is one of the relevant ones
  hit@3  - at least one relevant passage is in the top 3
  MRR    - mean of 1/rank of the first relevant passage (1.0 = always first)
Gate (all questions): in-scope must pass, out-of-scope must be refused.
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services.embeddings import get_embedder  # noqa: E402
from app.services.retrieval import Retriever  # noqa: E402

EVAL_PATH = BACKEND_DIR / "tests" / "eval_questions.json"
REPORT_PATH = BACKEND_DIR.parent / "docs" / "EVAL_RETRIEVAL.md"


def first_relevant_rank(ranked_ids: list[str], relevant: set[str]) -> int | None:
    return next((r for r, pid in enumerate(ranked_ids, start=1) if pid in relevant), None)


def main() -> int:
    s = get_settings()
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    embedder = get_embedder(s.embedding_model)
    with db.connection(s.db_file) as conn:
        retriever = Retriever.from_db(conn, embedder.embed_query, s.semantic_threshold, s.bm25_threshold, s.top_k,
                                      s.strong_semantic_threshold)

    lines: list[str] = ["# Retrieval evaluation", "",
                        f"Knowledge base: {len(retriever.ids)} passages · embedding model `{s.embedding_model}` · "
                        f"{len(data['in_scope'])} in-scope and {len(data['out_of_scope'])} out-of-scope questions "
                        f"(`backend/tests/eval_questions.json`).", ""]

    # ---- 1. ranking quality per mode ------------------------------------------------------
    lines += ["## Ranking quality (in-scope questions)", "",
              "| Method | hit@1 | hit@3 | MRR | English hit@3 | Hindi hit@3 |", "|---|---|---|---|---|---|"]
    per_question: dict[str, dict] = {}
    for mode in ("bm25", "semantic", "hybrid"):
        h1 = h3 = mrr = 0.0
        by_lang = {"en": [0, 0], "hi": [0, 0]}
        for item in data["in_scope"]:
            res = retriever.search(item["q"], mode=mode, top_k=len(retriever.ids))
            ranked = [p.id for p in res.all_ranked]
            rank = first_relevant_rank(ranked, set(item["relevant"]))
            h1 += rank == 1
            h3 += rank is not None and rank <= 3
            mrr += 1 / rank if rank else 0
            lang = "en" if item["lang"] == "en" else "hi"
            by_lang[lang][0] += rank is not None and rank <= 3
            by_lang[lang][1] += 1
            per_question.setdefault(item["q"], {})[mode] = (rank, ranked[:3])
        n = len(data["in_scope"])
        lines.append(f"| {mode} | {h1 / n:.0%} | {h3 / n:.0%} | {mrr / n:.2f} | "
                     f"{by_lang['en'][0]}/{by_lang['en'][1]} | {by_lang['hi'][0]}/{by_lang['hi'][1]} |")

    lines += ["", "Rank of the first relevant passage per question (– = not retrieved by that method):", "",
              "| Question | BM25 | Semantic | Hybrid | Hybrid top 3 |", "|---|---|---|---|---|"]
    for q, modes in per_question.items():
        cells = [str(modes[m][0] or "–") for m in ("bm25", "semantic", "hybrid")]
        lines.append(f"| {q} | {' | '.join(cells)} | {', '.join(modes['hybrid'][1])} |")

    # ---- 2. relevance gate -----------------------------------------------------------------
    rows, ins, outs = [], [], []
    per_round = {1: [0, 0], 2: [0, 0]}
    for kind, items in (("in-scope", data["in_scope"]), ("out-of-scope", data["out_of_scope"])):
        for item in items:
            res = retriever.search(item["q"])
            ok = res.relevant if kind == "in-scope" else not res.relevant
            (ins if kind == "in-scope" else outs).append(res)
            per_round[item.get("round", 1)][0] += ok
            per_round[item.get("round", 1)][1] += 1
            rows.append(f"| {item.get('round', 1)} | {kind} | {item['q']} | {res.best_cosine:.3f} | {res.best_bm25:.2f} | "
                        f"{'pass' if res.relevant else 'refuse'} | {'✅' if ok else '❌'} |")
    min_in = min(r.best_cosine for r in ins)
    max_out = max(r.best_cosine for r in outs)
    max_out_bm = max(r.best_bm25 for r in outs)
    correct = sum(r.relevant for r in ins) + sum(not r.relevant for r in outs)

    lines += ["", "## Relevance gate", "",
              f"Current settings: `STRONG_SEMANTIC_THRESHOLD={s.strong_semantic_threshold}`, "
              f"`SEMANTIC_THRESHOLD={s.semantic_threshold}`, `BM25_THRESHOLD={s.bm25_threshold}`. A question passes if "
              f"cosine ≥ strong threshold, or BM25 ≥ its threshold, or cosine ≥ semantic threshold **and** at least one "
              f"keyword is shared (BM25 > 0).", "",
              f"* Lowest best-cosine among in-scope questions: **{min_in:.3f}**",
              f"* Highest best-cosine among out-of-scope questions: **{max_out:.3f}**",
              f"* Highest BM25 score among out-of-scope questions: **{max_out_bm:.2f}**",
              f"* Suggested semantic threshold (midpoint of the gap): **{(min_in + max_out) / 2:.3f}**"
              if min_in > max_out else "* ⚠️ In-scope and out-of-scope scores overlap — the gate alone cannot separate them; "
                                         "the LLM's `is_answerable` check is the second line of defence.",
              f"* Gate decisions correct: **{correct}/{len(ins) + len(outs)}** "
              f"(round 1: {per_round[1][0]}/{per_round[1][1]}, round 2: {per_round[2][0]}/{per_round[2][1]})", "",
              "| Round | Type | Question | Best cosine | Best BM25 | Gate | Correct |", "|---|---|---|---|---|---|---|", *rows, "",
              "_Caveat: thresholds are calibrated on this same small question set, so real-world accuracy will be "
              "somewhat lower. The LLM is instructed to refuse when passages do not answer the question, as a "
              "second safeguard._"]

    report = "\n".join(lines) + "\n"
    print(report)
    if "--write" in sys.argv:
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"Saved {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
