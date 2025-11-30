# Script PowerShell để build và test images trước khi deploy

Write-Host "🔨 Building EduTwin Docker Images..." -ForegroundColor Cyan

# Backend
Write-Host "`n📦 Building Backend image..." -ForegroundColor Yellow
docker build -t edutwin-backend:test -f backend/Dockerfile.prod backend/
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Backend build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Backend image built successfully!" -ForegroundColor Green

# Frontend
Write-Host "`n📦 Building Frontend image..." -ForegroundColor Yellow
docker build -t edutwin-frontend:test -f frontend_react/Dockerfile.prod frontend_react/
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Frontend build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Frontend image built successfully!" -ForegroundColor Green

Write-Host "`n🎉 All images built successfully!" -ForegroundColor Green
Write-Host "`nTo test locally:" -ForegroundColor Cyan
Write-Host "  docker run -p 8000:8000 edutwin-backend:test" -ForegroundColor White
Write-Host "  docker run -p 80:80 edutwin-frontend:test" -ForegroundColor White
