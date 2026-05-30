"""POST /api/diagnose — AI-powered cluster diagnosis."""

import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException

from core.anomaly import detect_anomalies
from core.database import insert_diagnosis
from core.llm import get_llm_provider
from core.poller import cluster_state
from models.schemas import DiagnosisRequest, DiagnosisResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["diagnosis"])


def _build_cluster_summary(focus: str | None = None) -> str:
    """Serialise the poller state and detected anomalies into a prompt payload."""
    pods = cluster_state.get("pods", [])
    events = cluster_state.get("events", [])
    resources = cluster_state.get("resources", {})
    anomalies = detect_anomalies(cluster_state)

    # Keep the payload concise — only Warning events and pod problems
    warning_events = [e for e in events if e.get("type") == "Warning"][:20]
    problem_pods = [
        p for p in pods
        if p.get("phase") not in ("Running", "Succeeded") or p.get("restart_count", 0) >= 3
    ]

    payload: dict = {
        "total_pods": len(pods),
        "problem_pods": problem_pods,
        "warning_events": warning_events,
        "nodes": resources.get("nodes", []),
        "deployments": resources.get("deployments", []),
        "anomalies": anomalies,
    }

    if focus:
        payload["focus"] = focus

    return json.dumps(payload, default=str, indent=2)


@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(request: DiagnosisRequest) -> DiagnosisResponse:
    """Analyse current cluster state and return an AI-generated diagnosis.

    Uses Claude to produce a plain-English summary, root-cause analysis,
    and three actionable ``kubectl`` remediation commands.
    """
    if not cluster_state.get("last_updated"):
        raise HTTPException(
            status_code=503,
            detail="Cluster state not yet available — poller may still be starting.",
        )

    cluster_json = _build_cluster_summary(focus=request.focus)

    prompt = f"Analyse this Kubernetes cluster state and respond with the JSON schema described in the system prompt.\n\n{cluster_json}"
    if request.extra_context:
        prompt += f"\n\nAdditional context:\n{json.dumps(request.extra_context, indent=2)}"

    try:
        provider = get_llm_provider()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        response_text = await provider.diagnose(prompt)
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API error %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("LLM connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach LLM API.")

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON response: %s", response_text[:500])
        raise HTTPException(
            status_code=502,
            detail="LLM returned an unexpected response format.",
        )

    # Validate required keys
    missing = [k for k in ("summary", "rootCause", "kubectlCommands") if k not in data]
    if missing:
        raise HTTPException(
            status_code=502,
            detail=f"Claude response missing fields: {missing}",
        )

    kubectl_cmds: list[str] = data["kubectlCommands"]
    if not isinstance(kubectl_cmds, list):
        kubectl_cmds = [str(kubectl_cmds)]
    kubectl_cmds = kubectl_cmds[:3]  # Enforce maximum of 3

    # Persist to history
    try:
        anomalies = detect_anomalies(cluster_state)
        pods = cluster_state.get("pods", [])
        insert_diagnosis(
            focus=request.focus,
            summary=data["summary"],
            root_cause=data["rootCause"],
            kubectl_commands=kubectl_cmds,
            anomaly_count=len(anomalies),
            pod_count=len(pods),
        )
    except Exception:
        logger.exception("Failed to persist diagnosis to history")

    return DiagnosisResponse(
        summary=data["summary"],
        rootCause=data["rootCause"],
        kubectlCommands=kubectl_cmds,
    )


@router.get("/diagnose/auto-status")
async def auto_diagnosis_status() -> dict:
    """Return the current auto-diagnosis trigger state."""
    trigger = cluster_state.get(
        "auto_diagnosis_trigger",
        {"should_trigger": False, "triggered_at": None, "anomaly_snapshot": []},
    )
    anomalies = detect_anomalies(cluster_state)
    return {
        "should_trigger": trigger.get("should_trigger", False),
        "last_triggered_at": trigger.get("triggered_at"),
        "anomaly_count": len(anomalies),
    }
