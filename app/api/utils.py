"""
Utility functions for API routes.

Common functionality shared across different route modules.
"""

import logging
from typing import Optional

from fastapi import HTTPException

from app.services.sheets import GoogleSheetsService

logger = logging.getLogger(__name__)


async def get_worksheet_from_ids(
    svc: GoogleSheetsService,
    document_id: str,
    sheet_id: str,
    access_token: Optional[str] = None,
):
    """
    Helper function to get worksheet from document and sheet IDs.

    Args:
        svc: Injected ``GoogleSheetsService`` instance.
        document_id: Google Spreadsheet document ID.
        sheet_id: Sheet identifier (ID, index, or title).
        access_token: OAuth2 access token (optional).

    Returns:
        tuple: (document, worksheet) objects.

    Raises:
        HTTPException: If document or sheet cannot be accessed.
    """
    try:
        document = await svc.get_document(document_id, access_token)
        worksheet = await svc.get_sheet(document, sheet_id)
        return document, worksheet
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting worksheet: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


def log_request(endpoint: str, document_id: str, sheet_id: str, **kwargs) -> None:
    """Log API request with consistent format."""
    params = ", ".join([f"{k}={v}" for k, v in kwargs.items() if v is not None])
    log_msg = f"{endpoint} /{document_id}/{sheet_id}"
    if params:
        log_msg += f" - {params}"
    logger.info(log_msg)


def log_success(
    action: str, document_title: str, sheet_title: str, details: str = ""
) -> None:
    """Log successful operation."""
    log_msg = f"{action} in {document_title}/{sheet_title}"
    if details:
        log_msg += f" - {details}"
    logger.info(log_msg)
