# Hướng dẫn chạy hệ thống EduTwin với Docker Compose

## Yêu cầu hệ thống
- Docker Desktop (Windows/Mac) hoặc Docker Engine (Linux)
- Docker Compose
- Ít nhất 4GB RAM
- 10GB dung lượng ổ cứng trống

## Cấu trúc dự án
```
EduTwin/
├── backend/           # FastAPI backend
├── frontend/          # Streamlit frontend  
├── docker-compose.yml # Cấu hình Docker Compose
├── docker.env         # Biến môi trường
└── DOCKER_SETUP.md    # File hướng dẫn này
```

## Các dịch vụ được triển khai
1. **PostgreSQL Database** (Port 5432)
2. **Redis Cache** (Port 6379) 
3. **Backend API** (Port 8000)
4. **Frontend Streamlit** (Port 8501)

## Hướng dẫn từng bước

### Bước 1: Kiểm tra Docker
```bash
docker --version
docker-compose --version
```

### Bước 2: Di chuyển vào thư mục dự án
```bash
cd "D:\TaiXuong\AI project\EduTwin"
```

### Bước 3: Chạy toàn bộ hệ thống
```bash
# Xây dựng và chạy tất cả services
docker-compose up --build

# Hoặc chạy ở chế độ background
docker-compose up --build -d
```

### Bước 4: Kiểm tra trạng thái
```bash
# Xem trạng thái các container
docker-compose ps

# Xem logs của tất cả services
docker-compose logs

# Xem logs của service cụ thể
docker-compose logs backend
docker-compose logs frontend
```

### Bước 5: Truy cập ứng dụng
- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Bước 6: Dừng hệ thống
```bash
# Dừng tất cả services
docker-compose down

# Dừng và xóa volumes (xóa dữ liệu database)
docker-compose down -v
```

## Lệnh hữu ích

### Quản lý services
```bash
# Chạy lại một service cụ thể
docker-compose restart backend

# Xem logs real-time
docker-compose logs -f backend

# Vào trong container
docker-compose exec backend bash
docker-compose exec frontend bash
```

### Debugging
```bash
# Xem logs chi tiết
docker-compose logs --tail=100 backend

# Kiểm tra kết nối database
docker-compose exec backend python -c "import psycopg2; print('DB OK')"

# Kiểm tra kết nối Redis
docker-compose exec backend python -c "import redis; print('Redis OK')"
```

### Dọn dẹp
```bash
# Xóa tất cả containers và networks
docker-compose down --remove-orphans

# Xóa images không sử dụng
docker system prune -a

# Xóa volumes (CẢNH BÁO: Sẽ xóa dữ liệu database)
docker volume prune
```

## Xử lý sự cố thường gặp

### 1. Port đã được sử dụng
```bash
# Kiểm tra port nào đang được sử dụng
netstat -an | findstr :8000
netstat -an | findstr :8501

# Thay đổi port trong docker-compose.yml nếu cần
```

### 2. Lỗi kết nối database
```bash
# Kiểm tra database có chạy không
docker-compose exec db psql -U edutwin_user -d edutwin

# Reset database
docker-compose down -v
docker-compose up --build
```

### 3. Lỗi build
```bash
# Xóa cache và build lại
docker-compose build --no-cache
docker-compose up --build
```

### 4. Lỗi memory
```bash
# Tăng memory limit cho Docker Desktop
# Settings > Resources > Memory > 4GB+
```

## Monitoring và Health Check

### Kiểm tra health của services
```bash
# Xem trạng thái chi tiết
docker-compose ps

# Kiểm tra resource usage
docker stats
```

### Backup database
```bash
# Backup database
docker-compose exec db pg_dump -U edutwin_user edutwin > backup.sql

# Restore database
docker-compose exec -T db psql -U edutwin_user -d edutwin < backup.sql
```

## Cấu hình nâng cao

### Thay đổi cấu hình database
Chỉnh sửa file `docker.env`:
```
POSTGRES_DB=your_database_name
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

### Thay đổi port
Chỉnh sửa file `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Thay đổi port backend
  - "8502:8501"  # Thay đổi port frontend
```

## Lưu ý quan trọng
- Luôn backup dữ liệu trước khi thay đổi cấu hình
- Không commit file `.env` vào git (chứa thông tin nhạy cảm)
- Sử dụng `docker-compose down -v` để xóa hoàn toàn dữ liệu
- Kiểm tra logs khi có lỗi: `docker-compose logs [service_name]`
