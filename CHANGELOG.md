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