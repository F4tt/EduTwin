#!/usr/bin/env pwsh
# EduTwin - All-in-one script
# Usage:
#   .\start.ps1          # Start (hot reload enabled)
#   .\start.ps1 -Build   # Rebuild images
#   .\start.ps1 -Down    # Stop all containers
#   .\start.ps1 -Logs    # View logs
#   .\start.ps1 -Clean   # Clean cache & rebuild

param(
    [switch]$Build,
    [switch]$Down,
    [switch]$Logs,
    [switch]$Clean
)

$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"

Write-Host "=== EDUTWIN ===" -ForegroundColor Cyan

# Clean cache
if ($Clean) {
    Write-Host "Cleaning Docker cache..." -ForegroundColor Yellow
    docker compose down -v
    docker system prune -f
    docker builder prune -f
    Write-Host "[OK] Cache cleaned. Run .\start.ps1 -Build to rebuild" -ForegroundColor Green
    exit 0
}

# Stop containers
if ($Down) {
    Write-Host "Stopping containers..." -ForegroundColor Yellow
    docker compose down
    Write-Host "[OK] Stopped" -ForegroundColor Green
    exit 0
}

# View logs
if ($Logs) {
    docker compose logs -f --tail=100
    exit 0
}

# Build images
if ($Build) {
    Write-Host "Building images..." -ForegroundColor Yellow
    Write-Host "First build: ~5-8 phut | Rebuild: ~30s - 2 phut" -ForegroundColor Gray
    
    docker compose build --parallel
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Build complete!" -ForegroundColor Green
}

# Start containers
Write-Host "Starting EduTwin..." -ForegroundColor Cyan
docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] EduTwin is running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services:" -ForegroundColor Cyan
    Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor White
    Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
    Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  Grafana:   http://localhost:3001 (admin/admin)" -ForegroundColor White
    Write-Host "  Adminer:   http://localhost:8081" -ForegroundColor White
    Write-Host ""
    Write-Host "Hot Reload: ENABLED" -ForegroundColor Green
    Write-Host "  - Edit backend/*.py   -> Auto reload (1-2s)" -ForegroundColor Gray
    Write-Host "  - Edit frontend/src/* -> HMR instant!" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 -Logs   # View logs" -ForegroundColor Gray
    Write-Host "  .\start.ps1 -Down   # Stop" -ForegroundColor Gray
    Write-Host "  .\start.ps1 -Build  # Rebuild (when dependencies change)" -ForegroundColor Gray
    Write-Host "  .\start.ps1 -Clean  # Clean cache" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Tip: Use '.\start.ps1 -Logs' to watch logs" -ForegroundColor Gray
} else {
    Write-Host "[ERROR] Failed to start!" -ForegroundColor Red
    Write-Host "Check logs: .\start.ps1 -Logs" -ForegroundColor Yellow
    exit 1
}
