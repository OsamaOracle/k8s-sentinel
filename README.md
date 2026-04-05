# Kubernetes Sentinel ⎈

> AI-powered Kubernetes cluster health dashboard — monitors **all namespaces** in real time, detects anomalies automatically, and uses Claude AI to generate plain-English root-cause diagnoses with ready-to-run `kubectl` remediation commands.

| Python | FastAPI | React | Kubernetes | License |
|--------|---------|-------|------------|---------|
| 3.12+ | 0.115 | 18 | 1.29+ | MIT |

---

## Dashboard Preview

![Kubernetes Sentinel Dashboard](docs/screenshots/dashboard.png)

> The dashboard runs in your browser and connects to the FastAPI backend running locally or inside your cluster.

---

## Features

- **Live pod status** across all namespaces — phase, restart count, node, CPU and memory
- **Event stream** — all Kubernetes events color-coded by severity with namespace context
- **Resource inventory** — nodes, deployments, services, PVCs, configmaps, secrets
- **7 anomaly detection rules** — `CrashLoopBackOff`, `OOMKilled`, `FailedMount`, `BackOff`, `NodeNotReady`, `CPUThrottling`, high restart count
- **AI diagnosis** — one click sends full cluster state to Claude and returns a plain-English root cause + 3 copy-paste `kubectl` remediation commands
- **Health score** — 0–100 composite score updated every 15 seconds
- **SSE live updates** — browser receives push updates without polling
- **Mock mode** — works without a real cluster for development and demos (`DEV_MODE=true`)

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Kubernetes Cluster                 │
│                                                 │
│  ┌──────────────────────┐  ┌─────────────────┐  │
│  │   sentinel pod       │  │ All namespaces  │  │
│  │  FastAPI + poller    │◀▶│ pods / events / │  │
│  │  Python 3.12         │  │ deployments     │  │
│  └──────────┬───────────┘  └─────────────────┘  │
└─────────────┼───────────────────────────────────┘
              │ HTTP + SSE
              ▼
   ┌──────────────────┐       ┌──────────────────┐
   │  React Frontend  │──────▶│   Claude API     │
   │  sentinel.jsx    │◀──────│  AI diagnosis    │
   └──────────────────┘       └──────────────────┘
```

---

## Project Structure

```
k8s-sentinel/
├── .env.example              ← copy to .env, fill in your keys
├── .gitignore                ← .env and .venv are excluded
├── README.md
├── docs/
│   └── screenshots/
│       └── dashboard.png     ← dashboard preview
│
├── backend/
│   ├── main.py               ← FastAPI entry point + lifespan hooks
│   ├── requirements.txt      ← pinned Python dependencies
│   ├── Dockerfile            ← multi-stage, non-root sentinel user
│   ├── core/
│   │   ├── k8s_client.py     ← auto-detects in-cluster vs kubeconfig
│   │   ├── poller.py         ← background thread, 15s polling loop
│   │   └── anomaly.py        ← 7-rule detection engine
│   ├── models/
│   │   └── schemas.py        ← Pydantic v2 data models
│   └── routers/
│       ├── pods.py           ← GET /api/pods
│       ├── events.py         ← GET /api/events + SSE stream
│       ├── resources.py      ← GET /api/resources
│       └── diagnosis.py      ← POST /api/diagnose → Claude
│
├── frontend/
│   └── sentinel.jsx          ← React dashboard (single file)
│
├── k8s/
│   ├── namespace.yaml        ← k8s-sentinel namespace
│   ├── rbac.yaml             ← ClusterRole (read-only, all namespaces)
│   ├── deployment.yaml       ← pod spec with liveness + readiness probes
│   ├── service.yaml          ← ClusterIP on port 8000
│   └── configmap.yaml        ← app configuration
│
└── scripts/
    ├── dev.ps1               ← run locally (Windows PowerShell)
    ├── deploy.ps1            ← kubectl apply all manifests
    └── port-forward.ps1      ← forward service to localhost:8000
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend runtime |
| kubectl | 1.29+ | Cluster access (for k8s deploy) |
| Docker Desktop | 24+ | Build image + run kind |
| A Kubernetes cluster | any | AKS / EKS / GKE / k3s / kind |
| Anthropic API key | — | AI diagnosis feature |

---

## Option A — Run Locally (no cluster needed)

This mode uses mock data so you can see the full dashboard without any Kubernetes cluster.

### 1. Clone the repo

```bash
git clone https://github.com/your-username/k8s-sentinel.git
cd k8s-sentinel
```

### 2. Configure environment

```powershell
# Windows
copy .env.example .env
```
```bash
# macOS / Linux
cp .env.example .env
```

Open `.env` and set:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEV_MODE=true
POLL_INTERVAL_SECONDS=15
HOST=0.0.0.0
PORT=8000
```

> ⚠️ **Never commit `.env`** — it is gitignored. Only `.env.example` belongs in version control.

### 3. Create virtual environment and install dependencies

```powershell
cd backend

# Create venv
python -m venv .venv

# Activate (Windows)
.venv\Scripts\Activate.ps1

# Activate (macOS / Linux)
# source .venv/bin/activate

# Install all packages
pip install -r requirements.txt
```

### 4. Start the backend

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
$env:DEV_MODE = "true"
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5. Verify the API

Open a second terminal:

```powershell
curl http://localhost:8000/healthz
# {"status":"ok"}

curl http://localhost:8000/api/pods
# [...list of mock pods...]

curl http://localhost:8000/api/events
# [...list of mock events...]
```

### 6. Open the dashboard

Open `frontend/sentinel.jsx`, copy the entire contents, and paste it into a Claude.ai chat with:

```
Render this React component as an artifact
```

The dashboard will render and connect to your backend at `http://localhost:8000`.

---

## Option B — Run with a Real Kubernetes Cluster

### 1. Set up a local cluster with kind

If you don't have a cloud cluster, spin one up locally:

```powershell
# Install kind
winget install Kubernetes.kind

# Create a cluster
kind create cluster --name sentinel-dev

# Verify
kubectl cluster-info --context kind-sentinel-dev
kubectl get nodes
```

### 2. Configure environment

```powershell
copy .env.example .env
```

Open `.env` and set:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEV_MODE=false
KUBECONFIG_PATH=           # leave blank to use ~/.kube/config
POLL_INTERVAL_SECONDS=15
HOST=0.0.0.0
PORT=8000
```

### 3. Start the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
$env:DEV_MODE = "false"
uvicorn main:app --reload --port 8000
```

The backend will now poll your real cluster every 15 seconds and return live data.

---

## Option C — Deploy to Kubernetes

This runs the sentinel as a pod inside your cluster.

### 1. Build and push the Docker image

```bash
# Replace with your own registry
docker build -t your-registry/k8s-sentinel:latest ./backend
docker push your-registry/k8s-sentinel:latest
```

Update the image name in `k8s/deployment.yaml`:
```yaml
image: your-registry/k8s-sentinel:latest
```

### 2. Create the API key secret

```bash
# Never store secrets in files — create them directly with kubectl
kubectl create secret generic sentinel-secrets \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -n k8s-sentinel
```

### 3. Apply all manifests

```powershell
# Windows — using the deploy script
.\scripts\deploy.ps1
```

```bash
# macOS / Linux — apply in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 4. Verify the deployment

```bash
# Check pod is running
kubectl get pods -n k8s-sentinel

# Check logs
kubectl logs -n k8s-sentinel -l app=k8s-sentinel -f

# Expected output:
# INFO:     Application startup complete.
# INFO:     K8s client loaded via in-cluster config
```

### 5. Access the dashboard

```powershell
# Windows
.\scripts\port-forward.ps1
```
```bash
# macOS / Linux
kubectl port-forward svc/k8s-sentinel 8000:8000 -n k8s-sentinel
```

Then open `http://localhost:8000` or load `frontend/sentinel.jsx` as a Claude.ai artifact.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Liveness / readiness probe |
| `GET` | `/api/pods` | All pods across all namespaces |
| `GET` | `/api/events` | All events (filter: `?namespace=&type=&limit=`) |
| `GET` | `/api/events/stream` | SSE live event stream |
| `GET` | `/api/resources` | Nodes + deployments |
| `POST` | `/api/diagnose` | AI diagnosis via Claude |

### Example diagnosis response

```json
{
  "summary": "The ml-worker pod in ml-pipeline is crashlooping due to OOM — the container is being killed before it can complete startup.",
  "rootCause": "Memory limit of 2Gi is too low for the current workload. The container needs at least 4Gi to initialize the model.",
  "kubectlCommands": [
    "kubectl logs ml-worker-6f4d8c9b5-tn8wq -n ml-pipeline --previous --tail=100",
    "kubectl set resources deployment ml-worker -n ml-pipeline --limits=memory=4Gi",
    "kubectl rollout status deployment/ml-worker -n ml-pipeline --timeout=120s"
  ]
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `DEV_MODE` | `false` | `true` = use mock data, skip k8s connection |
| `KUBECONFIG_PATH` | `~/.kube/config` | Path to kubeconfig (leave blank for in-cluster) |
| `POLL_INTERVAL_SECONDS` | `15` | How often to poll the Kubernetes API |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

---

## Anomaly Detection Rules

| Rule | Severity | Trigger |
|------|----------|---------|
| `CrashLoopBackOff` | 🔴 High | Pod phase = CrashLoopBackOff |
| `OOMKilled` | 🔴 High | Event reason = OOMKilled |
| `NodeNotReady` | 🔴 High | Node ready = false |
| `HighRestartCount` | 🔴 High | Pod restarts ≥ 3 |
| `BackOff` | 🟡 Medium | Event reason = BackOff |
| `FailedMount` | 🟡 Medium | Event reason = FailedMount |
| `CPUThrottling` | 🟡 Medium | Event reason = CPUThrottling |

---

## Security

- **No secrets in code** — all credentials loaded from environment variables or Kubernetes Secrets
- **Read-only RBAC** — `ClusterRole` only grants `get`, `list`, `watch` — sentinel can never modify cluster resources
- **Non-root container** — Docker image runs as `sentinel` user (UID 1000), never root
- **No data persistence** — cluster state held in memory only, never written to disk
- **`.env` is gitignored** — your secrets file is never committed

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'core'`**
```powershell
# Make sure you're running uvicorn from inside the backend/ folder
cd backend
uvicorn main:app --reload --port 8000
```

**`ConfigException: Invalid kube-config file`**
```powershell
# Check kubectl is configured
kubectl cluster-info

# Or use mock mode
$env:DEV_MODE = "true"
```

**`venv not found`**
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

**Dashboard shows "Backend unreachable"**
- Confirm backend is running: `curl http://localhost:8000/healthz`
- Check `BASE_URL` in `sentinel.jsx` matches your backend port
- Dashboard will fall back to mock data automatically

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Copy `.env.example` → `.env` and fill in your keys
4. Make your changes
5. Open a pull request

Please do not commit `.env`, real API keys, or kubeconfig files.

---

## License

MIT — see [LICENSE](LICENSE) for details.