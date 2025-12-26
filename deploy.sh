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
    
    # Login to ECR with retry logic
    echo -e "\n${YELLOW}Logging into ECR...${NC}"
    for attempt in 1 2 3; do
        if aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com; then
            echo -e "${GREEN}ECR login successful${NC}"
            break
        else
            echo -e "${RED}ECR login failed (attempt $attempt/3)${NC}"
            if [ $attempt -eq 3 ]; then
                echo -e "${RED}Failed to login to ECR after 3 attempts${NC}"
                exit 1
            fi
            sleep 5
        fi
    done
    
    # Clean up existing images
    echo -e "\n${YELLOW}Cleaning up local Docker cache...${NC}"
    docker system prune -f

    # Build and push backend with optimizations
    echo -e "\n${YELLOW}Building backend image...${NC}"
    cd backend
    
    # Build with BuildKit for better caching
    DOCKER_BUILDKIT=1 docker build \
        --progress=plain \
        --no-cache \
        -f Dockerfile.prod \
        -t edutwin-backend:latest \
        -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:latest \
        -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:$(date +%Y%m%d-%H%M%S) \
        .

    if [ $? -ne 0 ]; then
        echo -e "${RED}Backend build failed${NC}"
        exit 1
    fi
    
    # Push backend images
    echo -e "\n${YELLOW}Pushing backend images...${NC}"
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-backend:$(date +%Y%m%d-%H%M%S)
    cd ..
    
    # Build and push frontend
    echo -e "\n${YELLOW}Building frontend image...${NC}"
    cd frontend_react
    
    DOCKER_BUILDKIT=1 docker build \
        --progress=plain \
        --no-cache \
        -f Dockerfile.prod \
        -t edutwin-frontend:latest \
        -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:latest \
        -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:$(date +%Y%m%d-%H%M%S) \
        .

    if [ $? -ne 0 ]; then
        echo -e "${RED}Frontend build failed${NC}"
        exit 1
    fi
    
    # Push frontend images
    echo -e "\n${YELLOW}Pushing frontend images...${NC}"
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edutwin-frontend:$(date +%Y%m%d-%H%M%S)
    cd ..
    
    echo -e "${GREEN}Docker images built and pushed successfully!${NC}"
    
    # Verify images in ECR
    echo -e "\n${YELLOW}Verifying images in ECR...${NC}"
    aws ecr describe-images --repository-name edutwin-backend --query 'imageDetails[0].imageTags' --output table
    aws ecr describe-images --repository-name edutwin-frontend --query 'imageDetails[0].imageTags' --output table
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

# Update ECS services with improved monitoring
update_services() {
    echo -e "\n${YELLOW}Updating ECS services...${NC}"
    
    # Update backend service
    echo -e "\n${YELLOW}Updating backend service...${NC}"
    BACKEND_UPDATE=$(aws ecs update-service \
        --cluster edutwin-cluster \
        --service edutwin-backend \
        --force-new-deployment \
        --region $AWS_REGION \
        --output json)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to update backend service${NC}"
        exit 1
    fi
    
    # Update frontend service  
    echo -e "\n${YELLOW}Updating frontend service...${NC}"
    FRONTEND_UPDATE=$(aws ecs update-service \
        --cluster edutwin-cluster \
        --service edutwin-frontend \
        --force-new-deployment \
        --region $AWS_REGION \
        --output json)
        
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to update frontend service${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}ECS services update initiated!${NC}"
    
    # Monitor backend deployment with extended timeout
    echo -e "\n${YELLOW}Monitoring backend deployment (may take up to 20 minutes)...${NC}"
    
    max_attempts=80  # 80 * 15 seconds = 20 minutes
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo -e "Checking backend service stability (attempt $attempt/$max_attempts)..."
        
        # Get service status
        SERVICE_STATUS=$(aws ecs describe-services \
            --cluster edutwin-cluster \
            --services edutwin-backend \
            --region $AWS_REGION \
            --query 'services[0]' \
            --output json)
        
        RUNNING_COUNT=$(echo $SERVICE_STATUS | jq -r '.runningCount')
        DESIRED_COUNT=$(echo $SERVICE_STATUS | jq -r '.desiredCount')
        PENDING_COUNT=$(echo $SERVICE_STATUS | jq -r '.pendingCount')
        
        echo -e "  Running: $RUNNING_COUNT, Desired: $DESIRED_COUNT, Pending: $PENDING_COUNT"
        
        # Check if stable (running count matches desired count)
        if [ "$RUNNING_COUNT" -eq "$DESIRED_COUNT" ] && [ "$RUNNING_COUNT" -gt "0" ] && [ "$PENDING_COUNT" -eq "0" ]; then
            echo -e "${GREEN}Backend service is stable!${NC}"
            break
        fi
        
        # Show recent events for debugging
        if [ $((attempt % 4)) -eq 0 ]; then
            echo -e "Recent service events:"
            aws ecs describe-services \
                --cluster edutwin-cluster \
                --services edutwin-backend \
                --region $AWS_REGION \
                --query 'services[0].events[0:2].[createdAt,message]' \
                --output table
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}Backend service failed to stabilize after 20 minutes${NC}"
            echo -e "Final status: Running=$RUNNING_COUNT, Desired=$DESIRED_COUNT, Pending=$PENDING_COUNT"
            
            # Show task details for debugging
            echo -e "\nTask details:"
            aws ecs list-tasks \
                --cluster edutwin-cluster \
                --service-name edutwin-backend \
                --region $AWS_REGION \
                --query 'taskArns[0]' \
                --output text | xargs -I {} aws ecs describe-tasks \
                --cluster edutwin-cluster \
                --tasks {} \
                --region $AWS_REGION \
                --query 'tasks[0].lastStatus'
            
            exit 1
        fi
        
        sleep 15
        attempt=$((attempt + 1))
    done
    
    # Monitor frontend deployment (shorter timeout)
    echo -e "\n${YELLOW}Monitoring frontend deployment...${NC}"
    
    timeout 600 aws ecs wait services-stable \
        --cluster edutwin-cluster \
        --services edutwin-frontend \
        --region $AWS_REGION || {
        echo -e "${RED}Frontend service failed to stabilize${NC}"
        exit 1
    }
    
    echo -e "${GREEN}All services deployed successfully!${NC}"
    
    # Final status check
    echo -e "\n${YELLOW}Final service status:${NC}"
    aws ecs describe-services \
        --cluster edutwin-cluster \
        --services edutwin-backend edutwin-frontend \
        --region $AWS_REGION \
        --query 'services[].[serviceName,status,runningCount,desiredCount]' \
        --output table
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
