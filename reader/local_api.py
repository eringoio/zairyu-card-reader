from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from reader.card_number import card_number_is_valid, normalize_card_number
from reader.config import get_debug_trace_config, get_rc2_config
from reader.display_fields import build_display_fields
from reader.friendly_errors import (
    INVALID_CARD_NUMBER,
    NO_READER_FOUND,
    READ_ALREADY_IN_PROGRESS,
    classify_card_error,
    classify_read_failure,
    error_response,
)
from reader.i18n import locale_from_accept_language, translate
from reader.local_config import DEFAULT_APP_VERSION, LocalConfigStore
from reader.mock_reader import get_mock_residence_card_data
from reader.parsing.address_splitter import split_japanese_address
from reader.pcsc import check_card_presence, list_readers
from reader.policy import sanitize_response
from reader.residence_card_reader import read_residence_card

router = APIRouter(prefix="/api/local", tags=["local"])
_config_store: LocalConfigStore | None = None

# Uvicorn runs synchronous endpoints in a thread pool, so two scans can genuinely overlap.
# A PC/SC card session is not reentrant: a second read against the same reader mid-session
# corrupts the first one's secure messaging and can return one card's fields under the
# other's requested number. One read at a time, and say so plainly rather than queueing —
# a staff member holding a card on the reader needs an answer now, not a delayed one.
_card_read_lock = threading.Lock()


def get_config_store() -> LocalConfigStore:
    global _config_store
    if _config_store is None:
        _config_store = LocalConfigStore()
    return _config_store


def set_config_store(store: LocalConfigStore | None) -> None:
    global _config_store
    _config_store = store


class LocalConfigRequest(BaseModel):
    reader_id: int | None = Field(default=None, ge=0)


class ManualScanRequest(BaseModel):
    reader_id: int = Field(default=0, ge=0)
    card_number: str = Field(default="", max_length=32)
    use_mock: bool = False


def _reader_status(reader_id: int) -> dict[str, Any]:
    listing = list_readers()
    readers = listing.get("readers", []) if listing.get("success") else []
    selected = next((reader for reader in readers if reader.get("id") == reader_id), None)
    return {"available": bool(readers), "count": len(readers), "selected_reader_id": reader_id,
            "name": selected.get("name", "") if selected else "", "readers": readers,
            "message": listing.get("message", "")}


def _prepare_staff_result(data: dict[str, Any], locale: str) -> dict[str, Any]:
    safe = sanitize_response(data)
    if safe.get("address_full") and not safe.get("address_prefecture"):
        safe.update(split_japanese_address(str(safe["address_full"])))
    safe.update(build_display_fields(safe, locale))
    allowed = {
        "card_number", "display_name", "birth_date", "display_sex", "nationality_label",
        "residence_status_label", "display_period_of_stay", "residence_expiry_date",
        "card_expiry_date", "permission_date", "address_prefecture", "address_municipality",
        "address_other", "work_restriction_label", "display_qualification_activity_permission",
        "display_qualification_activity_permission_detail", "display_signature_status",
        "name_ocr_candidate", "sex_code", "period_of_stay_raw", "period_of_stay_label",
        "comprehensive_permission_code", "comprehensive_permission_label", "individual_permission_code",
        "individual_permission_label", "signature_verification_status", "signature_verified",
        "implementation_status", "trust_profile", "selected_anchor_id", "trust_anchor_status",
        "certificate_chain_status", "certificate_validity_status", "anchor_validity_status",
        "signed_components_status", "production_authenticity_verified", "review_required",
        "name_ocr_status", "name_ocr_note", "name_ocr_confidence", "name_ocr_confidence_category",
        "name_ocr_review_required", "name_ocr_review_reasons", "name_ocr_suggested_candidate",
        "address_ocr_status", "address_ocr_note", "address_ocr_confidence", "address_ocr_confidence_category",
        "address_ocr_review_required", "address_ocr_review_reasons", "address_ocr_suggested_candidate",
        "front_ocr_status", "front_ocr_engine", "front_ocr_model", "front_ocr_confidence", "front_ocr_row_count",
        "front_image_width", "front_image_height", "front_ocr_address_strategy", "front_ocr_nationality_strategy",
        "card_generation", "card_type_code", "certificate_field_length", "certificate_encoding_detected",
        "certificate_normalization_status", "certificate_trailing_padding_length", "signature_status",
        "technical_category"
    }
    return {key: safe.get(key, "") for key in allowed}


@router.get("/status")
def local_status(check_card: bool = False, accept_language: str | None = Header(default=None)) -> dict[str, Any]:
    config = get_config_store().load()
    trust_profile = get_rc2_config().verification_trust_profile
    status: dict[str, Any] = {"success": True, "app": {"version": config.app_version or DEFAULT_APP_VERSION},
                              "config": config.safe_dict(), "reader": _reader_status(config.reader_id),
                              "verification": {"trust_profile": trust_profile, "official_test_mode": trust_profile == "official_test"}}
    if check_card:
        presence = check_card_presence(config.reader_id)
        status["card"] = {"card_detected": bool(presence.get("success")),
                          "message": "" if presence.get("success") else str(presence.get("message", ""))}
    return status


@router.post("/config")
def local_config(request: LocalConfigRequest) -> dict[str, Any]:
    config = get_config_store().load()
    if request.reader_id is not None:
        config.reader_id = request.reader_id
    get_config_store().save(config)
    return {"success": True, "stage": "config_saved", "config": config.safe_dict()}


def _emit_verification_diagnostics(data: dict[str, Any]) -> None:
    """Print card-free verification statuses when diagnostics are explicitly enabled.

    Every value here is a status code or a length, never a card field. It stays gated
    anyway: the packaged build is windowed, so this output goes somewhere nobody reviews,
    and one block per read is a per-card trail in whatever console the process inherited.
    """
    if not get_debug_trace_config().enabled:
        return
    fields = [
        ("Card Generation", "card_generation"),
        ("Card Type Code", "card_type_code"),
        ("Certificate Field Length", "certificate_field_length"),
        ("Certificate Encoding", "certificate_encoding_detected"),
        ("Certificate Normalization Status", "certificate_normalization_status"),
        ("Certificate Trailing Padding Length", "certificate_trailing_padding_length"),
        ("Certificate Parse Status", "public_key_certificate_parse_status"),
        ("Certificate Chain Verification", "certificate_chain_verified"),
        ("Selected Anchor ID", "selected_anchor_id"),
        ("Certificate Validity Status", "certificate_validity_status"),
        ("Signature Status", "signature_verification_status"),
        ("Signature Verified", "signature_verified"),
        ("Technical Category", "technical_category"),
    ]
    print("\n=== Residence Card Verification Diagnostics ===", flush=True)
    for label, key in fields:
        print(f"{label + ':':37}{data.get(key)}", flush=True)
    print("================================================\n", flush=True)


@router.post("/manual-scan")
def local_manual_scan(request: ManualScanRequest, accept_language: str | None = Header(default=None)) -> dict[str, Any]:
    locale = locale_from_accept_language(accept_language)
    number = normalize_card_number(request.card_number)
    if not card_number_is_valid(number):
        return error_response(INVALID_CARD_NUMBER, stage="manual_scan", locale=locale)
    if request.use_mock:
        data = get_mock_residence_card_data(number)
    else:
        if not _reader_status(request.reader_id)["available"]:
            return error_response(NO_READER_FOUND, stage="manual_scan", locale=locale)
        # Refuse rather than queue: a second reader session started mid-read corrupts the
        # first one's secure messaging, and a queued read would run against whatever card
        # is on the reader by the time it starts, not the one the staff member requested.
        if not _card_read_lock.acquire(blocking=False):
            return error_response(READ_ALREADY_IN_PROGRESS, stage="manual_scan", locale=locale)
        try:
            presence = check_card_presence(request.reader_id)
            if not presence.get("success"):
                return error_response(classify_card_error(presence), stage="manual_scan", locale=locale)
            try:
                result = read_residence_card(request.reader_id, number)
                if not result.get("success"):
                    return error_response(classify_read_failure(str(result.get("message") or result.get("error") or "")), stage="manual_scan", locale=locale)
                data = result.get("data") if isinstance(result.get("data"), dict) else result
            except Exception as exc:
                return error_response(classify_read_failure(str(exc)), stage="manual_scan", locale=locale)
        finally:
            _card_read_lock.release()

    if data:
        _emit_verification_diagnostics(data)

    return {"success": True, "stage": "manual_scan_ready", "message": translate("manual_scan.ready", locale),
            "data": _prepare_staff_result(data, locale)}
