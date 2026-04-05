"""Pydantic v2 models for the k8s-sentinel API."""

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core cluster resource models
# ---------------------------------------------------------------------------


class ContainerStateInfo(BaseModel):
    type: str = ""
    reason: str | None = None
    exit_code: int | None = None


class ContainerInfo(BaseModel):
    name: str
    ready: bool = False
    restart_count: int = 0
    state: ContainerStateInfo = Field(default_factory=ContainerStateInfo)


class PodInfo(BaseModel):
    name: str
    namespace: str
    phase: str
    reason: str
    restart_count: int = 0
    node: str | None = None
    containers: list[ContainerInfo] = Field(default_factory=list)


class InvolvedObject(BaseModel):
    kind: str
    name: str
    namespace: str | None = None


class EventInfo(BaseModel):
    name: str
    namespace: str
    reason: str | None = None
    message: str | None = None
    type: str | None = None  # "Normal" | "Warning"
    count: int = 1
    involved_object: InvolvedObject
    last_timestamp: str | None = None


class NodeInfo(BaseModel):
    name: str
    ready: bool
    cpu_capacity: str | None = None
    memory_capacity: str | None = None
    cpu_allocatable: str | None = None
    memory_allocatable: str | None = None
    conditions: dict[str, str] = Field(default_factory=dict)


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    desired: int = 0
    ready: int = 0
    available: int = 0


class ResourceInfo(BaseModel):
    nodes: list[NodeInfo] = Field(default_factory=list)
    deployments: list[DeploymentInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Anomaly model
# ---------------------------------------------------------------------------


class AnomalyInfo(BaseModel):
    sev: str  # "high" | "med"
    label: str
    detail: str
    namespace: str


# ---------------------------------------------------------------------------
# Full cluster snapshot
# ---------------------------------------------------------------------------


class ClusterState(BaseModel):
    pods: list[PodInfo] = Field(default_factory=list)
    events: list[EventInfo] = Field(default_factory=list)
    resources: ResourceInfo = Field(default_factory=ResourceInfo)
    anomalies: list[AnomalyInfo] = Field(default_factory=list)
    last_updated: float | None = None


# ---------------------------------------------------------------------------
# Diagnosis request / response
# ---------------------------------------------------------------------------


class DiagnosisRequest(BaseModel):
    focus: str | None = Field(
        default=None,
        description="Optional free-text focus area, e.g. 'nginx pod in production'.",
    )
    extra_context: dict[str, Any] | None = Field(
        default=None,
        description="Any additional structured context to pass to the model.",
    )


class DiagnosisResponse(BaseModel):
    summary: str = Field(description="One-paragraph plain-English cluster summary.")
    root_cause: str = Field(
        alias="rootCause",
        description="Most likely root cause of any detected issues.",
    )
    kubectl_commands: list[str] = Field(
        alias="kubectlCommands",
        description="Up to 3 actionable kubectl commands.",
    )

    model_config = {"populate_by_name": True}
