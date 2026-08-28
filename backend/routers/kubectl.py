"""POST /api/kubectl/translate + POST /api/kubectl/execute.

Natural-language kubectl translation and gated execution.
"""

import json
import logging
import os
import shlex
import subprocess

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.llm import get_llm_provider
from core.poller import cluster_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["kubectl"])

_DEV_MODE = os.environ.get("DEV_MODE", "false").strip().lower() == "true"

_TRANSLATE_SYSTEM = """\
You are a senior Kubernetes SRE. Convert the user's plain-English request into
one or more kubectl commands, using the provided cluster state to resolve
ambiguous names (namespaces, deployments, pods).

Respond ONLY with a valid JSON object — no markdown fences, no prose outside
the object — with exactly these keys:

{
  "commands":    ["kubectl ...", "kubectl ..."],
  "explanation": "<plain-English explanation of what the commands do>",
  "risk":        "low|medium|high",
  "risk_reason": "<why this risk level>"
}

Rules:
- commands MUST be a non-empty array of shell-safe kubectl commands.
- Never suggest destructive commands (delete namespace, delete secret, exec, rm, port-forward).
- If the request is destructive or unsafe, still return a JSON object but set risk="high"
  and put a warning in risk_reason. Prefer read-only alternatives when possible.
- Risk levels: low = read-only (get/describe/logs), medium = scale/rollout/patch, high = anything
  that changes cluster state in a way that could cause outages.
"""

_DANGEROUS_TOKENS = {"exec", "port-forward", "rm"}
_DANGEROUS_DELETE_TARGETS = {"secret", "secrets", "namespace", "namespaces", "ns"}


class TranslateRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class TranslateResponse(BaseModel):
    commands: list[str]
    explanation: str
    risk: str
    risk_reason: str


class ExecuteRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


class ExecuteResponse(BaseModel):
    command: str
    stdout: str
    stderr: str
    exit_code: int
    success: bool


def _build_cluster_context() -> str:
    """Compact JSON snapshot for the translation prompt."""
    pods = cluster_state.get("pods", [])
    resources = cluster_state.get("resources", {})
    namespaces = sorted({p.get("namespace") for p in pods if p.get("namespace")})
    payload = {
        "namespaces": namespaces,
        "pods": [
            {"name": p.get("name"), "namespace": p.get("namespace"), "phase": p.get("phase")}
            for p in pods
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
    }
    return json.dumps(payload, default=str, indent=2)


def _validate_command(command: str) -> tuple[bool, str]:
    """Return (allowed, reason). Reason is empty when allowed."""
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return False, f"Could not parse command: {exc}"

    if not tokens:
        return False, "Empty command."
    if tokens[0] != "kubectl":
        return False, "Only 'kubectl' commands are allowed."

    lowered = [t.lower() for t in tokens]
    for banned in _DANGEROUS_TOKENS:
        if banned in lowered:
            return False, f"Blocked: '{banned}' is not permitted."

    if "delete" in lowered:
        for i, tok in enumerate(lowered):
            if tok == "delete":
                for follow in lowered[i + 1 :]:
                    if follow.startswith("-"):
                        continue
                    if follow in _DANGEROUS_DELETE_TARGETS:
                        return False, f"Blocked: 'delete {follow}' is not permitted."
                    break
    return True, ""


@router.post("/kubectl/translate", response_model=TranslateResponse)
async def translate_kubectl(request: TranslateRequest) -> TranslateResponse:
    try:
        provider = get_llm_provider()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    context = _build_cluster_context()
    user_prompt = (
        f"Cluster state (JSON):\n{context}\n\n"
        f"User instruction: {request.instruction.strip()}"
    )

    try:
        raw = await provider.complete(
            _TRANSLATE_SYSTEM,
            [{"role": "user", "content": user_prompt}],
        )
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API error %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("LLM connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach LLM API.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON response: %s", raw[:500])
        raise HTTPException(status_code=502, detail="LLM returned an unexpected response format.")

    missing = [k for k in ("commands", "explanation", "risk", "risk_reason") if k not in data]
    if missing:
        raise HTTPException(status_code=502, detail=f"LLM response missing fields: {missing}")

    commands = data["commands"]
    if not isinstance(commands, list) or not commands:
        raise HTTPException(status_code=502, detail="LLM response contained no commands.")

    return TranslateResponse(
        commands=[str(c) for c in commands],
        explanation=str(data["explanation"]),
        risk=str(data["risk"]).lower(),
        risk_reason=str(data["risk_reason"]),
    )


@router.post("/kubectl/execute", response_model=ExecuteResponse)
async def execute_kubectl(request: ExecuteRequest) -> ExecuteResponse:
    command = request.command.strip()
    allowed, reason = _validate_command(command)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)

    if _DEV_MODE:
        return ExecuteResponse(
            command=command,
            stdout=f"[DEV_MODE] Simulated execution of: {command}\ndeployment.apps/example scaled",
            stderr="",
            exit_code=0,
            success=True,
        )

    try:
        tokens = shlex.split(command)
        proc = subprocess.run(
            tokens,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out after 30 seconds.")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="kubectl binary not found on the server.")
    except Exception as exc:
        logger.exception("kubectl execution failed")
        raise HTTPException(status_code=500, detail=f"Execution error: {exc}")

    return ExecuteResponse(
        command=command,
        stdout=proc.stdout,
        stderr=proc.stderr,
        exit_code=proc.returncode,
        success=proc.returncode == 0,
    )
