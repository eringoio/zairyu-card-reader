"""Unit tests for the loopback request guard's decision functions.

These cover the parsing and policy decisions in isolation. `test_local_web_security.py`
exercises the same rules through the real ASGI stack.
"""

from __future__ import annotations

import pytest

from reader.local_guard import (
    MAX_REQUEST_BYTES,
    content_length_is_acceptable,
    host_header_is_local,
    hostname_from_host_header,
    new_request_token,
    origin_is_local,
    request_provenance_is_acceptable,
    token_is_required,
    token_matches,
)

# ------------------------------------------------------------------ Host parsing


@pytest.mark.parametrize(
    "header,expected",
    [
        ("127.0.0.1", "127.0.0.1"),
        ("127.0.0.1:8787", "127.0.0.1"),
        ("localhost:8787", "localhost"),
        ("LOCALHOST:8787", "localhost"),
        ("[::1]:8787", "::1"),
        ("[::1]", "::1"),
        ("  127.0.0.1:8787  ", "127.0.0.1"),
    ],
)
def test_loopback_host_headers_parse_to_a_loopback_name(header: str, expected: str) -> None:
    assert hostname_from_host_header(header) == expected
    assert host_header_is_local(header) is True


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "evil.example.com",
        "evil.example.com:8787",
        # DNS rebinding: the address resolves to loopback, but the Host header still
        # carries the name the browser dialled. That is exactly what this check catches.
        "rebind.attacker.test:8787",
        "127.0.0.1.attacker.test",
        "attacker.test:8787.127.0.0.1",
        "0.0.0.0:8787",
        "192.168.1.10:8787",
        "[2001:db8::1]:8787",
        "[unterminated:8787",
    ],
)
def test_non_loopback_host_headers_are_rejected(header: str | None) -> None:
    assert host_header_is_local(header) is False


# ---------------------------------------------------------------- Origin parsing


@pytest.mark.parametrize(
    "origin",
    ["http://127.0.0.1:8787", "http://localhost:8787", "http://[::1]:8787", "http://127.0.0.1"],
)
def test_loopback_origins_are_local(origin: str) -> None:
    assert origin_is_local(origin) is True


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "",
        "null",
        "https://127.0.0.1:8787",
        "http://evil.example.com",
        "http://evil.example.com:8787",
        "file://",
        "127.0.0.1:8787",
    ],
)
def test_foreign_or_malformed_origins_are_not_local(origin: str | None) -> None:
    assert origin_is_local(origin) is False


# ------------------------------------------------------------------- provenance


def test_read_only_methods_always_pass_provenance() -> None:
    assert request_provenance_is_acceptable("GET", origin="http://evil.test", referer=None, sec_fetch_site=None) is True


def test_state_changing_request_from_a_foreign_origin_is_rejected() -> None:
    assert (
        request_provenance_is_acceptable("POST", origin="http://evil.test", referer=None, sec_fetch_site=None)
        is False
    )


def test_state_changing_request_from_the_local_origin_is_accepted() -> None:
    assert (
        request_provenance_is_acceptable("POST", origin="http://127.0.0.1:8787", referer=None, sec_fetch_site="same-origin")
        is True
    )


def test_cross_site_fetch_metadata_is_rejected_even_without_an_origin() -> None:
    assert request_provenance_is_acceptable("POST", origin=None, referer=None, sec_fetch_site="cross-site") is False


def test_foreign_referer_is_rejected_when_no_origin_is_sent() -> None:
    assert request_provenance_is_acceptable("POST", origin=None, referer="http://evil.test/page", sec_fetch_site=None) is False


def test_non_browser_local_client_without_provenance_headers_is_allowed() -> None:
    # curl, a test client, or the launcher sends neither header. The token still applies.
    assert request_provenance_is_acceptable("POST", origin=None, referer=None, sec_fetch_site=None) is True


# ------------------------------------------------------------------------ token


def test_tokens_are_unique_and_long_enough_to_be_unguessable() -> None:
    tokens = {new_request_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(token) >= 32 for token in tokens)


def test_staff_endpoints_require_a_token_and_health_does_not() -> None:
    assert token_is_required("/api/local/manual-scan") is True
    assert token_is_required("/api/local/status") is True
    assert token_is_required("/api/health") is False
    # The page itself and its static assets are not API endpoints.
    assert token_is_required("/") is False
    assert token_is_required("/static/local.js") is False


def test_token_comparison_rejects_absent_empty_and_wrong_values() -> None:
    expected = new_request_token()
    assert token_matches(expected, expected) is True
    assert token_matches(None, expected) is False
    assert token_matches("", expected) is False
    assert token_matches(expected[:-1], expected) is False
    assert token_matches(expected + "x", expected) is False


# ----------------------------------------------------------------- body bounding


def test_request_size_bounds() -> None:
    assert content_length_is_acceptable(None) is True
    assert content_length_is_acceptable("0") is True
    assert content_length_is_acceptable(str(MAX_REQUEST_BYTES)) is True
    assert content_length_is_acceptable(str(MAX_REQUEST_BYTES + 1)) is False
    assert content_length_is_acceptable("-1") is False
    assert content_length_is_acceptable("not-a-number") is False
