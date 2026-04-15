"""
Health and readiness routes.

``/health`` is a liveness probe (process is up). ``/ready`` is a readiness
probe that exercises authentication against Google and reports unavailable
(503) when the upstream is broken.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.models import HealthCheckResponse
from app.services.sheets import GoogleSheetsService, get_sheets_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=dict)
async def root():
    """Root endpoint providing basic API information."""
    return {
        "message": "Sheetful API - Turn your Google Sheet into a RESTful API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Liveness probe: returns 200 as long as the process is running."""
    return HealthCheckResponse(
        status="healthy",
        version=settings.API_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready")
async def readiness_check(
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> dict:
    """
    Readiness probe: exercises the Google auth path. Returns 503 if the
    upstream is unreachable or credentials are invalid.
    """
    try:
        await svc.ping()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail="Upstream unavailable")
    return {"status": "ready"}
