"""Pure anomaly-detection logic — no Kubernetes API calls."""

from typing import Any

# Restart count that triggers a high-severity anomaly
HIGH_RESTART_THRESHOLD = 3

# Event reasons we care about and their severity
_EVENT_RULES: list[tuple[str, str, str]] = [
    # (reason_substring, severity, label)
    ("FailedMount", "high", "FailedMount"),
    ("BackOff", "med", "BackOff"),
    ("OOMKilling", "high", "OOMKilled"),
]


def _detect_pod_anomalies(pods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inspect pod list for container-level and phase-level issues."""
    anomalies: list[dict[str, Any]] = []

    for pod in pods:
        name = pod.get("name", "")
        ns = pod.get("namespace", "")
        restart_count: int = pod.get("restart_count", 0)

        # Check each container's state
        for container in pod.get("containers", []):
            state = container.get("state", {})
            state_type = state.get("type", "")
            reason = state.get("reason", "") or ""

            if "CrashLoopBackOff" in reason:
                anomalies.append(
                    {
                        "sev": "high",
                        "label": "CrashLoopBackOff",
                        "detail": (
                            f"Container '{container['name']}' in pod '{name}' "
                            f"is in CrashLoopBackOff."
                        ),
                        "namespace": ns,
                    }
                )

            if "OOMKilled" in reason:
                anomalies.append(
                    {
                        "sev": "high",
                        "label": "OOMKilled",
                        "detail": (
                            f"Container '{container['name']}' in pod '{name}' "
                            f"was OOMKilled (exit_code={state.get('exit_code')})."
                        ),
                        "namespace": ns,
                    }
                )

            if state_type == "waiting" and "BackOff" in reason and "Crash" not in reason:
                anomalies.append(
                    {
                        "sev": "med",
                        "label": "BackOff",
                        "detail": (
                            f"Container '{container['name']}' in pod '{name}' "
                            f"is waiting: {reason}."
                        ),
                        "namespace": ns,
                    }
                )

        # High restart count
        if restart_count >= HIGH_RESTART_THRESHOLD:
            anomalies.append(
                {
                    "sev": "high",
                    "label": "HighRestartCount",
                    "detail": (
                        f"Pod '{name}' has restarted {restart_count} time(s)."
                    ),
                    "namespace": ns,
                }
            )

    return anomalies


def _detect_event_anomalies(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scan cluster events for known warning patterns."""
    anomalies: list[dict[str, Any]] = []
    seen: set[str] = set()  # deduplicate by (namespace, object, label)

    for ev in events:
        if ev.get("type") != "Warning":
            continue

        reason: str = ev.get("reason", "") or ""
        message: str = ev.get("message", "") or ""
        ns: str = ev.get("namespace", "") or ""
        obj = ev.get("involved_object", {})
        obj_name: str = obj.get("name", "")

        combined = f"{reason} {message}"

        for rule_reason, sev, label in _EVENT_RULES:
            if rule_reason in combined:
                key = f"{ns}/{obj_name}/{label}"
                if key in seen:
                    continue
                seen.add(key)
                anomalies.append(
                    {
                        "sev": sev,
                        "label": label,
                        "detail": (
                            f"{label} on {obj.get('kind', 'object')} "
                            f"'{obj_name}': {message[:200]}"
                        ),
                        "namespace": ns,
                    }
                )

    return anomalies


def _detect_node_anomalies(resources: dict[str, Any]) -> list[dict[str, Any]]:
    """Flag nodes whose Ready condition is False or Unknown."""
    anomalies: list[dict[str, Any]] = []

    for node in resources.get("nodes", []):
        if not node.get("ready", True):
            conditions = node.get("conditions", {})
            anomalies.append(
                {
                    "sev": "high",
                    "label": "NodeNotReady",
                    "detail": (
                        f"Node '{node['name']}' is NotReady. "
                        f"Conditions: {conditions}"
                    ),
                    "namespace": "",
                }
            )

    return anomalies


def _detect_cpu_throttling(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect CPUThrottling warnings surfaced as events."""
    anomalies: list[dict[str, Any]] = []
    seen: set[str] = set()

    for ev in events:
        message: str = ev.get("message", "") or ""
        reason: str = ev.get("reason", "") or ""
        ns: str = ev.get("namespace", "") or ""
        obj = ev.get("involved_object", {})
        obj_name = obj.get("name", "")

        if "throttl" in message.lower() or "CPUThrottling" in reason:
            key = f"{ns}/{obj_name}/CPUThrottling"
            if key in seen:
                continue
            seen.add(key)
            anomalies.append(
                {
                    "sev": "med",
                    "label": "CPUThrottling",
                    "detail": (
                        f"CPU throttling detected on "
                        f"{obj.get('kind', 'object')} '{obj_name}': "
                        f"{message[:200]}"
                    ),
                    "namespace": ns,
                }
            )

    return anomalies


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_anomalies(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Run all detectors against the current cluster state.

    Args:
        state: The shared ``cluster_state`` dict maintained by the poller.

    Returns:
        List of anomaly dicts, each with keys:
        ``sev`` ("high" | "med"), ``label``, ``detail``, ``namespace``.
    """
    pods: list[dict[str, Any]] = state.get("pods", [])
    events: list[dict[str, Any]] = state.get("events", [])
    resources: dict[str, Any] = state.get("resources", {})

    anomalies: list[dict[str, Any]] = []
    anomalies.extend(_detect_pod_anomalies(pods))
    anomalies.extend(_detect_event_anomalies(events))
    anomalies.extend(_detect_node_anomalies(resources))
    anomalies.extend(_detect_cpu_throttling(events))

    # High-severity first, then alphabetically by label
    anomalies.sort(key=lambda a: (0 if a["sev"] == "high" else 1, a["label"]))
    return anomalies
