import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from db import models, database
from api import auth, study

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
                    ADD COLUMN IF NOT EXISTS age VARCHAR
                """))
            print("Database tables created successfully")
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

@app.get("/")
def root():
    return {"message": "Backend is running"}
