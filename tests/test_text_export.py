from pathlib import Path

import pytest

from reader.text_export import COPY_FIELDS, TextExportError, build_batch_text, build_card_text, normalize_export_value

FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "text_export"
)


def card(number="AB12345678AJ"):
    return {"card_number": number, "name_ocr_candidate": "SAMPLE NAME", "birth_date": "2000-01-01", "sex_code": "M", "nationality_label": "SAMPLELAND", "residence_status_label": "留学", "period_of_stay_label": "2年", "residence_expiry_date": "2027-04-01", "card_expiry_date": "2030-04-01", "permission_date": "2026-04-01", "address_prefecture": "東京都", "address_municipality": "新宿区", "address_other": "西新宿2-8-1 SAMPLE BUILDING 101", "work_restriction_label": "就労不可", "comprehensive_permission_code": "1", "comprehensive_permission_label": "許可あり（原則週28時間以内・風俗営業等不可）", "signature_verification_status": "verified"}


def test_single_fixture_matches_exactly():
    expected = (
        FIXTURE_DIR
        / "single_card_expected.txt"
    ).read_text(encoding="utf-8").rstrip("\n")
    assert build_card_text(card()) == expected


def test_batch_has_headers_and_one_blank_line():
    second = card("CD12345678EF"); second.update({"name_ocr_candidate":"ANOTHER PERSON", "birth_date":"2001-02-03", "sex_code":"F", "nationality_label":"NEPAL", "period_of_stay_raw":"0103", "residence_expiry_date":"2027-08-20", "card_expiry_date":"2030-08-20", "permission_date":"2026-08-21", "address_prefecture":"愛知県", "address_municipality":"名古屋市中区", "address_other":"栄1-2-3", "signature_verification_status":"unsupported_card_generation"})
    expected = (
        FIXTURE_DIR
        / "multi_card_expected.txt"
    ).read_text(encoding="utf-8").rstrip("\n")
    assert build_batch_text([card(), second]) == expected


def test_values_are_normalized_and_raw_fields_are_rejected():
    assert normalize_export_value(" a\tb\n c\x00 ") == "a b  c"
    with pytest.raises(TextExportError):
        build_card_text({**card(), "raw_tlv": "secret"})
    assert len(build_card_text({"card_number": "AB12345678AJ"}).splitlines()) == len(COPY_FIELDS)
