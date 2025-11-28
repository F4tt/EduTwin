"""
System metrics collector for monitoring resource usage.
Runs periodically to update system-level metrics.
"""
import asyncio
import psutil
import time
from backend.core.metrics import (
    process_memory_bytes,
    process_cpu_percent,
    db_connections_active,
)


def collect_system_metrics():
    """Collect and update system metrics."""
    try:
        # Process metrics
        process = psutil.Process()
        memory_info = process.memory_info()
        process_memory_bytes.set(memory_info.rss)
        process_cpu_percent.set(process.cpu_percent(interval=1))
        
    except Exception as e:
        print(f"Error collecting system metrics: {e}")


async def start_metrics_collector(interval: int = 15):
    """
    Start background task to collect system metrics periodically.
    
    Args:
        interval: Collection interval in seconds (default: 15s)
    """
    while True:
        collect_system_metrics()
        await asyncio.sleep(interval)


def update_db_pool_metrics(pool):
    """
    Update database connection pool metrics.
    Call this from database connection pool manager.
    
    Args:
        pool: SQLAlchemy connection pool
    """
    try:
        # Get pool statistics
        if hasattr(pool, 'size'):
            db_connections_active.set(pool.checkedout())
    except Exception as e:
        print(f"Error updating DB pool metrics: {e}")
