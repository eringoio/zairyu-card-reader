from __future__ import annotations

from typing import Any

RESET_NOT_RESPONDING_CODE = "0x80100066"
REMOVED_CARD_CODE = "0x80100069"
RESIDENCE_CARD_STANDARD = "JIS X 6322 B / ISO/IEC 14443 Type B"


class CardActivationError(Exception):
    def __init__(self, original: Exception, attempts: list[dict[str, str]]) -> None:
        super().__init__(str(original))
        self.original = original
        self.attempts = attempts


def _protocol_attempts() -> list[tuple[str, int | None]]:
    try:
        from smartcard.scard import SCARD_PROTOCOL_T0, SCARD_PROTOCOL_T1
    except Exception:
        return [("default", None)]

    return [
        ("T=1", SCARD_PROTOCOL_T1),
        ("T=0", SCARD_PROTOCOL_T0),
        ("default", None),
    ]


def _load_readers():
    try:
        from smartcard.System import readers
    except Exception as exc:  # pyscard may be absent or unavailable on non-Windows CI.
        return None, str(exc)
    return readers, None


def _reader_compatibility_hint(name: str) -> str:
    lowered = name.lower()
    contactless_markers = ["nfc", "contactless", "picc", "pico", "acr12", "rc-s", "pasori"]
    if any(marker in lowered for marker in contactless_markers):
        return "Confirm this reader supports ISO/IEC 14443 Type B over PC/SC for residence cards."
    if "alcorlink" in lowered or "smart card reader" in lowered:
        return (
            "This looks like a contact smart-card reader. Residence cards require a contactless "
            "ISO/IEC 14443 Type B PC/SC reader."
        )
    return "Unknown residence-card compatibility. Confirm ISO/IEC 14443 Type B support."


def _format_card_connection_error(
    exc: Exception,
    attempts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    detail = str(exc)
    attempted_protocols = [attempt["protocol"] for attempt in attempts or []]
    if RESET_NOT_RESPONDING_CODE in detail or "reset" in detail.lower():
        return {
            "success": False,
            "error": (
                "The reader was found, but the card did not respond as a residence-card-compatible "
                f"{RESIDENCE_CARD_STANDARD} smart card. "
                "Remove and place the card again, make sure it is centered on the reader, "
                "and confirm the reader supports ISO/IEC 14443 Type B through PC/SC."
            ),
            "code": RESET_NOT_RESPONDING_CODE,
            "detail": detail,
            "required_standard": RESIDENCE_CARD_STANDARD,
            "attempted_protocols": attempted_protocols,
            "attempts": attempts or [],
        }

    if REMOVED_CARD_CODE in detail:
        return {
            "success": False,
            "error": (
                "The card connection was lost during activation. Keep the residence card still on the "
                "reader and confirm the hardware is a contactless ISO/IEC 14443 Type B PC/SC reader."
            ),
            "code": REMOVED_CARD_CODE,
            "detail": detail,
            "required_standard": RESIDENCE_CARD_STANDARD,
            "attempted_protocols": attempted_protocols,
            "attempts": attempts or [],
        }

    return {
        "success": False,
        "error": "No card detected or card connection failed.",
        "detail": detail,
        "required_standard": RESIDENCE_CARD_STANDARD,
        "attempted_protocols": attempted_protocols,
        "attempts": attempts or [],
    }


def _connect_and_get_atr(reader) -> tuple[str, str]:
    attempts: list[dict[str, str]] = []
    last_error: Exception | None = None

    for label, protocol in _protocol_attempts():
        try:
            connection = reader.createConnection()
            if protocol is None:
                connection.connect()
            else:
                connection.connect(protocol=protocol)
            atr = " ".join(f"{byte:02X}" for byte in connection.getATR())
            return label, atr
        except Exception as exc:
            last_error = exc
            attempts.append({"protocol": label, "error": str(exc)})

    if last_error is None:
        last_error = RuntimeError("No PC/SC protocol attempts were available.")
    raise CardActivationError(last_error, attempts)


def list_readers() -> dict[str, Any]:
    readers_fn, error = _load_readers()
    if error:
        return {
            "success": True,
            "readers": [],
            "message": f"PC/SC unavailable: {error}",
        }

    try:
        detected = readers_fn()
    except Exception as exc:
        return {"success": False, "error": f"Failed to list PC/SC readers: {exc}"}

    return {
        "success": True,
        "readers": [
            {
                "id": index,
                "name": str(reader),
                "required_standard": RESIDENCE_CARD_STANDARD,
                "compatibility_hint": _reader_compatibility_hint(str(reader)),
            }
            for index, reader in enumerate(detected)
        ],
    }


def check_card_presence(reader_id: int) -> dict[str, Any]:
    readers_fn, error = _load_readers()
    if error:
        return {"success": False, "error": f"PC/SC unavailable: {error}"}

    try:
        detected = readers_fn()
    except Exception as exc:
        return {"success": False, "error": f"Failed to list PC/SC readers: {exc}"}

    if reader_id >= len(detected):
        return {"success": False, "error": "Invalid reader ID."}

    reader = detected[reader_id]
    try:
        protocol, atr = _connect_and_get_atr(reader)
    except CardActivationError as exc:
        return _format_card_connection_error(exc.original, exc.attempts)
    except Exception as exc:
        return _format_card_connection_error(exc)

    return {
        "success": True,
        "reader": str(reader),
        "card_detected": True,
        "atr": atr,
        "protocol": protocol,
        "required_standard": RESIDENCE_CARD_STANDARD,
    }
