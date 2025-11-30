# 🚀 Hướng dẫn Deploy EduTwin lên AWS với CI/CD

## 📋 Mục lục
1. [Chuẩn bị](#1-chuẩn-bị)
2. [Setup AWS Infrastructure](#2-setup-aws-infrastructure)
3. [Cấu hình GitHub Actions](#3-cấu-hình-github-actions)
4. [Deploy lần đầu](#4-deploy-lần-đầu)
5. [Monitoring & Maintenance](#5-monitoring--maintenance)

---

## 1. Chuẩn bị

### 1.1. Tạo AWS Account
- Truy cập [AWS Console](https://aws.amazon.com/)
- Đăng ký tài khoản (cần thẻ tín dụng)
- **Lưu ý**: AWS Free Tier cho phép dùng miễn phí 1 năm đầu với giới hạn nhất định

### 1.2. Cài đặt AWS CLI
```powershell
# Tải và cài đặt AWS CLI
# https://aws.amazon.com/cli/

# Kiểm tra cài đặt
aws --version

# Cấu hình credentials
aws configure
# Nhập:
# - AWS Access Key ID
# - AWS Secret Access Key  
# - Default region: ap-southeast-1 (Singapore) hoặc us-east-1 (Virginia)
# - Default output format: json
```

### 1.3. Các thông tin cần chuẩn bị
- [ ] Domain name (nếu có) - ví dụ: edutwin.com
- [ ] OPENAI_API_KEY
- [ ] Database password
- [ ] Secret key cho JWT

---

## 2. Setup AWS Infrastructure

### 2.1. Tạo VPC và Networking

#### Option A: Sử dụng AWS Console (Dễ cho người mới)

1. **Tạo VPC**
   - Vào AWS Console → VPC → "Create VPC"
   - Chọn "VPC and more" (tạo tự động subnets, route tables, etc.)
   - Name: `edutwin-vpc`
   - IPv4 CIDR: `10.0.0.0/16`
   - Number of AZs: 2
   - Number of public subnets: 2
   - Number of private subnets: 2
   - NAT gateways: 1 (tiết kiệm chi phí) hoặc 2 (high availability)
   - VPC endpoints: None (có thể bỏ qua)

2. **Security Groups**
   
   **a. ALB Security Group**
   ```
   Name: edutwin-alb-sg
   Inbound Rules:
   - HTTP (80) from 0.0.0.0/0
   - HTTPS (443) from 0.0.0.0/0
   ```
   
   **b. Backend Security Group**
   ```
   Name: edutwin-backend-sg
   Inbound Rules:
   - Custom TCP (8000) from ALB Security Group
   ```
   
   **c. Frontend Security Group**
   ```
   Name: edutwin-frontend-sg
   Inbound Rules:
   - HTTP (80) from ALB Security Group
   ```
   
   **d. RDS Security Group**
   ```
   Name: edutwin-rds-sg
   Inbound Rules:
   - PostgreSQL (5432) from Backend Security Group
   ```

#### Option B: Sử dụng AWS CLI (Nhanh hơn)

```powershell
# Tạo VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=edutwin-vpc}]'

# Lưu VPC ID vào biến
$VPC_ID = (aws ec2 describe-vpcs --filters "Name=tag:Name,Values=edutwin-vpc" --query "Vpcs[0].VpcId" --output text)

# Tạo Internet Gateway
aws ec2 create-internet-gateway --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=edutwin-igw}]'
$IGW_ID = (aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=edutwin-igw" --query "InternetGateways[0].InternetGatewayId" --output text)
aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID

# Tạo Subnets (public và private)
# Public Subnet 1
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone ap-southeast-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=edutwin-public-1a}]'

# Public Subnet 2
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone ap-southeast-1b --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=edutwin-public-1b}]'

# Private Subnet 1
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.11.0/24 --availability-zone ap-southeast-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=edutwin-private-1a}]'

# Private Subnet 2
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.12.0/24 --availability-zone ap-southeast-1b --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=edutwin-private-1b}]'
```

### 2.2. Tạo RDS (PostgreSQL Database)

1. Vào RDS → "Create database"
2. Cấu hình:
   - Engine: PostgreSQL 15.x
   - Templates: **Free tier** (để tiết kiệm) hoặc Production
   - DB instance identifier: `edutwin-db`
   - Master username: `edutwin_admin`
   - Master password: (tạo password mạnh và lưu lại)
   - DB instance class: `db.t3.micro` (Free tier) hoặc `db.t4g.micro`
   - Storage: 20 GB (SSD)
   - VPC: `edutwin-vpc`
   - Subnet group: Tạo mới với private subnets
   - Public access: **No**
   - VPC security group: `edutwin-rds-sg`
   - Database name: `edutwin`

3. Sau khi tạo, lưu lại **Endpoint** (ví dụ: `edutwin-db.xxxx.ap-southeast-1.rds.amazonaws.com`)

### 2.3. Tạo ECR Repositories

```powershell
# Tạo repository cho backend
aws ecr create-repository --repository-name edutwin-backend --region ap-southeast-1

# Tạo repository cho frontend
aws ecr create-repository --repository-name edutwin-frontend --region ap-southeast-1

# Lấy repository URIs
aws ecr describe-repositories --repository-names edutwin-backend edutwin-frontend --region ap-southeast-1
```

Lưu lại các URIs (ví dụ: `123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-backend`)

### 2.4. Tạo Secrets Manager

```powershell
# Lấy ACCOUNT_ID
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$REGION = "ap-southeast-1"

# Tạo secret cho DATABASE_URL
aws secretsmanager create-secret `
    --name edutwin/database-url `
    --description "Database connection string" `
    --secret-string "postgresql://edutwin_admin:YOUR_DB_PASSWORD@edutwin-db.xxxx.ap-southeast-1.rds.amazonaws.com:5432/edutwin" `
    --region $REGION

# Tạo secret cho SECRET_KEY (JWT)
aws secretsmanager create-secret `
    --name edutwin/secret-key `
    --description "JWT secret key" `
    --secret-string "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" `
    --region $REGION

# Tạo secret cho OPENAI_API_KEY
aws secretsmanager create-secret `
    --name edutwin/openai-key `
    --description "OpenAI API Key" `
    --secret-string "sk-your-openai-key-here" `
    --region $REGION
```

### 2.5. Tạo IAM Roles

#### a. ECS Task Execution Role

```powershell
# Tạo trust policy file
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -FilePath trust-policy.json -Encoding utf8

# Tạo role
aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Thêm quyền truy cập Secrets Manager
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-southeast-1:*:secret:edutwin/*"
      ]
    }
  ]
}
'@ | Out-File -FilePath secrets-policy.json -Encoding utf8

aws iam put-role-policy --role-name ecsTaskExecutionRole --policy-name SecretsManagerAccess --policy-document file://secrets-policy.json
```

#### b. ECS Task Role (cho application)

```powershell
# Tạo role
aws iam create-role --role-name ecsTaskRole --assume-role-policy-document file://trust-policy.json

# Attach policies cho S3, CloudWatch, etc. nếu cần
aws iam attach-role-policy --role-name ecsTaskRole --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
```

### 2.6. Tạo CloudWatch Log Groups

```powershell
aws logs create-log-group --log-group-name /ecs/edutwin-backend --region ap-southeast-1
aws logs create-log-group --log-group-name /ecs/edutwin-frontend --region ap-southeast-1
```

### 2.7. Tạo ECS Cluster

```powershell
aws ecs create-cluster --cluster-name edutwin-cluster --region ap-southeast-1
```

### 2.8. Tạo Application Load Balancer

1. Vào EC2 → Load Balancers → "Create Load Balancer"
2. Chọn "Application Load Balancer"
3. Cấu hình:
   - Name: `edutwin-alb`
   - Scheme: Internet-facing
   - IP address type: IPv4
   - VPC: `edutwin-vpc`
   - Subnets: Chọn 2 public subnets
   - Security group: `edutwin-alb-sg`

4. Tạo Target Groups:
   
   **Backend Target Group**
   ```
   Name: edutwin-backend-tg
   Target type: IP
   Protocol: HTTP
   Port: 8000
   VPC: edutwin-vpc
   Health check path: /health
   ```
   
   **Frontend Target Group**
   ```
   Name: edutwin-frontend-tg
   Target type: IP
   Protocol: HTTP
   Port: 80
   VPC: edutwin-vpc
   Health check path: /
   ```

5. Tạo Listeners:
   - HTTP:80 → Forward to `edutwin-frontend-tg`
   - Thêm rule: Path `/api/*` → Forward to `edutwin-backend-tg`

### 2.9. Cập nhật Task Definitions

Mở các file `backend-task-definition.json` và `frontend-task-definition.json`, thay thế:
- `YOUR_ACCOUNT_ID` → AWS Account ID của bạn
- `ap-southeast-1` → Region bạn chọn (nếu khác)

---

## 3. Cấu hình GitHub Actions

### 3.1. Tạo IAM User cho GitHub Actions

```powershell
# Tạo user
aws iam create-user --user-name github-actions-edutwin

# Tạo policy
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
'@ | Out-File -FilePath github-actions-policy.json -Encoding utf8

aws iam create-policy --policy-name GitHubActionsECSDeployPolicy --policy-document file://github-actions-policy.json

# Attach policy
aws iam attach-user-policy --user-name github-actions-edutwin --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/GitHubActionsECSDeployPolicy

# Tạo access key
aws iam create-access-key --user-name github-actions-edutwin
```

Lưu lại `AccessKeyId` và `SecretAccessKey`!

### 3.2. Thêm Secrets vào GitHub Repository

1. Vào GitHub repo của bạn
2. Settings → Secrets and variables → Actions
3. Thêm các secrets:
   - `AWS_ACCESS_KEY_ID`: Access Key từ bước trên
   - `AWS_SECRET_ACCESS_KEY`: Secret Key từ bước trên

---

## 4. Deploy lần đầu

### 4.1. Push Docker Images lên ECR (Manual first time)

```powershell
# Login vào ECR
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com

# Build và push backend
cd backend
docker build -t edutwin-backend:latest -f Dockerfile.prod .
docker tag edutwin-backend:latest ${ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-backend:latest
docker push ${ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-backend:latest

# Build và push frontend
cd ../frontend_react
docker build -t edutwin-frontend:latest -f Dockerfile.prod .
docker tag edutwin-frontend:latest ${ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-frontend:latest
docker push ${ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com/edutwin-frontend:latest
```

### 4.2. Tạo ECS Services

```powershell
# Register task definitions
aws ecs register-task-definition --cli-input-json file://backend-task-definition.json --region ap-southeast-1
aws ecs register-task-definition --cli-input-json file://frontend-task-definition.json --region ap-southeast-1

# Lấy IDs
$PUBLIC_SUBNET_1 = (aws ec2 describe-subnets --filters "Name=tag:Name,Values=edutwin-public-1a" --query "Subnets[0].SubnetId" --output text)
$PUBLIC_SUBNET_2 = (aws ec2 describe-subnets --filters "Name=tag:Name,Values=edutwin-public-1b" --query "Subnets[0].SubnetId" --output text)
$BACKEND_SG = (aws ec2 describe-security-groups --filters "Name=group-name,Values=edutwin-backend-sg" --query "SecurityGroups[0].GroupId" --output text)
$FRONTEND_SG = (aws ec2 describe-security-groups --filters "Name=group-name,Values=edutwin-frontend-sg" --query "SecurityGroups[0].GroupId" --output text)
$BACKEND_TG_ARN = (aws elbv2 describe-target-groups --names edutwin-backend-tg --query "TargetGroups[0].TargetGroupArn" --output text)
$FRONTEND_TG_ARN = (aws elbv2 describe-target-groups --names edutwin-frontend-tg --query "TargetGroups[0].TargetGroupArn" --output text)

# Tạo Backend Service
aws ecs create-service `
  --cluster edutwin-cluster `
  --service-name edutwin-backend-service `
  --task-definition edutwin-backend `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2],securityGroups=[$BACKEND_SG],assignPublicIp=ENABLED}" `
  --load-balancers "targetGroupArn=$BACKEND_TG_ARN,containerName=backend,containerPort=8000" `
  --region ap-southeast-1

# Tạo Frontend Service
aws ecs create-service `
  --cluster edutwin-cluster `
  --service-name edutwin-frontend-service `
  --task-definition edutwin-frontend `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2],securityGroups=[$FRONTEND_SG],assignPublicIp=ENABLED}" `
  --load-balancers "targetGroupArn=$FRONTEND_TG_ARN,containerName=frontend,containerPort=80" `
  --region ap-southeast-1
```

### 4.3. Kiểm tra Deployment

```powershell
# Check services
aws ecs describe-services --cluster edutwin-cluster --services edutwin-backend-service edutwin-frontend-service --region ap-southeast-1

# Get ALB DNS name
aws elbv2 describe-load-balancers --names edutwin-alb --query "LoadBalancers[0].DNSName" --output text
```

Truy cập vào ALB DNS name để kiểm tra ứng dụng!

### 4.4. Setup Domain (Optional)

1. Vào Route 53 → Hosted zones
2. Tạo A record trỏ về ALB:
   - `edutwin.com` → Alias to ALB
   - `www.edutwin.com` → Alias to ALB
   - `api.edutwin.com` → Alias to ALB

3. Request SSL Certificate (ACM):
   - Vào Certificate Manager
   - Request certificate cho `*.edutwin.com`
   - Validate bằng DNS
   - Thêm HTTPS listener vào ALB

---

## 5. Monitoring & Maintenance

### 5.1. CloudWatch Dashboards

Tạo dashboard để monitor:
- ECS Service metrics (CPU, Memory)
- ALB metrics (Request count, latency)
- RDS metrics (Connections, CPU)

### 5.2. Auto Scaling (Optional)

```powershell
# Setup auto scaling cho backend
aws application-autoscaling register-scalable-target `
  --service-namespace ecs `
  --resource-id service/edutwin-cluster/edutwin-backend-service `
  --scalable-dimension ecs:service:DesiredCount `
  --min-capacity 1 `
  --max-capacity 4

# Tạo scaling policy
aws application-autoscaling put-scaling-policy `
  --service-namespace ecs `
  --resource-id service/edutwin-cluster/edutwin-backend-service `
  --scalable-dimension ecs:service:DesiredCount `
  --policy-name cpu-scaling `
  --policy-type TargetTrackingScaling `
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

### 5.3. Cost Optimization

- Sử dụng **Fargate Spot** cho non-critical tasks (giảm ~70% chi phí)
- Setup **Auto Scaling** để scale down khi không cần
- Sử dụng **RDS Aurora Serverless** nếu traffic không đều
- Enable **S3 Intelligent-Tiering** cho storage

---

## 📊 Ước tính Chi phí (Singapore region)

| Service | Configuration | Cost/month |
|---------|--------------|------------|
| ECS Fargate (Backend) | 0.5 vCPU, 1GB RAM, 24/7 | ~$15 |
| ECS Fargate (Frontend) | 0.25 vCPU, 0.5GB RAM, 24/7 | ~$7 |
| RDS PostgreSQL | db.t3.micro, 20GB | ~$15 |
| ALB | Standard | ~$16 |
| NAT Gateway | 1 NAT | ~$32 |
| Data Transfer | ~50GB/month | ~$5 |
| **TOTAL** | | **~$90/month** |

**Lưu ý**: 
- Free Tier (12 tháng đầu) giảm ~50% chi phí
- Có thể giảm còn ~$30-40/month nếu optimize tốt

---

## 🔧 Troubleshooting

### Issue: Task keeps stopping
→ Check CloudWatch Logs: `/ecs/edutwin-backend` hoặc `/ecs/edutwin-frontend`

### Issue: Cannot connect to database
→ Kiểm tra Security Group của RDS có allow traffic từ Backend SG không

### Issue: GitHub Actions fails
→ Kiểm tra IAM permissions của user `github-actions-edutwin`

---

## 📚 Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [GitHub Actions for AWS](https://github.com/aws-actions)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

---

## ✅ Checklist Deploy

- [ ] AWS Account đã tạo
- [ ] VPC và Networking đã setup
- [ ] RDS Database đã tạo
- [ ] ECR Repositories đã tạo
- [ ] Secrets Manager đã cấu hình
- [ ] IAM Roles đã tạo
- [ ] ECS Cluster đã tạo
- [ ] Load Balancer đã cấu hình
- [ ] GitHub Secrets đã thêm
- [ ] Task Definitions đã cập nhật
- [ ] Services đã deploy thành công
- [ ] Application accessible qua ALB DNS

🎉 **Chúc bạn deploy thành công!**
