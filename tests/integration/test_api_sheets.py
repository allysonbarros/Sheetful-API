"""
Integration tests for the Sheets HTTP API using FastAPI's TestClient with
the ``GoogleSheetsService`` swapped via ``dependency_overrides``.
"""

from __future__ import annotations


def test_get_rows_returns_mocked_records(api_client) -> None:
    response = api_client.get("/test-doc-id/0")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["name"] == "Alice"


def test_get_sheet_info_returns_camel_case_keys(api_client) -> None:
    response = api_client.get("/test-doc-id/0/info")
    assert response.status_code == 200
    body = response.json()
    assert body["sheetId"] == 42
    assert body["headerValues"] == ["name", "email"]
    assert body["rowCount"] == 4


def test_get_row_valid_index(api_client) -> None:
    response = api_client.get("/test-doc-id/0/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Bob"


def test_get_row_out_of_range_returns_404(api_client) -> None:
    response = api_client.get("/test-doc-id/0/99")
    assert response.status_code == 404


def test_health_endpoint(api_client) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


def test_root_endpoint(api_client) -> None:
    response = api_client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "Sheetful API" in body["message"]
