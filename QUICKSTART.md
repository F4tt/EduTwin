# EduTwin - Quick Start

## 🚀 Cài đặt lần đầu

```powershell
# 1. Build images (chỉ 1 lần)
.\start.ps1 -Build

# 2. Start
.\start.ps1
```

**Thời gian build lần đầu**: ~5-8 phút

## 🔄 Sử dụng hằng ngày

```powershell
# Chỉ cần start (KHÔNG cần build lại!)
.\start.ps1
```

**Thời gian khởi động**: ~15-20 giây

### Sửa code:
- ✅ **Backend (*.py)**: Tự động reload sau 1-2 giây
- ✅ **Frontend (*.jsx)**: Hot Module Replacement (HMR) - instant!
- ❌ **KHÔNG CẦN** rebuild!

## 📝 Commands

```powershell
.\start.ps1           # Start (hot reload enabled)
.\start.ps1 -Build    # Rebuild images (khi thêm dependencies)
.\start.ps1 -Down     # Stop all containers
.\start.ps1 -Logs     # View logs
.\start.ps1 -Clean    # Clean cache & volumes
```

## 🌐 Services

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Adminer | http://localhost:8081 |
| Prometheus | http://localhost:9090 |

## 🔧 Khi nào cần rebuild?

### ❌ KHÔNG cần rebuild:
- Sửa code Python (*.py)
- Sửa code React (*.jsx, *.css)
- Thêm/sửa API endpoint
- Thêm/sửa component

### ✅ CẦN rebuild:
- Thêm package vào `requirements-*.txt`
- Thêm package vào `package.json`
- Sửa Dockerfile
- Sửa docker-compose.yml

```powershell
# Sau khi thêm dependencies
.\start.ps1 -Down
.\start.ps1 -Build
.\start.ps1
```

## 🐛 Troubleshooting

### Code không auto reload?
```powershell
# Restart container
docker compose restart backend
# hoặc
docker compose restart frontend
```

### Port đã được sử dụng?
```powershell
# Stop containers
.\start.ps1 -Down

# Kiểm tra port
netstat -ano | findstr ":8000"
netstat -ano | findstr ":3000"
```

### Lỗi khi build?
```powershell
# Clean cache và rebuild
.\start.ps1 -Clean
.\start.ps1 -Build
```

### Xem logs chi tiết:
```powershell
# Tất cả services
.\start.ps1 -Logs

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
```

## 📊 Architecture

```
EduTwin/
├── backend/              # FastAPI + Python
│   ├── Dockerfile        # Backend image (dev + prod)
│   ├── main.py
│   ├── requirements-ml.txt
│   └── requirements-base.txt
├── frontend_react/       # React + Vite
│   ├── Dockerfile        # Frontend image (dev + prod)
│   └── src/
├── docker-compose.yml    # Single compose file
├── start.ps1             # All-in-one script
└── .env                  # Environment variables
```

## 🎯 Development Workflow

```powershell
# Sáng: Start
.\start.ps1

# Cả ngày: Sửa code, test, sửa tiếp
# (auto reload - không cần build!)

# Tối: Stop (optional)
.\start.ps1 -Down
```

## 💡 Tips

### Exec vào container:
```powershell
docker exec -it edutwin_backend bash
docker exec -it edutwin_frontend sh
```

### Database commands:
```powershell
# Migrations
docker exec -it edutwin_backend alembic upgrade head

# Direct psql
docker exec -it edutwin_db psql -U edutwin_user -d edutwin_db
```

### Monitor resources:
```powershell
docker stats
docker compose ps
```

### Clean everything:
```powershell
.\start.ps1 -Down
docker system prune -a -f
docker volume prune -f
```

## 📦 Production Deployment

Để deploy production, comment out volume mounts trong `docker-compose.yml`:

```yaml
backend:
  # volumes:  # Comment out for production
  #   - ./backend:/app
```

Và thay đổi command:
```yaml
backend:
  command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

**Need help?** Check logs with `.\start.ps1 -Logs`
