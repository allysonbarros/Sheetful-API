"""
Unit tests for ``GoogleSheetsService`` — mock gspread, never hit the network.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.sheets import (
    GoogleSheetsService,
    _api_row_to_sheet_row,
    _col_index_to_letter,
    _sheet_row_to_api_row,
)

# ``gspread`` is already imported by the app code under test, so this is a
# cheap alias — but we avoid a direct ``import gspread`` in test modules so
# any collection-time import error caused by broken transitive bindings
# surfaces only when the app module is actually loaded.
from app.services import sheets as _sheets_module  # noqa: E402

gspread = _sheets_module.gspread  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helper unit tests (spec 0009)
# ---------------------------------------------------------------------------


def test_api_row_to_sheet_row_adds_two_for_header_and_one_indexing() -> None:
    assert _api_row_to_sheet_row(0) == 2
    assert _api_row_to_sheet_row(5) == 7


def test_sheet_row_round_trips() -> None:
    for api in (0, 1, 99):
        assert _sheet_row_to_api_row(_api_row_to_sheet_row(api)) == api


@pytest.mark.parametrize(
    "col_index, expected",
    [
        (1, "A"),
        (2, "B"),
        (26, "Z"),
        (27, "AA"),
        (28, "AB"),
        (52, "AZ"),
        (53, "BA"),
        (702, "ZZ"),
        (703, "AAA"),
    ],
)
def test_col_index_to_letter(col_index: int, expected: str) -> None:
    assert _col_index_to_letter(col_index) == expected


def test_col_index_to_letter_rejects_zero() -> None:
    with pytest.raises(ValueError):
        _col_index_to_letter(0)


# ---------------------------------------------------------------------------
# Header handling
# ---------------------------------------------------------------------------


def test_get_safe_headers_dedupes_and_fills_blanks(mock_worksheet) -> None:
    mock_worksheet.row_values.return_value = ["id", "", "name", "name"]
    svc = GoogleSheetsService()
    headers = svc._get_safe_headers(mock_worksheet)
    assert headers == ["id", "Column_2", "name", "name_1"]


def test_get_safe_headers_returns_empty_list_on_error(mock_worksheet) -> None:
    mock_worksheet.row_values.side_effect = RuntimeError("boom")
    svc = GoogleSheetsService()
    assert svc._get_safe_headers(mock_worksheet) == []


def test_get_all_records_safe_falls_back_when_get_all_records_throws(
    mock_worksheet,
) -> None:
    mock_worksheet.get_all_records.side_effect = gspread.exceptions.GSpreadException(
        "dup"
    )
    mock_worksheet.row_values.return_value = ["", "name"]
    mock_worksheet.get_all_values.return_value = [
        ["", "name"],
        ["1", "Alice"],
    ]
    svc = GoogleSheetsService()
    records = svc._get_all_records_safe(mock_worksheet)
    assert records == [{"Column_1": "1", "name": "Alice"}]


# ---------------------------------------------------------------------------
# Sheet resolution (get_sheet)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_sheet_resolves_by_numeric_id_first(mock_document, mock_worksheet) -> None:
    svc = GoogleSheetsService()
    result = await svc.get_sheet(mock_document, "42")
    mock_document.get_worksheet_by_id.assert_called_once_with(42)
    assert result is mock_worksheet


@pytest.mark.asyncio
async def test_get_sheet_falls_back_to_index(mock_document, mock_worksheet) -> None:
    mock_document.get_worksheet_by_id.side_effect = (
        gspread.exceptions.WorksheetNotFound("nope")
    )
    svc = GoogleSheetsService()
    result = await svc.get_sheet(mock_document, "0")
    mock_document.get_worksheet.assert_called_once_with(0)
    assert result is mock_worksheet


@pytest.mark.asyncio
async def test_get_sheet_falls_back_to_title(mock_document, mock_worksheet) -> None:
    svc = GoogleSheetsService()
    result = await svc.get_sheet(mock_document, "Customers")
    mock_document.worksheet.assert_called_once_with("Customers")
    assert result is mock_worksheet


@pytest.mark.asyncio
async def test_get_sheet_not_found_becomes_http_404(mock_document) -> None:
    mock_document.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("no")
    svc = GoogleSheetsService()
    with pytest.raises(HTTPException) as exc:
        await svc.get_sheet(mock_document, "MissingSheet")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Row operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_row_out_of_range_raises_404(mock_worksheet) -> None:
    svc = GoogleSheetsService()
    with pytest.raises(HTTPException) as exc:
        await svc.get_row(mock_worksheet, 999)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_row_writes_single_range_at_sheet_row_two(mock_worksheet) -> None:
    svc = GoogleSheetsService()
    result = await svc.update_row(mock_worksheet, 0, {"name": "Renamed"})

    # One batched write, not N update_cell calls.
    mock_worksheet.update.assert_called_once_with(
        "A2:B2", [["Renamed", "alice@example.com"]]
    )
    mock_worksheet.update_cell.assert_not_called()
    # Patch semantics: unspecified columns preserved.
    assert result == {"name": "Renamed", "email": "alice@example.com"}


@pytest.mark.asyncio
async def test_update_row_preserves_columns_not_in_patch(mock_worksheet) -> None:
    svc = GoogleSheetsService()
    result = await svc.update_row(mock_worksheet, 1, {"email": "new@example.com"})

    mock_worksheet.update.assert_called_once_with(
        "A3:B3", [["Bob", "new@example.com"]]
    )
    assert result["name"] == "Bob"


@pytest.mark.asyncio
async def test_update_rows_bulk_issues_two_calls_regardless_of_size(
    mock_worksheet,
) -> None:
    mock_worksheet.get_all_records.return_value = [
        {"name": f"u{i}", "email": f"u{i}@x.com"} for i in range(10)
    ]
    mock_worksheet.get.return_value = [
        ["u0", "u0@x.com"],
        ["u1", "u1@x.com"],
        ["u2", "u2@x.com"],
    ]
    svc = GoogleSheetsService()
    n = await svc.update_rows_bulk(
        mock_worksheet,
        start_row_id=0,
        data=[
            {"name": "A"},
            {"email": "b@x.com"},
            {"name": "C", "email": "c@x.com"},
        ],
    )
    assert n == 3
    # Exactly one read + one write, regardless of N × M.
    mock_worksheet.get.assert_called_once_with("A2:B4")
    mock_worksheet.update.assert_called_once_with(
        "A2:B4",
        [
            ["A", "u0@x.com"],   # name patched, email preserved
            ["u1", "b@x.com"],   # email patched, name preserved
            ["C", "c@x.com"],    # both patched
        ],
    )
    mock_worksheet.update_cell.assert_not_called()


@pytest.mark.asyncio
async def test_create_row_does_not_reread_sheet(mock_worksheet) -> None:
    svc = GoogleSheetsService()
    mock_worksheet.get_all_records.reset_mock()
    result = await svc.create_row(mock_worksheet, {"name": "Dave", "email": "d@x.com"})

    mock_worksheet.append_row.assert_called_once_with(["Dave", "d@x.com"])
    # Must not trigger another full read-back after the insert.
    mock_worksheet.get_all_records.assert_not_called()
    assert result == {"name": "Dave", "email": "d@x.com"}


# ---------------------------------------------------------------------------
# Pagination (in-memory fallback path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_sheet_rows_fast_path_reads_only_requested_range(
    mock_worksheet,
) -> None:
    from app.models import SheetGetRowsOptions

    mock_worksheet.row_values.return_value = ["name", "email"]
    mock_worksheet.get.return_value = [
        ["u3", "u3@x.com"],
        ["u4", "u4@x.com"],
    ]
    svc = GoogleSheetsService()
    rows = await svc.get_sheet_rows(
        mock_worksheet, SheetGetRowsOptions(offset=3, limit=2)
    )
    # Fast path: one read of the exact range A5:B6, no get_all_records.
    mock_worksheet.get.assert_called_once_with("A5:B6")
    mock_worksheet.get_all_records.assert_not_called()
    assert [r["name"] for r in rows] == ["u3", "u4"]


@pytest.mark.asyncio
async def test_get_sheet_rows_fast_path_offset_zero(mock_worksheet) -> None:
    from app.models import SheetGetRowsOptions

    mock_worksheet.row_values.return_value = ["a", "b", "c"]  # 3 cols → col C
    mock_worksheet.get.return_value = [["1", "2", "3"]]
    svc = GoogleSheetsService()
    await svc.get_sheet_rows(
        mock_worksheet, SheetGetRowsOptions(offset=0, limit=100)
    )
    mock_worksheet.get.assert_called_once_with("A2:C101")


@pytest.mark.asyncio
async def test_get_sheet_rows_query_filter_uses_in_memory_fallback(
    mock_worksheet,
) -> None:
    from app.models import SheetGetRowsOptions

    mock_worksheet.get_all_records.return_value = [
        {"name": "a", "role": "x"},
        {"name": "b", "role": "y"},
        {"name": "c", "role": "x"},
    ]
    svc = GoogleSheetsService()
    rows = await svc.get_sheet_rows(
        mock_worksheet, SheetGetRowsOptions(query={"role": "x"})
    )
    # Slow path is used: get_all_records called, worksheet.get is not.
    mock_worksheet.get_all_records.assert_called_once()
    mock_worksheet.get.assert_not_called()
    assert [r["name"] for r in rows] == ["a", "c"]
