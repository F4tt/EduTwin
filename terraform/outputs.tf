output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer - use this to access your application"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint - update this in Secrets Manager"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_url" {
  description = "Complete database URL for application"
  value       = "postgresql://admin:${var.db_password}@${aws_db_instance.main.endpoint}/${var.project_name}"
  sensitive   = true
}

output "ecr_backend_repository_url" {
  description = "ECR repository URL for backend images"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "ECR repository URL for frontend images"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "backend_security_group_id" {
  description = "Security group ID for backend tasks"
  value       = aws_security_group.backend.id
}

output "frontend_security_group_id" {
  description = "Security group ID for frontend tasks"
  value       = aws_security_group.frontend.id
}

output "backend_target_group_arn" {
  description = "ARN of backend target group"
  value       = aws_lb_target_group.backend.arn
}

output "frontend_target_group_arn" {
  description = "ARN of frontend target group"
  value       = aws_lb_target_group.frontend.arn
}

output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "next_steps" {
  description = "What to do next after Terraform apply"
  value = <<-EOT
  
  ✅ Infrastructure created successfully!
  
  📋 Next Steps:
  
  1. Update Secrets Manager with RDS endpoint:
     aws secretsmanager update-secret --secret-id ${var.project_name}/database-url \
       --secret-string "postgresql://admin:YOUR_PASSWORD@${aws_db_instance.main.endpoint}/${var.project_name}"
  
  2. Build and push Docker images:
     - Backend: ${aws_ecr_repository.backend.repository_url}
     - Frontend: ${aws_ecr_repository.frontend.repository_url}
  
  3. Access your application at:
     http://${aws_lb.main.dns_name}
  
  4. Set up GitHub Actions secrets:
     - AWS_ACCESS_KEY_ID
     - AWS_SECRET_ACCESS_KEY
  
  5. Deploy ECS services (see DEPLOYMENT_GUIDE.md section 4.2)
  
  EOT
}
