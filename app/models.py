"""
Pydantic models for the Sheetful API.

This module contains all data models used for request/response validation,
serialization, and documentation in the API.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class SheetRow(BaseModel):
    """
    Represents a row in a Google Sheet.
    
    This is a flexible model that can accommodate any field names
    since Google Sheets can have arbitrary column headers.
    
    Example:
        {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }
    """
    model_config = {"extra": "allow"}
    
    def __init__(self, **data):
        super().__init__(**data)
        
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Export model data as dictionary."""
        return super().model_dump(**kwargs)


class SheetInfo(BaseModel):
    """
    Information about a Google Sheet.
    
    Contains metadata about the sheet including dimensions,
    headers, and configuration.
    """
    sheet_id: Union[str, int] = Field(
        ..., 
        alias="sheetId",
        description="Unique identifier for the sheet"
    )
    title: str = Field(..., description="Sheet title/name")
    index: int = Field(..., description="Sheet index in the spreadsheet")
    header_values: List[str] = Field(
        ..., 
        alias="headerValues",
        description="Column headers from the first row"
    )
    row_count: int = Field(..., alias="rowCount", description="Total number of rows")
    column_count: int = Field(..., alias="columnCount", description="Total number of columns")
    sheet_type: str = Field(
        ..., 
        alias="sheetType",
        description="Type of sheet (usually 'GRID')"
    )
    hidden: bool = Field(False, description="Whether the sheet is hidden")
    right_to_left: bool = Field(
        False, 
        alias="rightToLeft",
        description="Whether the sheet is right-to-left"
    )


class SheetGetRowsOptions(BaseModel):
    """
    Options for filtering and paginating sheet rows.
    
    Used to control which rows are returned when querying a sheet.
    """
    offset: int = Field(
        0, 
        ge=0,
        description="Number of rows to skip from the beginning"
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of rows to return"
    )
    query: Optional[Dict[str, str]] = Field(
        None,
        description="Key-value pairs for filtering rows"
    )
    
    @validator('limit')
    def validate_limit(cls, v):
        """Ensure limit is within reasonable bounds."""
        if v > 1000:
            raise ValueError('Limit cannot exceed 1000 rows')
        return v


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    
    Used consistently across all API endpoints for error reporting.
    """
    message: str = Field(..., description="Human-readable error message")
    status: int = Field(..., description="HTTP status code")
    detail: Optional[str] = Field(None, description="Additional error details")


class BulkOperationResponse(BaseModel):
    """
    Response for bulk operations.
    
    Used when creating or updating multiple rows at once.
    """
    message: str = Field(..., description="Operation result message")
    affected_rows: int = Field(..., description="Number of rows affected")
    success: bool = Field(True, description="Whether operation was successful")


class HealthCheckResponse(BaseModel):
    """
    Health check response model.
    
    Used for monitoring and health checks.
    """
    status: str = Field("healthy", description="Service status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
