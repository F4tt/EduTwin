# Script AWS Setup tự động
# Chạy script này để tự động setup infrastructure cơ bản

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName = "edutwin",
    
    [Parameter(Mandatory=$true)]
    [string]$Region = "ap-southeast-1",
    
    [Parameter(Mandatory=$true)]
    [string]$DbPassword,
    
    [Parameter(Mandatory=$false)]
    [string]$OpenAIKey = ""
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting AWS Infrastructure Setup for $ProjectName" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Yellow

# Get Account ID
Write-Host "`n📋 Getting AWS Account ID..." -ForegroundColor Yellow
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
Write-Host "Account ID: $ACCOUNT_ID" -ForegroundColor Green

# 1. Create ECR Repositories
Write-Host "`n📦 Creating ECR Repositories..." -ForegroundColor Yellow
try {
    aws ecr create-repository --repository-name "$ProjectName-backend" --region $Region 2>$null
    Write-Host "✅ Backend repository created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Backend repository already exists" -ForegroundColor Yellow
}

try {
    aws ecr create-repository --repository-name "$ProjectName-frontend" --region $Region 2>$null
    Write-Host "✅ Frontend repository created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Frontend repository already exists" -ForegroundColor Yellow
}

# 2. Create CloudWatch Log Groups
Write-Host "`n📊 Creating CloudWatch Log Groups..." -ForegroundColor Yellow
try {
    aws logs create-log-group --log-group-name "/ecs/$ProjectName-backend" --region $Region 2>$null
    Write-Host "✅ Backend log group created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Backend log group already exists" -ForegroundColor Yellow
}

try {
    aws logs create-log-group --log-group-name "/ecs/$ProjectName-frontend" --region $Region 2>$null
    Write-Host "✅ Frontend log group created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Frontend log group already exists" -ForegroundColor Yellow
}

# 3. Create Secrets
Write-Host "`n🔐 Creating Secrets in Secrets Manager..." -ForegroundColor Yellow

# Generate random secret key
$SecretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

try {
    aws secretsmanager create-secret `
        --name "$ProjectName/secret-key" `
        --description "JWT secret key for $ProjectName" `
        --secret-string $SecretKey `
        --region $Region 2>$null
    Write-Host "✅ Secret key created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Secret key already exists, updating..." -ForegroundColor Yellow
    aws secretsmanager update-secret `
        --secret-id "$ProjectName/secret-key" `
        --secret-string $SecretKey `
        --region $Region
}

# Database URL (you'll need to update this after RDS is created)
$DbUrl = "postgresql://admin:$DbPassword@REPLACE_WITH_RDS_ENDPOINT:5432/$ProjectName"
try {
    aws secretsmanager create-secret `
        --name "$ProjectName/database-url" `
        --description "Database connection string" `
        --secret-string $DbUrl `
        --region $Region 2>$null
    Write-Host "✅ Database URL placeholder created (update after RDS creation)" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Database URL already exists" -ForegroundColor Yellow
}

# OpenAI Key
if ($OpenAIKey) {
    try {
        aws secretsmanager create-secret `
            --name "$ProjectName/openai-key" `
            --description "OpenAI API Key" `
            --secret-string $OpenAIKey `
            --region $Region 2>$null
        Write-Host "✅ OpenAI key created" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  OpenAI key already exists, updating..." -ForegroundColor Yellow
        aws secretsmanager update-secret `
            --secret-id "$ProjectName/openai-key" `
            --secret-string $OpenAIKey `
            --region $Region
    }
}

# 4. Create ECS Cluster
Write-Host "`n🐳 Creating ECS Cluster..." -ForegroundColor Yellow
try {
    aws ecs create-cluster --cluster-name "$ProjectName-cluster" --region $Region 2>$null
    Write-Host "✅ ECS Cluster created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  ECS Cluster already exists" -ForegroundColor Yellow
}

# 5. Create IAM Roles
Write-Host "`n👤 Creating IAM Roles..." -ForegroundColor Yellow

# Trust policy for ECS
$TrustPolicy = @"
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
"@
$TrustPolicy | Out-File -FilePath "trust-policy.json" -Encoding utf8

# Create execution role
try {
    aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://trust-policy.json 2>$null
    aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    
    # Add Secrets Manager permissions
    $SecretsPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:${Region}:${ACCOUNT_ID}:secret:${ProjectName}/*"
      ]
    }
  ]
}
"@
    $SecretsPolicy | Out-File -FilePath "secrets-policy.json" -Encoding utf8
    aws iam put-role-policy --role-name ecsTaskExecutionRole --policy-name SecretsManagerAccess --policy-document file://secrets-policy.json
    
    Write-Host "✅ ECS Task Execution Role created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  ECS Task Execution Role already exists" -ForegroundColor Yellow
}

# Create task role
try {
    aws iam create-role --role-name ecsTaskRole --assume-role-policy-document file://trust-policy.json 2>$null
    aws iam attach-role-policy --role-name ecsTaskRole --policy-arn "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
    Write-Host "✅ ECS Task Role created" -ForegroundColor Green
} catch {
    Write-Host "⚠️  ECS Task Role already exists" -ForegroundColor Yellow
}

# Cleanup temp files
Remove-Item -Path "trust-policy.json", "secrets-policy.json" -ErrorAction SilentlyContinue

# 6. Update Task Definition files
Write-Host "`n📝 Updating Task Definition files..." -ForegroundColor Yellow

$backendTaskDef = Get-Content "backend-task-definition.json" -Raw
$backendTaskDef = $backendTaskDef -replace "YOUR_ACCOUNT_ID", $ACCOUNT_ID
$backendTaskDef = $backendTaskDef -replace "ap-southeast-1", $Region
$backendTaskDef | Out-File -FilePath "backend-task-definition.json" -Encoding utf8

$frontendTaskDef = Get-Content "frontend-task-definition.json" -Raw
$frontendTaskDef = $frontendTaskDef -replace "YOUR_ACCOUNT_ID", $ACCOUNT_ID
$frontendTaskDef = $frontendTaskDef -replace "ap-southeast-1", $Region
$frontendTaskDef | Out-File -FilePath "frontend-task-definition.json" -Encoding utf8

Write-Host "✅ Task definitions updated" -ForegroundColor Green

# Summary
Write-Host "`n✅ ========================================" -ForegroundColor Green
Write-Host "✅ AWS Infrastructure Setup Complete!" -ForegroundColor Green
Write-Host "✅ ========================================" -ForegroundColor Green

Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Create VPC and Networking (manually or with CloudFormation)" -ForegroundColor White
Write-Host "2. Create RDS Database" -ForegroundColor White
Write-Host "3. Update secret '$ProjectName/database-url' with real RDS endpoint" -ForegroundColor White
Write-Host "4. Create Application Load Balancer and Target Groups" -ForegroundColor White
Write-Host "5. Create Security Groups" -ForegroundColor White
Write-Host "6. Run: .\build-images.ps1" -ForegroundColor White
Write-Host "7. Push images to ECR" -ForegroundColor White
Write-Host "8. Create ECS Services" -ForegroundColor White
Write-Host "9. Configure GitHub Actions secrets" -ForegroundColor White

Write-Host "`n📌 Important ARNs:" -ForegroundColor Yellow
Write-Host "Account ID: $ACCOUNT_ID" -ForegroundColor White
Write-Host "Backend ECR: $ACCOUNT_ID.dkr.ecr.$Region.amazonaws.com/$ProjectName-backend" -ForegroundColor White
Write-Host "Frontend ECR: $ACCOUNT_ID.dkr.ecr.$Region.amazonaws.com/$ProjectName-frontend" -ForegroundColor White
Write-Host "ECS Cluster: $ProjectName-cluster" -ForegroundColor White
