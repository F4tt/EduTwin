# AWS Secrets Manager for sensitive data
# Note: You need to create these secrets manually with actual values

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project_name}/database-url"
  recovery_window_in_days = 0  # Immediate deletion for development

  tags = {
    Name = "${var.project_name}-database-url"
  }
}

resource "aws_secretsmanager_secret" "secret_key" {
  name                    = "${var.project_name}/secret-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-secret-key"
  }
}

resource "aws_secretsmanager_secret" "llm_api_key" {
  name                    = "${var.project_name}/llm-api-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-llm-api-key"
  }
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${var.project_name}/redis-url"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-redis-url"
  }
}

# Output secret ARNs for task definitions
output "database_url_secret_arn" {
  description = "Database URL Secret ARN"
  value       = aws_secretsmanager_secret.database_url.arn
}

output "llm_api_key_secret_arn" {
  description = "LLM API Key Secret ARN"
  value       = aws_secretsmanager_secret.llm_api_key.arn
}
