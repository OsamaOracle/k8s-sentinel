"""POST /api/conversation — multi-turn cluster chat backed by the LLM."""

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.anomaly import detect_anomalies
from core.llm import get_llm_provider
from core.poller import cluster_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversation"])

_SYSTEM_PREAMBLE = """\
You are a senior Site Reliability Engineer with full read-only visibility into
the Kubernetes cluster described below. Answer the user's questions accurately
using ONLY the real data provided in the cluster snapshot. Be concise and
direct — no filler. When a question calls for action, suggest the specific
kubectl command that would help. If the snapshot does not contain the answer,
say so plainly instead of guessing.
"""


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class ConversationRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)


class ConversationResponse(BaseModel):
    role: str
    content: str


def _calc_health_score(pods: list[dict], resources: dict) -> int:
    score = 100
    for pod in pods:
        reason = pod.get("reason") or ""
        if reason == "CrashLoopBackOff":
            score -= 15
        elif pod.get("phase") not in ("Running", "Succeeded"):
            score -= 8
        rc = pod.get("restart_count", 0)
        if rc >= 10:
            score -= 10
        elif rc >= 3:
            score -= 5
    for node in resources.get("nodes", []):
        if not node.get("ready", True):
            score -= 20
    return max(0, min(100, score))


def _build_system_prompt() -> str:
    pods = cluster_state.get("pods", [])
    events = cluster_state.get("events", [])
    resources = cluster_state.get("resources", {})
    anomalies = detect_anomalies(cluster_state)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)
    recent_events = []
    for ev in events:
        ts = ev.get("last_timestamp")
        if not ts:
            continue
        try:
            ev_time = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if ev_time >= cutoff:
            recent_events.append(ev)

    snapshot = {
        "current_time_utc": now.isoformat(),
        "health_score": _calc_health_score(pods, resources),
        "pods": [
            {
                "name": p.get("name"),
                "namespace": p.get("namespace"),
                "phase": p.get("phase"),
                "reason": p.get("reason"),
                "restart_count": p.get("restart_count", 0),
                "node": p.get("node"),
            }
            for p in pods
        ],
        "events_last_hour": [
            {
                "reason": e.get("reason"),
                "namespace": e.get("namespace"),
                "message": e.get("message"),
                "type": e.get("type"),
                "count": e.get("count"),
                "last_timestamp": e.get("last_timestamp"),
            }
            for e in recent_events[:80]
        ],
        "nodes": [
            {"name": n.get("name"), "ready": n.get("ready")}
            for n in resources.get("nodes", [])
        ],
        "deployments": [
            {
                "name": d.get("name"),
                "namespace": d.get("namespace"),
                "desired": d.get("desired"),
                "ready": d.get("ready"),
            }
            for d in resources.get("deployments", [])
        ],
        "anomalies": anomalies,
    }

    return f"{_SYSTEM_PREAMBLE}\nCluster snapshot (JSON):\n{json.dumps(snapshot, default=str, indent=2)}"


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest) -> ConversationResponse:
    try:
        provider = get_llm_provider()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    system_prompt = _build_system_prompt()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        answer = await provider.complete(system_prompt, messages)
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API error %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("LLM connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach LLM API.")

    return ConversationResponse(role="assistant", content=answer.strip())
