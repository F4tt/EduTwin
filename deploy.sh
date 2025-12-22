#!/bin/bash
# ===========================================
# EduTwin AWS Deployment Script
# ===========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   EduTwin AWS Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check required tools
check_tools() {
    echo -e "\n${YELLOW}Checking required tools...${NC}"
    
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    if ! command -v terraform &> /dev/null; then
        echo -e "${RED}Terraform is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}All required tools are installed!${NC}"
}

# Get AWS account info
get_aws_info() {
    echo -e "\n${YELLOW}Getting AWS account information...${NC}"
    
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    
    echo -e "AWS Account ID: ${GREEN}$AWS_ACCOUNT_ID${NC}"
    echo -e "AWS Region: ${GREEN}$AWS_REGION${NC}"
}

# Build and push Docker images
build_and_push() {
    echo -e "\n${YELLOW}Building and pushing Docker images...${NC}"
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Build and push backend
    echo -e "\n${YELLOW}Building backend image...${NC}"
    cd backend
    docker build -f Dockerfile.prod -t edutwin-backend:latest .
    docker tag edutwin-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:latest
    cd ..
    
    # Build and push frontend
    echo -e "\n${YELLOW}Building frontend image...${NC}"
    cd frontend_react
    docker build -f Dockerfile.prod -t edutwin-frontend:latest .
    docker tag edutwin-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:latest
    cd ..
    
    echo -e "${GREEN}Docker images built and pushed successfully!${NC}"
}

# Apply Terraform
apply_terraform() {
    echo -e "\n${YELLOW}Applying Terraform...${NC}"
    
    cd terraform
    
    if [ ! -f "terraform.tfvars" ]; then
        echo -e "${RED}terraform.tfvars not found!${NC}"
        echo -e "Please copy terraform.tfvars.example to terraform.tfvars and fill in your values."
        exit 1
    fi
    
    terraform init
    terraform plan -out=tfplan
    
    echo -e "\n${YELLOW}Review the plan above. Continue? (yes/no)${NC}"
    read -r response
    if [ "$response" = "yes" ]; then
        terraform apply tfplan
    else
        echo -e "${RED}Deployment cancelled.${NC}"
        exit 1
    fi
    
    cd ..
    
    echo -e "${GREEN}Terraform applied successfully!${NC}"
}

# Update ECS services
update_services() {
    echo -e "\n${YELLOW}Updating ECS services...${NC}"
    
    aws ecs update-service --cluster edutwin-cluster --service edutwin-backend --force-new-deployment --region $AWS_REGION
    aws ecs update-service --cluster edutwin-cluster --service edutwin-frontend --force-new-deployment --region $AWS_REGION
    
    echo -e "${GREEN}ECS services updated!${NC}"
}

# Main menu
main() {
    check_tools
    get_aws_info
    
    echo -e "\n${YELLOW}What would you like to do?${NC}"
    echo "1. Full deployment (Terraform + Build + Push)"
    echo "2. Build and push Docker images only"
    echo "3. Apply Terraform only"
    echo "4. Update ECS services (redeploy existing images)"
    echo "5. Exit"
    
    read -r choice
    
    case $choice in
        1)
            apply_terraform
            build_and_push
            update_services
            ;;
        2)
            build_and_push
            ;;
        3)
            apply_terraform
            ;;
        4)
            update_services
            ;;
        5)
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            exit 1
            ;;
    esac
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}   Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    # Get outputs
    cd terraform
    echo -e "\n${YELLOW}Important URLs:${NC}"
    terraform output
    cd ..
}

main
