#Requires -Version 5.1
<#
.SYNOPSIS
    Start the k8s-sentinel backend in development mode with mock cluster data.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot  = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir    = Join-Path $BackendDir ".venv"
$Activate   = Join-Path $VenvDir "Scripts\Activate.ps1"

Write-Host ""
Write-Host "  k8s-sentinel — dev mode" -ForegroundColor Cyan
Write-Host "  ────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── Navigate to backend/ ──────────────────────────────────────────────────────
Set-Location $BackendDir
Write-Host "[1/5] Working directory: $BackendDir" -ForegroundColor DarkGray

# ── Create virtualenv if absent ───────────────────────────────────────────────
if (-not (Test-Path $VenvDir)) {
    Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[2/5] Virtual environment already exists." -ForegroundColor DarkGray
}

# ── Activate ──────────────────────────────────────────────────────────────────
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor DarkGray
& $Activate

# ── Install dependencies ──────────────────────────────────────────────────────
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

# ── Environment ───────────────────────────────────────────────────────────────
$env:DEV_MODE = "true"
Write-Host ""
Write-Host "  DEV_MODE = true  (mock cluster data, no kubeconfig required)" -ForegroundColor Green
Write-Host ""

# Prompt for API key securely (input is masked)
$ApiKeySecure = Read-Host "  Enter ANTHROPIC_API_KEY (leave blank to skip diagnosis)" -AsSecureString
$ApiKeyPlain  = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ApiKeySecure))

if ($ApiKeyPlain -ne "") {
    $env:ANTHROPIC_API_KEY = $ApiKeyPlain
    Write-Host "  ANTHROPIC_API_KEY set." -ForegroundColor Green
} else {
    Write-Host "  ANTHROPIC_API_KEY not set — /api/diagnose will return 500." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[5/5] Starting uvicorn..." -ForegroundColor Cyan
Write-Host "  http://localhost:8000        — API root"  -ForegroundColor DarkGray
Write-Host "  http://localhost:8000/docs   — Swagger UI" -ForegroundColor DarkGray
Write-Host "  http://localhost:8000/healthz — Health check" -ForegroundColor DarkGray
Write-Host ""

uvicorn main:app --reload --port 8000
