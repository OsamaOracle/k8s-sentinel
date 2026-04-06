"""Background poller that refreshes cluster state every 15 seconds."""

import logging
import os
import threading
import time
from typing import Any

# Load .env from the backend/ directory (no-op if file absent or dotenv missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEV_MODE: bool = os.environ.get("DEV_MODE", "false").strip().lower() == "true"

if not DEV_MODE:
    from core.k8s_client import get_apps_v1, get_core_v1

from core.anomaly import detect_anomalies as _detect_anomalies
from core.database import init_db, insert_snapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory state
# ---------------------------------------------------------------------------

# Thread-safe via a read-write lock is overkill for this use-case; a plain
# dict + GIL is sufficient because we replace sub-keys atomically.
cluster_state: dict[str, Any] = {
    "pods": [],
    "events": [],
    "resources": {},
    "last_updated": None,
}

_stop_event = threading.Event()
_thread: threading.Thread | None = None

POLL_INTERVAL = 15  # seconds


# ---------------------------------------------------------------------------
# Health score (mirrors calcHealthScore in sentinel.jsx)
# ---------------------------------------------------------------------------


def _calc_health_score(pods: list[dict[str, Any]], resources: dict[str, Any]) -> int:
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


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------


def _collect_pods() -> list[dict[str, Any]]:
    """Fetch all pods cluster-wide and return normalised dicts."""
    core = get_core_v1()
    pod_list = core.list_pod_for_all_namespaces(watch=False)
    pods: list[dict[str, Any]] = []

    for pod in pod_list.items:
        meta = pod.metadata
        spec = pod.spec
        status = pod.status

        container_statuses = status.container_statuses or [] if status else []
        restart_count = sum(cs.restart_count for cs in container_statuses)

        # Derive a simple phase/reason string
        phase = status.phase if status else "Unknown"
        reason: str = phase or "Unknown"
        for cs in container_statuses:
            if cs.state and cs.state.waiting and cs.state.waiting.reason:
                reason = cs.state.waiting.reason
                break
            if cs.state and cs.state.terminated and cs.state.terminated.reason:
                reason = cs.state.terminated.reason
                break

        pods.append(
            {
                "name": meta.name,
                "namespace": meta.namespace,
                "phase": phase,
                "reason": reason,
                "restart_count": restart_count,
                "node": spec.node_name if spec else None,
                "containers": [
                    {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restart_count": cs.restart_count,
                        "state": _container_state(cs),
                    }
                    for cs in container_statuses
                ],
            }
        )

    return pods


def _container_state(cs: Any) -> dict[str, Any]:
    """Flatten kubernetes ContainerStatus state into a plain dict."""
    if cs.state is None:
        return {}
    if cs.state.running:
        return {"type": "running"}
    if cs.state.waiting:
        return {"type": "waiting", "reason": cs.state.waiting.reason}
    if cs.state.terminated:
        t = cs.state.terminated
        return {"type": "terminated", "reason": t.reason, "exit_code": t.exit_code}
    return {}


def _collect_events() -> list[dict[str, Any]]:
    """Fetch all events cluster-wide and return normalised dicts."""
    core = get_core_v1()
    event_list = core.list_event_for_all_namespaces(watch=False)
    events: list[dict[str, Any]] = []

    for ev in event_list.items:
        meta = ev.metadata
        events.append(
            {
                "name": meta.name,
                "namespace": meta.namespace,
                "reason": ev.reason,
                "message": ev.message,
                "type": ev.type,  # Normal / Warning
                "count": ev.count or 1,
                "involved_object": {
                    "kind": ev.involved_object.kind,
                    "name": ev.involved_object.name,
                    "namespace": ev.involved_object.namespace,
                },
                "last_timestamp": (
                    ev.last_timestamp.isoformat() if ev.last_timestamp else None
                ),
            }
        )

    # Most-recent first
    events.sort(key=lambda e: e["last_timestamp"] or "", reverse=True)
    return events


def _collect_resources() -> dict[str, Any]:
    """Collect node capacity, deployment replicas, and resource requests."""
    core = get_core_v1()
    apps = get_apps_v1()

    # Nodes
    node_list = core.list_node(watch=False)
    nodes: list[dict[str, Any]] = []
    for node in node_list.items:
        meta = node.metadata
        status = node.status
        conditions = {
            c.type: c.status for c in (status.conditions or [])
        } if status else {}
        capacity = status.capacity if status else {}
        allocatable = status.allocatable if status else {}

        nodes.append(
            {
                "name": meta.name,
                "ready": conditions.get("Ready") == "True",
                "cpu_capacity": capacity.get("cpu"),
                "memory_capacity": capacity.get("memory"),
                "cpu_allocatable": allocatable.get("cpu"),
                "memory_allocatable": allocatable.get("memory"),
                "conditions": conditions,
            }
        )

    # Deployments
    deploy_list = apps.list_deployment_for_all_namespaces(watch=False)
    deployments: list[dict[str, Any]] = []
    for dep in deploy_list.items:
        meta = dep.metadata
        spec = dep.spec
        status = dep.status
        deployments.append(
            {
                "name": meta.name,
                "namespace": meta.namespace,
                "desired": spec.replicas if spec else 0,
                "ready": status.ready_replicas or 0 if status else 0,
                "available": status.available_replicas or 0 if status else 0,
            }
        )

    return {"nodes": nodes, "deployments": deployments}


# ---------------------------------------------------------------------------
# Mock data (DEV_MODE)
# ---------------------------------------------------------------------------

_MOCK_PODS: list[dict[str, Any]] = [
    {
        "name": "api-gateway-7d9f6b-x4k2p",
        "namespace": "openclaw",
        "phase": "Running",
        "reason": "Running",
        "restart_count": 0,
        "node": "node-01",
        "containers": [
            {
                "name": "api-gateway",
                "ready": True,
                "restart_count": 0,
                "state": {"type": "running"},
            }
        ],
    },
    {
        "name": "web-frontend-5c8d4a-p9m3q",
        "namespace": "production",
        "phase": "Running",
        "reason": "Running",
        "restart_count": 0,
        "node": "node-02",
        "containers": [
            {
                "name": "web-frontend",
                "ready": True,
                "restart_count": 0,
                "state": {"type": "running"},
            }
        ],
    },
    {
        "name": "etl-processor-6b7c9d-r2n5v",
        "namespace": "data",
        "phase": "Running",
        "reason": "Running",
        "restart_count": 7,
        "node": "node-01",
        "containers": [
            {
                "name": "etl-processor",
                "ready": True,
                "restart_count": 7,
                "state": {"type": "running"},
            }
        ],
    },
    {
        "name": "model-trainer-9a1b2c-t7w8x",
        "namespace": "ml-pipeline",
        "phase": "Waiting",
        "reason": "CrashLoopBackOff",
        "restart_count": 4,
        "node": "node-02",
        "containers": [
            {
                "name": "model-trainer",
                "ready": False,
                "restart_count": 4,
                "state": {"type": "waiting", "reason": "CrashLoopBackOff"},
            }
        ],
    },
    {
        "name": "prometheus-server-3f5e6d-h1j4k",
        "namespace": "monitoring",
        "phase": "Running",
        "reason": "Running",
        "restart_count": 0,
        "node": "node-01",
        "containers": [
            {
                "name": "prometheus",
                "ready": True,
                "restart_count": 0,
                "state": {"type": "running"},
            },
            {
                "name": "config-reloader",
                "ready": True,
                "restart_count": 0,
                "state": {"type": "running"},
            },
        ],
    },
    {
        "name": "nginx-ingress-controller-8c2d-q6s9t",
        "namespace": "ingress-nginx",
        "phase": "Running",
        "reason": "Running",
        "restart_count": 0,
        "node": "node-02",
        "containers": [
            {
                "name": "nginx-ingress-controller",
                "ready": True,
                "restart_count": 0,
                "state": {"type": "running"},
            }
        ],
    },
]

_MOCK_EVENTS: list[dict[str, Any]] = [
    {
        "name": "model-trainer-crashloop.17e8b1a2c3d4e5f6",
        "namespace": "ml-pipeline",
        "reason": "BackOff",
        "message": "Back-off restarting failed container model-trainer in pod model-trainer-9a1b2c-t7w8x",
        "type": "Warning",
        "count": 18,
        "involved_object": {
            "kind": "Pod",
            "name": "model-trainer-9a1b2c-t7w8x",
            "namespace": "ml-pipeline",
        },
        "last_timestamp": "2026-04-06T09:55:00+00:00",
    },
    {
        "name": "model-trainer-crashloop.17e8b1a000000001",
        "namespace": "ml-pipeline",
        "reason": "CrashLoopBackOff",
        "message": "Container model-trainer is in CrashLoopBackOff (exit code 1)",
        "type": "Warning",
        "count": 4,
        "involved_object": {
            "kind": "Pod",
            "name": "model-trainer-9a1b2c-t7w8x",
            "namespace": "ml-pipeline",
        },
        "last_timestamp": "2026-04-06T09:52:00+00:00",
    },
    {
        "name": "etl-processor-oom.17e8b0f100000002",
        "namespace": "data",
        "reason": "OOMKilling",
        "message": "Memory limit reached, container etl-processor killed. Limit: 512Mi, Usage: 528Mi",
        "type": "Warning",
        "count": 5,
        "involved_object": {
            "kind": "Pod",
            "name": "etl-processor-6b7c9d-r2n5v",
            "namespace": "data",
        },
        "last_timestamp": "2026-04-06T09:48:00+00:00",
    },
    {
        "name": "node-02-notready.17e8b0e200000003",
        "namespace": "",
        "reason": "NodeNotReady",
        "message": "Node node-02 status is now: NodeNotReady — kubelet stopped posting node status",
        "type": "Warning",
        "count": 1,
        "involved_object": {
            "kind": "Node",
            "name": "node-02",
            "namespace": None,
        },
        "last_timestamp": "2026-04-06T09:45:00+00:00",
    },
    {
        "name": "web-frontend-mount.17e8b0d300000004",
        "namespace": "production",
        "reason": "FailedMount",
        "message": "Unable to attach or mount volumes: unmounted volumes=[config-volume], failed to sync configmaps cache: timed out waiting for the condition",
        "type": "Warning",
        "count": 3,
        "involved_object": {
            "kind": "Pod",
            "name": "web-frontend-5c8d4a-p9m3q",
            "namespace": "production",
        },
        "last_timestamp": "2026-04-06T09:42:00+00:00",
    },
    {
        "name": "prometheus-throttle.17e8b0c400000005",
        "namespace": "monitoring",
        "reason": "CPUThrottling",
        "message": "75% throttling of CPU in container prometheus of pod prometheus-server-3f5e6d-h1j4k",
        "type": "Warning",
        "count": 12,
        "involved_object": {
            "kind": "Pod",
            "name": "prometheus-server-3f5e6d-h1j4k",
            "namespace": "monitoring",
        },
        "last_timestamp": "2026-04-06T09:40:00+00:00",
    },
    {
        "name": "api-gateway-scaled.17e8b0b500000006",
        "namespace": "openclaw",
        "reason": "ScalingReplicaSet",
        "message": "Scaled up replica set api-gateway-7d9f6b to 3",
        "type": "Normal",
        "count": 1,
        "involved_object": {
            "kind": "Deployment",
            "name": "api-gateway",
            "namespace": "openclaw",
        },
        "last_timestamp": "2026-04-06T09:35:00+00:00",
    },
    {
        "name": "nginx-pulled.17e8b0a600000007",
        "namespace": "ingress-nginx",
        "reason": "Pulled",
        "message": "Successfully pulled image nginx/nginx-ingress:3.4.3",
        "type": "Normal",
        "count": 1,
        "involved_object": {
            "kind": "Pod",
            "name": "nginx-ingress-controller-8c2d-q6s9t",
            "namespace": "ingress-nginx",
        },
        "last_timestamp": "2026-04-06T09:30:00+00:00",
    },
    {
        "name": "etl-processor-backoff.17e8b09700000008",
        "namespace": "data",
        "reason": "BackOff",
        "message": "Back-off pulling image spark-etl:latest — ImagePullBackOff",
        "type": "Warning",
        "count": 6,
        "involved_object": {
            "kind": "Pod",
            "name": "etl-processor-6b7c9d-r2n5v",
            "namespace": "data",
        },
        "last_timestamp": "2026-04-06T09:20:00+00:00",
    },
    {
        "name": "prometheus-started.17e8b08800000009",
        "namespace": "monitoring",
        "reason": "Started",
        "message": "Started container prometheus",
        "type": "Normal",
        "count": 1,
        "involved_object": {
            "kind": "Pod",
            "name": "prometheus-server-3f5e6d-h1j4k",
            "namespace": "monitoring",
        },
        "last_timestamp": "2026-04-06T09:15:00+00:00",
    },
    {
        "name": "ml-pipeline-pvc-mount.17e8b079000000010",
        "namespace": "ml-pipeline",
        "reason": "FailedMount",
        "message": "MountVolume.SetUp failed for volume pvc-model-weights: rpc error: desc = stat /mnt/disks/model-weights: no such file or directory",
        "type": "Warning",
        "count": 2,
        "involved_object": {
            "kind": "Pod",
            "name": "model-trainer-9a1b2c-t7w8x",
            "namespace": "ml-pipeline",
        },
        "last_timestamp": "2026-04-06T09:10:00+00:00",
    },
    {
        "name": "web-frontend-created.17e8b06a000000011",
        "namespace": "production",
        "reason": "Created",
        "message": "Created container web-frontend",
        "type": "Normal",
        "count": 1,
        "involved_object": {
            "kind": "Pod",
            "name": "web-frontend-5c8d4a-p9m3q",
            "namespace": "production",
        },
        "last_timestamp": "2026-04-06T09:05:00+00:00",
    },
]

_MOCK_RESOURCES: dict[str, Any] = {
    "nodes": [
        {
            "name": "node-01",
            "ready": True,
            "cpu_capacity": "8",
            "memory_capacity": "16384Mi",
            "cpu_allocatable": "7750m",
            "memory_allocatable": "15360Mi",
            "conditions": {
                "Ready": "True",
                "MemoryPressure": "False",
                "DiskPressure": "False",
                "PIDPressure": "False",
            },
        },
        {
            "name": "node-02",
            "ready": False,
            "cpu_capacity": "8",
            "memory_capacity": "16384Mi",
            "cpu_allocatable": "7750m",
            "memory_allocatable": "15360Mi",
            "conditions": {
                "Ready": "False",
                "MemoryPressure": "False",
                "DiskPressure": "False",
                "PIDPressure": "False",
            },
        },
    ],
    "deployments": [
        {
            "name": "api-gateway",
            "namespace": "openclaw",
            "desired": 3,
            "ready": 3,
            "available": 3,
        },
        {
            "name": "web-frontend",
            "namespace": "production",
            "desired": 2,
            "ready": 2,
            "available": 2,
        },
        {
            "name": "etl-processor",
            "namespace": "data",
            "desired": 1,
            "ready": 1,
            "available": 1,
        },
        {
            "name": "model-trainer",
            "namespace": "ml-pipeline",
            "desired": 1,
            "ready": 0,
            "available": 0,
        },
        {
            "name": "prometheus",
            "namespace": "monitoring",
            "desired": 1,
            "ready": 1,
            "available": 1,
        },
        {
            "name": "nginx-ingress-controller",
            "namespace": "ingress-nginx",
            "desired": 2,
            "ready": 2,
            "available": 2,
        },
    ],
}


def _dev_poll_loop() -> None:
    """Load mock data once, then idle until stopped."""
    cluster_state["pods"] = _MOCK_PODS
    cluster_state["events"] = _MOCK_EVENTS
    cluster_state["resources"] = _MOCK_RESOURCES
    cluster_state["last_updated"] = time.time()
    logger.info(
        "DEV_MODE: mock state loaded (%d pods, %d events)",
        len(_MOCK_PODS),
        len(_MOCK_EVENTS),
    )
    # Stay alive so stop_poller() can join() normally
    _stop_event.wait()


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------


def _poll_loop() -> None:
    """Run one poll immediately then repeat every POLL_INTERVAL seconds."""
    while not _stop_event.is_set():
        try:
            pods = _collect_pods()
            events = _collect_events()
            resources = _collect_resources()

            cluster_state["pods"] = pods
            cluster_state["events"] = events
            cluster_state["resources"] = resources
            cluster_state["last_updated"] = time.time()

            logger.debug(
                "Poll complete: %d pods, %d events, %d nodes",
                len(pods),
                len(events),
                len(resources.get("nodes", [])),
            )

            try:
                score = _calc_health_score(pods, resources)
                pod_count = len(pods)
                unhealthy_count = sum(
                    1 for p in pods
                    if "CrashLoopBackOff" in (p.get("reason") or "")
                    or p.get("restart_count", 0) >= 3
                )
                warning_count = sum(
                    1 for e in events if e.get("type") == "Warning"
                )
                anomaly_count = len(
                    _detect_anomalies(
                        {"pods": pods, "events": events, "resources": resources}
                    )
                )
                insert_snapshot(score, pod_count, unhealthy_count, warning_count, anomaly_count)
            except Exception:
                logger.exception("Failed to persist health snapshot")

        except Exception:
            logger.exception("Error during cluster poll — will retry")

        _stop_event.wait(timeout=POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_poller() -> None:
    """Start the background polling thread (idempotent).

    Reads DEV_MODE from os.environ at call time. When true, loads mock
    data into cluster_state and skips the Kubernetes polling loop entirely.
    When false, runs the normal Kubernetes polling loop.
    """
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    init_db()
    dev = os.environ.get("DEV_MODE", "false").strip().lower() == "true"
    if dev:
        cluster_state["pods"] = _MOCK_PODS
        cluster_state["events"] = _MOCK_EVENTS
        cluster_state["resources"] = _MOCK_RESOURCES
        cluster_state["last_updated"] = time.time()
        logger.info(
            "Poller started in DEV_MODE — mock state loaded (%d pods, %d events)",
            len(_MOCK_PODS),
            len(_MOCK_EVENTS),
        )
        # No polling thread needed; mock data is static.
        return
    _thread = threading.Thread(target=_poll_loop, name="k8s-poller", daemon=True)
    _thread.start()
    logger.info("Poller started (interval=%ds)", POLL_INTERVAL)


def stop_poller() -> None:
    """Signal the poller thread to stop and wait for it to exit."""
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
        _thread = None
    logger.info("Poller stopped")
