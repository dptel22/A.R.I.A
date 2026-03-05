"""
tests/test_cors.py — A.R.I.A. CORS Configuration Tests
Verifies that the API correctly handles cross-origin requests.
"""

import pytest
from fastapi.testclient import TestClient

def test_cors_headers(test_client):
    """
    Test that the API returns correct CORS headers when a request is made from an allowed origin.
    """
    client, _ = test_client
    origin = "http://localhost:8501"

    # Test GET request with Origin header
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_preflight(test_client):
    """
    Test that the API correctly handles CORS preflight (OPTIONS) requests.
    """
    client, _ = test_client
    origin = "http://localhost:8501"

    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }

    response = client.options("/detections", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-methods") is not None
    assert "POST" in response.headers.get("access-control-allow-methods")

def test_cors_disallowed_origin(test_client):
    """
    Test that the API does not return CORS headers for disallowed origins.
    """
    client, _ = test_client
    origin = "http://malicious-site.com"

    response = client.get("/health", headers={"Origin": origin})

    # FastAPI/Starlette CORS middleware doesn't necessarily block the request,
    # but it won't include the CORS headers if the origin is not allowed.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
