"""POST /api/report/generate + GET /api/report/history — incident report generator."""

import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.anomaly import detect_anomalies
from core.database import get_diagnosis_history, get_report_history, get_timeline, insert_report
from core.llm import get_llm_provider
from core.poller import cluster_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["report"])

_REPORT_SYSTEM = """\
You are a senior Site Reliability Engineer writing a formal incident report.
Use the real cluster data provided to fill every section — do not invent
events, times, or metrics that are not in the input. Respond ONLY with the
markdown report (no code fences around the whole document, no prose before or
after). Follow the exact structure requested by the user.
"""

_ALLOWED_SEVERITIES = {"P1", "P2", "P3"}


class ReportRequest(BaseModel):
    incident_title: str = Field(min_length=1, max_length=200)
    severity: str = Field(pattern="^(P1|P2|P3)$")
    reported_by: str | None = Field(default=None, max_length=120)


class ReportResponse(BaseModel):
    markdown: str
    generated_at: str


class ReportHistoryItem(BaseModel):
    id: int
    timestamp: str
    title: str
    severity: str
    reported_by: str | None = None
    markdown: str
    generated_at: str


def _summarise_timeline(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {"min": None, "avg": None, "max": None, "sample_count": 0}
    scores = [s["score"] for s in snapshots]
    return {
        "min": min(scores),
        "avg": round(sum(scores) / len(scores)),
        "max": max(scores),
        "sample_count": len(scores),
    }


def _build_report_prompt(title: str, severity: str, reported_by: str | None) -> str:
    pods = cluster_state.get("pods", [])
    events = cluster_state.get("events", [])
    anomalies = detect_anomalies(cluster_state)

    snapshots = get_timeline(hours=24)
    diagnoses = get_diagnosis_history(limit=10)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    context = {
        "incident_title": title,
        "severity": severity,
        "reported_by": reported_by or "unknown",
        "date": today,
        "current_time_utc": datetime.now(timezone.utc).isoformat(),
        "health_score_stats": _summarise_timeline(snapshots),
        "health_snapshots_last_24h": snapshots,
        "recent_diagnoses": diagnoses,
        "current_pods": [
            {
                "name": p.get("name"),
                "namespace": p.get("namespace"),
                "phase": p.get("phase"),
                "reason": p.get("reason"),
                "restart_count": p.get("restart_count", 0),
            }
            for p in pods
        ],
        "recent_warning_events": [
            e for e in events if e.get("type") == "Warning"
        ][:30],
        "current_anomalies": anomalies,
    }

    return f"""Generate an incident report using EXACTLY this markdown structure:

# Incident Report: {title}
**Date:** {today}
**Severity:** {severity}
**Reported by:** {reported_by or "unknown"}
**Status:** Resolved / Ongoing

## Summary
2-3 sentence summary of what happened.

## Timeline
| Time | Event |
|------|-------|
| HH:MM | ... |

Build the timeline from health snapshots and events in the data. Use UTC HH:MM.

## Impact
Which namespaces and pods were affected, how many restarts, and the lowest
health score during the window.

## Root Cause
Draw from the most recent diagnosis record when available.

## Remediation Steps
List the kubectl commands from the recent diagnosis records as a bulleted list
of code-fenced commands.

## Prevention
3 specific recommendations to prevent recurrence, informed by the actual
failure pattern.

## Health Score Timeline
Min: X | Avg: X | Max: X during the incident window.

---
Cluster data (JSON):
{json.dumps(context, default=str, indent=2)}
"""


@router.post("/report/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest) -> ReportResponse:
    if request.severity not in _ALLOWED_SEVERITIES:
        raise HTTPException(status_code=400, detail="Severity must be one of P1, P2, P3.")

    try:
        provider = get_llm_provider()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    prompt = _build_report_prompt(request.incident_title, request.severity, request.reported_by)

    try:
        markdown = await provider.complete(
            _REPORT_SYSTEM,
            [{"role": "user", "content": prompt}],
        )
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API error %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("LLM connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach LLM API.")

    markdown = markdown.strip()
    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        insert_report(
            title=request.incident_title,
            severity=request.severity,
            reported_by=request.reported_by,
            markdown=markdown,
        )
    except Exception:
        logger.exception("Failed to persist generated report")

    return ReportResponse(markdown=markdown, generated_at=generated_at)


@router.get("/report/history", response_model=list[ReportHistoryItem])
async def report_history(limit: int = 20) -> list[ReportHistoryItem]:
    limit = max(1, min(100, limit))
    rows = get_report_history(limit=limit)
    return [ReportHistoryItem(**row) for row in rows]
