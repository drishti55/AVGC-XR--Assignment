"""Validate data/passages.json before ingestion.

Checks the assignment's knowledge-base rules: 15-20 passages, every required field present,
Sanskrit/Hindi really in Devanagari, every source reference resolvable, no leftover placeholders.

Run:  uv run python scripts/validate_kb.py      (exit code 1 on any error)
"""
import json
import re
import sys
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "passages.json"

REQUIRED_PASSAGE_FIELDS = [
    "id", "khanda", "chapter", "chapter_title", "verse_ref_en", "verse_ref_sa",
    "hindi", "english", "hindi_source_id", "english_source_id", "keywords", "topics",
]
REQUIRED_SOURCE_FIELDS = ["id", "title", "translator", "publisher", "languages"]
ID_PATTERN = re.compile(r"^GPS-\d{2}-\d{3}$")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
PLACEHOLDER = re.compile(r"<verbatim|TODO|TBD|lorem", re.IGNORECASE)


def devanagari_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(bool(DEVANAGARI.match(c)) for c in letters) / max(len(letters), 1)


def validate(kb: dict) -> list[str]:
    errors: list[str] = []
    sources = {s.get("id"): s for s in kb.get("sources", [])}
    passages = kb.get("passages", [])

    for s in sources.values():
        for f in REQUIRED_SOURCE_FIELDS:
            if not s.get(f):
                errors.append(f"source {s.get('id')}: missing '{f}'")

    if not 15 <= len(passages) <= 20:
        errors.append(f"expected 15-20 passages, found {len(passages)}")

    seen: set[str] = set()
    for p in passages:
        pid = p.get("id", "<no id>")
        if pid in seen:
            errors.append(f"{pid}: duplicate id")
        seen.add(pid)
        if not ID_PATTERN.match(pid):
            errors.append(f"{pid}: id must look like GPS-02-015")

        for f in REQUIRED_PASSAGE_FIELDS:
            if p.get(f) in (None, "", []):
                errors.append(f"{pid}: missing '{f}'")

        # Sanskrit is optional ("wherever available") but, when present, must be Devanagari + sourced.
        if p.get("sanskrit"):
            if devanagari_ratio(p["sanskrit"]) < 0.9:
                errors.append(f"{pid}: 'sanskrit' is not Devanagari text")
            if not p.get("sanskrit_source_id"):
                errors.append(f"{pid}: 'sanskrit' has no sanskrit_source_id")
        if p.get("hindi") and devanagari_ratio(p["hindi"]) < 0.9:
            errors.append(f"{pid}: 'hindi' is not Devanagari text")
        if p.get("english") and devanagari_ratio(p["english"]) > 0.1:
            errors.append(f"{pid}: 'english' contains Devanagari")

        for f in ("sanskrit_source_id", "hindi_source_id", "english_source_id"):
            if p.get(f) and p[f] not in sources:
                errors.append(f"{pid}: {f} '{p[f]}' is not in sources")

        for f in ("sanskrit", "hindi", "english"):
            if p.get(f) and PLACEHOLDER.search(p[f]):
                errors.append(f"{pid}: '{f}' still contains placeholder text")

        if isinstance(p.get("chapter"), int) and not 1 <= p["chapter"] <= 16:
            errors.append(f"{pid}: chapter {p['chapter']} outside Saroddhara's 16 chapters")

    return errors


def main() -> int:
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    errors = validate(kb)
    if errors:
        print(f"FAILED — {len(errors)} problem(s):")
        for e in errors:
            print("  -", e)
        return 1
    n = len(kb["passages"])
    with_sa = sum(bool(p.get("sanskrit")) for p in kb["passages"])
    print(f"OK — {n} passages, {len(kb['sources'])} sources, Sanskrit present in {with_sa}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
