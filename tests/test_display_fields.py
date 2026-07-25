from __future__ import annotations

import pytest

from reader.display_fields import (
    build_display_fields,
    display_name,
    display_period_of_stay,
    display_qualification_activity_permission,
    display_qualification_activity_permission_detail,
    display_sex,
    display_signature_status,
    ocr_field_was_not_read,
    qualification_activity_permission_granted,
)

# --------------------------------------------------------------------------- name


def test_display_name_uses_the_ocr_candidate() -> None:
    assert display_name({"name_ocr_candidate": "YAMADA TARO"}) == "YAMADA TARO"


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("ja", "未取得（OCR確認が必要）"), ("en", "Not detected; review OCR")],
)
def test_display_name_falls_back_when_ocr_found_nothing(locale: str, expected: str) -> None:
    assert display_name({"name_ocr_candidate": ""}, locale) == expected


# ---------------------------------------------------------------------------- sex


@pytest.mark.parametrize("code", ["1", "M", "男"])
def test_sex_codes_that_mean_male(code: str) -> None:
    assert display_sex({"sex_code": code}, "ja") == "男性"
    assert display_sex({"sex_code": code}, "en") == "Male"


@pytest.mark.parametrize("code", ["2", "F", "女"])
def test_sex_codes_that_mean_female(code: str) -> None:
    assert display_sex({"sex_code": code}, "ja") == "女性"
    assert display_sex({"sex_code": code}, "en") == "Female"


@pytest.mark.parametrize("code", ["3", "X", "未指定", "9"])
def test_every_other_recognised_sex_code_maps_to_other(code: str) -> None:
    assert display_sex({"sex_code": code}, "ja") == "その他"
    assert display_sex({"sex_code": code}, "en") == "Other"


def test_missing_sex_code_renders_empty_not_other() -> None:
    assert display_sex({}, "ja") == ""


def test_sex_falls_back_to_the_label_when_no_code_is_present() -> None:
    assert display_sex({"sex_label": "女"}, "ja") == "女性"


# ----------------------------------------------------------------- period of stay


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0010", "10月"), ("0103", "1年3月"), ("0200", "2年"), ("0000", "無期限"), ("090", "90日")],
)
def test_period_of_stay_is_rendered_in_japanese(raw: str, expected: str) -> None:
    assert display_period_of_stay({"period_of_stay_raw": raw}, "ja") == expected


def test_period_of_stay_is_rendered_in_english_for_english_browsers() -> None:
    assert display_period_of_stay({"period_of_stay_raw": "0010"}, "en") == "10 months"
    assert display_period_of_stay({"period_of_stay_raw": "0000"}, "en") == "Indefinite"


def test_japanese_period_never_shows_english_wording() -> None:
    for raw in ["0010", "0103", "0000"]:
        rendered = display_period_of_stay({"period_of_stay_raw": raw}, "ja")
        assert "month" not in rendered
        assert "year" not in rendered
        assert "Indefinite" not in rendered


def test_period_falls_back_to_the_stored_label_when_no_raw_code_exists() -> None:
    assert display_period_of_stay({"period_of_stay_label": "2年"}, "ja") == "2年"


# --------------------------------------------------- qualification activity permission


def test_comprehensive_permission_grants_even_when_individual_permission_is_zero() -> None:
    data = {"comprehensive_permission_code": "1", "individual_permission_code": "0"}

    assert qualification_activity_permission_granted(data) is True
    assert display_qualification_activity_permission(data, "ja") == "あり"


def test_comprehensive_permission_grants_even_when_individual_permission_is_empty() -> None:
    data = {"comprehensive_permission_code": "2", "individual_permission_code": ""}

    assert display_qualification_activity_permission(data, "ja") == "あり"


def test_individual_permission_alone_grants() -> None:
    data = {"comprehensive_permission_code": "0", "individual_permission_code": "1"}

    assert display_qualification_activity_permission(data, "ja") == "あり"


def test_no_permission_codes_means_none() -> None:
    data = {"comprehensive_permission_code": "0", "individual_permission_code": "0"}

    assert display_qualification_activity_permission(data, "ja") == "なし"
    assert display_qualification_activity_permission(data, "en") == "Not permitted"
    assert display_qualification_activity_permission_detail(data) == ""


def test_permission_detail_prefers_the_comprehensive_label() -> None:
    data = {
        "comprehensive_permission_code": "1",
        "comprehensive_permission_label": "許可あり（原則週28時間以内・風俗営業等不可）",
        "individual_permission_code": "0",
        "individual_permission_label": "なし",
    }

    assert display_qualification_activity_permission(data, "ja") == "あり"
    assert display_qualification_activity_permission_detail(data) == "許可あり（原則週28時間以内・風俗営業等不可）"


def test_permission_detail_uses_the_individual_label_when_only_that_permission_exists() -> None:
    data = {
        "comprehensive_permission_code": "0",
        "individual_permission_code": "1",
        "individual_permission_label": "あり",
    }

    assert display_qualification_activity_permission_detail(data) == "あり"


# ---------------------------------------------------------------- signature status


@pytest.mark.parametrize(
    ("status", "ja", "en"),
    [
        ("verified_production", "真正性確認: 確認済み", "Authenticity: Verified"),
        ("verified_official_test", "真正性確認: 公的テストカードとして確認済み", "Authenticity: Verified as an official test card"),
        ("untrusted_certificate", "真正性確認: 未確認（信頼済み認証局まで確認できません）", "Authenticity: Unconfirmed (untrusted certificate)"),
        ("skipped_by_config", "署名検証: 未確認（設定によりスキップ）", "Signature: Not checked; skipped by settings"),
        (
            "certificate_unavailable",
            "署名検証: 未確認（証明書を確認できません）",
            "Signature: Not checked; certificate unavailable",
        ),
        (
            "unsupported_card_generation",
            "署名検証: 未対応（旧世代カード）",
            "Signature: Not supported for this card generation",
        ),
    ],
)
def test_signature_status_display_strings(status: str, ja: str, en: str) -> None:
    assert display_signature_status({"signature_verification_status": status}, "ja") == ja
    assert display_signature_status({"signature_verification_status": status}, "en") == en


def test_missing_dependency_reads_as_certificate_unavailable() -> None:
    assert display_signature_status({"signature_verification_status": "missing_dependency"}, "en") == (
        "Signature: Not checked; certificate unavailable"
    )


def test_missing_images_never_read_as_verified() -> None:
    assert display_signature_status({"signature_verification_status": "images_unavailable"}, "en") == (
        "Signature: Not verified"
    )


def test_signature_status_is_derived_from_older_payloads_without_a_status_field() -> None:
    assert display_signature_status({"signature_verified": True}, "en") == "Authenticity: Verified"
    assert display_signature_status({"signature_verified": "true"}, "en") == "Authenticity: Verified"
    assert display_signature_status({"signature_verified": False}, "en") == "Signature: Not verified"
    assert display_signature_status({}, "en") == "Signature: Not checked; certificate unavailable"


# ------------------------------------------------------------------------ bundle


def test_build_display_fields_returns_every_display_key() -> None:
    fields = build_display_fields(
        {
            "name_ocr_candidate": "YAMADA TARO",
            "sex_code": "1",
            "period_of_stay_raw": "0103",
            "comprehensive_permission_code": "1",
            "comprehensive_permission_label": "許可あり（原則週28時間以内・風俗営業等不可）",
            "signature_verification_status": "verified_production",
        },
        "ja",
    )

    assert fields == {
        "display_name": "YAMADA TARO",
        "display_sex": "男性",
        "display_period_of_stay": "1年3月",
        "display_qualification_activity_permission": "あり",
        "display_qualification_activity_permission_detail": "許可あり（原則週28時間以内・風俗営業等不可）",
        "display_signature_status": "真正性確認: 確認済み",
    }


# --------------------------------------------- "not read" is distinct from "review this"


def test_a_name_the_recognizer_never_produced_is_shown_as_not_read():
    """Staff cannot type a name into this application, so the two states differ.

    "Could not be read" means read it off the card and fix it downstream. "Not detected;
    review OCR" implies a candidate exists to check. Showing one for the other is wrong.
    """
    assert display_name({"name_ocr_status": "failed_model_unavailable"}, "ja") == "読み取れませんでした"
    assert display_name({"name_ocr_status": "failed_runtime_unavailable"}, "en") == "Could not be read"
    assert display_name({"name_ocr_status": "failed"}, "en") == "Could not be read"


def test_an_empty_candidate_without_a_failure_still_asks_for_review():
    assert display_name({}, "en") == "Not detected; review OCR"
    assert display_name({"name_ocr_status": "completed_local_onnx_ocr"}, "en") == "Not detected; review OCR"


def test_a_real_candidate_always_wins_over_either_placeholder():
    data = {"name_ocr_candidate": "SAMPLE NAME", "name_ocr_status": "failed_model_unavailable"}
    assert display_name(data, "en") == "SAMPLE NAME"


def test_ocr_field_not_read_detection_covers_name_and_address():
    assert ocr_field_was_not_read({"address_ocr_status": "failed_model_unavailable"}, "address") is True
    assert ocr_field_was_not_read({"address_ocr_status": "completed_local_onnx_ocr"}, "address") is False
    assert ocr_field_was_not_read({}, "address") is False
