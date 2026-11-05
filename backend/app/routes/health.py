"""GET /health — is the backend up, and are its dependencies usable?"""
import httpx
from fastapi import APIRouter, Depends

from app import db
from app.config import Settings
from app.deps import get_settings_dep
from app.schemas import HealthOut

router = APIRouter(tags=["system"])


def _ollama_status(base_url: str) -> str:
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=1.0)   # short timeout: health must stay fast
        return "reachable" if r.status_code == 200 else "error"
    except httpx.HTTPError:
        return "unreachable"


@router.get("/health", response_model=HealthOut, summary="Backend health check")
def health(settings: Settings = Depends(get_settings_dep)):
    database, passages = "missing", 0
    if settings.db_file.exists():
        try:
            with db.connection(settings.db_file) as conn:
                passages = db.count_passages(conn)
            database = "ok"
        except Exception:
            database = "error"

    llm = {
        # Only report whether a key is set — never the key itself.
        "gemini": "configured" if settings.gemini_api_key else "not_configured",
        "ollama": _ollama_status(settings.ollama_base_url),
    }
    usable_llm = llm["gemini"] == "configured" or llm["ollama"] == "reachable"
    status = "ok" if database == "ok" and passages > 0 and usable_llm else "degraded"
    return {"status": status, "database": database, "passages": passages, "llm": llm}
