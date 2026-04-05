#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy k8s-sentinel to the current kubectl context.
.DESCRIPTION
    Applies all Kubernetes manifests in order, waits for the rollout to complete,
    and prints next-step instructions.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$K8sDir   = Join-Path $RepoRoot "k8s"

function Step([string]$msg) {
    Write-Host ""
    Write-Host "  $msg" -ForegroundColor Cyan
}

function Ok([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Warn([string]$msg) {
    Write-Host "  ! $msg" -ForegroundColor Yellow
}

# ── Pre-flight: verify kubectl is available ───────────────────────────────────
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  ERROR: kubectl not found in PATH." -ForegroundColor Red
    exit 1
}

$Context = kubectl config current-context 2>&1
Write-Host ""
Write-Host "  k8s-sentinel — deploy" -ForegroundColor Cyan
Write-Host "  ──────────────────────" -ForegroundColor DarkGray
Write-Host "  kubectl context : $Context" -ForegroundColor DarkGray

# Confirm before deploying
Write-Host ""
$Confirm = Read-Host "  Deploy to this context? [y/N]"
if ($Confirm -notmatch '^[Yy]$') {
    Write-Host "  Aborted." -ForegroundColor Yellow
    exit 0
}

# ── Check sentinel-secrets exists ─────────────────────────────────────────────
$SecretExists = kubectl get secret sentinel-secrets -n k8s-sentinel 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "Secret 'sentinel-secrets' not found in namespace k8s-sentinel."
    Warn "Create it before the pod can start:"
    Warn ""
    Warn "  kubectl create secret generic sentinel-secrets ``"
    Warn "    --from-literal=ANTHROPIC_API_KEY=sk-ant-... ``"
    Warn "    -n k8s-sentinel"
    Warn ""
}

# ── Apply manifests in order ──────────────────────────────────────────────────
$Manifests = @(
    @{ File = "namespace.yaml"; Label = "Namespace" },
    @{ File = "rbac.yaml";      Label = "RBAC (ServiceAccount / ClusterRole / ClusterRoleBinding)" },
    @{ File = "configmap.yaml"; Label = "ConfigMap" },
    @{ File = "deployment.yaml"; Label = "Deployment" },
    @{ File = "service.yaml";   Label = "Service" }
)

foreach ($m in $Manifests) {
    $Path = Join-Path $K8sDir $m.File
    Step "Applying $($m.Label)..."
    kubectl apply -f $Path
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ERROR: kubectl apply failed for $($m.File)." -ForegroundColor Red
        exit 1
    }
    Ok $m.Label
}

# ── Wait for rollout ──────────────────────────────────────────────────────────
Step "Waiting for rollout to complete..."
kubectl rollout status deployment/k8s-sentinel -n k8s-sentinel --timeout=120s
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: Rollout did not complete within 120 s." -ForegroundColor Red
    Write-Host "  Check pod logs:" -ForegroundColor Yellow
    Write-Host "    kubectl logs -l app=k8s-sentinel -n k8s-sentinel" -ForegroundColor DarkGray
    exit 1
}

Ok "Rollout complete."

# ── Success ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ──────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Deployment successful!" -ForegroundColor Green
Write-Host "  ──────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Forward the service port to your machine:" -ForegroundColor White
Write-Host "       .\scripts\port-forward.ps1" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Or expose via Ingress / LoadBalancer." -ForegroundColor White
Write-Host ""
Write-Host "  3. Check pod status at any time:" -ForegroundColor White
Write-Host "       kubectl get pods -n k8s-sentinel" -ForegroundColor DarkGray
Write-Host "       kubectl logs -l app=k8s-sentinel -n k8s-sentinel" -ForegroundColor DarkGray
Write-Host ""
