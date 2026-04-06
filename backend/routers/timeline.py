"""GET /api/timeline — health snapshot history."""

from fastapi import APIRouter, Query

from core.database import get_timeline

router = APIRouter(tags=["timeline"])


@router.get("/timeline")
async def timeline(
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to return"),
) -> list[dict]:
    """Return health snapshots from the last N hours (default 24), oldest first."""
    return get_timeline(hours=hours)
