# Changelog

All notable changes to Kubernetes Sentinel are documented here.

---

## [Unreleased]

### Planned
- Docker image published to GitHub Container Registry (ghcr.io)
  - Automated build via GitHub Actions on every push to main
  - Multi-arch image supporting amd64 and arm64
  - Image tagged by version and latest
  - k8s/deployment.yaml updated to pull from ghcr.io/OsamaOracle/k8s-sentinel
- Multi-cluster support with cluster switcher in the dashboard header
- Configurable anomaly thresholds per namespace via settings page
- Deployment diff viewer showing before and after spec on every rollout
- Predictive alerting based on trend analysis before thresholds are reached
- RBAC audit view flagging service accounts with write access
- Helm release tracking with version and outdated chart detection
- Cost estimation per namespace based on resource requests and cloud pricing
- Email digest with daily or weekly cluster health summary

---

## [1.6.0] - 2026-05-30

### Added
- GitHub Actions CI/CD workflow that automatically builds and publishes the Docker image on every push to main
- Docker image published to GitHub Container Registry at ghcr.io/osamaoracle/k8s-sentinel
- Image tagged automatically with version number, major.minor, and latest on every release
- Multi-architecture build supporting amd64 and arm64
- GitHub Actions cache for Docker layers reducing build time on repeat runs
- CI workflow that runs on every push and pull request to catch syntax errors before merge
- Python syntax check across all backend files using py_compile
- Import validation running python -c "import main" with DEV_MODE=true to catch missing modules
- One-command Kubernetes deployment using raw GitHub URLs, no local build required
- Pull request builds run without pushing so contributors can verify their changes safely
- Node.js deprecation fixed by upgrading docker/build-push-action to v6

### Changed
- k8s/deployment.yaml image updated from placeholder to ghcr.io/osamaoracle/k8s-sentinel:latest
- imagePullPolicy set to Always so clusters always pull the latest published image
- README updated with GitHub Actions badges and one-command deploy section

---

## [1.5.0] - 2026-05-30

### Added
- Natural Language kubectl tab allowing plain English instructions to be translated into kubectl commands
- POST /api/kubectl/translate endpoint using the active LLM provider to generate commands with risk scoring
- POST /api/kubectl/execute endpoint running translated commands with strict security restrictions
- Commands are blocked if they contain rm, delete secret, delete namespace, exec, or port-forward
- Risk scoring on every translation: LOW in green, MEDIUM in amber, HIGH in red with plain English reason
- Run and Run All buttons to execute translated commands directly from the dashboard
- Execution results showing stdout in green, stderr in red, and a success or failure badge
- Cluster Conversation tab with a full persistent chat interface powered by the active LLM
- POST /api/conversation endpoint passing full real-time cluster state as context to the LLM
- Chat bubbles with user messages right-aligned in blue and assistant messages left-aligned in dark
- Auto-scroll to latest message, three-dot loading animation, and Enter to send
- Four starter questions shown on empty conversation to guide first-time users
- Clear conversation button to start fresh
- Incident Report Generator tab producing professional postmortem documents in one click
- POST /api/report/generate endpoint pulling health timeline, diagnosis history, and current cluster state
- Reports include summary, timeline table, impact assessment, root cause, remediation steps, and prevention recommendations
- GET /api/report/history endpoint returning previously generated reports
- Reports table added to SQLite database with insert_report and get_report_history functions
- Copy Markdown and Download .md buttons on every generated report
- P1, P2, P3 severity selector with color-coded buttons: red, amber, and blue
- Report history cards below the generator showing previous reports with click to view

### Changed
- Dashboard now has 9 tabs: Pods, Events, Resources, Timeline, History, kubectl, Chat, Report, Diagnosis
- database.py updated with reports table initialized on startup

---

## [1.4.0] - 2026-05-30

### Added
- Multi-LLM provider support with a clean abstraction layer in core/llm.py
- AnthropicProvider using claude-sonnet-4-20250514 (default)
- OpenAIProvider using gpt-4o via the OpenAI chat completions API
- GeminiProvider using gemini-1.5-pro via the Google Generative Language API
- OllamaProvider for fully local inference with any Ollama model (default llama3)
- AzureOpenAIProvider for enterprise deployments via Azure OpenAI Service
- LLM_PROVIDER env var to switch providers without touching any code
- GET /api/llm/status endpoint returning active provider, model, and configuration state
- Color-coded provider pill in the dashboard header showing the active LLM
- System prompt centralized in llm.py and injected correctly for each provider
- All providers return the same structured JSON format for diagnosis results
- Silent fallback in the frontend if the llm/status endpoint is unreachable

### Changed
- diagnosis.py no longer imports the Anthropic SDK directly
- All LLM calls now go through the get_llm_provider() factory function
- Error handling in diagnosis.py now catches httpx.HTTPStatusError and httpx.RequestError
- .env.example updated with all provider variables and comments

---

## [1.3.0] - 2026-05-30

### Added
- Namespace filter bar above the health score row with clickable namespace pills
- All pill selected by default showing the full cluster view
- Active namespace filter applied simultaneously across Pods, Events, and Resources tabs
- Namespace favorites with a star toggle on each pill
- Favorited namespaces always float to the front of the filter bar
- Favorites persisted in localStorage under key k8s-sentinel-favorites
- Tab counts update dynamically to reflect the currently filtered namespace
- Diagnosis history tab showing every past AI diagnosis saved to SQLite
- Search input on the history tab with 400ms debounce for fast filtering
- Each history card shows timestamp, anomaly count, pod count, summary, root cause, and kubectl commands
- Summary and kubectl command blocks are collapsible to keep the history list clean
- Re-run button on each history card that copies the focus text back to the Diagnosis tab
- Five realistic mock history entries in DEV_MODE
- Auto-refresh diagnosis that triggers automatically when new anomalies are detected
- GET /api/diagnose/auto-status endpoint returning trigger state and last triggered timestamp
- Toast notification at the bottom right when an auto-diagnosis runs in the background
- Red badge on the Diagnosis tab label when a new auto result is available
- AUTO_DIAGNOSIS_INTERVAL_SECONDS env var controlling how often auto-diagnosis can fire

### Changed
- Dashboard now has 6 tabs: Pods, Events, Resources, Timeline, History, Diagnosis
- Nodes are always shown unfiltered in the Resources tab regardless of namespace selection
- .env.example updated with AUTO_DIAGNOSIS_INTERVAL_SECONDS

---

## [1.2.0] - 2026-05-30

### Added
- Slack alerting via incoming webhook when anomalies are detected
- Microsoft Teams alerting via Adaptive Card webhook
- Alert cooldown system preventing duplicate notifications (default 5 minutes)
- GET /api/alerts/status endpoint showing which channels are configured
- Alert status indicator in the dashboard header showing active channels
- Pod log viewer as a slide-in drawer on the right side of the dashboard
- GET /api/pods/{namespace}/{pod_name}/logs endpoint with line count and previous container support
- Color-coded log lines: red for ERROR and FATAL, amber for WARN, muted for DEBUG
- Line numbers in the log viewer for easier navigation
- Previous container toggle to inspect logs from crashed containers
- Line count selector allowing 50, 100, 200, or 500 lines
- Logs button on every pod row in the Pods tab
- Mock log output in DEV_MODE with realistic ERROR and WARN lines

### Changed
- Pods tab now includes a Logs button column on every row
- Dashboard header now shows alert channel status next to the live indicator
- .env.example updated with SLACK_WEBHOOK_URL, TEAMS_WEBHOOK_URL, and ALERT_COOLDOWN_SECONDS

---

## [1.1.0] - 2026-05-30

### Added
- Historical health timeline with a 24-hour SVG sparkline graph
- SQLite database recording health score every 15 seconds
- Timeline tab on the dashboard showing min, max, and average score cards
- Health score trend classification showing Rising, Stable, or Declining
- GET /api/timeline endpoint returning the last 24 hours of health snapshots
- Mock timeline data in DEV_MODE with realistic score variation

### Changed
- Dashboard expanded from 4 tabs to 5 tabs adding the Timeline view
- Poller now writes a health snapshot to the database on every poll cycle

---

## [1.0.0] - 2026-05-30

### Added
- Initial release of Kubernetes Sentinel
- FastAPI backend with a background polling thread hitting the Kubernetes API every 15 seconds
- React dashboard with 4 tabs covering Pods, Events, Resources, and Diagnosis
- Live health score from 0 to 100 computed from pod and node state
- 7 anomaly detection rules covering CrashLoopBackOff, OOMKilled, NodeNotReady,
  HighRestartCount, BackOff, FailedMount, and CPUThrottling
- AI-powered diagnosis via Claude API returning plain-English root cause and kubectl remediation commands
- Server-Sent Events stream for real-time browser updates without polling
- Read-only ClusterRole RBAC so the sentinel can never modify cluster resources
- DEV_MODE with realistic mock data for development and demos without a cluster
- Kubernetes manifests covering namespace, rbac, deployment, service, and configmap
- PowerShell scripts for local development, cluster deployment, and port forwarding
- Multi-stage Dockerfile running as a non-root sentinel user
- Full README covering local dev, kubeconfig, and in-cluster deployment options