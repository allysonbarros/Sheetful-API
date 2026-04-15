"""
Sheets API routes.

Thin handlers: parse + delegate to ``GoogleSheetsService``. Unexpected
exceptions bubble up to ``app.api.errors`` which logs the traceback under
an ``error_id`` and returns a generic 500 (spec 0005).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, Path, Query, Request

from app.api.utils import get_worksheet_from_ids, log_request, log_success
from app.models import BulkOperationResponse, SheetGetRowsOptions
from app.services.sheets import GoogleSheetsService, get_sheets_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_filter_params(request: Request) -> Optional[Dict[str, str]]:
    """
    Extract ``filter[<column>]=<value>`` pairs from a request's query string.

    Returns ``None`` if no filters are present so ``SheetGetRowsOptions.query``
    stays unset and the fast pagination path is used (spec 0003).
    """
    filters: Dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith("filter[") and key.endswith("]"):
            column = key[len("filter[") : -1]
            if column:
                filters[column] = value
    return filters or None


@router.get("/{document_id}/{sheet_id}", response_model=List[Dict[str, Any]])
async def get_rows(
    request: Request,
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of rows to return"
    ),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> List[Dict[str, Any]]:
    """
    Return rows from a sheet with offset/limit pagination.

    Optional column filters can be passed as ``filter[<column>]=<value>``
    query params (AND across multiple keys, exact string match). When any
    filter is present, the server falls back to an in-memory filtering pass.
    """
    filters = _parse_filter_params(request)
    log_request(
        "GET",
        document_id,
        sheet_id,
        offset=offset,
        limit=limit,
        filters=filters,
    )

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    options = SheetGetRowsOptions(offset=offset, limit=limit, query=filters)
    rows = await svc.get_sheet_rows(worksheet, options)

    log_success(f"Retrieved {len(rows)} rows", document.title, worksheet.title)
    return rows


@router.get("/{document_id}/{sheet_id}/info", response_model=Dict[str, Any])
async def get_sheet_info(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> Dict[str, Any]:
    """Return worksheet metadata (dimensions, headers, etc.)."""
    log_request("GET INFO", document_id, sheet_id)

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    sheet_info = await svc.get_sheet_info(worksheet)

    log_success("Retrieved info", document.title, worksheet.title)
    return sheet_info


@router.get("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def get_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Row index (0-based)"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> Dict[str, Any]:
    """Return a single row by its 0-based index."""
    log_request("GET ROW", document_id, sheet_id, row_id=row_id)

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    row = await svc.get_row(worksheet, row_id)

    log_success(f"Retrieved row {row_id}", document.title, worksheet.title)
    return row


@router.put("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def update_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Row index (0-based)"),
    body: Dict[str, Any] = Body(..., description="Row data to update"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> Dict[str, Any]:
    """Patch a row: unspecified fields are preserved."""
    log_request("UPDATE ROW", document_id, sheet_id, row_id=row_id)

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    updated_row = await svc.update_row(worksheet, row_id, body)

    log_success(f"Updated row {row_id}", document.title, worksheet.title)
    return updated_row


@router.post("/{document_id}/{sheet_id}", response_model=Dict[str, Any])
async def create_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    body: Dict[str, Any] = Body(..., description="Row data to create"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> Dict[str, Any]:
    """Append a new row to the end of the sheet."""
    log_request("CREATE ROW", document_id, sheet_id)

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    new_row = await svc.create_row(worksheet, body)

    log_success("Created new row", document.title, worksheet.title)
    return new_row


@router.put(
    "/{document_id}/{sheet_id}/{row_id}/bulk",
    response_model=BulkOperationResponse,
)
async def update_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    row_id: int = Path(..., ge=0, description="Starting row index (0-based)"),
    body: List[Dict[str, Any]] = Body(..., description="Row data patches"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> BulkOperationResponse:
    """Patch a contiguous block of rows starting at ``row_id``."""
    log_request("BULK UPDATE", document_id, sheet_id, row_id=row_id, count=len(body))

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    updated_count = await svc.update_rows_bulk(worksheet, row_id, body)

    log_success(
        f"Bulk updated {updated_count} rows starting from {row_id}",
        document.title,
        worksheet.title,
    )
    return BulkOperationResponse(
        message=f"Successfully updated {updated_count} rows",
        affected_rows=updated_count,
        success=True,
    )


@router.post("/{document_id}/{sheet_id}/bulk", response_model=BulkOperationResponse)
async def create_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID, index, or title"),
    body: List[Dict[str, Any]] = Body(..., description="Rows to create"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    svc: GoogleSheetsService = Depends(get_sheets_service),
) -> BulkOperationResponse:
    """Append multiple rows at once."""
    log_request("BULK CREATE", document_id, sheet_id, count=len(body))

    document, worksheet = await get_worksheet_from_ids(
        svc, document_id, sheet_id, x_google_access_token
    )
    created_count = await svc.create_rows_bulk(worksheet, body)

    log_success(f"Bulk created {created_count} rows", document.title, worksheet.title)
    return BulkOperationResponse(
        message=f"Successfully created {created_count} rows",
        affected_rows=created_count,
        success=True,
    )
