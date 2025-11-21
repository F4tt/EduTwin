import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from db import models, database
from api import auth, study, developer, chatbot
from api import user
from services.vector_store_provider import get_vector_store

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Tạo bảng database khi ứng dụng khởi động"""
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
            print("Database tables created successfully")
            # Preload vector store (loads embedding model) to avoid long delays on first request
            try:
                get_vector_store()
                print("Vector store initialized on startup")
            except Exception as e:
                print(f"Failed to initialize vector store at startup: {e}")
            # Start background pruning/summarizer job if enabled
            try:
                from services.prune_service import start_background_prune_scheduler

                start_background_prune_scheduler()
            except Exception:
                pass
            break
        except OperationalError as exc:
            wait_time = min(2 ** attempt, 10)
            print(f"Database not ready (attempt {attempt}/{max_attempts}): {exc}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except Exception as exc:  # noqa: BLE001
            print(f"Error creating database tables: {exc}")
            break
    else:
        print("Failed to initialize database tables after several attempts.")

app.include_router(auth.router)
app.include_router(study.router)
app.include_router(developer.router)
app.include_router(chatbot.router)
app.include_router(user.router)

@app.get("/")
def root():
    return {"message": "Backend is running"}
