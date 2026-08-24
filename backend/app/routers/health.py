"""Health-check router — GET /api/health"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Returns service status and a quick DB connectivity check.
    Frontend uses this endpoint to confirm the API is reachable.
    """
    start = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:          # noqa: BLE001
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "db": db_status,
        "latency_ms": round((time.monotonic() - start) * 1000, 2),
    }
