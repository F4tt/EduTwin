@echo off
REM ===========================================
REM EduTwin AWS Deployment Script for Windows
REM ===========================================

echo ========================================
echo    EduTwin AWS Deployment Script
echo ========================================

REM Check AWS CLI
where aws >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: AWS CLI is not installed!
    exit /b 1
)

REM Get AWS account info
echo.
echo Getting AWS account information...
for /f "tokens=*" %%i in ('aws sts get-caller-identity --query Account --output text') do set AWS_ACCOUNT_ID=%%i
for /f "tokens=*" %%i in ('aws configure get region') do set AWS_REGION=%%i
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

echo AWS Account ID: %AWS_ACCOUNT_ID%
echo AWS Region: %AWS_REGION%

echo.
echo What would you like to do?
echo 1. Full deployment (Terraform + Build + Push)
echo 2. Build and push Docker images only
echo 3. Apply Terraform only
echo 4. Update ECS services (redeploy)
echo 5. Exit
echo.
set /p choice=Enter choice (1-5): 

if "%choice%"=="1" goto full_deploy
if "%choice%"=="2" goto build_push
if "%choice%"=="3" goto terraform_only
if "%choice%"=="4" goto update_ecs
if "%choice%"=="5" exit /b 0

:full_deploy
call :terraform_apply
call :docker_build_push
call :ecs_update
goto :end

:build_push
call :docker_build_push
goto :end

:terraform_only
call :terraform_apply
goto :end

:update_ecs
call :ecs_update
goto :end

:terraform_apply
echo.
echo Applying Terraform...
cd terraform
if not exist terraform.tfvars (
    echo ERROR: terraform.tfvars not found!
    echo Please copy terraform.tfvars.example to terraform.tfvars
    exit /b 1
)
terraform init
terraform plan
echo.
set /p confirm=Apply this plan? (yes/no): 
if "%confirm%"=="yes" terraform apply -auto-approve
cd ..
exit /b 0

:docker_build_push
echo.
echo Logging into ECR...
aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com

echo.
echo Building backend image...
cd backend
docker build -f Dockerfile.prod -t edutwin-backend:latest .
docker tag edutwin-backend:latest %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/edutwin-backend:latest
docker push %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/edutwin-backend:latest
cd ..

echo.
echo Building frontend image...
cd frontend_react
docker build -f Dockerfile.prod -t edutwin-frontend:latest .
docker tag edutwin-frontend:latest %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/edutwin-frontend:latest
docker push %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/edutwin-frontend:latest
cd ..

echo Docker images built and pushed!
exit /b 0

:ecs_update
echo.
echo Updating ECS services...
aws ecs update-service --cluster edutwin-cluster --service edutwin-backend --force-new-deployment --region %AWS_REGION%
aws ecs update-service --cluster edutwin-cluster --service edutwin-frontend --force-new-deployment --region %AWS_REGION%
echo ECS services updated!
exit /b 0

:end
echo.
echo ========================================
echo    Deployment Complete!
echo ========================================
cd terraform
terraform output
cd ..
pause
