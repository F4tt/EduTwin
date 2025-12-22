# SSL Certificate and Route 53 Configuration
# Only created when domain_name is set (non-empty)

# Lookup existing hosted zone (you need to create this first in Route 53)
data "aws_route53_zone" "main" {
  count        = var.domain_name != "" ? 1 : 0
  name         = var.domain_name
  private_zone = false
}

# ACM Certificate (Free SSL)
resource "aws_acm_certificate" "main" {
  count                     = var.domain_name != "" ? 1 : 0
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project_name}-ssl-cert"
  }
}

# DNS validation records
resource "aws_route53_record" "cert_validation" {
  for_each = var.domain_name != "" ? {
    for dvo in aws_acm_certificate.main[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main[0].zone_id
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "main" {
  count                   = var.domain_name != "" ? 1 : 0
  certificate_arn         = aws_acm_certificate.main[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# DNS record for the main domain pointing to ALB
resource "aws_route53_record" "main" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# DNS record for www subdomain
resource "aws_route53_record" "www" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# DNS record for API subdomain
resource "aws_route53_record" "api" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# HTTPS Listener (main listener)
resource "aws_lb_listener" "https" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# Backend path routing for HTTPS - Rule 1 (API paths)
resource "aws_lb_listener_rule" "backend_https" {
  count        = var.domain_name != "" ? 1 : 0
  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/auth/*", "/docs", "/health", "/metrics"]
    }
  }
}

# Backend path routing for HTTPS - Rule 2 (WebSocket)
resource "aws_lb_listener_rule" "backend_https_ws" {
  count        = var.domain_name != "" ? 1 : 0
  listener_arn = aws_lb_listener.https[0].arn
  priority     = 101

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/socket.io/*"]
    }
  }
}

# Backend path routing for HTTPS - Rule 3 (Other API paths)
resource "aws_lb_listener_rule" "backend_https_api" {
  count        = var.domain_name != "" ? 1 : 0
  listener_arn = aws_lb_listener.https[0].arn
  priority     = 102

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/user/*", "/developer/*", "/custom-model/*", "/chatbot*"]
    }
  }
}

# Redirect HTTP to HTTPS (only when domain is set)
resource "aws_lb_listener" "http_redirect" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

output "domain_url" {
  description = "Application URL (HTTPS with domain)"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : null
}
