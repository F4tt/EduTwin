"""
CloudWatch Metrics for AWS Production Token Monitoring.
Uses structured logging that CloudWatch Logs Insights can query,
plus optional CloudWatch Metrics API for dashboards.

SIMPLIFIED: Only tracks RequestCount and TotalTokens to minimize costs.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional
from functools import wraps

# Check if running in AWS (ECS sets these environment variables)
IS_AWS = bool(os.getenv("AWS_EXECUTION_ENV") or os.getenv("ECS_CONTAINER_METADATA_URI"))

logger = logging.getLogger("cloudwatch_metrics")


class CloudWatchTokenTracker:
    """
    Token usage tracker that outputs structured logs for CloudWatch Logs Insights
    and optionally publishes to CloudWatch Metrics.
    
    COST OPTIMIZATION: Only publishes 2 metrics (RequestCount, TotalTokens) to minimize CloudWatch costs.
    Full details available via CloudWatch Logs Insights queries.
    """
    
    def __init__(self):
        self.is_aws = IS_AWS
        self._boto_client = None
        self.namespace = os.getenv("CLOUDWATCH_NAMESPACE", "EduTwin/LLM")
        
    def _get_boto_client(self):
        """Lazy load boto3 client only in AWS environment."""
        if self._boto_client is None and self.is_aws:
            try:
                import boto3
                self._boto_client = boto3.client('cloudwatch', 
                    region_name=os.getenv("AWS_REGION", "us-east-1"))
            except ImportError:
                logger.warning("boto3 not installed, CloudWatch Metrics disabled")
            except Exception as e:
                logger.warning(f"Failed to create CloudWatch client: {e}")
        return self._boto_client
    
    def track_token_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        request_type: str = "chat",
        user_id: Optional[int] = None,
        duration_seconds: Optional[float] = None
    ):
        """
        Track token usage - logs to CloudWatch-compatible format.
        
        In AWS: Publishes to CloudWatch Metrics + structured logs
        Local: Just logs in structured JSON format
        """
        # Structured log for CloudWatch Logs Insights (full details)
        log_data = {
            "metric_type": "token_usage",
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "request_type": request_type,
            "user_id": user_id,
            "duration_seconds": duration_seconds,
            "environment": "aws" if self.is_aws else "local"
        }
        
        # Log in JSON format for CloudWatch Logs Insights
        logger.info(json.dumps(log_data))
        
        # Publish ONLY essential metrics to CloudWatch (cost optimization)
        if self.is_aws:
            self._publish_cloudwatch_metrics(total_tokens, request_type)
    
    def _publish_cloudwatch_metrics(self, total_tokens: int, request_type: str):
        """
        Publish ONLY 2 metrics to CloudWatch to minimize costs:
        - RequestCount
        - TotalTokens
        
        CloudWatch Pricing: $0.30/metric/month for first 10,000 metrics
        With 1 dimension (RequestType: chat/learning), we have:
        - 2 metrics × 2 request_types = 4 unique metric streams
        - Cost: ~$1.20/month
        """
        client = self._get_boto_client()
        if not client:
            return
        
        try:
            dimensions = [
                {"Name": "RequestType", "Value": request_type}
            ]
            
            metric_data = [
                {
                    "MetricName": "TotalTokens",
                    "Dimensions": dimensions,
                    "Value": total_tokens,
                    "Unit": "Count"
                },
                {
                    "MetricName": "RequestCount",
                    "Dimensions": dimensions,
                    "Value": 1,
                    "Unit": "Count"
                }
            ]
            
            client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
        except Exception as e:
            logger.error(f"Failed to publish CloudWatch metrics: {e}")


# Singleton instance
_tracker: Optional[CloudWatchTokenTracker] = None


def get_cloudwatch_tracker() -> CloudWatchTokenTracker:
    """Get singleton CloudWatch tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CloudWatchTokenTracker()
    return _tracker


def track_llm_tokens(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    request_type: str = "chat",
    user_id: Optional[int] = None,
    duration_seconds: Optional[float] = None
):
    """
    Convenience function to track LLM token usage.
    Works both locally (structured logs) and in AWS (CloudWatch Metrics).
    """
    tracker = get_cloudwatch_tracker()
    tracker.track_token_usage(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_type=request_type,
        user_id=user_id,
        duration_seconds=duration_seconds
    )


# ========== CloudWatch Logs Insights Queries ==========
# 
# Full details are in structured logs. Use these queries:
#
# 1. Total tokens by request type (last 24h):
#    fields @timestamp, request_type, total_tokens
#    | filter metric_type = "token_usage"
#    | stats sum(total_tokens) as total, count(*) as requests by request_type
#
# 2. Token usage over time:
#    fields @timestamp, total_tokens
#    | filter metric_type = "token_usage"
#    | stats sum(total_tokens) as tokens by bin(1h)
#
# 3. Breakdown by model:
#    fields model, total_tokens, prompt_tokens, completion_tokens
#    | filter metric_type = "token_usage"
#    | stats sum(total_tokens) as total, sum(prompt_tokens) as prompt, sum(completion_tokens) as completion by model

