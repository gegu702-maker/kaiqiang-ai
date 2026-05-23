$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker 未安装或未加入 PATH。请先安装 Docker Desktop，然后重新打开 PowerShell。" -ForegroundColor Yellow
  Write-Host "下载地址：https://www.docker.com/products/docker-desktop/"
  exit 1
}

$hasGpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  try {
    nvidia-smi | Out-Null
    $hasGpu = $true
  } catch {
    $hasGpu = $false
  }
}

if ($hasGpu) {
  Write-Host "检测到 NVIDIA GPU，使用 GPU compose override 启动 CosyVoice。" -ForegroundColor Green
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build cosyvoice
} else {
  Write-Host "未检测到可用 NVIDIA GPU，使用 CPU 模式启动 CosyVoice。" -ForegroundColor Yellow
  docker compose up --build cosyvoice
}
