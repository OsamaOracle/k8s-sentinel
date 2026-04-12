"""GET /api/pods — return all pods from the shared poller state.
GET /api/pods/{namespace}/{pod_name}/logs — tail pod logs.
"""

import os
import textwrap
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from core.poller import DEV_MODE, cluster_state
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


@router.get("/pods/{namespace}/{pod_name}/logs")
async def get_pod_logs(
    namespace: str,
    pod_name: str,
    lines: int = Query(default=100, ge=1, le=5000, description="Number of log lines to return"),
    previous: bool = Query(default=False, description="Return logs from the previous (terminated) container"),
) -> dict:
    """Return the last N lines of logs for a pod container.

    In DEV_MODE returns realistic mock log lines including ERROR/WARN entries.
    """
    if DEV_MODE:
        log_text = _mock_logs(pod_name, namespace, lines)
    else:
        try:
            from core.k8s_client import get_core_v1
            core = get_core_v1()
            log_text = core.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=lines,
                previous=previous,
            ) or ""
        except Exception as exc:
            return {
                "pod": pod_name,
                "namespace": namespace,
                "lines": lines,
                "previous": previous,
                "logs": f"Error fetching logs: {exc}",
            }

    return {
        "pod": pod_name,
        "namespace": namespace,
        "lines": lines,
        "previous": previous,
        "logs": log_text,
    }


# ---------------------------------------------------------------------------
# Mock log generation (DEV_MODE only)
# ---------------------------------------------------------------------------

_INFO_LINES = [
    "Starting container initialization",
    "Loading configuration from /etc/config/app.yaml",
    "Connected to database at postgres:5432",
    "HTTP server listening on :8080",
    "Health check endpoint registered at /healthz",
    "Metrics exporter initialized on :9090",
    "Cache warmed up with 1024 entries",
    "Worker pool started with 8 goroutines",
    "Reconcile loop started, interval=30s",
    "Received request: GET /api/v1/status 200 OK 2ms",
    "Received request: POST /api/v1/jobs 201 Created 18ms",
    "Lease acquired, this instance is leader",
    "Configuration hot-reload triggered",
    "Batch processed: 256 records in 340ms",
    "Checkpoint saved at offset 4096",
    "TLS certificate loaded, expires 2027-01-01",
    "gRPC server listening on :50051",
    "Shutdown signal received, draining connections",
]

_DEBUG_LINES = [
    "Cache hit for key: session:a3f2b1",
    "Spawning worker for task-id=9921",
    "DB query took 4ms: SELECT * FROM jobs LIMIT 50",
    "Polling interval elapsed, triggering sync",
    "Heartbeat sent to leader",
    "Token refreshed, next expiry in 3600s",
    "Received ping from peer node-01",
]

_WARN_LINES = [
    "Memory usage at 78% of configured limit — consider increasing resources",
    "Slow query detected: SELECT aggregation took 820ms",
    "Retry attempt 2/3 for downstream service api-gateway",
    "Circuit breaker is in half-open state",
    "Connection pool exhausted, queuing request",
    "Disk usage above 80% threshold on /data",
    "Rate limit approaching: 850/1000 requests used",
]

_ERROR_LINES = [
    "ERROR: Failed to connect to upstream: connection refused (redis:6379)",
    "FATAL: Out of memory — container exceeded limit of 512Mi",
    "ERROR: Unhandled exception in request handler: nil pointer dereference",
    "ERROR: Failed to parse response body: unexpected EOF",
    "ERROR: CrashLoopBackOff — container exiting with code 1",
    "ERROR: Volume mount failed: no such file or directory /mnt/data",
    "ERROR: TLS handshake timeout after 10s",
]

_CRASH_LINES = [
    "ERROR: panic: runtime error: index out of range [5] with length 3",
    "goroutine 1 [running]:",
    "main.processJob(0xc000124000, 0x5)",
    "\t/src/main.go:142 +0x2f3",
    "ERROR: Container exited with code 1",
    "ERROR: Back-off restarting failed container",
]


def _mock_logs(pod_name: str, namespace: str, n: int) -> str:
    """Generate n realistic log lines for DEV_MODE."""
    import random  # local import so it only loads when needed
    rng = random.Random(hash(pod_name + namespace) & 0xFFFFFFFF)

    is_crashing = "model-trainer" in pod_name
    is_degraded = "etl-processor" in pod_name

    lines: list[str] = []
    now = datetime.now(timezone.utc)

    # Work backwards in time from now
    seconds_back = n * 3  # roughly 3 seconds per log line
    start_ts = now.timestamp() - seconds_back

    for i in range(n):
        ts = datetime.fromtimestamp(start_ts + i * (seconds_back / max(n - 1, 1)), tz=timezone.utc)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"

        if is_crashing and i >= n - 6:
            # Last 6 lines show crash trace
            crash_line = _CRASH_LINES[i - (n - 6)]
            lines.append(f"{ts_str}  {crash_line}")
        else:
            roll = rng.random()
            if is_crashing and roll < 0.25:
                msg = rng.choice(_ERROR_LINES)
            elif is_degraded and roll < 0.15:
                msg = rng.choice(_ERROR_LINES)
                if roll < 0.30:
                    msg = rng.choice(_WARN_LINES)
            elif roll < 0.05:
                msg = rng.choice(_ERROR_LINES)
            elif roll < 0.15:
                msg = rng.choice(_WARN_LINES)
            elif roll < 0.30:
                msg = f"DEBUG  {rng.choice(_DEBUG_LINES)}"
            else:
                msg = f"INFO   {rng.choice(_INFO_LINES)}"

            lines.append(f"{ts_str}  {msg}")

    return "\n".join(lines)
