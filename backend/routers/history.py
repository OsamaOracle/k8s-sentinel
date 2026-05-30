"""GET /api/history — diagnosis history retrieval and search."""

from fastapi import APIRouter

from core.database import get_diagnosis_history, search_diagnosis

router = APIRouter(tags=["history"])


@router.get("/history")
async def get_history(limit: int = 50, search: str = "") -> list[dict]:
    """Return diagnosis history records, newest first.

    Optionally filtered by a search query matched against summary
    and root_cause columns.
    """
    if search.strip():
        return search_diagnosis(search.strip(), limit=limit)
    return get_diagnosis_history(limit=limit)
