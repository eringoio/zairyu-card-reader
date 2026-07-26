from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from reader.ocr.engine import OcrResult
from reader.ocr.front_text import parse_front_ocr_text
from reader.ocr.pipeline import recognize_front_card_text
from reader.residence_card_reader import _old_card_front_review_fields, _old_card_name_ocr_fields


def _synthetic_old_card_front() -> bytes:
    image = Image.new("L", (720, 450), color=255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    # The left-side rectangle represents the portrait area and must not join text rows.
    draw.rectangle((20, 100, 160, 330), fill=80)
    for y, text in ((55, "NAME: YAMADA TARO"), (125, "2000-01-02 M"), (195, "SAMPLELAND")):
        draw.text((210, y), text, fill=0, font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_old_card_front_is_recognized_as_separate_text_rows() -> None:
    class Engine:
        def recognize_address(self, image: bytes) -> OcrResult:
            return OcrResult(text="SAMPLE", confidence=0.99, engine="ppocrv6", model="synthetic")

    result = recognize_front_card_text(Engine(), _synthetic_old_card_front())

    assert result.engine == "ppocrv6"
    assert len(result.text.splitlines()) >= 3


def test_old_card_name_is_mapped_to_the_staff_review_field() -> None:
    parsed = parse_front_ocr_text("NAME: YAMADA TARO\n2000-01-02 M")
    fields = _old_card_name_ocr_fields(parsed, engine="ppocrv6", model="synthetic", confidence=0.99)

    assert parsed["name"] == "YAMADA TARO"
    assert fields["name_ocr_candidate"] == "YAMADA TARO"
    assert fields["name_ocr_status"] == "completed_local_onnx_ocr"


def test_old_card_parsed_fields_use_the_staff_display_contract() -> None:
    parsed = {
        "name": "YAMADA TARO", "birth_date": "2000-01-02", "sex": "M",
        "nationality": "SAMPLELAND", "residence_status": "留学", "address": "東京都新宿区西新宿2-8-1",
        "card_expiry_date": "2030-04-01", "work_restriction": "就労制限なし",
    }

    fields = _old_card_front_review_fields(parsed, engine="ppocrv6", model="synthetic", confidence=0.99)

    assert fields["name_ocr_candidate"] == "YAMADA TARO"
    assert fields["sex_code"] == "M"
    assert fields["nationality_label"] == "SAMPLELAND"
    assert fields["residence_status_label"] == "留学"
    assert fields["address_full"] == "東京都新宿区西新宿2-8-1"
    assert fields["address_ocr_status"] == "completed_local_onnx_ocr"
    assert fields["work_restriction_label"] == "就労制限なし"


def test_old_card_address_stops_before_the_next_labeled_field() -> None:
    parsed = parse_front_ocr_text("住所\n東京都新宿区西新宿2-8-1\n国籍・地域\nNEPAL\n在留資格\n留学")

    assert parsed["address"] == "東京都新宿区西新宿2-8-1"
    assert parsed["nationality"] == "NEPAL"
    assert parsed["front_ocr_address_strategy"] == "explicit_label"
    assert parsed["front_ocr_nationality_strategy"] == "explicit_label"


def test_old_card_fields_are_not_mixed_when_ocr_joins_adjacent_labels() -> None:
    parsed = parse_front_ocr_text("住所 東京都新宿区西新宿2-8-1 国籍・地域 NEPAL 在留資格 留学")

    assert parsed["address"] == "東京都新宿区西新宿2-8-1"
    assert parsed["nationality"] == "NEPAL"


def test_old_card_country_never_uses_the_one_letter_sex_marker_as_a_fallback() -> None:
    parsed = parse_front_ocr_text("2000-01-02 M\n東京都新宿区西新宿2-8-1")

    assert "nationality" not in parsed


def test_old_card_nationality_keeps_japanese_text_after_the_english_sex_marker() -> None:
    parsed = parse_front_ocr_text("2001年02月03日 男M. サンプルランド")

    assert parsed["sex"] == "M"
    assert parsed["nationality"] == "サンプルランド"


def test_old_card_rejects_an_unanchored_address_fragment() -> None:
    parsed = parse_front_ocr_text("名無し0区見本通5丁目5番地サンプル川")

    assert "address" not in parsed
    assert parsed["front_ocr_address_strategy"] == "unanchored_pattern_rejected"
