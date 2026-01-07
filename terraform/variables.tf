variable "aws_region" {
  description = "AWS Region to deploy resources"
  type        = string
  default     = "us-east-1"  # Cheapest region
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

variable "gemini_api_key" {
  description = "Gemini API Key for AI chatbot functionality"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application secret key for JWT tokens"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Your domain name (optional, leave empty for HTTP-only mode)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "google_api_key" {
  description = "Google API Key for Google Custom Search"
  type        = string
  sensitive   = true
  default     = ""  # Optional - falls back to Wikipedia if empty
}

variable "google_cse_id" {
  description = "Google Custom Search Engine ID"
  type        = string
  sensitive   = true
  default     = ""  # Optional - falls back to Wikipedia if empty
}
