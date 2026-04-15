"""Unit tests for Pydantic models in ``app.models``."""

import pytest
from pydantic import ValidationError

from app.models import SheetGetRowsOptions, SheetInfo


def test_sheet_get_rows_options_defaults() -> None:
    opts = SheetGetRowsOptions()
    assert opts.offset == 0
    assert opts.limit == 100
    assert opts.query is None


def test_sheet_get_rows_options_rejects_negative_offset() -> None:
    with pytest.raises(ValidationError):
        SheetGetRowsOptions(offset=-1)


def test_sheet_get_rows_options_rejects_limit_over_1000() -> None:
    with pytest.raises(ValidationError):
        SheetGetRowsOptions(limit=1001)


def test_sheet_get_rows_options_rejects_limit_zero() -> None:
    with pytest.raises(ValidationError):
        SheetGetRowsOptions(limit=0)


def test_sheet_info_serializes_with_camel_case_aliases() -> None:
    info = SheetInfo(
        sheetId=42,
        title="Sheet1",
        index=0,
        headerValues=["a", "b"],
        rowCount=10,
        columnCount=2,
        sheetType="GRID",
        hidden=False,
        rightToLeft=False,
    )
    dumped = info.model_dump(by_alias=True)
    assert dumped["sheetId"] == 42
    assert dumped["headerValues"] == ["a", "b"]
    assert dumped["rowCount"] == 10
    assert dumped["rightToLeft"] is False
