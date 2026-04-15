"""
Google Sheets service module.

This module provides a service class for interacting with Google Sheets API,
handling authentication, sheet operations, and error management.

Row indexing convention: the API exposes 0-based indices that exclude the
header row. Internal gspread calls use 1-based sheet coordinates. Always use
``_api_row_to_sheet_row`` / ``_sheet_row_to_api_row`` to convert — never
compute ``+2`` inline. See spec 0009.

Concurrency: ``gspread`` is synchronous and blocking. Every public method on
``GoogleSheetsService`` is ``async`` but delegates its body to a ``_*_sync``
counterpart via ``asyncio.to_thread`` so it does not block the event loop.
Never call gspread directly from an ``async def`` — always route through the
sync core. See spec 0001.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import gspread
from fastapi import HTTPException
from google.oauth2.credentials import Credentials

from app.config import settings
from app.models import SheetGetRowsOptions

# Configure logger for this module
logger = logging.getLogger(__name__)

# Row indexing: number of header rows at the top of every sheet we operate on.
HEADER_ROW_COUNT = 1


def _api_row_to_sheet_row(api_row_id: int) -> int:
    """Convert a 0-based API row index to a 1-based sheet row number."""
    return api_row_id + HEADER_ROW_COUNT + 1


def _sheet_row_to_api_row(sheet_row: int) -> int:
    """Convert a 1-based sheet row number to a 0-based API row index."""
    return sheet_row - HEADER_ROW_COUNT - 1


def _col_index_to_letter(col_index: int) -> str:
    """Convert a 1-based column index to an A1 column letter (1→A, 27→AA)."""
    if col_index < 1:
        raise ValueError(f"Column index must be >= 1, got {col_index}")
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


class GoogleSheetsAuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class GoogleSheetsNotFoundError(Exception):
    """Custom exception for resource not found errors."""
    pass


class GoogleSheetsService:
    """
    Service for interacting with Google Sheets API.

    Public methods are ``async`` thin wrappers; the real work happens in
    ``_*_sync`` methods that are invoked via ``asyncio.to_thread``.
    """

    def __init__(self) -> None:
        """Initialize the Google Sheets service."""
        logger.info("GoogleSheetsService initialized")

    # ------------------------------------------------------------------
    # Internal sync helpers (never ``await`` anything)
    # ------------------------------------------------------------------

    def _get_client(self, access_token: Optional[str] = None) -> gspread.Client:
        """Return an authenticated gspread client."""
        try:
            if access_token:
                logger.debug("Using OAuth2 access token for authentication")
                credentials = Credentials(token=access_token)
                return gspread.authorize(credentials)
            elif settings.GOOGLE_API_KEY:
                logger.debug("Using API key for authentication")
                return gspread.api_key(settings.GOOGLE_API_KEY)
            else:
                raise GoogleSheetsAuthError("No valid authentication method available")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Please check your credentials.",
            )

    def _get_safe_headers(self, worksheet) -> List[str]:
        """Return cleaned, deduplicated headers from row 1."""
        try:
            headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
            cleaned_headers: List[str] = []
            seen_headers: set = set()

            for i, header in enumerate(headers):
                clean_header = str(header).strip()

                if not clean_header:
                    clean_header = f"Column_{i + 1}"

                original_header = clean_header
                counter = 1
                while clean_header in seen_headers:
                    clean_header = f"{original_header}_{counter}"
                    counter += 1

                cleaned_headers.append(clean_header)
                seen_headers.add(clean_header)

            return cleaned_headers
        except Exception as e:
            logger.error(f"Error getting headers: {str(e)}")
            return []

    def _get_all_records_safe(self, worksheet) -> List[Dict[str, Any]]:
        """Return all rows as dicts, falling back to raw values on header errors."""
        try:
            return worksheet.get_all_records()
        except Exception as e:
            logger.warning(f"Standard get_all_records failed: {str(e)}")
            logger.info("Attempting to retrieve data with custom header handling")

            headers = self._get_safe_headers(worksheet)
            if not headers:
                logger.warning("No headers found, returning empty list")
                return []

            all_values = worksheet.get_all_values()
            if len(all_values) <= 1:
                logger.info("No data rows found")
                return []

            records: List[Dict[str, Any]] = []
            for row_values in all_values[1:]:
                record: Dict[str, Any] = {}
                for i, value in enumerate(row_values):
                    if i < len(headers):
                        record[headers[i]] = value
                    else:
                        record[f"Column_{i + 1}"] = value
                records.append(record)

            logger.info(
                f"Retrieved {len(records)} records via custom header handling"
            )
            return records

    def _apply_filters(
        self, records: List[Dict[str, Any]], filters: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Filter records by exact string match, AND across keys."""
        filtered_records: List[Dict[str, Any]] = []
        for record in records:
            match = True
            for key, value in filters.items():
                if str(record.get(key, "")) != str(value):
                    match = False
                    break
            if match:
                filtered_records.append(record)
        return filtered_records

    # ------------------------------------------------------------------
    # Sync cores for public operations
    # ------------------------------------------------------------------

    def _get_document_sync(self, document_id: str, access_token: Optional[str] = None):
        try:
            logger.info(f"Accessing document: {document_id}")
            client = self._get_client(access_token)
            document = client.open_by_key(document_id)
            logger.info(f"Successfully opened document: {document.title}")
            return document
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error accessing document {document_id}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot access Google document '{document_id}': {str(e)}",
            )

    def _get_sheet_sync(self, document, sheet_id: str):
        try:
            logger.debug(f"Looking for sheet: {sheet_id}")

            # Try numeric ID first
            try:
                sheet_id_int = int(sheet_id)
                worksheet = document.get_worksheet_by_id(sheet_id_int)
                logger.debug(f"Found sheet by ID: {worksheet.title}")
                return worksheet
            except (ValueError, gspread.exceptions.WorksheetNotFound):
                pass

            # Then by index
            try:
                sheet_index = int(sheet_id)
                worksheet = document.get_worksheet(sheet_index)
                logger.debug(f"Found sheet by index: {worksheet.title}")
                return worksheet
            except (ValueError, IndexError):
                pass

            # Finally by title
            worksheet = document.worksheet(sheet_id)
            logger.debug(f"Found sheet by title: {worksheet.title}")
            return worksheet
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Sheet not found '{sheet_id}': {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"Sheet '{sheet_id}' not found: {str(e)}",
            )

    def _get_sheet_rows_sync(
        self,
        worksheet,
        options: SheetGetRowsOptions,
    ) -> List[Dict[str, Any]]:
        try:
            logger.debug(
                f"Getting rows with offset={options.offset}, limit={options.limit}"
            )

            # Query filters require the full dataset in memory because the
            # Sheets API does not support server-side predicate filtering.
            if options.query:
                return self._get_sheet_rows_in_memory(worksheet, options)

            return self._get_sheet_rows_paginated(worksheet, options)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving sheet rows: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving sheet rows: {str(e)}",
            )

    def _get_sheet_rows_paginated(
        self,
        worksheet,
        options: SheetGetRowsOptions,
    ) -> List[Dict[str, Any]]:
        """
        Fast path: read only ``limit`` rows at ``offset`` via an A1 range.

        Two API calls total (headers + range) regardless of sheet size.
        """
        headers = self._get_safe_headers(worksheet)
        if not headers:
            return []

        sheet_start = _api_row_to_sheet_row(options.offset)
        sheet_end = sheet_start + options.limit - 1
        last_col = _col_index_to_letter(len(headers))
        range_a1 = f"A{sheet_start}:{last_col}{sheet_end}"

        raw_rows = worksheet.get(range_a1)

        records: List[Dict[str, Any]] = []
        for row_values in raw_rows:
            record: Dict[str, Any] = {}
            for i, value in enumerate(row_values):
                if i < len(headers):
                    record[headers[i]] = value
                else:
                    record[f"Column_{i + 1}"] = value
            records.append(record)

        logger.debug(
            f"Returning {len(records)} records via range {range_a1}"
        )
        return records

    def _get_sheet_rows_in_memory(
        self,
        worksheet,
        options: SheetGetRowsOptions,
    ) -> List[Dict[str, Any]]:
        """
        Slow path: materialize all rows, apply filters, then paginate.

        Used when ``options.query`` is set, because Sheets has no
        server-side filtering.
        """
        all_records = self._get_all_records_safe(worksheet)
        logger.debug(f"Retrieved {len(all_records)} total records")

        if options.query:
            all_records = self._apply_filters(all_records, options.query)
            logger.debug(f"Filtered to {len(all_records)} records")

        start_index = options.offset
        end_index = start_index + options.limit
        paginated_records = all_records[start_index:end_index]

        logger.debug(f"Returning {len(paginated_records)} records")
        return paginated_records

    def _get_sheet_info_sync(self, worksheet) -> Dict[str, Any]:
        try:
            logger.debug(f"Getting info for sheet: {worksheet.title}")

            sheet_info = {
                "sheetId": worksheet.id,
                "title": worksheet.title,
                "index": worksheet.index,
                "headerValues": self._get_safe_headers(worksheet),
                "rowCount": worksheet.row_count,
                "columnCount": worksheet.col_count,
                "sheetType": "GRID",
                "hidden": False,
                "rightToLeft": False,
            }

            logger.debug(f"Sheet info retrieved for: {worksheet.title}")
            return sheet_info
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting sheet info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting sheet info: {str(e)}",
            )

    def _get_row_sync(self, worksheet, row_id: int) -> Dict[str, Any]:
        try:
            logger.debug(f"Getting row {row_id} from {worksheet.title}")

            all_records = self._get_all_records_safe(worksheet)
            if row_id >= len(all_records) or row_id < 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found",
                )

            return all_records[row_id]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving row {row_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving row: {str(e)}",
            )

    def _update_row_sync(
        self, worksheet, row_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            logger.debug(f"Updating row {row_id} in {worksheet.title}")

            all_records = self._get_all_records_safe(worksheet)
            if row_id >= len(all_records) or row_id < 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found",
                )

            headers = self._get_safe_headers(worksheet)
            if not headers:
                raise HTTPException(
                    status_code=500,
                    detail="Sheet has no headers; cannot update row",
                )

            # Patch semantics: preserve fields not present in ``data``.
            current = all_records[row_id]
            merged = {**current, **data}
            new_values = [merged.get(h, "") for h in headers]

            sheet_row = _api_row_to_sheet_row(row_id)
            last_col = _col_index_to_letter(len(headers))
            range_a1 = f"A{sheet_row}:{last_col}{sheet_row}"

            # Single write call instead of N update_cell calls.
            worksheet.update(range_a1, [new_values])

            logger.info(f"Updated row {row_id} in {worksheet.title}")
            return merged
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating row {row_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error updating row: {str(e)}",
            )

    def _create_row_sync(self, worksheet, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.debug(f"Creating new row in {worksheet.title}")

            headers = self._get_safe_headers(worksheet)
            row_data = [data.get(header, "") for header in headers]

            # Single call; do not re-read the whole sheet afterwards.
            worksheet.append_row(row_data)
            logger.info(f"Created new row in {worksheet.title}")

            return dict(zip(headers, row_data))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating row: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating row: {str(e)}",
            )

    def _update_rows_bulk_sync(
        self,
        worksheet,
        start_row_id: int,
        data: List[Dict[str, Any]],
    ) -> int:
        try:
            logger.debug(
                f"Bulk updating {len(data)} rows starting from {start_row_id}"
            )

            if not data:
                return 0

            headers = self._get_safe_headers(worksheet)
            if not headers:
                raise HTTPException(
                    status_code=500,
                    detail="Sheet has no headers; cannot update rows",
                )

            sheet_start = _api_row_to_sheet_row(start_row_id)
            sheet_end = sheet_start + len(data) - 1
            last_col = _col_index_to_letter(len(headers))
            range_a1 = f"A{sheet_start}:{last_col}{sheet_end}"

            # Read existing rows once to preserve fields not in the patches.
            existing_rows = worksheet.get(range_a1)

            merged_rows: List[List[Any]] = []
            for i, patch in enumerate(data):
                raw = existing_rows[i] if i < len(existing_rows) else []
                current = {headers[j]: raw[j] for j in range(min(len(headers), len(raw)))}
                merged = {**current, **patch}
                merged_rows.append([merged.get(h, "") for h in headers])

            # Single batched write for the entire block.
            worksheet.update(range_a1, merged_rows)

            logger.info(f"Bulk updated {len(data)} rows in {worksheet.title}")
            return len(data)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating rows in bulk: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error updating rows in bulk: {str(e)}",
            )

    def _create_rows_bulk_sync(
        self,
        worksheet,
        data: List[Dict[str, Any]],
    ) -> int:
        try:
            logger.debug(f"Bulk creating {len(data)} rows")

            headers = self._get_safe_headers(worksheet)

            rows_data: List[List[Any]] = []
            for row_data in data:
                row = [row_data.get(header, "") for header in headers]
                rows_data.append(row)

            worksheet.append_rows(rows_data)

            logger.info(f"Bulk created {len(data)} rows in {worksheet.title}")
            return len(data)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating rows in bulk: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating rows in bulk: {str(e)}",
            )

    # ------------------------------------------------------------------
    # Public async surface (thread-offload shells)
    # ------------------------------------------------------------------

    async def get_document(
        self, document_id: str, access_token: Optional[str] = None
    ):
        return await asyncio.to_thread(
            self._get_document_sync, document_id, access_token
        )

    async def get_sheet(self, document, sheet_id: str):
        return await asyncio.to_thread(self._get_sheet_sync, document, sheet_id)

    async def get_sheet_rows(
        self,
        worksheet,
        options: Optional[SheetGetRowsOptions] = None,
    ) -> List[Dict[str, Any]]:
        opts = options or SheetGetRowsOptions()
        return await asyncio.to_thread(self._get_sheet_rows_sync, worksheet, opts)

    async def get_sheet_info(self, worksheet) -> Dict[str, Any]:
        return await asyncio.to_thread(self._get_sheet_info_sync, worksheet)

    async def get_row(self, worksheet, row_id: int) -> Dict[str, Any]:
        return await asyncio.to_thread(self._get_row_sync, worksheet, row_id)

    async def update_row(
        self, worksheet, row_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._update_row_sync, worksheet, row_id, data
        )

    async def create_row(self, worksheet, data: Dict[str, Any]) -> Dict[str, Any]:
        return await asyncio.to_thread(self._create_row_sync, worksheet, data)

    async def update_rows_bulk(
        self,
        worksheet,
        start_row_id: int,
        data: List[Dict[str, Any]],
    ) -> int:
        return await asyncio.to_thread(
            self._update_rows_bulk_sync, worksheet, start_row_id, data
        )

    async def create_rows_bulk(
        self,
        worksheet,
        data: List[Dict[str, Any]],
    ) -> int:
        return await asyncio.to_thread(
            self._create_rows_bulk_sync, worksheet, data
        )


# Global service instance. Prefer the ``get_sheets_service`` factory below
# (usable with ``fastapi.Depends``) so tests can override via
# ``app.dependency_overrides``. Direct imports of ``sheets_service`` are kept
# for backwards compatibility but should be avoided in new code.
sheets_service = GoogleSheetsService()


def get_sheets_service() -> GoogleSheetsService:
    """FastAPI dependency returning the process-wide ``GoogleSheetsService``."""
    return sheets_service
