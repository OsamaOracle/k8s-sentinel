"""GET /api/alerts/status — returns which alerting channels are configured."""

import os

from fastapi import APIRouter

router = APIRouter(tags=["alerts"])


@router.get("/alerts/status")
async def alerts_status() -> dict:
    """Return which alerting channels are currently configured."""
    slack = bool(os.environ.get("SLACK_WEBHOOK_URL", "").strip())
    teams = bool(os.environ.get("TEAMS_WEBHOOK_URL", "").strip())
    cooldown = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300"))
    return {
        "slack": slack,
        "teams": teams,
        "cooldown_seconds": cooldown,
    }
