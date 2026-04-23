# Changelog

All notable changes to Kubernetes Sentinel are documented here.

---

## [Unreleased]

### Planned
- Docker image published to GitHub Container Registry (ghcr.io)
  - Automated build via GitHub Actions on every push to main
  - Multi-arch image supporting amd64 and arm64 for broad cluster compatibility
  - Image tagged by version and latest
  - k8s/deployment.yaml updated to pull from ghcr.io/OsamaOracle/k8s-sentinel
- Multi-cluster support with cluster switcher in the dashboard header
- Configurable anomaly thresholds per namespace via settings page
- Deployment diff viewer showing before and after spec on every rollout
- Predictive alerting based on trend analysis before thresholds are reached
- RBAC audit view flagging service accounts with write access
- Helm release tracking with version and outdated chart detection
- GitHub Actions integration linking deployment failures to commits
- Cost estimation per namespace based on resource requests and cloud pricing
- Email digest with daily or weekly cluster health summary

---

## [1.3.0] - 2026-04-12

### Added
- Namespace filter bar above the health score row with clickable namespace pills
- All pill selected by default showing the full cluster view
- Active namespace filter applied simultaneously across Pods, Events, and Resources tabs
- Namespace favorites with a star toggle on each pill
- Favorited namespaces always float to the front of the filter bar
- Favorites persisted in localStorage so they survive page refreshes
- Tab counts update dynamically to reflect the currently filtered namespace
- Diagnosis history tab showing every past AI diagnosis saved to SQLite
- Search input on the history tab with 400ms debounce for fast filtering
- Each history card shows timestamp, anomaly count, pod count, summary, root cause, and kubectl commands
- Summary and kubectl command blocks are collapsible to keep the history list clean
- Re-run button on each history card that copies the focus text back to the Diagnosis tab
- Empty state on the history tab when no diagnoses have been run yet
- Five realistic mock history entries in DEV_MODE
- Auto-refresh diagnosis that triggers automatically when new anomalies are detected
- GET /api/diagnose/auto-status endpoint returning trigger state and last triggered timestamp
- Toast notification at the bottom right when an auto-diagnosis runs in the background
- Red badge on the Diagnosis tab label when a new auto result is available
- Badge clears automatically when the user opens the Diagnosis tab
- AUTO_DIAGNOSIS_INTERVAL_SECONDS env var controlling how often auto-diagnosis can fire (default 300)

### Changed
- Dashboard now has 6 tabs in this order: Pods, Events, Resources, Timeline, History, Diagnosis
- Nodes are always shown unfiltered in the Resources tab regardless of namespace selection
- .env.example updated with AUTO_DIAGNOSIS_INTERVAL_SECONDS

---

## [1.2.0] - 2026-04-12

### Added
- Slack alerting via incoming webhook when anomalies are detected
- Microsoft Teams alerting via Adaptive Card webhook
- Alert cooldown system preventing duplicate notifications (default 5 minutes)
- GET /api/alerts/status endpoint showing which channels are configured
- Alert status indicator in the dashboard header showing active channels
- Pod log viewer as a slide-in drawer on the right side of the dashboard
- GET /api/pods/{namespace}/{pod_name}/logs endpoint with line count and previous container support
- Color-coded log lines in the viewer: red for ERROR and FATAL, amber for WARN, muted for DEBUG
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

## [1.1.0] - 2026-04-06

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

## [1.0.0] - 2026-04-06

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
