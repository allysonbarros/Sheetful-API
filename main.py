from fastapi import FastAPI, HTTPException, Header, Query, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional, Union
import uvicorn
import logging

from models import SheetRow, SheetInfo, SheetGetRowsOptions
from sheets_service import sheets_service
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sheetful API",
    description="The easiest way to turn your Google Sheet into a RESTful API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Sheetful API - Turn your Google Sheet into a RESTful API"}

@app.get("/{document_id}/{sheet_id}", response_model=List[Dict[str, Any]])
async def get_rows(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    offset: int = Query(0, description="Number of rows to skip"),
    limit: int = Query(100, description="Maximum number of rows to return"),
    # Dynamic query parameters will be handled separately
) -> List[Dict[str, Any]]:
    """Get rows from a Google Sheet with optional filtering and pagination."""
    
    logger.info(f"GET /{document_id}/{sheet_id} - offset: {offset}, limit: {limit}")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Create options for getting rows
        options = SheetGetRowsOptions(offset=offset, limit=limit)
        
        # Get rows
        rows = await sheets_service.get_sheet_rows(worksheet, options)
        
        logger.info(f"Retrieved {len(rows)} rows from {document.title}/{worksheet.title}")
        
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rows: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/{document_id}/{sheet_id}/info", response_model=Dict[str, Any])
async def get_sheet_info(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """Get information about a Google Sheet."""
    
    logger.info(f"GET /{document_id}/{sheet_id}/info")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Get sheet info
        sheet_info = await sheets_service.get_sheet_info(worksheet)
        
        logger.info(f"Retrieved info for {document.title}/{worksheet.title}")
        
        return sheet_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sheet info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def get_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    row_id: int = Path(..., description="Row index (0-based)"),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """Get a specific row from a Google Sheet."""
    
    logger.info(f"GET /{document_id}/{sheet_id}/{row_id}")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Get row
        row = await sheets_service.get_row(worksheet, row_id)
        
        logger.info(f"Retrieved row {row_id} from {document.title}/{worksheet.title}")
        
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting row: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/{document_id}/{sheet_id}/{row_id}", response_model=Dict[str, Any])
async def update_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    row_id: int = Path(..., description="Row index (0-based)"),
    body: Dict[str, Any] = Body(...),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """Update a specific row in a Google Sheet."""
    
    logger.info(f"PUT /{document_id}/{sheet_id}/{row_id}")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Update row
        updated_row = await sheets_service.update_row(worksheet, row_id, body)
        
        logger.info(f"Updated row {row_id} in {document.title}/{worksheet.title}")
        
        return updated_row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating row: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/{document_id}/{sheet_id}/{row_id}/bulk")
async def update_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    row_id: int = Path(..., description="Starting row index (0-based)"),
    body: List[Dict[str, Any]] = Body(...),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
):
    """Update multiple rows in bulk in a Google Sheet."""
    
    logger.info(f"PUT /{document_id}/{sheet_id}/{row_id}/bulk - {len(body)} rows")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Update rows in bulk
        await sheets_service.update_rows_bulk(worksheet, row_id, body)
        
        logger.info(f"Updated {len(body)} rows starting from {row_id} in {document.title}/{worksheet.title}")
        
        return {"message": f"Successfully updated {len(body)} rows"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rows in bulk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/{document_id}/{sheet_id}", response_model=Dict[str, Any])
async def create_row(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    body: Dict[str, Any] = Body(...),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
) -> Dict[str, Any]:
    """Create a new row in a Google Sheet."""
    
    logger.info(f"POST /{document_id}/{sheet_id}")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Create row
        new_row = await sheets_service.create_row(worksheet, body)
        
        logger.info(f"Created new row in {document.title}/{worksheet.title}")
        
        return new_row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating row: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/{document_id}/{sheet_id}/bulk")
async def create_rows_bulk(
    document_id: str = Path(..., description="Google Spreadsheet document ID"),
    sheet_id: str = Path(..., description="Sheet ID or index"),
    body: List[Dict[str, Any]] = Body(...),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token")
):
    """Create multiple rows in bulk in a Google Sheet."""
    
    logger.info(f"POST /{document_id}/{sheet_id}/bulk - {len(body)} rows")
    
    try:
        # Get document and sheet
        document = await sheets_service.get_document(document_id, x_google_access_token)
        worksheet = await sheets_service.get_sheet(document, sheet_id)
        
        # Create rows in bulk
        await sheets_service.create_rows_bulk(worksheet, body)
        
        logger.info(f"Created {len(body)} rows in {document.title}/{worksheet.title}")
        
        return {"message": f"Successfully created {len(body)} rows"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating rows in bulk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=True,
        log_level="info"
    )
