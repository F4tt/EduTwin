variable "aws_region" {
  description = "AWS Region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "edutwin"
}

variable "db_password" {
  description = "Master password for RDS PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API Key for chatbot functionality"
  type        = string
  sensitive   = true
  default     = ""
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"
}
