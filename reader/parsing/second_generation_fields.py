from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from reader.parsing.tlv import TlvParseError, parse_tlvs_by_hex
from reader.runtime_paths import countries_ja_path, resource_root

SEX_LABELS = {
    "1": "男",
    "2": "女",
    "3": "未指定",
}
WORK_RESTRICTION_LABELS = {
    "1": "就労制限なし",
    "2": "在留資格に基づく就労活動のみ可",
    "4": "指定書により指定された就労活動のみ可",
    "9": "就労不可",
}
COMPREHENSIVE_PERMISSION_LABELS = {
    "0": "なし",
    "1": "許可あり（原則週28時間以内・風俗営業等不可）",
    "2": "許可あり（教育等に係る資格外活動）",
}
INDIVIDUAL_PERMISSION_LABELS = {
    "0": "なし",
    "1": "あり",
}
RENEWAL_APPLICATION_STATUS_LABELS = {
    "0": "なし",
    "1": "申請中",
}
ISA_COMMISSIONER_NOTE_LABELS = {
    "0": "なし",
    "1": "記録あり",
}
BASE_DIR = resource_root()
COUNTRIES_JA_PATH = countries_ja_path()


def _decode_utf8(value: bytes) -> str:
    return value.rstrip(b"\x00").decode("utf-8", errors="replace").strip()


def _date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


@lru_cache(maxsize=1)
def load_nationality_labels(path: Path = COUNTRIES_JA_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key).upper(): str(value) for key, value in data.items()}


def map_nationality_code(code: str) -> str:
    normalized = code.strip().upper()
    if not normalized:
        return ""
    return load_nationality_labels().get(normalized, f"Unmapped nationality/region code: {normalized}")


def map_residence_status_code(code: str) -> str:
    if not code:
        return ""
    return f"Unmapped residence status code: {code}"


def interpret_period_of_stay_ja(raw: str) -> str:
    """Canonical staff label. `0000` means indefinite, never zero months."""
    if not raw:
        return ""
    if raw == "0000":
        return "無期限"
    if len(raw) == 4 and raw.isdigit():
        years = int(raw[:2])
        months = int(raw[2:])
        parts = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}月")
        return "".join(parts) if parts else "無期限"
    if len(raw) == 3 and raw.isdigit():
        return f"{int(raw)}日"
    return f"未対応の在留期間コード: {raw}"


def interpret_period_of_stay_en(raw: str) -> str:
    """Diagnostic-mode label. Kept separate so the staff label never leaks English."""
    if not raw:
        return ""
    if raw == "0000":
        return "Indefinite"
    if len(raw) == 4 and raw.isdigit():
        years = int(raw[:2])
        months = int(raw[2:])
        parts = []
        if years:
            parts.append(f"{years} year" + ("" if years == 1 else "s"))
        if months:
            parts.append(f"{months} month" + ("" if months == 1 else "s"))
        return " ".join(parts) if parts else "Indefinite"
    if len(raw) == 3 and raw.isdigit():
        days = int(raw)
        return f"{days} day" + ("" if days == 1 else "s")
    return f"Unmapped period code: {raw}"


def interpret_period_of_stay(raw: str, locale: str = "ja") -> str:
    if locale == "ja":
        return interpret_period_of_stay_ja(raw)
    return interpret_period_of_stay_en(raw)


def parse_printed_entries(data: bytes) -> dict[str, Any]:
    tlvs = parse_tlvs_by_hex(data)
    fields = {
        "card_expiry_date": _date(_decode_utf8(tlvs.get("C5", b""))),
        "birth_date": _date(_decode_utf8(tlvs.get("C6", b""))),
        "sex_code": _decode_utf8(tlvs.get("C7", b"")),
        "nationality_region_code": _decode_utf8(tlvs.get("C8", b"")),
        "residence_status_code": _decode_utf8(tlvs.get("C9", b"")),
        "period_of_stay_raw": _decode_utf8(tlvs.get("CE", b"")),
        "permission_type_code": _decode_utf8(tlvs.get("CA", b"")),
        "permission_date": _date(_decode_utf8(tlvs.get("CB", b""))),
        "work_restriction_code": _decode_utf8(tlvs.get("CC", b"")),
        "residence_expiry_date": _date(_decode_utf8(tlvs.get("CD", b""))),
    }
    fields["sex_label"] = SEX_LABELS.get(fields["sex_code"], fields["sex_code"])
    fields["work_restriction_label"] = WORK_RESTRICTION_LABELS.get(
        fields["work_restriction_code"],
        fields["work_restriction_code"],
    )
    fields["nationality_code"] = fields["nationality_region_code"]
    fields["nationality_label"] = map_nationality_code(fields["nationality_code"])
    fields["residence_status_label"] = map_residence_status_code(fields["residence_status_code"])
    fields["period_of_stay_label"] = interpret_period_of_stay(fields["period_of_stay_raw"])
    return fields


def parse_df2_fields(card_type_code: str, ef01: bytes | None = None, ef02: bytes | None = None, ef03: bytes | None = None) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if card_type_code == "05" and ef01 is not None:
        tlvs = parse_tlvs_by_hex(ef01)
        fields["comprehensive_permission_code"] = _decode_utf8(tlvs.get("D5", b""))
        fields["comprehensive_permission_expiry_date"] = _date(_decode_utf8(tlvs.get("D6", b"")))
        fields["individual_permission_code"] = _decode_utf8(tlvs.get("D7", b""))
        fields["comprehensive_permission_label"] = COMPREHENSIVE_PERMISSION_LABELS.get(
            fields["comprehensive_permission_code"],
            fields["comprehensive_permission_code"],
        )
        fields["individual_permission_label"] = INDIVIDUAL_PERMISSION_LABELS.get(
            fields["individual_permission_code"],
            fields["individual_permission_code"],
        )
    if card_type_code == "05" and ef02 is not None:
        tlvs = parse_tlvs_by_hex(ef02)
        status = _decode_utf8(tlvs.get("D8", b""))
        fields["renewal_application_status"] = RENEWAL_APPLICATION_STATUS_LABELS.get(status, status)
    if ef03 is not None:
        tlvs = parse_tlvs_by_hex(ef03)
        fields["isa_commissioner_note_code"] = _decode_utf8(tlvs.get("D9", b""))
        fields["isa_commissioner_note_label"] = ISA_COMMISSIONER_NOTE_LABELS.get(
            fields["isa_commissioner_note_code"],
            fields["isa_commissioner_note_code"],
        )
        fields["reserved_note_text"] = _decode_utf8(tlvs.get("DE", b""))
    return fields


def parse_signature_metadata(
    data: bytes,
    *,
    printed_entries: bytes | None = None,
    face_image: bytes | None = None,
    name_image: bytes | None = None,
    full_validation_enabled: bool | None = None,
    trust_profile: str | None = None,
    card_type_code: str = "",
) -> dict[str, Any]:
    """
    Read DF3/EF01 and, when the images are supplied, verify the card signature.

    ``face_image`` is accepted for cryptographic verification only. It is never copied into
    the returned metadata; only booleans, statuses and notes come back out.
    """
    if full_validation_enabled is None:
        from reader.config import get_rc2_config

        config = get_rc2_config()
        full_validation_enabled = config.enable_full_signature_validation
        trust_profile = trust_profile or config.verification_trust_profile

    tlvs = parse_tlvs_by_hex(data)
    signature = tlvs.get("DC", b"")
    certificate = tlvs.get("DD", b"")
    metadata: dict[str, Any] = {
        "signature_present": bool(signature),
        "public_key_certificate_status": "present" if certificate else "not_present",
    }

    try:
        from reader.signature.rc_signature import verify_rc2_signature
    except ModuleNotFoundError as exc:
        if exc.name != "cryptography":
            raise
        metadata.update(
            {
                "public_key_certificate_parse_status": "not_attempted_missing_dependency",
                "certificate_chain_verified": None,
                "certificate_chain_verification_note": "cryptography is not installed; install requirements to parse and verify card certificate metadata.",
                "signature_verified": None,
                "signature_verification_status": "missing_dependency",
                "signature_verification_note": "cryptography is not installed; the card signature was not checked.",
            }
        )
        return metadata

    metadata.update(
        verify_rc2_signature(
            signature=signature,
            certificate_bytes=certificate,
            printed_entries=printed_entries,
            face_image=face_image,
            name_image=name_image,
            full_validation_enabled=bool(full_validation_enabled),
            trust_profile=trust_profile,
            card_type_code=card_type_code,
        )
    )
    return metadata


def parse_rc2_business_fields(
    card_type_code: str,
    files: dict[str, bytes],
    *,
    face_image: bytes | None = None,
    name_image: bytes | None = None,
    full_validation_enabled: bool | None = None,
    trust_profile: str | None = None,
) -> dict[str, Any]:
    try:
        printed_entries = files.get("DF1/EF02", b"")
        fields = parse_printed_entries(printed_entries)
        fields.update(
            parse_df2_fields(
                card_type_code,
                ef01=files.get("DF2/EF01"),
                ef02=files.get("DF2/EF02"),
                ef03=files.get("DF2/EF03") or (files.get("DF2/EF01") if card_type_code == "06" else None),
            )
        )
        if "DF3/EF01" in files:
            fields.update(
                parse_signature_metadata(
                    files["DF3/EF01"],
                    printed_entries=printed_entries,
                    face_image=face_image,
                    name_image=name_image,
                    full_validation_enabled=full_validation_enabled,
                    trust_profile=trust_profile,
                    card_type_code=card_type_code,
                )
            )
        return fields
    except TlvParseError:
        raise
