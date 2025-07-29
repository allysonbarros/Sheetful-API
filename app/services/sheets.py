"""
Google Sheets service module.

This module provides a service class for interacting with Google Sheets API,
handling authentication, sheet operations, and error management.
"""

import logging
from typing import Any, Dict, List, Optional

import gspread
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from app.config import settings
from app.models import SheetGetRowsOptions

# Configure logger for this module
logger = logging.getLogger(__name__)


class GoogleSheetsAuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class GoogleSheetsNotFoundError(Exception):
    """Custom exception for resource not found errors."""
    pass


class GoogleSheetsService:
    """
    Service for interacting with Google Sheets API.
    
    This service handles all Google Sheets operations including:
    - Authentication (OAuth2 tokens and API keys)
    - Document and worksheet access
    - CRUD operations on sheet data
    - Bulk operations for efficiency
    
    Example:
        service = GoogleSheetsService()
        document = await service.get_document("document_id", "access_token")
        rows = await service.get_sheet_rows(worksheet, options)
    """
    
    def __init__(self):
        """Initialize the Google Sheets service."""
        self.gc = None
        logger.info("GoogleSheetsService initialized")
    
    def _get_client(self, access_token: Optional[str] = None) -> gspread.Client:
        """
        Get authenticated Google Sheets client.
        
        Args:
            access_token: OAuth2 access token (optional)
            
        Returns:
            Authenticated gspread client
            
        Raises:
            GoogleSheetsAuthError: If authentication fails
            HTTPException: If no valid authentication method is available
        """
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
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Please check your credentials."
            )
    
    async def get_document(self, document_id: str, access_token: Optional[str] = None):
        """
        Get Google Spreadsheet document.
        
        Args:
            document_id: Google Spreadsheet document ID
            access_token: OAuth2 access token (optional)
            
        Returns:
            Google Spreadsheet document object
            
        Raises:
            HTTPException: If document cannot be accessed
        """
        try:
            logger.info(f"Accessing document: {document_id}")
            client = self._get_client(access_token)
            document = client.open_by_key(document_id)
            logger.info(f"Successfully opened document: {document.title}")
            return document
            
        except Exception as e:
            logger.error(f"Error accessing document {document_id}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot access Google document '{document_id}': {str(e)}"
            )
    
    async def get_sheet(self, document, sheet_id: str):
        """
        Get specific worksheet from document.
        
        Tries multiple methods to find the sheet:
        1. By numeric ID
        2. By index
        3. By title/name
        
        Args:
            document: Google Spreadsheet document
            sheet_id: Sheet identifier (ID, index, or title)
            
        Returns:
            Worksheet object
            
        Raises:
            HTTPException: If sheet is not found
        """
        try:
            logger.debug(f"Looking for sheet: {sheet_id}")
            
            # Try to get sheet by numeric ID first
            try:
                sheet_id_int = int(sheet_id)
                worksheet = document.get_worksheet_by_id(sheet_id_int)
                logger.debug(f"Found sheet by ID: {worksheet.title}")
                return worksheet
            except (ValueError, gspread.exceptions.WorksheetNotFound):
                pass
            
            # Try to get sheet by index
            try:
                sheet_index = int(sheet_id)
                worksheet = document.get_worksheet(sheet_index)
                logger.debug(f"Found sheet by index: {worksheet.title}")
                return worksheet
            except (ValueError, IndexError):
                pass
            
            # Try to get sheet by title
            worksheet = document.worksheet(sheet_id)
            logger.debug(f"Found sheet by title: {worksheet.title}")
            return worksheet
            
        except Exception as e:
            logger.error(f"Sheet not found '{sheet_id}': {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"Sheet '{sheet_id}' not found: {str(e)}"
            )
    
    async def get_sheet_rows(
        self, 
        worksheet, 
        options: Optional[SheetGetRowsOptions] = None
    ) -> List[Dict[str, Any]]:
        """
        Get rows from worksheet with filtering and pagination.
        
        Args:
            worksheet: Google Sheets worksheet object
            options: Options for filtering and pagination
            
        Returns:
            List of row dictionaries
            
        Raises:
            HTTPException: If rows cannot be retrieved
        """
        if options is None:
            options = SheetGetRowsOptions()
        
        try:
            logger.debug(f"Getting rows with offset={options.offset}, limit={options.limit}")
            
            # Get all records as dictionaries
            all_records = worksheet.get_all_records()
            logger.debug(f"Retrieved {len(all_records)} total records")
            
            # Apply query filters if provided
            if options.query:
                filtered_records = self._apply_filters(all_records, options.query)
                logger.debug(f"Filtered to {len(filtered_records)} records")
                all_records = filtered_records
            
            # Apply pagination
            start_index = options.offset
            end_index = start_index + options.limit
            paginated_records = all_records[start_index:end_index]
            
            logger.debug(f"Returning {len(paginated_records)} records")
            return paginated_records
            
        except Exception as e:
            logger.error(f"Error retrieving sheet rows: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving sheet rows: {str(e)}"
            )
    
    def _apply_filters(self, records: List[Dict[str, Any]], filters: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Apply query filters to records.
        
        Args:
            records: List of record dictionaries
            filters: Dictionary of field filters
            
        Returns:
            Filtered list of records
        """
        filtered_records = []
        
        for record in records:
            match = True
            for key, value in filters.items():
                if str(record.get(key, "")) != str(value):
                    match = False
                    break
            if match:
                filtered_records.append(record)
                
        return filtered_records
    
    async def get_sheet_info(self, worksheet) -> Dict[str, Any]:
        """
        Get comprehensive information about a worksheet.
        
        Args:
            worksheet: Google Sheets worksheet object
            
        Returns:
            Dictionary containing sheet metadata
            
        Raises:
            HTTPException: If sheet info cannot be retrieved
        """
        try:
            logger.debug(f"Getting info for sheet: {worksheet.title}")
            
            sheet_info = {
                "sheetId": worksheet.id,
                "title": worksheet.title,
                "index": worksheet.index,
                "headerValues": worksheet.row_values(1) if worksheet.row_count > 0 else [],
                "rowCount": worksheet.row_count,
                "columnCount": worksheet.col_count,
                "sheetType": "GRID",
                "hidden": False,
                "rightToLeft": False
            }
            
            logger.debug(f"Sheet info retrieved for: {worksheet.title}")
            return sheet_info
            
        except Exception as e:
            logger.error(f"Error getting sheet info: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting sheet info: {str(e)}"
            )
    
    async def get_row(self, worksheet, row_id: int) -> Dict[str, Any]:
        """
        Get a specific row from worksheet.
        
        Args:
            worksheet: Google Sheets worksheet object
            row_id: Zero-based row index
            
        Returns:
            Row data as dictionary
            
        Raises:
            HTTPException: If row is not found or cannot be retrieved
        """
        try:
            logger.debug(f"Getting row {row_id} from {worksheet.title}")
            
            all_records = worksheet.get_all_records()
            if row_id >= len(all_records) or row_id < 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found"
                )
            
            return all_records[row_id]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving row {row_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving row: {str(e)}"
            )
    
    async def update_row(self, worksheet, row_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a specific row in worksheet.
        
        Args:
            worksheet: Google Sheets worksheet object
            row_id: Zero-based row index
            data: New data for the row
            
        Returns:
            Updated row data
            
        Raises:
            HTTPException: If row cannot be updated
        """
        try:
            logger.debug(f"Updating row {row_id} in {worksheet.title}")
            
            # Verify row exists first
            all_records = worksheet.get_all_records()
            if row_id >= len(all_records) or row_id < 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found"
                )
            
            # Calculate actual row number (1-indexed, +1 for header)
            actual_row_number = row_id + 2
            headers = worksheet.row_values(1)
            
            # Update each cell in the row
            for i, header in enumerate(headers):
                if header in data:
                    worksheet.update_cell(actual_row_number, i + 1, data[header])
            
            logger.info(f"Updated row {row_id} in {worksheet.title}")
            
            # Return updated row
            return await self.get_row(worksheet, row_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating row {row_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error updating row: {str(e)}"
            )
    
    async def create_row(self, worksheet, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new row in worksheet.
        
        Args:
            worksheet: Google Sheets worksheet object
            data: Data for the new row
            
        Returns:
            Created row data
            
        Raises:
            HTTPException: If row cannot be created
        """
        try:
            logger.debug(f"Creating new row in {worksheet.title}")
            
            headers = worksheet.row_values(1)
            
            # Prepare row data in the correct column order
            row_data = [data.get(header, "") for header in headers]
            
            # Append the row
            worksheet.append_row(row_data)
            
            logger.info(f"Created new row in {worksheet.title}")
            
            # Return the created row (get the last row)
            all_records = worksheet.get_all_records()
            return all_records[-1] if all_records else {}
            
        except Exception as e:
            logger.error(f"Error creating row: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating row: {str(e)}"
            )
    
    async def update_rows_bulk(self, worksheet, start_row_id: int, data: List[Dict[str, Any]]) -> int:
        """
        Update multiple rows in bulk.
        
        Args:
            worksheet: Google Sheets worksheet object
            start_row_id: Starting row index (zero-based)
            data: List of row data dictionaries
            
        Returns:
            Number of rows updated
            
        Raises:
            HTTPException: If bulk update fails
        """
        try:
            logger.debug(f"Bulk updating {len(data)} rows starting from {start_row_id}")
            
            headers = worksheet.row_values(1)
            
            for i, row_data in enumerate(data):
                actual_row_number = start_row_id + i + 2  # +1 for 1-indexing, +1 for header
                
                # Update each cell in the row
                for j, header in enumerate(headers):
                    if header in row_data:
                        worksheet.update_cell(actual_row_number, j + 1, row_data[header])
            
            logger.info(f"Bulk updated {len(data)} rows in {worksheet.title}")
            return len(data)
            
        except Exception as e:
            logger.error(f"Error updating rows in bulk: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error updating rows in bulk: {str(e)}"
            )
    
    async def create_rows_bulk(self, worksheet, data: List[Dict[str, Any]]) -> int:
        """
        Create multiple rows in bulk.
        
        Args:
            worksheet: Google Sheets worksheet object
            data: List of row data dictionaries
            
        Returns:
            Number of rows created
            
        Raises:
            HTTPException: If bulk creation fails
        """
        try:
            logger.debug(f"Bulk creating {len(data)} rows")
            
            headers = worksheet.row_values(1)
            
            # Prepare all rows data in correct column order
            rows_data = []
            for row_data in data:
                row = [row_data.get(header, "") for header in headers]
                rows_data.append(row)
            
            # Append all rows at once
            worksheet.append_rows(rows_data)
            
            logger.info(f"Bulk created {len(data)} rows in {worksheet.title}")
            return len(data)
            
        except Exception as e:
            logger.error(f"Error creating rows in bulk: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating rows in bulk: {str(e)}"
            )


# Global service instance
sheets_service = GoogleSheetsService()
