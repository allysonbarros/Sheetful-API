"""
Sheets API routes.

Handles all endpoints related to Google Sheets operations:
- Reading sheets data
- Getting sheet information
- CRUD operations on rows
- Bulk operations
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Path, Query

from app.api.utils import get_worksheet_from_ids, log_request, log_success
from app.models import BulkOperationResponse, SheetGetRowsOptions
from app.services import sheets_service

# Configure logger for this module
logger = logging.getLogger(__name__)

# Create router for sheets endpoints
router = APIRouter()


@router.get("/{document_id}/{sheet_id}", response_model=List[Dict[str, Any]])
async def get_rows(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rows to return"),
) -> List[Dict[str, Any]]:
    """
    Get rows from a Google Sheet with optional pagination.
    
    Retrieves data from a Google Sheet with support for:
    - Pagination using offset and limit
    - Authentication via OAuth2 token or API key
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        x_google_access_token: OAuth2 access token (optional)
        offset: Number of rows to skip from the beginning
        limit: Maximum number of rows to return (max 1000)
        
    Returns:
        List of row dictionaries with column headers as keys
        
    Raises:
        HTTPException: If document/sheet is not accessible or other errors occur
    """
    log_request("GET", document_id, sheet_id, offset=offset, limit=limit)
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Create options for getting rows
        options = SheetGetRowsOptions(offset=offset, limit=limit)
        
        # Get rows
        rows = await sheets_service.get_sheet_rows(worksheet, options)
        
        log_success(
            f"Retrieved {len(rows)} rows",
            document.title,
            worksheet.title
        )
        
        return rows
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rows: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/{document_id}/{sheet_id}/info", response_model=Dict[str, Any])
async def get_sheet_info(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """
    Get metadata information about a Google Sheet.
    
    Returns comprehensive information about the sheet including:
    - Sheet ID, title, and index
    - Row and column counts
    - Header values
    - Sheet configuration
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Dictionary containing sheet metadata
        
    Raises:
        HTTPException: If document/sheet is not accessible
    """
    log_request("GET INFO", document_id, sheet_id)
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Get sheet info
        sheet_info = await sheets_service.get_sheet_info(worksheet)
        
        log_success("Retrieved info", document.title, worksheet.title)
        
        return sheet_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sheet info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def get_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Row index (0-based)"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """
    Get a specific row from a Google Sheet.
    
    Retrieves a single row by its index (0-based).
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        row_id: Zero-based row index
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Dictionary containing row data with column headers as keys
        
    Raises:
        HTTPException: If document/sheet/row is not found
    """
    log_request("GET ROW", document_id, sheet_id, row_id=row_id)
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Get specific row
        row = await sheets_service.get_row(worksheet, row_id)
        
        log_success(f"Retrieved row {row_id}", document.title, worksheet.title)
        
        return row
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting row: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.put("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def update_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Row index (0-based)"),
    body: Dict[str, Any] = Body(..., description="Row data to update"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """
    Update a specific row in a Google Sheet.
    
    Updates an existing row with new data. Only provided fields will be updated.
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        row_id: Zero-based row index
        body: Dictionary containing the new row data
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Dictionary containing the updated row data
        
    Raises:
        HTTPException: If document/sheet/row is not found or update fails
    """
    log_request("UPDATE ROW", document_id, sheet_id, row_id=row_id)
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Update row
        updated_row = await sheets_service.update_row(worksheet, row_id, body)
        
        log_success(f"Updated row {row_id}", document.title, worksheet.title)
        
        return updated_row
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating row: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/{document_id}/{sheet_id}", response_model=Dict[str, Any])
async def create_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    body: Dict[str, Any] = Body(..., description="Row data to create"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """
    Create a new row in a Google Sheet.
    
    Adds a new row to the end of the sheet with the provided data.
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        body: Dictionary containing the new row data
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Dictionary containing the created row data
        
    Raises:
        HTTPException: If document/sheet is not accessible or creation fails
    """
    log_request("CREATE ROW", document_id, sheet_id)
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Create new row
        new_row = await sheets_service.create_row(worksheet, body)
        
        log_success("Created new row", document.title, worksheet.title)
        
        return new_row
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating row: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.put("/{document_id}/{sheet_id}/{row_id}/bulk", response_model=BulkOperationResponse)
async def update_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Starting row index (0-based)"),
    body: List[Dict[str, Any]] = Body(..., description="List of row data to update"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> BulkOperationResponse:
    """
    Update multiple rows in bulk in a Google Sheet.
    
    Updates multiple consecutive rows starting from the specified row index.
    This is more efficient than updating rows individually.
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        row_id: Starting row index (0-based)
        body: List of dictionaries containing row data to update
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Response indicating success and number of rows updated
        
    Raises:
        HTTPException: If document/sheet is not accessible or update fails
    """
    log_request("BULK UPDATE", document_id, sheet_id, row_id=row_id, count=len(body))
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Update rows in bulk
        updated_count = await sheets_service.update_rows_bulk(worksheet, row_id, body)
        
        log_success(
            f"Bulk updated {updated_count} rows starting from {row_id}",
            document.title,
            worksheet.title
        )
        
        return BulkOperationResponse(
            message=f"Successfully updated {updated_count} rows",
            affected_rows=updated_count,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rows in bulk: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/{document_id}/{sheet_id}/bulk", response_model=BulkOperationResponse)
async def create_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    body: List[Dict[str, Any]] = Body(..., description="List of row data to create"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> BulkOperationResponse:
    """
    Create multiple rows in bulk in a Google Sheet.
    
    Adds multiple new rows to the end of the sheet.
    This is more efficient than creating rows individually.
    
    Args:
        document_id: The Google Spreadsheet document ID from the URL
        sheet_id: Sheet identifier (can be numeric ID, index, or title)
        body: List of dictionaries containing row data to create
        x_google_access_token: OAuth2 access token (optional)
        
    Returns:
        Response indicating success and number of rows created
        
    Raises:
        HTTPException: If document/sheet is not accessible or creation fails
    """
    log_request("BULK CREATE", document_id, sheet_id, count=len(body))
    
    try:
        # Get document and worksheet
        document, worksheet = await get_worksheet_from_ids(
            document_id, sheet_id, x_google_access_token
        )
        
        # Create rows in bulk
        created_count = await sheets_service.create_rows_bulk(worksheet, body)
        
        log_success(
            f"Bulk created {created_count} rows",
            document.title,
            worksheet.title
        )
        
        return BulkOperationResponse(
            message=f"Successfully created {created_count} rows",
            affected_rows=created_count,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating rows in bulk: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
