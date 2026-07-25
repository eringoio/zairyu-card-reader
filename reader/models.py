from __future__ import annotations

from dataclasses import asdict, dataclass

from reader.policy import (
    BACK_SIDE_CAPTURE_STATUS,
    FACE_PHOTO_STATUS,
    MY_NUMBER_STATUS,
    RAW_IC_STORAGE_STATUS,
)


@dataclass
class ReviewedResidenceCardResult:
    read_at: str = ""
    reviewed_at: str = ""
    reviewed_by: str = ""
    student_id: str = ""
    match_method: str = ""
    card_number: str = ""
    card_type_code: str = ""
    card_type_label: str = ""
    chip_version: str = ""
    birth_date: str = ""
    sex_code: str = ""
    sex_label: str = ""
    nationality_code: str = ""
    nationality_label: str = ""
    residence_status_code: str = ""
    residence_status_label: str = ""
    period_of_stay_raw: str = ""
    period_of_stay_label: str = ""
    residence_expiry_date: str = ""
    card_expiry_date: str = ""
    permission_type_code: str = ""
    permission_type_label: str = ""
    permission_date: str = ""
    work_restriction_code: str = ""
    work_restriction_label: str = ""
    comprehensive_permission_code: str = ""
    comprehensive_permission_label: str = ""
    comprehensive_permission_expiry_date: str = ""
    individual_permission_code: str = ""
    individual_permission_label: str = ""
    renewal_application_status: str = ""
    name_ocr_candidate: str = ""
    name_ocr_status: str = ""
    name_ocr_source: str = ""
    name_ocr_note: str = ""
    name_ocr_confidence: str = ""
    name_ocr_confidence_category: str = ""
    name_ocr_review_required: bool = False
    name_ocr_review_reasons: list[str] | None = None
    name_ocr_suggested_candidate: str = ""
    address_full: str = ""
    address_prefecture: str = ""
    address_municipality: str = ""
    address_other: str = ""
    address_source: str = ""
    address_ocr_status: str = ""
    address_ocr_note: str = ""
    address_ocr_confidence: str = ""
    address_ocr_confidence_category: str = ""
    address_ocr_review_required: bool = False
    address_ocr_review_reasons: list[str] | None = None
    address_ocr_suggested_candidate: str = ""
    isa_commissioner_note_code: str = ""
    isa_commissioner_note_label: str = ""
    reserved_note_text: str = ""
    signature_present: str = ""
    public_key_certificate_status: str = ""
    public_key_certificate_parse_status: str = ""
    certificate_chain_verified: str = ""
    certificate_chain_verification_note: str = ""
    signature_verified: str = ""
    signature_verification_status: str = ""
    signature_verification_note: str = ""
    face_photo_status: str = FACE_PHOTO_STATUS
    my_number_status: str = MY_NUMBER_STATUS
    back_side_capture_status: str = BACK_SIDE_CAPTURE_STATUS
    raw_ic_storage_status: str = RAW_IC_STORAGE_STATUS
    scan_method: str = ""
    review_status: str = ""
    review_note: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _tristate(value: object) -> str:
    """
    Render a `True | False | None` verification outcome as text.

    `str(None)` would render the literal "None", which reads as a value rather than as
    "not checked".
    """
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return text.lower()
    if text.lower() == "none":
        return ""
    return text


def reviewed_result_from_legacy(data: dict[str, object]) -> ReviewedResidenceCardResult:
    address_full = str(data.get("address_full") or data.get("address") or "")
    result = ReviewedResidenceCardResult(
        read_at=str(data.get("read_at", "")),
        reviewed_at=str(data.get("reviewed_at", "")),
        reviewed_by=str(data.get("reviewed_by", "")),
        student_id=str(data.get("student_id", "")),
        match_method=str(data.get("match_method", "")),
        card_number=str(data.get("card_number", "")),
        card_type_code=str(data.get("card_type_code", "")),
        card_type_label=str(data.get("card_type_label") or data.get("card_type") or ""),
        chip_version=str(data.get("chip_version", "")),
        birth_date=str(data.get("birth_date", "")),
        sex_code=str(data.get("sex_code") or data.get("sex") or ""),
        sex_label=str(data.get("sex_label") or data.get("sex") or ""),
        nationality_code=str(data.get("nationality_code") or data.get("nationality") or ""),
        nationality_label=str(data.get("nationality_label") or data.get("nationality") or ""),
        residence_status_code=str(data.get("residence_status_code", "")),
        residence_status_label=str(
            data.get("residence_status_label") or data.get("residence_status") or ""
        ),
        period_of_stay_raw=str(data.get("period_of_stay_raw") or data.get("period_of_stay") or ""),
        period_of_stay_label=str(data.get("period_of_stay_label") or data.get("period_of_stay") or ""),
        residence_expiry_date=str(data.get("residence_expiry_date", "")),
        card_expiry_date=str(data.get("card_expiry_date", "")),
        permission_type_code=str(data.get("permission_type_code", "")),
        permission_type_label=str(data.get("permission_type_label", "")),
        permission_date=str(data.get("permission_date", "")),
        work_restriction_code=str(data.get("work_restriction_code", "")),
        work_restriction_label=str(
            data.get("work_restriction_label") or data.get("work_restriction") or ""
        ),
        comprehensive_permission_code=str(data.get("comprehensive_permission_code", "")),
        comprehensive_permission_label=str(data.get("comprehensive_permission_label", "")),
        comprehensive_permission_expiry_date=str(
            data.get("comprehensive_permission_expiry_date", "")
        ),
        individual_permission_code=str(data.get("individual_permission_code", "")),
        individual_permission_label=str(
            data.get("individual_permission_label") or data.get("part_time_permission") or ""
        ),
        renewal_application_status=str(
            data.get("renewal_application_status") or data.get("residence_update_status") or ""
        ),
        name_ocr_candidate=str(data.get("name_ocr_candidate") or data.get("name") or ""),
        name_ocr_status=str(data.get("name_ocr_status", "")),
        name_ocr_source=str(data.get("name_ocr_source", "")),
        name_ocr_note=str(data.get("name_ocr_note", "")),
        name_ocr_confidence=str(data.get("name_ocr_confidence", "")),
        name_ocr_confidence_category=str(data.get("name_ocr_confidence_category", "")),
        name_ocr_review_required=bool(data.get("name_ocr_review_required", False)),
        name_ocr_review_reasons=list(data.get("name_ocr_review_reasons", [])) if isinstance(data.get("name_ocr_review_reasons"), list) else [],
        name_ocr_suggested_candidate=str(data.get("name_ocr_suggested_candidate", "")),
        address_full=address_full,
        address_prefecture=str(data.get("address_prefecture", "")),
        address_municipality=str(data.get("address_municipality", "")),
        address_other=str(data.get("address_other", "")),
        address_source=str(data.get("address_source") or ("chip_or_ocr_reviewed" if address_full else "")),
        address_ocr_status=str(data.get("address_ocr_status", "")),
        address_ocr_note=str(data.get("address_ocr_note", "")),
        address_ocr_confidence=str(data.get("address_ocr_confidence", "")),
        address_ocr_confidence_category=str(data.get("address_ocr_confidence_category", "")),
        address_ocr_review_required=bool(data.get("address_ocr_review_required", False)),
        address_ocr_review_reasons=list(data.get("address_ocr_review_reasons", [])) if isinstance(data.get("address_ocr_review_reasons"), list) else [],
        address_ocr_suggested_candidate=str(data.get("address_ocr_suggested_candidate", "")),
        isa_commissioner_note_code=str(data.get("isa_commissioner_note_code", "")),
        isa_commissioner_note_label=str(data.get("isa_commissioner_note_label", "")),
        reserved_note_text=str(data.get("reserved_note_text", "")),
        signature_present=_tristate(data.get("signature_present", "")),
        public_key_certificate_status=str(data.get("public_key_certificate_status", "")),
        public_key_certificate_parse_status=str(data.get("public_key_certificate_parse_status", "")),
        certificate_chain_verified=_tristate(data.get("certificate_chain_verified", "")),
        certificate_chain_verification_note=str(data.get("certificate_chain_verification_note", "")),
        signature_verified=_tristate(data.get("signature_verified", "")),
        signature_verification_status=str(data.get("signature_verification_status", "")),
        signature_verification_note=str(data.get("signature_verification_note", "")),
        scan_method=str(data.get("scan_method", "")),
        review_status=str(data.get("review_status") or data.get("export_review_status") or ""),
        review_note=str(data.get("review_note") or data.get("read_note") or ""),
    )
    return result
