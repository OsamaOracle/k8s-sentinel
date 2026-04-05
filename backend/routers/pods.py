"""GET /api/pods — return all pods from the shared poller state."""

from fastapi import APIRouter, Query

from core.poller import cluster_state
from models.schemas import PodInfo

router = APIRouter(tags=["pods"])


@router.get("/pods", response_model=list[PodInfo])
async def list_pods(
    namespace: str | None = Query(default=None, description="Filter by namespace"),
) -> list[dict]:
    """Return all pods currently in the poller cache.

    Optionally filter by ``namespace``.
    """
    pods: list[dict] = cluster_state.get("pods", [])
    if namespace:
        pods = [p for p in pods if p.get("namespace") == namespace]
    return pods
