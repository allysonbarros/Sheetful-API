#!/usr/bin/env python3
"""
Sheetful Python API Server
"""

import uvicorn

import config
from main import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.PORT,
        reload=True,
        log_level="info"
    )
