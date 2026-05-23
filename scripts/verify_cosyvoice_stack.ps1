$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$dockerPaths = @("C:\Program Files\Docker\Docker\resources\bin", "C:\Program Files\Docker\Docker")
$env:Path = ($dockerPaths -join ";") + ";" + $env:Path
$env:HF_ENDPOINT = "https://hf-mirror.com"

Write-Host "== Windows features ==" -ForegroundColor Cyan
foreach ($feature in @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform", "Microsoft-Hyper-V-All")) {
  Get-WindowsOptionalFeature -Online -FeatureName $feature | Select-Object FeatureName, State, RestartNeeded
}

Write-Host "== WSL ==" -ForegroundColor Cyan
wsl --status
wsl -l -v

Write-Host "== Docker CLI ==" -ForegroundColor Cyan
docker --version
docker compose version

Write-Host "== Docker Engine ==" -ForegroundColor Cyan
docker info
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker Engine is not ready. Open Docker Desktop once, wait until it says running, then rerun this script." -ForegroundColor Yellow
  exit 1
}

Write-Host "== FastAPI health ==" -ForegroundColor Cyan
try {
  Invoke-RestMethod http://127.0.0.1:8000/health
} catch {
  Write-Host "FastAPI is not running. Starting backend..." -ForegroundColor Yellow
  Start-Process -FilePath "$root\start_backend.bat" -WindowStyle Hidden
  Start-Sleep -Seconds 8
  Invoke-RestMethod http://127.0.0.1:8000/health
}

Write-Host "== Start CosyVoice container ==" -ForegroundColor Cyan
docker compose up --build -d cosyvoice

Write-Host "Waiting for CosyVoice port 50000..." -ForegroundColor Cyan
for ($i = 0; $i -lt 60; $i++) {
  try {
    $client = New-Object Net.Sockets.TcpClient
    $client.Connect("127.0.0.1", 50000)
    $client.Close()
    Write-Host "CosyVoice port is open." -ForegroundColor Green
    break
  } catch {
    Start-Sleep -Seconds 5
  }
}

Write-Host "== Containers ==" -ForegroundColor Cyan
docker compose ps

Write-Host "== FastAPI CosyVoice route ==" -ForegroundColor Cyan
Push-Location "$root\apps\api"
.\.venv\Scripts\python.exe -c "from app.main import app; print('/api/cosyvoice/clone' in [r.path for r in app.routes])"
Pop-Location

Write-Host "CosyVoice stack verification finished." -ForegroundColor Green
