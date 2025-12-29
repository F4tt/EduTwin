# Terraform Import Script for EduTwin
# This script imports existing AWS resources into Terraform state

$ErrorActionPreference = "Continue"
$env:AWS_PAGER = ""

Write-Host "=== EduTwin Terraform Import Script ===" -ForegroundColor Cyan
Write-Host ""

# Change to terraform directory
Set-Location -Path "$PSScriptRoot\terraform"

# Step 1: Get Account ID
Write-Host "1. Getting AWS Account ID..." -ForegroundColor Yellow
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text --no-cli-pager)
Write-Host "   Account ID: $ACCOUNT_ID" -ForegroundColor Green

# Step 2: Get resource ARNs
Write-Host ""
Write-Host "2. Getting resource ARNs..." -ForegroundColor Yellow

$ALB_ARN = (aws elbv2 describe-load-balancers --names edutwin-alb --query "LoadBalancers[0].LoadBalancerArn" --output text --no-cli-pager 2>$null)
Write-Host "   ALB ARN: $ALB_ARN" -ForegroundColor Green

$BACKEND_TG_ARN = (aws elbv2 describe-target-groups --names edutwin-backend-tg --query "TargetGroups[0].TargetGroupArn" --output text --no-cli-pager 2>$null)
Write-Host "   Backend TG ARN: $BACKEND_TG_ARN" -ForegroundColor Green

$FRONTEND_TG_ARN = (aws elbv2 describe-target-groups --names edutwin-frontend-tg --query "TargetGroups[0].TargetGroupArn" --output text --no-cli-pager 2>$null)
Write-Host "   Frontend TG ARN: $FRONTEND_TG_ARN" -ForegroundColor Green

# Get VPC ID
$VPC_ID = (aws ec2 describe-vpcs --filters "Name=tag:Name,Values=edutwin-vpc" --query "Vpcs[0].VpcId" --output text --no-cli-pager 2>$null)
Write-Host "   VPC ID: $VPC_ID" -ForegroundColor Green

# Get Internet Gateway ID
$IGW_ID = (aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query "InternetGateways[0].InternetGatewayId" --output text --no-cli-pager 2>$null)
Write-Host "   IGW ID: $IGW_ID" -ForegroundColor Green

# Get ECS Cluster ARN
$CLUSTER_ARN = (aws ecs describe-clusters --clusters edutwin-cluster --query "clusters[0].clusterArn" --output text --no-cli-pager 2>$null)
Write-Host "   ECS Cluster ARN: $CLUSTER_ARN" -ForegroundColor Green

Write-Host ""
Write-Host "3. Starting Terraform imports..." -ForegroundColor Yellow
Write-Host "   (This will take a few minutes)" -ForegroundColor Gray
Write-Host ""

# Import VPC
Write-Host "   Importing aws_vpc.main..." -ForegroundColor Cyan
terraform import aws_vpc.main $VPC_ID 2>&1 | Out-Null

# Import Internet Gateway
Write-Host "   Importing aws_internet_gateway.main..." -ForegroundColor Cyan
terraform import aws_internet_gateway.main $IGW_ID 2>&1 | Out-Null

# Import IAM Roles
Write-Host "   Importing aws_iam_role.ecs_task_execution..." -ForegroundColor Cyan
terraform import aws_iam_role.ecs_task_execution edutwin-ecs-task-execution-role 2>&1 | Out-Null

Write-Host "   Importing aws_iam_role.ecs_task..." -ForegroundColor Cyan
terraform import aws_iam_role.ecs_task edutwin-ecs-task-role 2>&1 | Out-Null

# Import ECR Repositories
Write-Host "   Importing aws_ecr_repository.backend..." -ForegroundColor Cyan
terraform import aws_ecr_repository.backend edutwin-backend 2>&1 | Out-Null

Write-Host "   Importing aws_ecr_repository.frontend..." -ForegroundColor Cyan
terraform import aws_ecr_repository.frontend edutwin-frontend 2>&1 | Out-Null

# Import CloudWatch Log Groups
Write-Host "   Importing aws_cloudwatch_log_group.backend..." -ForegroundColor Cyan
terraform import aws_cloudwatch_log_group.backend /ecs/edutwin-backend 2>&1 | Out-Null

Write-Host "   Importing aws_cloudwatch_log_group.frontend..." -ForegroundColor Cyan
terraform import aws_cloudwatch_log_group.frontend /ecs/edutwin-frontend 2>&1 | Out-Null

# Import Load Balancer and Target Groups
Write-Host "   Importing aws_lb.main..." -ForegroundColor Cyan
terraform import aws_lb.main $ALB_ARN 2>&1 | Out-Null

Write-Host "   Importing aws_lb_target_group.backend..." -ForegroundColor Cyan
terraform import aws_lb_target_group.backend $BACKEND_TG_ARN 2>&1 | Out-Null

Write-Host "   Importing aws_lb_target_group.frontend..." -ForegroundColor Cyan
terraform import aws_lb_target_group.frontend $FRONTEND_TG_ARN 2>&1 | Out-Null

# Import Subnet Groups
Write-Host "   Importing aws_db_subnet_group.main..." -ForegroundColor Cyan
terraform import aws_db_subnet_group.main edutwin-db-subnet-group 2>&1 | Out-Null

Write-Host "   Importing aws_elasticache_subnet_group.main..." -ForegroundColor Cyan
terraform import aws_elasticache_subnet_group.main edutwin-redis-subnet-group 2>&1 | Out-Null

# Import ECS Cluster
Write-Host "   Importing aws_ecs_cluster.main..." -ForegroundColor Cyan
terraform import aws_ecs_cluster.main $CLUSTER_ARN 2>&1 | Out-Null

# Import Secrets
Write-Host ""
Write-Host "4. Importing Secrets Manager secrets..." -ForegroundColor Yellow

$secrets = @(
    @("aws_secretsmanager_secret.database_url", "edutwin/database-url"),
    @("aws_secretsmanager_secret.secret_key", "edutwin/secret-key"),
    @("aws_secretsmanager_secret.llm_api_key", "edutwin/llm-api-key"),
    @("aws_secretsmanager_secret.redis_url", "edutwin/redis-url")
)

foreach ($secret in $secrets) {
    $resource = $secret[0]
    $name = $secret[1]
    
    $arn = (aws secretsmanager describe-secret --secret-id $name --query "ARN" --output text --no-cli-pager 2>$null)
    if ($arn -and $arn -ne "None") {
        Write-Host "   Importing $resource..." -ForegroundColor Cyan
        terraform import $resource $arn 2>&1 | Out-Null
    }
}

Write-Host ""
Write-Host "=== Import Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run: terraform plan" -ForegroundColor White
Write-Host "  2. Run: terraform apply" -ForegroundColor White
Write-Host ""
