import gspread
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from typing import Dict, Any, List, Optional, Union
import json
from fastapi import HTTPException

from models import SheetRow, SheetGetRowsOptions
import config


class GoogleSheetsService:
    """Service for interacting with Google Sheets API."""
    
    def __init__(self):
        self.gc = None
    
    def _get_client(self, access_token: Optional[str] = None) -> gspread.Client:
        """Get authenticated Google Sheets client."""
        if access_token:
            # Use OAuth2 access token
            credentials = Credentials(token=access_token)
            return gspread.authorize(credentials)
        elif config.GOOGLE_API_KEY:
            # Use API key (read-only access)
            return gspread.api_key(config.GOOGLE_API_KEY)
        else:
            raise HTTPException(
                status_code=401,
                detail="Missing required oauth access token or API key"
            )
    
    async def get_document(self, document_id: str, access_token: Optional[str] = None):
        """Get Google Spreadsheet document."""
        try:
            client = self._get_client(access_token)
            return client.open_by_key(document_id)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error loading Google document \"{document_id}\": {str(e)}"
            )
    
    async def get_sheet(self, document, sheet_id: str):
        """Get specific worksheet from document."""
        try:
            # Try to get sheet by ID first
            try:
                sheet_id_int = int(sheet_id)
                worksheet = document.get_worksheet_by_id(sheet_id_int)
            except (ValueError, gspread.exceptions.WorksheetNotFound):
                # If not found by ID, try by index
                try:
                    sheet_index = int(sheet_id)
                    worksheet = document.get_worksheet(sheet_index)
                except (ValueError, IndexError):
                    # If not found by index, try by title
                    worksheet = document.worksheet(sheet_id)
            
            return worksheet
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Sheet not found \"{sheet_id}\": {str(e)}"
            )
    
    async def get_sheet_rows(
        self, 
        worksheet, 
        options: SheetGetRowsOptions = None
    ) -> List[Dict[str, Any]]:
        """Get rows from worksheet with filtering and pagination."""
        if options is None:
            options = SheetGetRowsOptions()
        
        try:
            # Get all records as dictionaries
            all_records = worksheet.get_all_records()
            
            # Apply query filters
            if options.query:
                filtered_records = []
                for record in all_records:
                    match = True
                    for key, value in options.query.items():
                        if str(record.get(key, "")) != str(value):
                            match = False
                            break
                    if match:
                        filtered_records.append(record)
                all_records = filtered_records
            
            # Apply pagination
            start_index = options.offset
            end_index = start_index + options.limit
            
            return all_records[start_index:end_index]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving sheet rows: {str(e)}"
            )
    
    async def get_sheet_info(self, worksheet) -> Dict[str, Any]:
        """Get information about a worksheet."""
        try:
            # Get basic worksheet properties
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
            
            return sheet_info
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting sheet info: {str(e)}"
            )
    
    async def get_row(self, worksheet, row_id: int) -> Dict[str, Any]:
        """Get a specific row from worksheet."""
        try:
            all_records = worksheet.get_all_records()
            if row_id >= len(all_records):
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found"
                )
            
            return all_records[row_id]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving row: {str(e)}"
            )
    
    async def update_row(self, worksheet, row_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific row in worksheet."""
        try:
            # Get all records to find the actual row number
            all_records = worksheet.get_all_records()
            if row_id >= len(all_records):
                raise HTTPException(
                    status_code=404,
                    detail=f"Row {row_id} not found"
                )
            
            # Row number is 1-indexed and we need to account for header row
            actual_row_number = row_id + 2  # +1 for 1-indexing, +1 for header
            
            # Get headers
            headers = worksheet.row_values(1)
            
            # Update each cell in the row
            for i, header in enumerate(headers):
                if header in data:
                    worksheet.update_cell(actual_row_number, i + 1, data[header])
            
            # Return updated row
            return await self.get_row(worksheet, row_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error updating row: {str(e)}"
            )
    
    async def create_row(self, worksheet, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new row in worksheet."""
        try:
            # Get headers
            headers = worksheet.row_values(1)
            
            # Prepare row data in the correct order
            row_data = []
            for header in headers:
                row_data.append(data.get(header, ""))
            
            # Append the row
            worksheet.append_row(row_data)
            
            # Return the created row (get the last row)
            all_records = worksheet.get_all_records()
            return all_records[-1]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating row: {str(e)}"
            )
    
    async def update_rows_bulk(self, worksheet, start_row_id: int, data: List[Dict[str, Any]]):
        """Update multiple rows in bulk."""
        try:
            headers = worksheet.row_values(1)
            
            for i, row_data in enumerate(data):
                actual_row_number = start_row_id + i + 2  # +1 for 1-indexing, +1 for header
                
                # Update each cell in the row
                for j, header in enumerate(headers):
                    if header in row_data:
                        worksheet.update_cell(actual_row_number, j + 1, row_data[header])
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error updating rows in bulk: {str(e)}"
            )
    
    async def create_rows_bulk(self, worksheet, data: List[Dict[str, Any]]):
        """Create multiple rows in bulk."""
        try:
            headers = worksheet.row_values(1)
            
            # Prepare all rows data
            rows_data = []
            for row_data in data:
                row = []
                for header in headers:
                    row.append(row_data.get(header, ""))
                rows_data.append(row)
            
            # Append all rows at once
            worksheet.append_rows(rows_data)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating rows in bulk: {str(e)}"
            )


# Global service instance
sheets_service = GoogleSheetsService()
