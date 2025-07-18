from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class SheetRow(BaseModel):
    """
    Represents a row in a Google Sheet.
    This is a flexible model that can accommodate any field names.
    """
    model_config = {"extra": "allow"}
    
    def __init__(self, **data):
        super().__init__(**data)
        
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

class SheetInfo(BaseModel):
    """Information about a Google Sheet."""
    sheet_id: Union[str, int] = Field(..., alias="sheetId")
    title: str
    index: int
    header_values: List[str] = Field(..., alias="headerValues")
    row_count: int = Field(..., alias="rowCount")
    column_count: int = Field(..., alias="columnCount")
    sheet_type: str = Field(..., alias="sheetType")
    hidden: bool = False
    right_to_left: bool = Field(False, alias="rightToLeft")

class SheetGetRowsOptions(BaseModel):
    """Options for getting rows from a sheet."""
    offset: int = 0
    limit: int = 100
    query: Optional[Dict[str, str]] = None

class ErrorResponse(BaseModel):
    """Standard error response."""
    message: str
    status: int
