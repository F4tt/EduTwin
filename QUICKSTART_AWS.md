# Hướng dẫn nhanh để bắt đầu deploy

## Cách 1: Setup thủ công (Khuyến nghị cho người mới)

### Bước 1: Cài đặt AWS CLI
```powershell
# Kiểm tra đã cài chưa
aws --version

# Nếu chưa có, tải tại: https://aws.amazon.com/cli/
```

### Bước 2: Cấu hình AWS Credentials
```powershell
aws configure
# Nhập Access Key ID và Secret Access Key từ AWS Console
```

### Bước 3: Chạy script setup tự động
```powershell
# Thay YOUR_DB_PASSWORD và YOUR_OPENAI_KEY
.\aws-setup.ps1 -ProjectName "edutwin" -Region "ap-southeast-1" -DbPassword "YOUR_DB_PASSWORD" -OpenAIKey "YOUR_OPENAI_KEY"
```

### Bước 4: Tạo VPC và RDS (sử dụng AWS Console)
- Làm theo hướng dẫn trong `DEPLOYMENT_GUIDE.md` phần 2.1 và 2.2

### Bước 5: Build và push Docker images
```powershell
# Build images
.\build-images.ps1

# Login vào ECR
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com

# Tag và push
docker tag edutwin-backend:test $ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-backend:latest
docker tag edutwin-frontend:test $ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-frontend:latest

docker push $ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-backend:latest
docker push $ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-frontend:latest
```

### Bước 6: Tạo Load Balancer và ECS Services
- Làm theo hướng dẫn trong `DEPLOYMENT_GUIDE.md` phần 2.8 và 4.2

---

## Cách 2: Sử dụng Terraform (Tự động hóa hoàn toàn)

### Bước 1: Cài đặt Terraform
```powershell
# Tải tại: https://www.terraform.io/downloads
terraform --version
```

### Bước 2: Tạo file terraform.tfvars
```powershell
cd terraform
notepad terraform.tfvars
```

Nội dung file:
```hcl
aws_region     = "ap-southeast-1"
project_name   = "edutwin"
db_password    = "YOUR_SECURE_PASSWORD_HERE"
openai_api_key = "sk-your-openai-key-here"
```

### Bước 3: Chạy Terraform
```powershell
cd terraform

# Khởi tạo
terraform init

# Xem kế hoạch
terraform plan

# Apply (tạo infrastructure)
terraform apply
# Nhập 'yes' để xác nhận
```

### Bước 4: Lưu outputs
```powershell
terraform output
# Lưu lại ALB DNS, RDS endpoint, ECR URLs
```

### Bước 5: Build và push images (tương tự Cách 1 - Bước 5)

---

## Cách 3: Deploy nhanh với GitHub Actions (sau khi đã có infrastructure)

### Bước 1: Thêm secrets vào GitHub
1. Vào repository Settings → Secrets and variables → Actions
2. Thêm:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

### Bước 2: Push code lên GitHub
```powershell
git add .
git commit -m "Add AWS deployment configuration"
git push origin master
```

GitHub Actions sẽ tự động build và deploy!

---

## Checklist nhanh

### Trước khi deploy:
- [ ] AWS Account đã tạo
- [ ] AWS CLI đã cài và cấu hình
- [ ] Đã chuẩn bị: DB password, OpenAI API key
- [ ] Đã chọn AWS region (khuyến nghị: ap-southeast-1)

### Infrastructure cơ bản:
- [ ] VPC và Subnets
- [ ] RDS PostgreSQL
- [ ] ECR Repositories
- [ ] ECS Cluster
- [ ] Load Balancer
- [ ] Security Groups
- [ ] IAM Roles

### Deployment:
- [ ] Docker images đã build
- [ ] Images đã push lên ECR
- [ ] ECS Services đã tạo
- [ ] Application accessible qua ALB DNS

### CI/CD:
- [ ] GitHub Secrets đã thêm
- [ ] Workflow đã test

---

## Ước tính thời gian

- **Cách 1 (Thủ công)**: 2-3 giờ (lần đầu)
- **Cách 2 (Terraform)**: 30-60 phút
- **Cách 3 (GitHub Actions)**: 10-15 phút (sau khi infrastructure đã có)

---

## Chi phí ước tính

### Free Tier (12 tháng đầu):
- ~$30-40/tháng

### Sau Free Tier:
- ~$80-100/tháng

### Tối ưu hóa:
- Sử dụng Fargate Spot: Giảm ~60%
- Stop services khi không dùng: $0
- Dùng RDS t3.micro: Tiết kiệm ~$10/tháng

---

## Hỗ trợ

Nếu gặp vấn đề, kiểm tra:
1. CloudWatch Logs: `/ecs/edutwin-backend`, `/ecs/edutwin-frontend`
2. ECS Console: Task status, Service events
3. RDS Console: Connection status
4. Security Groups: Inbound/Outbound rules

Đọc chi tiết trong `DEPLOYMENT_GUIDE.md`
