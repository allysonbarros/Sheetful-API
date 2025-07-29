"""
Sheetful API - Main application module.

This module sets up the FastAPI application with all necessary middleware,
routes, and configuration.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health_router, sheets_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Validate configuration
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    
    # Create FastAPI app instance
    app = FastAPI(
        title=settings.API_TITLE,
        description=settings.API_DESCRIPTION,
        version=settings.API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(sheets_router, tags=["Sheets"])
    
    logger.info(f"FastAPI application created - {settings.API_TITLE} v{settings.API_VERSION}")
    
    return app


# Create the app instance
app = create_app()
