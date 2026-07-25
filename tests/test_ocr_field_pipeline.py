from __future__ import annotations

from reader.ocr.address_ocr import build_address_ocr_result, extract_address_ocr_candidate
from reader.ocr.engine import OcrResult
from reader.ocr.name_ocr import build_name_ocr_result, extract_name_ocr_candidate
from reader.ocr.normalization import (
    address_candidate_score,
    join_address_lines,
    normalize_address_line,
    normalize_address_text,
)
from reader.ocr.pipeline import recognize_address_candidates, recognize_name_candidates


def test_address_nfkc_and_mixed_script_spacing_are_preserved() -> None:
    assert normalize_address_line("ｍａｉｓｏｎＩ　Ｎｏ．３７０５号") == "maisonI No.3705号"
    assert join_address_lines(normalize_address_text("東京都千代田区\nｍａｉｓｏｎＩ　Ｎｏ．３７０５号")) == "東京都千代田区 maisonI No.3705号"


def test_address_removes_only_japanese_component_spacing() -> None:
    assert normalize_address_line("大阪 府 大阪 市 北 区 梅田 一丁目 1 番 3 号") == "大阪府大阪市北区梅田一丁目1番3号"
    assert normalize_address_line("Maison Park No. 3705") == "Maison Park No.3705"


def test_address_normalizes_known_prefecture_glyph_and_numeric_at_sign() -> None:
    assert normalize_address_line("爱知県名古屋市中区栄5@1号") == "愛知県名古屋市中区栄501号"
    assert normalize_address_line("广岛县広島市中区5@1号") == "広島県広島市中区501号"
    assert normalize_address_line("Sample Tower @ 501") == "Sample Tower @ 501"


def test_ambiguous_n_zero_is_not_silently_repaired() -> None:
    text = normalize_address_line("maisonI N0.3705号")

    assert text == "maisonI N0.3705号"
    result = build_address_ocr_result(OcrResult(text=text, confidence=0.95))
    assert "room_number_confusion" in result["address_ocr_review_reasons"]


def test_address_candidate_keeps_line_order_for_parsing() -> None:
    candidate = extract_address_ocr_candidate("大阪府大阪市北区梅田一丁目1番3号\nmaisonI No.3705号")

    assert candidate["address_prefecture"] == "大阪府"
    assert candidate["address_municipality"] == "大阪市北区"
    assert candidate["address_other"] == "梅田一丁目1番3号 maisonI No.3705号"


def test_low_confidence_mixed_script_address_requires_review_without_replacement() -> None:
    result = build_address_ocr_result(OcrResult(text="東京都新宿区メデイアヾーク", confidence=0.31))

    assert result["address_ocr_review_required"] is True
    assert "low_confidence" in result["address_ocr_review_reasons"]
    assert "kana_voicing_confusion" in result["address_ocr_review_reasons"]
    assert result["address_ocr_suggested_candidate"] == "東京都新宿区メデイアヾーク"
    assert "メディアパーク" not in result["address_ocr_suggested_candidate"]


def test_katakana_names_are_supported_without_address_correction() -> None:
    assert extract_name_ocr_candidate("メディアパーク") == "メディアパーク"
    result = build_name_ocr_result("メディアパーク")
    assert result["name_ocr_suggested_candidate"] == "メディアパーク"
    assert result["name_ocr_review_required"] is True


def test_name_candidate_preserves_name_punctuation_and_latin_spacing() -> None:
    assert extract_name_ocr_candidate("Ｏ’Ｂｒｉｅｎ　Ｍａｒｙ－Ｊａｎｅ") == "O'BRIEN MARY-JANE"


def test_safe_address_result_does_not_include_raw_candidate_or_images() -> None:
    result = build_address_ocr_result(OcrResult(text="大阪府大阪市北区梅田一丁目1番3号", confidence=0.95))

    assert "ocr_raw_candidate" not in result
    assert "image" not in repr(result).lower()
    assert result["address_ocr_confidence_category"] == "high"


def test_address_validation_prefers_a_plausible_numbered_address() -> None:
    assert address_candidate_score("大阪府大阪市北区梅田一丁目1番3号", 0.6) > address_candidate_score("大阪府!?!? N0.3 I", 0.6)


def test_pipeline_uses_safe_original_bytes_when_image_cannot_be_decoded() -> None:
    class Engine:
        def recognize_name(self, image: bytes) -> OcrResult:
            return OcrResult()

        def recognize_address(self, image: bytes) -> OcrResult:
            assert image == b"not-an-image"
            return OcrResult(text="大阪府大阪市北区梅田一丁目1番3号", confidence=0.9, engine="synthetic")

    result = recognize_address_candidates(Engine(), b"not-an-image")

    assert result.text.startswith("大阪府")
    assert result.confidence == 0.9


def test_pipeline_normalizes_engine_text_before_returning_it() -> None:
    class Engine:
        def recognize_name(self, image: bytes) -> OcrResult:
            assert image == b"not-an-image"
            return OcrResult(text="Ｏ’Ｂｒｉｅｎ　Ｍａｒｙ－Ｊａｎｅ", confidence=0.9, engine="synthetic")

        def recognize_address(self, image: bytes) -> OcrResult:
            return OcrResult()

    result = recognize_name_candidates(Engine(), b"not-an-image")

    assert result.text == "O'BRIEN MARY-JANE"
    assert "ocr_raw_candidate" not in repr(result)
