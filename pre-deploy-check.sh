#!/bin/bash
# Pre-deployment check script for EduTwin Backend

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   EduTwin Pre-Deployment Checks${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if we're in the right directory
if [ ! -f "backend/main.py" ]; then
    echo -e "${RED}❌ Not in correct directory! Please run from project root.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}1. Checking project structure...${NC}"
required_files=(
    "backend/main.py"
    "backend/Dockerfile.prod" 
    "backend/requirements.txt"
    "backend-task-definition.json"
    ".github/workflows/deploy.yml"
    "frontend_react/Dockerfile.prod"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ✅ $file"
    else
        echo -e "  ❌ Missing: $file"
        exit 1
    fi
done

echo -e "\n${YELLOW}2. Checking Docker installation...${NC}"
if command -v docker &> /dev/null; then
    echo -e "  ✅ Docker installed: $(docker --version)"
    if docker info &> /dev/null; then
        echo -e "  ✅ Docker daemon running"
    else
        echo -e "  ❌ Docker daemon not running"
        exit 1
    fi
else
    echo -e "  ❌ Docker not installed"
    exit 1
fi

echo -e "\n${YELLOW}3. Checking AWS CLI...${NC}"
if command -v aws &> /dev/null; then
    echo -e "  ✅ AWS CLI installed: $(aws --version)"
    
    # Check AWS credentials
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        REGION=$(aws configure get region)
        echo -e "  ✅ AWS credentials configured"
        echo -e "    Account ID: $ACCOUNT_ID"
        echo -e "    Region: $REGION"
    else
        echo -e "  ❌ AWS credentials not configured"
        exit 1
    fi
else
    echo -e "  ❌ AWS CLI not installed"
    exit 1
fi

echo -e "\n${YELLOW}4. Checking ECR repositories...${NC}"
REPOS=("edutwin-backend" "edutwin-frontend")
for repo in "${REPOS[@]}"; do
    if aws ecr describe-repositories --repository-names "$repo" &> /dev/null; then
        echo -e "  ✅ ECR repository exists: $repo"
    else
        echo -e "  ❌ ECR repository missing: $repo"
        echo -e "    Run: aws ecr create-repository --repository-name $repo"
        exit 1
    fi
done

echo -e "\n${YELLOW}5. Checking ECS cluster and services...${NC}"
if aws ecs describe-clusters --clusters edutwin-cluster --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo -e "  ✅ ECS cluster exists: edutwin-cluster"
    
    # Check services
    SERVICES=("edutwin-backend" "edutwin-frontend")
    for service in "${SERVICES[@]}"; do
        if aws ecs describe-services --cluster edutwin-cluster --services "$service" --query 'services[0].serviceName' --output text 2>/dev/null | grep -q "$service"; then
            echo -e "  ✅ ECS service exists: $service"
        else
            echo -e "  ⚠️  ECS service missing: $service (will be created during deployment)"
        fi
    done
else
    echo -e "  ❌ ECS cluster not found: edutwin-cluster"
    echo -e "    Please create cluster first or run Terraform"
    exit 1
fi

echo -e "\n${YELLOW}6. Testing Docker build locally...${NC}"
echo -e "  🔨 Building backend image locally (test build)..."
cd backend
if docker build -f Dockerfile.prod -t edutwin-backend-test:latest . &> build.log; then
    echo -e "  ✅ Backend Docker build successful"
    docker rmi edutwin-backend-test:latest &> /dev/null || true
else
    echo -e "  ❌ Backend Docker build failed"
    echo -e "  Check build.log for details"
    exit 1
fi
cd ..

echo -e "\n${YELLOW}7. Checking secrets in AWS Secrets Manager...${NC}"
SECRETS=(
    "edutwin/database-url" 
    "edutwin/secret-key"
    "edutwin/llm-api-key"
    "edutwin/redis-url"
)

for secret in "${SECRETS[@]}"; do
    if aws secretsmanager describe-secret --secret-id "$secret" &> /dev/null; then
        echo -e "  ✅ Secret exists: $secret"
    else
        echo -e "  ❌ Secret missing: $secret"
        echo -e "    Please create this secret in AWS Secrets Manager"
        exit 1
    fi
done

echo -e "\n${YELLOW}8. Checking task definition validity...${NC}"
# Replace AWS_ACCOUNT_ID placeholder for validation
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed "s/\${AWS_ACCOUNT_ID}/$ACCOUNT_ID/g" backend-task-definition.json > backend-task-definition-test.json

if aws ecs register-task-definition --cli-input-json file://backend-task-definition-test.json --dry-run &> /dev/null; then
    echo -e "  ✅ Backend task definition is valid"
else
    echo -e "  ❌ Backend task definition has errors"
    exit 1
fi

# Cleanup
rm -f backend-task-definition-test.json backend/build.log

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   ✅ All pre-deployment checks passed!${NC}" 
echo -e "${GREEN}   Ready for deployment 🚀${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Commit and push your changes to GitHub"
echo -e "  2. GitHub Actions will automatically deploy to AWS"
echo -e "  3. Monitor deployment at: https://github.com/YOUR_USERNAME/EduTwin/actions"
echo -e "  4. Check application: https://edutwin.online"