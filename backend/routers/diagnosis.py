"""POST /api/diagnose — AI-powered cluster diagnosis via Claude."""

import json
import logging
import os

import anthropic
from fastapi import APIRouter, HTTPException

from core.anomaly import detect_anomalies
from core.poller import cluster_state
from models.schemas import DiagnosisRequest, DiagnosisResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["diagnosis"])

# Use the canonical alias for claude-sonnet-4-20250514
_MODEL = "claude-sonnet-4-0"

_SYSTEM_PROMPT = """\
You are an expert Kubernetes Site Reliability Engineer.
You will be given a JSON snapshot of a Kubernetes cluster's current state,
including pods, events, detected anomalies, and resource usage.

Respond ONLY with a valid JSON object (no markdown fences) with exactly these keys:
{
  "summary":         "<one-paragraph plain-English overview of cluster health>",
  "rootCause":       "<most likely root cause of the most critical issue, or 'No issues detected' if healthy>",
  "kubectlCommands": ["<cmd1>", "<cmd2>", "<cmd3>"]
}

Rules:
- kubectlCommands must contain exactly 3 actionable kubectl commands relevant to the issues found.
- If no issues are detected, provide 3 useful diagnostic/inspection commands anyway.
- Do not include any text outside the JSON object.
"""


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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY environment variable is not set.",
        )

    cluster_json = _build_cluster_summary(focus=request.focus)

    user_message = f"Analyse this Kubernetes cluster state and respond with the JSON schema described in the system prompt.\n\n{cluster_json}"
    if request.extra_context:
        user_message += f"\n\nAdditional context:\n{json.dumps(request.extra_context, indent=2)}"

    client = anthropic.Anthropic(api_key=api_key)

    try:
        # Use streaming to prevent timeouts on large cluster payloads
        with client.messages.stream(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            response = stream.get_final_message()

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Anthropic rate limit reached — try again later.")
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc.message}")
    except anthropic.APIConnectionError as exc:
        logger.error("Anthropic connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach Anthropic API.")

    # Extract text content
    text_content = next(
        (block.text for block in response.content if block.type == "text"), ""
    )

    try:
        data = json.loads(text_content)
    except json.JSONDecodeError:
        logger.error("Claude returned non-JSON response: %s", text_content[:500])
        raise HTTPException(
            status_code=502,
            detail="Claude returned an unexpected response format.",
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

    return DiagnosisResponse(
        summary=data["summary"],
        rootCause=data["rootCause"],
        kubectlCommands=kubectl_cmds,
    )
