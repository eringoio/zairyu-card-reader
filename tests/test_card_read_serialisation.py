"""A second card read must not start while one is already in progress.

Uvicorn runs synchronous endpoints in a thread pool, so two POSTs really can overlap. A
PC/SC session is not reentrant: a second read against the same reader mid-session corrupts
the first one's secure messaging, and could return one card's fields under the other's
requested number.
"""

from __future__ import annotations

import threading

import pytest

from reader import local_api
from reader.friendly_errors import READ_ALREADY_IN_PROGRESS


@pytest.fixture(autouse=True)
def _reader_is_present(monkeypatch):
    monkeypatch.setattr(local_api, "_reader_status", lambda reader_id: {"available": True})
    monkeypatch.setattr(local_api, "check_card_presence", lambda reader_id: {"success": True})


def _request(number: str = "AB12345678AJ"):
    return local_api.ManualScanRequest(reader_id=0, card_number=number, use_mock=False)


def test_a_concurrent_read_is_refused_rather_than_interleaved(monkeypatch) -> None:
    inside = threading.Event()
    release = threading.Event()
    overlaps: list[str] = []

    def slow_read(reader_id: int, number: str):
        inside.set()
        # Hold the reader session open while the second request arrives.
        release.wait(timeout=5)
        return {"success": True, "data": {"card_number": number}}

    monkeypatch.setattr(local_api, "read_residence_card", slow_read)

    first_result: list[dict] = []
    first = threading.Thread(target=lambda: first_result.append(local_api.local_manual_scan(_request(), accept_language=None)))
    first.start()
    assert inside.wait(timeout=5), "the first read never started"

    second = local_api.local_manual_scan(_request("CD12345678EF"), accept_language=None)
    overlaps.append(str(second.get("error_code")))

    release.set()
    first.join(timeout=5)

    assert second["success"] is False
    assert second["error_code"] == READ_ALREADY_IN_PROGRESS
    assert first_result and first_result[0]["success"] is True


def test_the_lock_is_released_after_a_failing_read(monkeypatch) -> None:
    def failing_read(reader_id: int, number: str):
        raise RuntimeError("reader disconnected mid-session")

    monkeypatch.setattr(local_api, "read_residence_card", failing_read)
    assert local_api.local_manual_scan(_request(), accept_language=None)["success"] is False
    assert not local_api._card_read_lock.locked()

    # A later read must still be possible; a leaked lock would wedge the application until
    # it is restarted.
    monkeypatch.setattr(local_api, "read_residence_card", lambda reader_id, number: {"success": True, "data": {"card_number": number}})
    assert local_api.local_manual_scan(_request(), accept_language=None)["success"] is True
    assert not local_api._card_read_lock.locked()


def test_mock_scans_do_not_take_the_reader_lock(monkeypatch) -> None:
    """Sample data touches no hardware, so it must never block a real read."""
    request = local_api.ManualScanRequest(reader_id=0, card_number="AB12345678AJ", use_mock=True)
    local_api._card_read_lock.acquire()
    try:
        assert local_api.local_manual_scan(request, accept_language=None)["success"] is True
    finally:
        local_api._card_read_lock.release()
