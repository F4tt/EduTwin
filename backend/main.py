import time
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from db import models, database
from api import auth, study, developer, chatbot, learning_goals
from api import user
from services.vector_store_provider import get_vector_store
from core.logging_config import setup_logging, get_logger
from core.metrics import PrometheusMiddleware, http_requests_total

# Setup structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level)
logger = get_logger(__name__)

app = FastAPI()

# Request timing middleware (log slow requests)
@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Log slow requests (>1s)
    if duration > 1.0:
        logger.warning("Slow request detected", extra={
            "method": request.method,
            "path": request.url.path,
            "duration_seconds": round(duration, 3),
            "status_code": response.status_code
        })
    else:
        logger.info("Request completed", extra={
            "method": request.method,
            "path": request.url.path,
            "duration_seconds": round(duration, 3),
            "status_code": response.status_code
        })
    
    # Add timing header for debugging
    response.headers["X-Process-Time"] = str(round(duration, 3))
    return response

# Add Prometheus middleware first
app.add_middleware(PrometheusMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse
    logger.error("Validation error occurred", extra={
        "errors": exc.errors(),
        "path": request.url.path,
        "method": request.method
    })
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.on_event("startup")
async def startup_event():
    """Tạo bảng database khi ứng dụng khởi động"""
    logger.info("Starting EduTwin application", extra={"log_level": log_level})
    
    # Start metrics collector
    try:
        from core.metrics_collector import start_metrics_collector
        import asyncio
        asyncio.create_task(start_metrics_collector(interval=15))
        logger.info("Metrics collector started")
    except Exception as e:
        logger.warning("Failed to start metrics collector", extra={"error": str(e)})
    
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            models.Base.metadata.create_all(bind=database.engine)
            with database.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS email VARCHAR,
                    ADD COLUMN IF NOT EXISTS phone VARCHAR,
                    ADD COLUMN IF NOT EXISTS address VARCHAR,
                    ADD COLUMN IF NOT EXISTS age VARCHAR,
                    ADD COLUMN IF NOT EXISTS current_grade VARCHAR,
                    ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS preferences JSON
                """))
                conn.execute(text("""
                    ALTER TABLE study_scores
                    ADD COLUMN IF NOT EXISTS actual_status VARCHAR,
                    ADD COLUMN IF NOT EXISTS predicted_status VARCHAR
                """))
                # Ensure model_parameters table is created (in case SQLAlchemy create_all doesn't catch it)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS model_parameters (
                        id SERIAL PRIMARY KEY,
                        knn_n INTEGER NOT NULL DEFAULT 15,
                        kr_bandwidth FLOAT NOT NULL DEFAULT 1.25,
                        lwlr_tau FLOAT NOT NULL DEFAULT 3.0,
                        updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                # Create learning_goals table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS learning_goals (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        target_average FLOAT NOT NULL,
                        target_semester VARCHAR NOT NULL,
                        target_grade_level VARCHAR NOT NULL,
                        predicted_scores JSON,
                        trajectory_data JSON,
                        ai_analysis TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_learning_goals_id ON learning_goals(id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_learning_goals_user_id ON learning_goals(user_id)
                """))
                # Add user_id to knn_reference_samples if not exists
                conn.execute(text("""
                    ALTER TABLE knn_reference_samples
                    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_knn_reference_samples_user_id ON knn_reference_samples(user_id)
                """))
            logger.info("Database tables created successfully")
            
            # Preload vector store (loads embedding model) to avoid long delays on first request
            try:
                get_vector_store()
                logger.info("Vector store initialized on startup")
            except Exception as e:
                logger.error(f"Failed to initialize vector store at startup", extra={"error": str(e)})
            
            # Start background pruning/summarizer job if enabled
            try:
                from services.prune_service import start_background_prune_scheduler
                start_background_prune_scheduler()
                logger.info("Background prune scheduler started")
            except Exception as e:
                logger.debug(f"Prune service not started", extra={"error": str(e)})
            break
            
        except OperationalError as exc:
            wait_time = min(2 ** attempt, 10)
            logger.warning(f"Database not ready, retrying...", extra={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "wait_time": wait_time,
                "error": str(exc)
            })
            time.sleep(wait_time)
        except Exception as exc:
            logger.error("Error creating database tables", extra={"error": str(exc)})
            break
    else:
        logger.error("Failed to initialize database tables after several attempts")
    
    logger.info("Application startup complete")

app.include_router(auth.router)
app.include_router(study.router)
app.include_router(developer.router)
app.include_router(chatbot.router)
app.include_router(user.router)
app.include_router(learning_goals.router)

@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {"message": "Backend is running"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/health")
def health():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "edutwin-backend",
        "timestamp": time.time()
    }
