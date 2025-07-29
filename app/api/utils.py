"""
Utility functions for API routes.

Common functionality shared across different route modules.
"""

import logging
from typing import Optional

from fastapi import Header, HTTPException

from app.services import sheets_service

logger = logging.getLogger(__name__)


async def get_worksheet_from_ids(
    document_id: str,
    sheet_id: str,
    access_token: Optional[str] = None
):
    """
    Helper function to get worksheet from document and sheet IDs.
    
    Args:
        document_id: Google Spreadsheet document ID
        sheet_id: Sheet identifier (ID, index, or title)
        access_token: OAuth2 access token (optional)
        
    Returns:
        tuple: (document, worksheet) objects
        
    Raises:
        HTTPException: If document or sheet cannot be accessed
    """
    try:
        document = await sheets_service.get_document(document_id, access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        return document, worksheet
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting worksheet: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


def log_request(endpoint: str, document_id: str, sheet_id: str, **kwargs):
    """
    Log API request with consistent format.
    
    Args:
        endpoint: API endpoint being called
        document_id: Google Spreadsheet document ID
        sheet_id: Sheet identifier
        **kwargs: Additional parameters to log
    """
    params = ", ".join([f"{k}={v}" for k, v in kwargs.items() if v is not None])
    log_msg = f"{endpoint} /{document_id}/{sheet_id}"
    if params:
        log_msg += f" - {params}"
    logger.info(log_msg)


def log_success(action: str, document_title: str, sheet_title: str, details: str = ""):
    """
    Log successful operation.
    
    Args:
        action: Action performed
        document_title: Document title
        sheet_title: Sheet title
        details: Additional details
    """
    log_msg = f"{action} in {document_title}/{sheet_title}"
    if details:
        log_msg += f" - {details}"
    logger.info(log_msg)
