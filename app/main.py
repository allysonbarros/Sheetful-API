"""
Sheetful API - Main application module.

This module sets up the FastAPI application with all necessary middleware,
routes, and configuration.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import errors, health_router, sheets_router
from app.api.middleware import RequestLoggingMiddleware
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
    
    # Add CORS middleware. ALLOWED_ORIGINS/ALLOW_CREDENTIALS are validated
    # against each other by Settings (see spec 0005/0007).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging + correlation ID (spec 0010). Must be added BEFORE
    # exception handlers are wired so request.state.request_id is populated
    # when an error is caught.
    app.add_middleware(RequestLoggingMiddleware)

    # Centralized error handlers (spec 0005) — never leak raw exception text.
    errors.register(app)

    # Include routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(sheets_router, tags=["Sheets"])
    
    logger.info(f"FastAPI application created - {settings.API_TITLE} v{settings.API_VERSION}")
    
    return app


# Create the app instance
app = create_app()
