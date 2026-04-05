# k8s-sentinel Project Memory

## Stack
- FastAPI + Python backend in `backend/`
- Kubernetes Python client (`kubernetes` package)
- Pydantic v2 models
- Anthropic SDK for AI diagnosis
- sse-starlette for SSE streaming

## Key Architecture
- `backend/main.py` — FastAPI app with lifespan (starts/stops poller), CORS, all routers at `/api`
- `backend/core/k8s_client.py` — Singleton CoreV1Api / AppsV1Api, loaded via `init_k8s()`
- `backend/core/poller.py` — Background thread polling every 15s; shared `cluster_state` dict
- `backend/core/anomaly.py` — Pure detection logic; `detect_anomalies(state)` → list of dicts
- `backend/models/schemas.py` — Pydantic v2 models (PodInfo, EventInfo, ResourceInfo, AnomalyInfo, ClusterState, DiagnosisRequest, DiagnosisResponse)
- `backend/routers/pods.py` — GET /api/pods
- `backend/routers/events.py` — GET /api/events + GET /api/events/stream (SSE)
- `backend/routers/resources.py` — GET /api/resources
- `backend/routers/diagnosis.py` — POST /api/diagnose → calls Claude API

## Claude Model
- Diagnosis uses `claude-sonnet-4-0` (alias for claude-sonnet-4-20250514, user-specified)
- Uses `anthropic` SDK with streaming (`.stream()` + `.get_final_message()`)
- Requires `ANTHROPIC_API_KEY` env var

## Anomaly Detection Labels
CrashLoopBackOff, OOMKilled, BackOff, FailedMount, NodeNotReady, CPUThrottling, HighRestartCount (>=3)

## DiagnosisResponse fields
- `summary`, `rootCause` (alias `rootCause`), `kubectlCommands` (alias `kubectlCommands`)
- Pydantic `populate_by_name=True` for alias support
