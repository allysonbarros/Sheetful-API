"""
Centralized exception handlers for the Sheetful API.

Responses never leak raw exception messages: unexpected errors are logged
with full traceback under a generated ``error_id`` and the client receives
only a generic message + that ID for correlation.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    """
    Return the correlation ID for this request.

    Prefer the one set by ``RequestLoggingMiddleware`` (spec 0010); fall
    back to an inbound ``x-request-id`` header; finally mint a fresh UUID.
    """
    return (
        getattr(request.state, "request_id", None)
        or request.headers.get("x-request-id")
        or str(uuid.uuid4())
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all: log the traceback, return a generic 500 with an error_id."""
    error_id = _request_id(request)
    logger.exception(
        "Unhandled error [%s] on %s %s",
        error_id,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "status": 500,
            "error_id": error_id,
        },
        headers={"x-request-id": error_id},
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Render HTTPException as the documented error envelope."""
    detail = exc.detail if isinstance(exc.detail, str) else "Error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": detail, "status": exc.status_code},
        headers={"x-request-id": _request_id(request)},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Preserve FastAPI's default 422 shape but under our envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "message": "Request validation failed",
            "status": 422,
            "errors": exc.errors(),
        },
    )


def register(app: FastAPI) -> None:
    """Wire the handlers above onto a FastAPI application."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
