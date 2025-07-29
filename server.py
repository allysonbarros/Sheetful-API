#!/usr/bin/env python3
"""
Sheetful Python API Server

Alternative entry point for running the server.
This is kept for backward compatibility.
"""

import uvicorn

from app.config import settings
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
