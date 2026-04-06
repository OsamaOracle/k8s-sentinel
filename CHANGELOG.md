# Changelog

All notable changes to Kubernetes Sentinel are documented here.

---

## [Unreleased]

### Planned
- Docker image published to GitHub Container Registry (ghcr.io)
  - Automated build via GitHub Actions on every push to main
  - Multi-arch image (amd64 + arm64) for broad cluster compatibility
  - Image tagged by version and latest
  - k8s/deployment.yaml updated to pull from ghcr.io/OsamaOracle/k8s-sentinel
- Slack and Teams alerting
- Pod log viewer inline in dashboard
- Multi-cluster support

---

## [1.1.0] - In Progress

### Added
- Historical health timeline — 24-hour sparkline graph showing cluster health score over time
- SQLite database recording health score every 15 seconds
- Timeline tab on the dashboard with min, max, and average score indicators
- Health score trend analysis — rising, stable, or declining classification
- GET /api/timeline endpoint returning the last 24 hours of health snapshots

### Changed
- Dashboard now has 5 tabs: Pods, Events, Resources, Timeline, Diagnosis
- Poller now writes health snapshots to database on every poll cycle

---

## [1.0.0] - 2026-04-06

### Added
- Initial release of Kubernetes Sentinel
- FastAPI backend with background Kubernetes polling every 15 seconds
- React dashboard with 4 tabs: Pods, Events, Resources, Diagnosis
- Live health score (0-100) computed from pod and node state
- 7 anomaly detection rules: CrashLoopBackOff, OOMKilled, NodeNotReady,
  HighRestartCount, BackOff, FailedMount, CPUThrottling
- AI-powered diagnosis via Claude API with kubectl remediation commands
- Server-Sent Events stream for real-time browser updates
- Read-only ClusterRole RBAC — sentinel never modifies cluster resources
- DEV_MODE with realistic mock data for development without a cluster
- Kubernetes manifests: namespace, rbac, deployment, service, configmap
- PowerShell scripts: dev.ps1, deploy.ps1, port-forward.ps1
- Multi-stage Dockerfile running as non-root sentinel user
- Full README covering local, kubeconfig, and in-cluster deployment
