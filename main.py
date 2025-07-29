"""
Sheetful API - Entry point for the application.

This is the main entry point that imports and runs the FastAPI application.
The actual application setup is now in app.main for better organization.
"""

import uvicorn

from app.config import settings
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
