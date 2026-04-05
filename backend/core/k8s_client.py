"""Kubernetes API client initialisation helpers."""

from kubernetes import client, config
from kubernetes.client import CoreV1Api, AppsV1Api

_core_v1: CoreV1Api | None = None
_apps_v1: AppsV1Api | None = None


def init_k8s() -> None:
    """Load kubeconfig (in-cluster or local) and instantiate API clients."""
    global _core_v1, _apps_v1
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    _core_v1 = client.CoreV1Api()
    _apps_v1 = client.AppsV1Api()


def get_core_v1() -> CoreV1Api:
    """Return the CoreV1Api singleton, raising if not initialised."""
    if _core_v1 is None:
        raise RuntimeError("k8s client not initialised — call init_k8s() first")
    return _core_v1


def get_apps_v1() -> AppsV1Api:
    """Return the AppsV1Api singleton, raising if not initialised."""
    if _apps_v1 is None:
        raise RuntimeError("k8s client not initialised — call init_k8s() first")
    return _apps_v1
