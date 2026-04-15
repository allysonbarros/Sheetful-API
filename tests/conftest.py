"""
Shared pytest fixtures for the Sheetful API test suite.

These fixtures build mock worksheets/documents that mirror the gspread
surface area used by ``GoogleSheetsService``, without ever touching the
real Google Sheets API. See ``specs/0002-fix-tooling-and-test-suite.md``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

# Ensure Settings.validate_config() passes during module imports in tests.
os.environ.setdefault("GOOGLE_API_KEY", "test-key")


@pytest.fixture
def mock_worksheet() -> MagicMock:
    """
    A MagicMock configured like a gspread Worksheet with sensible defaults.

    The default sheet has 3 data rows and headers ``name``, ``email``.
    Override attributes per-test as needed.
    """
    ws = MagicMock(name="Worksheet")
    ws.id = 42
    ws.title = "Sheet1"
    ws.index = 0
    ws.row_count = 4
    ws.col_count = 2

    ws.row_values.return_value = ["name", "email"]
    default_records: List[Dict[str, Any]] = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob", "email": "bob@example.com"},
        {"name": "Carol", "email": "carol@example.com"},
    ]
    ws.get_all_records.return_value = default_records
    ws.get_all_values.return_value = [
        ["name", "email"],
        ["Alice", "alice@example.com"],
        ["Bob", "bob@example.com"],
        ["Carol", "carol@example.com"],
    ]
    return ws


@pytest.fixture
def mock_document(mock_worksheet: MagicMock) -> MagicMock:
    """A MagicMock configured like a gspread Spreadsheet."""
    doc = MagicMock(name="Spreadsheet")
    doc.title = "Test Document"
    doc.get_worksheet_by_id.return_value = mock_worksheet
    doc.get_worksheet.return_value = mock_worksheet
    doc.worksheet.return_value = mock_worksheet
    return doc


@pytest.fixture
def mock_service(mock_document: MagicMock, mock_worksheet: MagicMock) -> MagicMock:
    """
    A fully mocked ``GoogleSheetsService`` with async methods pre-wired so
    handlers can be tested without touching the real service.
    """
    from app.services.sheets import GoogleSheetsService

    svc = MagicMock(spec=GoogleSheetsService)

    async def get_document(document_id, access_token=None):
        return mock_document

    async def get_sheet(document, sheet_id):
        return mock_worksheet

    async def get_sheet_rows(worksheet, options):
        return mock_worksheet.get_all_records.return_value

    async def get_sheet_info(worksheet):
        return {
            "sheetId": worksheet.id,
            "title": worksheet.title,
            "index": worksheet.index,
            "headerValues": ["name", "email"],
            "rowCount": worksheet.row_count,
            "columnCount": worksheet.col_count,
            "sheetType": "GRID",
            "hidden": False,
            "rightToLeft": False,
        }

    async def get_row(worksheet, row_id):
        records = mock_worksheet.get_all_records.return_value
        if row_id < 0 or row_id >= len(records):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
        return records[row_id]

    svc.get_document.side_effect = get_document
    svc.get_sheet.side_effect = get_sheet
    svc.get_sheet_rows.side_effect = get_sheet_rows
    svc.get_sheet_info.side_effect = get_sheet_info
    svc.get_row.side_effect = get_row
    return svc


@pytest.fixture
def api_client(mock_service: MagicMock):
    """
    FastAPI TestClient with ``get_sheets_service`` overridden to return
    ``mock_service``. Overrides are cleared on teardown.
    """
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.sheets import get_sheets_service

    app.dependency_overrides[get_sheets_service] = lambda: mock_service
    try:
        # raise_server_exceptions=False lets us assert on the error handler
        # response for uncaught exceptions (spec 0005).
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()
