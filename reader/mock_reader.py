from __future__ import annotations

from datetime import datetime

from reader.policy import POLICY_STATUS_FIELDS


def get_mock_residence_card_data(card_number: str) -> dict[str, str]:
    """
    Synthetic card data. Never real student data.

    Carries the structured codes a real RC2 read produces (`sex_code`, `period_of_stay_raw`,
    permission codes) so the display layer and the simple-mode UI exercise the same paths
    they would with a card on the reader.
    """
    data = {
        "read_at": datetime.now().replace(microsecond=0).isoformat(),
        "card_number": card_number.strip().upper(),
        "name": "SAMPLE NAME",
        "name_ocr_candidate": "SAMPLE NAME",
        "name_ocr_status": "mock",
        "name_ocr_source": "mock",
        "name_ocr_confidence": "1.0",
        "birth_date": "2000-01-01",
        "sex": "M",
        "sex_code": "1",
        "sex_label": "男",
        "nationality": "SAMPLELAND",
        "address": "東京都新宿区西新宿2-8-1 SAMPLE BUILDING 101",
        "residence_status": "留学",
        "period_of_stay": "2年",
        "period_of_stay_raw": "0200",
        "residence_expiry_date": "2027-04-01",
        "card_expiry_date": "2030-04-01",
        "permission_date": "2026-04-01",
        "work_restriction": "就労不可",
        "part_time_permission": "あり",
        "comprehensive_permission_code": "1",
        "comprehensive_permission_label": "許可あり（原則週28時間以内・風俗営業等不可）",
        "comprehensive_permission_expiry_date": "2027-04-01",
        "individual_permission_code": "0",
        "individual_permission_label": "なし",
        "signature_present": "",
        "public_key_certificate_status": "not_present",
        "public_key_certificate_parse_status": "not_evaluated",
        "certificate_chain_verified": "",
        "signature_verified": "",
        "signature_verification_status": "skipped_by_config",
        "signature_verification_note": "Synthetic mock data is never an authenticity-verification result.",
        "trust_profile": "production",
        "scan_method": "mock",
        "address_write_date": "2024-04-01",
        "municipality_code": "131041",
        "residence_update_status": "無し",
        "front_side_extraction": "mock",
        "front_image_status": "mock_not_read",
        "front_image_read_status": "mock_not_read",
        "front_image_length": "",
        "front_image_format_hint": "",
        "front_ocr_status": "mock_not_read",
        "front_ocr_language": "",
        "front_ocr_text": "SAMPLE NAME\n2000-01-01 M SAMPLELAND",
        "front_ocr_parse_note": "Synthetic OCR text.",
        "chip_version": "0001",
        "card_type_code": "1",
        "card_type": "在留カード",
        "card_type_label": "在留カード",
        "export_review_status": "",
        "reviewed_at": "",
        "reviewed_by": "",
        "student_id": "",
        "match_method": "",
        "review_warnings": "",
        "read_note": "Synthetic mock data.",
        "review_note": "",
    }
    data.update(POLICY_STATUS_FIELDS)
    return data
