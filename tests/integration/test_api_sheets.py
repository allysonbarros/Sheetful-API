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


def test_unhandled_exception_is_redacted(api_client, mock_service) -> None:
    secret = "SECRET_TOKEN_DO_NOT_LEAK"

    async def boom(*args, **kwargs):
        raise RuntimeError(secret)

    mock_service.get_sheet_rows.side_effect = boom

    response = api_client.get("/some-doc/0")
    assert response.status_code == 500
    body = response.json()
    assert body["message"] == "Internal server error"
    assert secret not in response.text
    # An error_id is returned for log correlation.
    assert "error_id" in body


def test_get_rows_without_filter_leaves_query_none(api_client, mock_service) -> None:
    api_client.get("/doc/0")
    assert mock_service.last_options.query is None


def test_get_rows_with_single_filter(api_client, mock_service) -> None:
    response = api_client.get("/doc/0?filter[name]=Bob")
    assert response.status_code == 200
    assert mock_service.last_options.query == {"name": "Bob"}
    assert [r["name"] for r in response.json()] == ["Bob"]


def test_get_rows_with_multiple_filters_is_anded(api_client, mock_service, mock_worksheet) -> None:
    mock_worksheet.get_all_records.return_value = [
        {"name": "Alice", "role": "x"},
        {"name": "Bob", "role": "y"},
        {"name": "Carol", "role": "x"},
    ]
    response = api_client.get("/doc/0?filter[role]=x&filter[name]=Alice")
    assert response.status_code == 200
    assert mock_service.last_options.query == {"role": "x", "name": "Alice"}
    assert [r["name"] for r in response.json()] == ["Alice"]


def test_get_rows_ignores_non_filter_params(api_client, mock_service) -> None:
    api_client.get("/doc/0?offset=0&limit=10")
    assert mock_service.last_options.query is None


def test_http_exception_shape(api_client) -> None:
    # 404 from the service comes through the custom handler.
    response = api_client.get("/some-doc/0/9999")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == 404
    assert "message" in body
