"""GET /api/events and GET /api/events/stream (SSE)."""

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from core.poller import cluster_state
from models.schemas import EventInfo

router = APIRouter(tags=["events"])

_SSE_INTERVAL = 5  # seconds between SSE pushes


@router.get("/events", response_model=list[EventInfo])
async def list_events(
    namespace: str | None = Query(default=None, description="Filter by namespace"),
    event_type: str | None = Query(
        default=None,
        alias="type",
        description="Filter by type: Normal or Warning",
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Max events to return"),
) -> list[dict]:
    """Return the most-recent cluster events from the poller cache.

    Supports optional filtering by ``namespace`` and ``type``.
    """
    events: list[dict] = cluster_state.get("events", [])

    if namespace:
        events = [e for e in events if e.get("namespace") == namespace]
    if event_type:
        events = [e for e in events if e.get("type") == event_type]

    return events[:limit]


async def _event_generator(namespace: str | None) -> AsyncGenerator[dict, None]:
    """Yield SSE messages whenever the poller refreshes the event list."""
    last_sent: float = 0.0

    while True:
        current_update: float = cluster_state.get("last_updated") or 0.0

        if current_update > last_sent:
            last_sent = current_update
            events: list[dict] = cluster_state.get("events", [])
            if namespace:
                events = [e for e in events if e.get("namespace") == namespace]

            yield {
                "event": "events",
                "data": json.dumps(events),
                "id": str(int(current_update)),
            }

        await asyncio.sleep(_SSE_INTERVAL)


@router.get("/events/stream")
async def stream_events(
    namespace: str | None = Query(default=None, description="Filter by namespace"),
):
    """Server-Sent Events stream that pushes updated events every poll cycle.

    Clients should connect with ``Accept: text/event-stream``.
    """
    return EventSourceResponse(_event_generator(namespace))
