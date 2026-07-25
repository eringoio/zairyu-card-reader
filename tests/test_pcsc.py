from __future__ import annotations

from reader.pcsc import (
    REMOVED_CARD_CODE,
    RESET_NOT_RESPONDING_CODE,
    RESIDENCE_CARD_STANDARD,
    _format_card_connection_error,
    _reader_compatibility_hint,
)


def test_formats_reset_not_responding_error() -> None:
    attempts = [{"protocol": "T=1", "error": "reset failed"}]
    result = _format_card_connection_error(
        RuntimeError(f"Unable to connect with protocol: T0 or T1. ({RESET_NOT_RESPONDING_CODE})"),
        attempts,
    )

    assert result["success"] is False
    assert result["code"] == RESET_NOT_RESPONDING_CODE
    assert "residence-card-compatible" in result["error"]
    assert result["required_standard"] == RESIDENCE_CARD_STANDARD
    assert result["attempted_protocols"] == ["T=1"]
    assert RESET_NOT_RESPONDING_CODE in result["detail"]


def test_formats_removed_card_error() -> None:
    result = _format_card_connection_error(RuntimeError(f"Card removed ({REMOVED_CARD_CODE})"))

    assert result["success"] is False
    assert result["code"] == REMOVED_CARD_CODE
    assert "connection was lost" in result["error"]


def test_flags_contact_reader_as_unlikely_for_residence_card() -> None:
    hint = _reader_compatibility_hint("Alcorlink USB Smart Card Reader 0")

    assert "contact smart-card reader" in hint
    assert "contactless" in hint
