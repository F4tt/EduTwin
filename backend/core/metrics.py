"""
Prometheus metrics for monitoring EduTwin application.
Tracks API requests, LLM calls, token usage, and system performance.
"""
import time
from functools import wraps
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, Info
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ===== Application Info =====
app_info = Info('edutwin_app', 'EduTwin application information')
app_info.info({'version': '1.0.0', 'component': 'backend'})


# ===== HTTP Request Metrics =====
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)


# ===== LLM Metrics =====
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status']
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider', 'model'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens consumed',
    ['provider', 'model', 'type']  # type: prompt, completion, total
)

llm_tokens_gauge = Gauge(
    'llm_tokens_current',
    'Current token count for active requests',
    ['provider', 'model', 'type']
)

llm_errors_total = Counter(
    'llm_errors_total',
    'Total LLM errors',
    ['provider', 'model', 'error_type']
)

llm_retries_total = Counter(
    'llm_retries_total',
    'Total LLM request retries',
    ['provider', 'model']
)


# ===== Database Metrics =====
db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table', 'status']
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)


# ===== Vector Store Metrics =====
vector_search_total = Counter(
    'vector_search_total',
    'Total vector store searches',
    ['status']
)

vector_search_duration_seconds = Histogram(
    'vector_search_duration_seconds',
    'Vector search duration in seconds',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

vector_search_results = Histogram(
    'vector_search_results',
    'Number of results returned from vector search',
    buckets=[0, 1, 5, 10, 20, 50, 100]
)


# ===== Chat Session Metrics =====
chat_sessions_active = Gauge(
    'chat_sessions_active',
    'Number of active chat sessions'
)

chat_messages_total = Counter(
    'chat_messages_total',
    'Total chat messages',
    ['role', 'has_context']
)


# ===== User Metrics =====
users_active = Gauge(
    'users_active',
    'Number of active users'
)

user_actions_total = Counter(
    'user_actions_total',
    'Total user actions',
    ['action_type', 'status']
)


# ===== Study Score Metrics =====
study_scores_updated = Counter(
    'study_scores_updated',
    'Total study score updates',
    ['subject', 'status']
)

predictions_total = Counter(
    'predictions_total',
    'Total predictions made',
    ['model_type', 'status']
)

prediction_duration_seconds = Histogram(
    'prediction_duration_seconds',
    'Prediction duration in seconds',
    ['model_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)


# ===== System Metrics =====
background_tasks_total = Counter(
    'background_tasks_total',
    'Total background tasks executed',
    ['task_type', 'status']
)

cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # operation: get, set, delete; result: hit, miss, success, error
)


# ===== Business & ML Metrics =====
ml_pipeline_executions = Counter(
    'ml_pipeline_executions_total',
    'ML pipeline executions',
    ['trigger', 'status']
)

ml_pipeline_duration = Histogram(
    'ml_pipeline_duration_seconds',
    'ML pipeline execution duration',
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

ml_pipeline_last_run_timestamp = Gauge(
    'ml_pipeline_last_run_timestamp',
    'Timestamp of last ML pipeline run'
)

student_logins_total = Counter(
    'student_logins_total',
    'Total student logins',
    ['grade']
)

auth_attempts_total = Counter(
    'auth_attempts_total',
    'Authentication attempts',
    ['status', 'method']
)

active_sessions_count = Gauge(
    'active_sessions_count',
    'Number of active user sessions'
)

excel_imports_total = Counter(
    'excel_imports_total',
    'Excel file imports',
    ['status']
)

excel_rows_processed = Counter(
    'excel_rows_processed_total',
    'Rows processed from Excel',
    ['status']
)

process_memory_bytes = Gauge(
    'process_memory_bytes',
    'Process memory usage in bytes'
)

process_cpu_percent = Gauge(
    'process_cpu_percent',
    'Process CPU usage percentage'
)


# ===== Middleware for HTTP Metrics =====
class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        method = request.method
        endpoint = request.url.path
        
        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        
        # Track request duration
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status = response.status_code
            
            # Track completed request
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
            
            return response
            
        except Exception as e:
            # Track failed request
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()
            raise
            
        finally:
            # Track duration and decrement in-progress
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()


# ===== Decorators for Tracking =====
def track_llm_call(provider: str, model: str):
    """Decorator to track LLM API calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                llm_errors_total.labels(
                    provider=provider,
                    model=model,
                    error_type=error_type
                ).inc()
                raise
                
            finally:
                duration = time.time() - start_time
                llm_requests_total.labels(
                    provider=provider,
                    model=model,
                    status=status
                ).inc()
                llm_request_duration_seconds.labels(
                    provider=provider,
                    model=model
                ).observe(duration)
        
        return wrapper
    return decorator


def track_db_query(operation: str, table: str):
    """Decorator to track database queries."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                status = "error"
                raise
                
            finally:
                duration = time.time() - start_time
                db_queries_total.labels(
                    operation=operation,
                    table=table,
                    status=status
                ).inc()
                db_query_duration_seconds.labels(
                    operation=operation,
                    table=table
                ).observe(duration)
        
        return wrapper
    return decorator


# ===== Token Tracking Functions =====
def track_tokens(provider: str, model: str, prompt_tokens: int = 0, 
                completion_tokens: int = 0, total_tokens: int = 0):
    """Track LLM token usage."""
    if prompt_tokens > 0:
        llm_tokens_total.labels(
            provider=provider,
            model=model,
            type='prompt'
        ).inc(prompt_tokens)
        
    if completion_tokens > 0:
        llm_tokens_total.labels(
            provider=provider,
            model=model,
            type='completion'
        ).inc(completion_tokens)
        
    if total_tokens > 0:
        llm_tokens_total.labels(
            provider=provider,
            model=model,
            type='total'
        ).inc(total_tokens)
