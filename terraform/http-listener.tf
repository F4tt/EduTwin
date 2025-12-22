# HTTP Listener for ALB (No Domain Required)
# This file is used when domain_name is not set or empty

resource "aws_lb_listener" "http" {
  count             = var.domain_name == "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# Backend path routing for HTTP - Rule 1 (API paths)
resource "aws_lb_listener_rule" "backend_http" {
  count        = var.domain_name == "" ? 1 : 0
  listener_arn = aws_lb_listener.http[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/openapi.json", "/health", "/metrics"]
    }
  }
}

# Backend path routing for HTTP - Rule 2 (WebSocket)
resource "aws_lb_listener_rule" "backend_http_ws" {
  count        = var.domain_name == "" ? 1 : 0
  listener_arn = aws_lb_listener.http[0].arn
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
