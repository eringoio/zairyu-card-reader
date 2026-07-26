"""
Staff-facing display normalization.

Business fields keep their raw shape (`sex_code`, `period_of_stay_raw`, permission codes).
This module turns them into the strings かんたんモード shows, so the browser never has to
re-implement card semantics and the same values stay consistent at every local boundary.

Nothing here reads the chip or touches image data. It is a pure function of already-parsed
fields, which is what makes it safe to run on both the manual-scan preview and the agent
payload.
"""

from __future__ import annotations

from typing import Any

from reader.i18n import DEFAULT_LOCALE, translate
from reader.parsing.second_generation_fields import interpret_period_of_stay

DISPLAY_FIELDS = (
    "display_name",
    "display_sex",
    "display_period_of_stay",
    "display_qualification_activity_permission",
    "display_qualification_activity_permission_detail",
    "display_signature_status",
)

MALE_VALUES = {"1", "M", "MALE", "男", "男性"}
FEMALE_VALUES = {"2", "F", "FEMALE", "女", "女性"}

# Comprehensive permission codes that mean "work outside the residence status is allowed".
COMPREHENSIVE_PERMISSION_GRANTED_CODES = {"1", "2"}
INDIVIDUAL_PERMISSION_GRANTED_CODES = {"1"}

SIGNATURE_STATUS_MESSAGE_KEYS = {
    "verified_production": "display.signature.verified_production",
    "verified_official_test": "display.signature.verified_official_test",
    "untrusted_certificate": "display.signature.untrusted_certificate",
    "ambiguous_trust_path": "display.signature.ambiguous_trust_path",
    "certificate_expired": "display.signature.certificate_expired",
    "certificate_not_yet_valid": "display.signature.certificate_not_yet_valid",
    "anchor_fingerprint_mismatch": "display.signature.anchor_fingerprint_mismatch",
    "missing_signature": "display.signature.missing_signature",
    "missing_certificate": "display.signature.missing_certificate",
    "missing_signed_component": "display.signature.missing_signed_component",
    "signature_mismatch": "display.signature.signature_mismatch",
    "certificate_invalid": "display.signature.certificate_invalid",
    "verification_error": "display.signature.verification_error",
    "verified": "display.signature.verified",
    "not_verified": "display.signature.not_verified",
    "skipped_by_config": "display.signature.skipped_by_config",
    "certificate_unavailable": "display.signature.certificate_unavailable",
    "missing_dependency": "display.signature.certificate_unavailable",
    "images_unavailable": "display.signature.not_verified",
    "unsupported_card_generation": "display.signature.unsupported_card_generation",
}


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def ocr_field_was_not_read(data: dict[str, Any], field: str) -> bool:
    """True when the local recognizer produced no candidate at all for this field.

    Worth distinguishing from a low-confidence result. This application has no editable
    field for a name or an address — staff review what was read — so "nothing
    was read" and "read, but check it" call for different actions and must not look alike.
    """
    return _text(data, f"{field}_ocr_status").startswith("failed")


def display_name(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    candidate = _text(data, "name_ocr_candidate")
    if candidate:
        return candidate
    if ocr_field_was_not_read(data, "name"):
        return translate("display.name.not_read", locale)
    return translate("display.name.missing", locale)


def display_sex(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    """Map the chip code onto a word. Anything recognised but not male/female is `その他`."""
    code = _text(data, "sex_code").upper() or _text(data, "sex_label").upper()
    if not code:
        return ""
    if code in MALE_VALUES:
        return translate("display.sex.male", locale)
    if code in FEMALE_VALUES:
        return translate("display.sex.female", locale)
    return translate("display.sex.other", locale)


def display_period_of_stay(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    """
    Prefer the raw code so the label is rendered in the viewer's language.

    Cards read before this layer existed only carry `period_of_stay_label`, so fall back to
    it rather than showing nothing.
    """
    raw = _text(data, "period_of_stay_raw")
    if raw:
        return interpret_period_of_stay(raw, locale)
    return _text(data, "period_of_stay_label")


def qualification_activity_permission_granted(data: dict[str, Any]) -> bool:
    """
    Either permission grants the right to work outside the residence status.

    Reading only `individual_permission_code` reports `なし` for the common case of a
    student holding a comprehensive 週28時間 permission.
    """
    comprehensive = _text(data, "comprehensive_permission_code")
    individual = _text(data, "individual_permission_code")
    if comprehensive in COMPREHENSIVE_PERMISSION_GRANTED_CODES:
        return True
    return individual in INDIVIDUAL_PERMISSION_GRANTED_CODES


def display_qualification_activity_permission(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    key = "display.permission.yes" if qualification_activity_permission_granted(data) else "display.permission.no"
    return translate(key, locale)


def display_qualification_activity_permission_detail(data: dict[str, Any]) -> str:
    """The wording printed on the card. Only meaningful when a permission was granted."""
    if not qualification_activity_permission_granted(data):
        return ""
    comprehensive = _text(data, "comprehensive_permission_code")
    if comprehensive in COMPREHENSIVE_PERMISSION_GRANTED_CODES:
        detail = _text(data, "comprehensive_permission_label")
        if detail:
            return detail
    return _text(data, "individual_permission_label")


def signature_verification_status(data: dict[str, Any]) -> str:
    """Normalize the machine-readable signature status, tolerating older payload shapes."""
    status = _text(data, "signature_verification_status")
    if status:
        return status
    verified = data.get("signature_verified")
    if verified is True or str(verified).strip().lower() == "true":
        return "verified"
    if verified is False or str(verified).strip().lower() == "false":
        return "not_verified"
    return "certificate_unavailable"


def display_signature_status(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> str:
    status = signature_verification_status(data)
    key = SIGNATURE_STATUS_MESSAGE_KEYS.get(status, "display.signature.not_verified")
    return translate(key, locale)


def build_display_fields(data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    """Derive every `display_*` field from already-parsed business fields."""
    return {
        "display_name": display_name(data, locale),
        "display_sex": display_sex(data, locale),
        "display_period_of_stay": display_period_of_stay(data, locale),
        "display_qualification_activity_permission": display_qualification_activity_permission(data, locale),
        "display_qualification_activity_permission_detail": display_qualification_activity_permission_detail(data),
        "display_signature_status": display_signature_status(data, locale),
    }
