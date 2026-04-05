#Requires -Version 5.1
<#
.SYNOPSIS
    Forward k8s-sentinel service port 8000 to localhost:8000.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Pre-flight ────────────────────────────────────────────────────────────────
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  ERROR: kubectl not found in PATH." -ForegroundColor Red
    exit 1
}

$Context = kubectl config current-context 2>&1

Write-Host ""
Write-Host "  k8s-sentinel — port-forward" -ForegroundColor Cyan
Write-Host "  ────────────────────────────" -ForegroundColor DarkGray
Write-Host "  kubectl context : $Context" -ForegroundColor DarkGray
Write-Host "  Namespace       : k8s-sentinel" -ForegroundColor DarkGray
Write-Host "  Local port      : 8000 → svc/k8s-sentinel:8000" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Dashboard available at http://localhost:8000" -ForegroundColor Green
Write-Host "  Swagger UI        at http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

kubectl port-forward svc/k8s-sentinel 8000:8000 -n k8s-sentinel
