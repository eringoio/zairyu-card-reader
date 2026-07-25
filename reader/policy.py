from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FACE_PHOTO_STATUS = "not_read_by_policy"
MY_NUMBER_STATUS = "not_accessed_by_policy"
BACK_SIDE_CAPTURE_STATUS = "disabled_by_policy"
RAW_IC_STORAGE_STATUS = "disabled_by_policy"

POLICY_STATUS_FIELDS = {
    "face_photo_status": FACE_PHOTO_STATUS,
    "my_number_status": MY_NUMBER_STATUS,
    "back_side_capture_status": BACK_SIDE_CAPTURE_STATUS,
    "raw_ic_storage_status": RAW_IC_STORAGE_STATUS,
}

FORBIDDEN_KEY_FRAGMENTS = (
    "face_photo",
    "face_image",
    "face_photo_bytes",
    "portrait",
    "my_number",
    "individual_number",
    "jpki",
    "signature_certificate",
    "user_certificate",
    "raw_ic",
    "raw_response",
    "raw_tlv",
    "tlv_bytes",
    "raw_apdu",
    "apdu_bytes",
    "apdu_log",
    "apdu_trace",
    "ic_dump",
    "chip_dump",
    "raw_dump",
    "image_bytes",
    "photo_bytes",
    "raw_signature",
    "signature_bytes",
    "raw_certificate",
    "certificate_bytes",
    "signed_target",
    "ocr_text",
    "ocr_full_text",
    "front_ocr_text",
    "front_image",
    "front_image_data_url",
    "back_image",
    "back_side_capture",
    "name_image",
    "address_image",
)

# Status strings describing what was *not* read. They name a forbidden concept but carry
# no card material, so they stay allowed while the raw variants are blocked.
ALLOWED_STATUS_KEYS = {
    "name_image_status",
    "address_image_status",
    # Numeric dimensions are safe scan-health metadata. They never contain pixels,
    # image encodings, or any OCR content.
    "front_image_width",
    "front_image_height",
}

ALLOWED_POLICY_STATUS_KEYS = set(POLICY_STATUS_FIELDS) | ALLOWED_STATUS_KEYS


def key_is_forbidden(key: str) -> bool:
    lowered = key.lower()
    if lowered in ALLOWED_POLICY_STATUS_KEYS:
        return False
    return any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS)


def forbidden_keys(data: Mapping[str, Any], prefix: str = "") -> list[str]:
    found: list[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if key_is_forbidden(str(key)):
            found.append(path)
        if isinstance(value, Mapping):
            found.extend(forbidden_keys(value, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    found.extend(forbidden_keys(item, f"{path}[{index}]"))
    return found


def sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return sanitize_response(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def sanitize_response(data: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if key_is_forbidden(str(key)):
            continue
        sanitized[key] = sanitize_value(value)
    sanitized.update(POLICY_STATUS_FIELDS)
    return sanitized
