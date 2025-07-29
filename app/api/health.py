"""
Health check and system status routes.

Provides endpoints for monitoring the API health and status.
"""

import logging
from datetime import datetime

from fastapi import APIRouter

from app.config import settings
from app.models import HealthCheckResponse

# Configure logger for this module
logger = logging.getLogger(__name__)

# Create router for health endpoints
router = APIRouter()


@router.get("/", response_model=dict)
async def root():
    """
    Root endpoint providing basic API information.
    
    Returns:
        Basic information about the API
    """
    return {
        "message": "Sheetful API - Turn your Google Sheet into a RESTful API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        Health status information
    """
    return HealthCheckResponse(
        status="healthy",
        version=settings.API_VERSION,
        timestamp=datetime.utcnow().isoformat()
    )
