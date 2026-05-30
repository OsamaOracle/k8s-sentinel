# Contributing to Kubernetes Sentinel

Thank you for your interest in contributing. This guide covers everything you need
to get the project running locally, understand the codebase, and submit a pull request.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Running Locally](#running-locally)
- [How to Add a New LLM Provider](#how-to-add-a-new-llm-provider)
- [How to Add a New Anomaly Rule](#how-to-add-a-new-anomaly-rule)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Code Style](#code-style)
- [Reporting Bugs](#reporting-bugs)

---

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally

```bash
git clone https://github.com/your-username/k8s-sentinel.git
cd k8s-sentinel
```

3. Create a branch for your change

```bash
git checkout -b feature/your-feature-name
```

---

## Project Structure

```
k8s-sentinel/
├── backend/
│   ├── main.py               FastAPI entry point and lifespan hooks
│   ├── requirements.txt      Pinned Python dependencies
│   ├── Dockerfile            Multi-stage build running as non-root user
│   ├── core/
│   │   ├── k8s_client.py     Kubernetes auth, supports in-cluster and kubeconfig
│   │   ├── poller.py         Background thread polling Kubernetes every 15 seconds
│   │   ├── anomaly.py        Seven built-in anomaly detection rules
│   │   ├── alerting.py       Slack and Teams webhook alerting with cooldown
│   │   ├── database.py       SQLite storage for health timeline and diagnosis history
│   │   └── llm.py            LLM provider abstraction layer
│   ├── models/
│   │   └── schemas.py        Pydantic v2 data models
│   └── routers/
│       ├── pods.py           GET /api/pods and GET /api/pods/{ns}/{name}/logs
│       ├── events.py         GET /api/events and SSE stream
│       ├── resources.py      GET /api/resources
│       ├── diagnosis.py      POST /api/diagnose and GET /api/diagnose/auto-status
│       ├── timeline.py       GET /api/timeline
│       ├── history.py        GET /api/history
│       ├── alerts.py         GET /api/alerts/status
│       └── llm.py            GET /api/llm/status
├── frontend/
│   └── sentinel.jsx          React dashboard as a single file
├── k8s/
│   ├── namespace.yaml
│   ├── rbac.yaml             Read-only ClusterRole for all namespaces
│   ├── deployment.yaml       Pod spec with liveness and readiness probes
│   ├── service.yaml          ClusterIP on port 8000
│   └── configmap.yaml
└── scripts/
    ├── dev.ps1               Local development on Windows
    ├── deploy.ps1            kubectl apply all manifests in order
    └── port-forward.ps1      Forward service to localhost
```

---

## Running Locally

```powershell
cd backend

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

$env:DEV_MODE = "true"
$env:ANTHROPIC_API_KEY = "your-key-here"

uvicorn main:app --reload --port 8000
```

The server starts at http://localhost:8000. Load frontend/sentinel.jsx as a
React artifact in Claude.ai to see the dashboard.

---

## How to Add a New LLM Provider

All LLM providers live in backend/core/llm.py. Adding a new one takes four steps.

**Step 1** — Create a class that extends BaseLLMProvider

```python
class MyProvider(BaseLLMProvider):

    @property
    def name(self) -> str:
        return "myprovider"

    @property
    def model(self) -> str:
        return os.getenv("MY_MODEL", "my-default-model")

    async def diagnose(self, prompt: str) -> str:
        api_key = os.getenv("MY_API_KEY", "")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.myprovider.com/v1/generate",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": self.model, "prompt": prompt}
            )
            response.raise_for_status()
            return response.json()["text"]
```

**Step 2** — Register it in get_llm_provider()

```python
def get_llm_provider() -> BaseLLMProvider:
    provider = os.getenv("LLM_PROVIDER", "claude").lower()
    providers = {
        "claude":    AnthropicProvider,
        "openai":    OpenAIProvider,
        "gemini":    GeminiProvider,
        "ollama":    OllamaProvider,
        "azure":     AzureOpenAIProvider,
        "myprovider": MyProvider,   # add this line
    }
    ...
```

**Step 3** — Add the env var to .env.example

```env
# My Provider
MY_API_KEY=
MY_MODEL=my-default-model
```

**Step 4** — Update the provider pill colors in frontend/sentinel.jsx

Find the llmStatus color mapping in the header section and add your provider color.

That is it. No other files need to change.

---

## How to Add a New Anomaly Rule

Anomaly detection lives in backend/core/anomaly.py. Each rule is a function
that receives the current cluster state and returns a list of anomaly dicts.

Each anomaly dict must have these keys:

```python
{
    "sev":       "high" or "med",
    "label":     "Short rule name shown in the UI",
    "detail":    "Human-readable explanation of what was detected",
    "namespace": "affected namespace or empty string for cluster-wide"
}
```

Add your rule to the detect_anomalies() function and return the result.
The anomaly banner, health score, and auto-diagnosis will all pick it up automatically.

---

## Submitting a Pull Request

1. Make sure the server starts cleanly with DEV_MODE=true
2. Test your change against at least one API endpoint
3. Update CHANGELOG.md under the Unreleased section
4. Push your branch and open a pull request against main
5. Describe what the change does and why in the PR description

Please do not commit .env files, real API keys, kubeconfig files, or
the sentinel.db SQLite database.

---

## Code Style

- Python: follow PEP 8, use type hints on all function signatures, add docstrings to new functions
- React: keep all styles as inline JavaScript objects consistent with the existing C object pattern
- Commit messages: use conventional commits format
  - feat: for new features
  - fix: for bug fixes
  - docs: for documentation changes
  - chore: for maintenance tasks

---

## Reporting Bugs

Open an issue on GitHub with:
- The version you are running
- Whether you are using DEV_MODE or a real cluster
- The full error message or unexpected behavior
- Steps to reproduce

---

## Questions

Open a GitHub Discussion or leave a comment on the latest LinkedIn post at
linkedin.com/in/OsamaOracle
