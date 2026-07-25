"""End-to-end checks that the loopback boundary behaves as the product claims.

These run against the real ASGI application, so they cover the middleware order, the
token injection into the served page, and the response headers a browser actually sees.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app as app_module
from reader.local_guard import TOKEN_HEADER

LOCAL_HOST = "127.0.0.1:8787"
LOCAL_ORIGIN = "http://127.0.0.1:8787"


@pytest.fixture(autouse=True)
def _no_real_smartcard_service(monkeypatch) -> None:
    """Keep these tests about HTTP policy, not about this machine's PC/SC service.

    `/api/local/status` otherwise calls `SCardListReaders`, which raises a native
    exception on a host with no smart-card service and makes the suite machine-dependent.
    """
    monkeypatch.setattr("reader.local_api.list_readers", lambda: {"success": True, "readers": [], "message": ""})
    monkeypatch.setattr("reader.local_api.check_card_presence", lambda reader_id: {"success": False, "message": ""})


@pytest.fixture()
def client() -> TestClient:
    # `base_url` sets the Host header the guard inspects.
    return TestClient(app_module.app, base_url=LOCAL_ORIGIN)


def _auth(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {TOKEN_HEADER: app_module.LOCAL_REQUEST_TOKEN, "Host": LOCAL_HOST}
    headers.update(extra or {})
    return headers


# ------------------------------------------------------------------ Host header


def test_page_is_served_over_a_loopback_host(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.parametrize("host", ["evil.example.com", "evil.example.com:8787", "rebind.attacker.test:8787", "192.168.1.10:8787"])
def test_non_loopback_host_header_is_refused_on_every_path(client: TestClient, host: str) -> None:
    """A DNS-rebound page reaches the socket but not the application."""
    for path in ("/", "/api/health", "/api/local/status"):
        response = client.get(path, headers={"Host": host})
        assert response.status_code == 400, path
        assert response.json()["success"] is False


def test_non_loopback_host_header_is_refused_for_state_changing_requests(client: TestClient) -> None:
    response = client.post(
        "/api/local/manual-scan",
        json={"reader_id": 0, "card_number": "AB12345678AJ", "use_mock": True},
        headers=_auth({"Host": "evil.example.com"}),
    )
    assert response.status_code == 400


# ----------------------------------------------------------------------- token


def test_served_page_carries_this_process_token_and_no_endpoint_hands_it_out(client: TestClient) -> None:
    html = client.get("/").text
    match = re.search(r'name="local-request-token" content="([^"]+)"', html)
    assert match is not None
    assert match.group(1) == app_module.LOCAL_REQUEST_TOKEN
    assert "__LOCAL_REQUEST_TOKEN__" not in html

    # The token must not be obtainable from any API, or a rebound origin could ask for it.
    health = client.get("/api/health")
    assert app_module.LOCAL_REQUEST_TOKEN not in health.text
    status = client.get("/api/local/status", headers=_auth())
    assert app_module.LOCAL_REQUEST_TOKEN not in status.text


@pytest.mark.parametrize("path", ["/api/local/status"])
def test_staff_endpoints_refuse_a_missing_token(client: TestClient, path: str) -> None:
    assert client.get(path, headers={"Host": LOCAL_HOST}).status_code == 403


def test_staff_endpoints_refuse_a_wrong_token(client: TestClient) -> None:
    response = client.get("/api/local/status", headers={"Host": LOCAL_HOST, TOKEN_HEADER: "not-the-token"})
    assert response.status_code == 403


def test_manual_scan_refuses_a_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/local/manual-scan",
        json={"reader_id": 0, "card_number": "AB12345678AJ", "use_mock": True},
        headers={"Host": LOCAL_HOST},
    )
    assert response.status_code == 403


def test_health_stays_reachable_without_a_token_for_the_launcher(client: TestClient) -> None:
    """The launcher probes this before any page — and therefore any token — exists."""
    response = client.get("/api/health", headers={"Host": LOCAL_HOST})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "ok", "app": "zairyu-reader"}


def test_a_valid_token_still_lets_the_staff_workflow_through(client: TestClient) -> None:
    response = client.post(
        "/api/local/manual-scan",
        json={"reader_id": 0, "card_number": "AB12345678AJ", "use_mock": True},
        headers=_auth({"Origin": LOCAL_ORIGIN}),
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


# ------------------------------------------------------------------ provenance


def test_state_changing_request_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/local/manual-scan",
        json={"reader_id": 0, "card_number": "AB12345678AJ", "use_mock": True},
        headers=_auth({"Origin": "http://evil.example.com"}),
    )
    assert response.status_code == 403


def test_cross_site_fetch_metadata_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/local/config",
        json={"reader_id": 0},
        headers=_auth({"Sec-Fetch-Site": "cross-site"}),
    )
    assert response.status_code == 403


# -------------------------------------------------------------- CORS and headers


def test_no_cors_headers_are_ever_emitted(client: TestClient) -> None:
    """No wildcard, and no CORS at all: nothing outside this page may read a response."""
    for response in (client.get("/"), client.get("/api/health"), client.get("/api/local/status", headers=_auth())):
        for header in response.headers:
            assert not header.lower().startswith("access-control-"), header


def test_security_response_headers_are_present(client: TestClient) -> None:
    page = client.get("/")
    assert page.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["Referrer-Policy"] == "no-referrer"


# ------------------------------------------------------------------ body bounds


def test_an_oversized_declared_body_is_refused_before_it_is_read(client: TestClient) -> None:
    response = client.post(
        "/api/local/copy-text",
        headers=_auth({"Content-Type": "application/json", "Content-Length": str(64 * 1024 * 1024)}),
        content=b"{}",
    )
    assert response.status_code == 413


def test_the_copy_batch_stays_bounded_by_its_schema(client: TestClient) -> None:
    response = client.post(
        "/api/local/copy-text",
        json={"cards": [{"card_number": "AB12345678AJ"} for _ in range(101)]},
        headers=_auth(),
    )
    assert response.status_code == 422


# ------------------------------------------------------------- error redaction


def test_an_unexpected_failure_returns_no_traceback_or_exception_text(client: TestClient, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise RuntimeError("card_number=AB12345678AJ leaked through an exception")

    monkeypatch.setattr("reader.local_api.get_mock_residence_card_data", explode)
    response = client.post(
        "/api/local/manual-scan",
        json={"reader_id": 0, "card_number": "AB12345678AJ", "use_mock": True},
        headers=_auth(),
    )

    assert response.status_code == 500
    body = response.text
    assert "Traceback" not in body
    assert "RuntimeError" not in body
    assert "leaked through an exception" not in body
    assert "AB12345678AJ" not in body


def test_removed_development_endpoints_are_gone(client: TestClient) -> None:
    """`/api/readers` and `/api/check-card` duplicated `/api/local/status` and were unused."""
    assert client.get("/api/readers", headers=_auth()).status_code == 404
    assert client.post("/api/check-card", headers=_auth()).status_code == 404
