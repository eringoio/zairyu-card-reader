"""Safe local-only errors for reader/card failures."""

from __future__ import annotations

from typing import Any

INVALID_CARD_NUMBER = "invalid_card_number"
NO_READER_FOUND = "no_reader_found"
READ_ALREADY_IN_PROGRESS = "read_already_in_progress"


def error_response(code: str, *, stage: str, locale: str = "ja") -> dict[str, str | bool]:
    messages = {
        "ja": {
            INVALID_CARD_NUMBER: "在留カード番号の形式を確認してください。",
            NO_READER_FOUND: "カードリーダーが見つかりません。",
            READ_ALREADY_IN_PROGRESS: "別の読み取りが進行中です。完了してから、もう一度お試しください。",
        },
        "en": {
            INVALID_CARD_NUMBER: "Check the residence card number format.",
            NO_READER_FOUND: "No card reader was found.",
            READ_ALREADY_IN_PROGRESS: "Another read is already in progress. Wait for it to finish and try again.",
        },
    }.get(locale, {})
    return {"success": False, "stage": stage, "error_code": code, "message": messages.get(code, "読み取りできませんでした。")}


def classify_card_error(result: dict[str, Any]) -> str:
    return "card_not_detected" if result.get("success") is False else "read_failed"


def classify_read_failure(detail: str) -> str:
    return "read_failed"
