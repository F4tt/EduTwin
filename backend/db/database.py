from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://edutwin_user:edutwin_password@db:5432/edutwin")

# Connection pooling configuration for performance
# pool_size: number of connections to keep open (default 5)
# max_overflow: max connections beyond pool_size (default 10)
# pool_timeout: seconds to wait for connection (default 30)
# pool_recycle: recycle connections after N seconds (prevent stale connections)
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Keep 10 connections ready
    max_overflow=20,        # Allow 20 more if needed (total 30 max)
    pool_timeout=30,        # Wait 30s for connection
    pool_recycle=3600,      # Recycle after 1 hour
    pool_pre_ping=True,     # Test connection before using
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
