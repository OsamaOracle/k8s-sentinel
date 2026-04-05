"""GET /api/resources — return node and deployment info from the poller cache."""

from fastapi import APIRouter

from core.poller import cluster_state
from models.schemas import ResourceInfo

router = APIRouter(tags=["resources"])


@router.get("/resources", response_model=ResourceInfo)
async def get_resources() -> dict:
    """Return current node capacity and deployment replica counts."""
    resources: dict = cluster_state.get("resources", {})
    # Ensure both keys are present so the schema validation passes
    return {
        "nodes": resources.get("nodes", []),
        "deployments": resources.get("deployments", []),
    }
