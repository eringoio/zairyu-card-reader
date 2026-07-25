from __future__ import annotations

from types import SimpleNamespace

from reader.ocr.engine import OcrResult
from reader.ocr.name_ocr import (
    LOW_CONFIDENCE_THRESHOLD,
    build_name_ocr_result,
    extract_name_ocr_candidate,
    rank_name_candidates,
    read_name_image,
    score_name_candidate,
)

# ------------------------------------------------------------------ extraction


def test_single_line_roman_name_is_uppercased_and_kept() -> None:
    assert extract_name_ocr_candidate("在留カード\nYamada Taro-Smith\n山田太郎") == "YAMADA TARO-SMITH"


def test_name_split_across_two_ocr_lines_is_combined() -> None:
    assert extract_name_ocr_candidate("YAMADA\nTARO SMITH") == "YAMADA TARO SMITH"


def test_name_split_across_three_ocr_lines_is_combined() -> None:
    assert extract_name_ocr_candidate("YAMADA\nTARO\nSMITH") == "YAMADA TARO SMITH"


def test_heading_text_is_never_selected_as_the_name() -> None:
    candidate = extract_name_ocr_candidate("RESIDENCE CARD\nPERMISSION TO WORK\nYAMADA TARO")

    assert candidate == "YAMADA TARO"


def test_heading_only_input_yields_no_candidate() -> None:
    assert extract_name_ocr_candidate("RESIDENCE CARD\nVALIDITY PERIOD\nSTATUS OF RESIDENCE") == ""


def test_a_heading_is_never_glued_onto_the_front_of_a_name() -> None:
    candidate = extract_name_ocr_candidate("RESIDENCE CARD\nMARIA SANTOS")

    assert candidate == "MARIA SANTOS"
    assert "RESIDENCE" not in candidate


def test_partial_short_candidate_loses_to_a_fuller_multi_word_candidate() -> None:
    ranked = dict(rank_name_candidates("TARO\nYAMADA TARO SMITH"))

    assert max(ranked, key=ranked.get) == "YAMADA TARO SMITH"
    assert ranked["YAMADA TARO SMITH"] > ranked["TARO"]


def test_punctuation_and_digit_noise_is_normalized_away() -> None:
    assert extract_name_ocr_candidate("###YAMADA  TARO 12345!!") == "YAMADA TARO"


def test_valid_name_punctuation_is_preserved() -> None:
    assert extract_name_ocr_candidate("O'BRIEN MARY-JANE") == "O'BRIEN MARY-JANE"
    assert extract_name_ocr_candidate("SMITH JR. JOHN") == "SMITH JR. JOHN"


def test_over_segmented_single_letters_lose_to_a_clean_reading() -> None:
    ranked = dict(rank_name_candidates("Y A M A D A\nYAMADA TARO"))

    assert max(ranked, key=ranked.get) == "YAMADA TARO"


def test_japanese_only_text_yields_no_roman_candidate() -> None:
    assert extract_name_ocr_candidate("山田太郎\n在留カード") == ""


def test_short_fragments_are_rejected() -> None:
    assert score_name_candidate("AB") < 0
    assert extract_name_ocr_candidate("AB") == ""


def test_a_merge_scores_lower_than_the_same_text_read_from_one_line() -> None:
    """The toll breaks ties toward the simpler reading rather than the longest run."""
    single = score_name_candidate("YAMADA TARO SMITH", merged_lines=1)
    merged = score_name_candidate("YAMADA TARO SMITH", merged_lines=3)

    assert merged < single


def test_a_merge_that_repeats_a_word_loses_to_its_best_single_line() -> None:
    ranked = dict(rank_name_candidates("YAMADA TARO SMITH\nSMITH"))

    assert max(ranked, key=ranked.get) == "YAMADA TARO SMITH"


def test_merging_still_wins_when_the_extra_line_is_a_real_name_word() -> None:
    ranked = dict(rank_name_candidates("YAMADA\nTARO SMITH"))

    assert max(ranked, key=ranked.get) == "YAMADA TARO SMITH"


# ---------------------------------------------------------------- bounding boxes


def test_line_details_are_used_when_present() -> None:
    details = [
        {"text": "YAMADA TARO", "x": 0.0, "y": 0.0, "width": 100.0, "height": 20.0},
        {"text": "RESIDENCE CARD", "x": 0.0, "y": 60.0, "width": 100.0, "height": 20.0},
    ]

    assert extract_name_ocr_candidate("", details) == "YAMADA TARO"


def test_upper_region_lines_are_preferred_between_equal_candidates() -> None:
    details = [
        {"text": "TARO YAMADA", "x": 0.0, "y": 0.0, "width": 100.0, "height": 20.0},
        {"text": "YAMADA TAROX", "x": 0.0, "y": 90.0, "width": 100.0, "height": 20.0},
    ]
    ranked = dict(rank_name_candidates("", details))

    assert ranked["TARO YAMADA"] > ranked["YAMADA TAROX"]


# --------------------------------------------------------------------- result


def test_result_reports_candidates_and_confidence() -> None:
    result = build_name_ocr_result("YAMADA TARO SMITH\nTARO")

    assert result["name_ocr_candidate"] == "YAMADA TARO SMITH"
    assert "YAMADA TARO SMITH" in result["name_ocr_candidates"]
    assert float(result["name_ocr_confidence"]) > LOW_CONFIDENCE_THRESHOLD
    assert "name_ocr_note" not in result


def test_result_adds_a_low_confidence_note_in_japanese() -> None:
    result = build_name_ocr_result("TARO", locale="ja")

    assert result["name_ocr_candidate"] == "TARO"
    assert float(result["name_ocr_confidence"]) < LOW_CONFIDENCE_THRESHOLD
    assert result["name_ocr_note"] == "氏名OCRの信頼度が低いため、確認してください。"


def test_result_adds_a_low_confidence_note_in_english() -> None:
    result = build_name_ocr_result("TARO", locale="en")

    assert result["name_ocr_note"] == "Name OCR confidence is low; please review."


def test_empty_ocr_text_reports_zero_confidence() -> None:
    result = build_name_ocr_result("")

    assert result["name_ocr_candidate"] == ""
    assert result["name_ocr_confidence"] == "0.0"
    assert result["name_ocr_note"]


def test_result_never_contains_full_ocr_text_or_bounding_boxes() -> None:
    details = [{"text": "YAMADA TARO", "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}]
    result = build_name_ocr_result("YAMADA TARO\n在留カード 2000年01月02日", details)

    text = repr(result)
    assert "在留カード" not in text
    assert "2000年" not in text
    assert "width" not in text
    assert set(result) <= {
        "name_ocr_candidate",
        "name_ocr_candidates",
        "name_ocr_confidence",
        "name_ocr_confidence_category",
        "name_ocr_review_required",
        "name_ocr_review_reasons",
        "name_ocr_suggested_candidate",
        "name_ocr_note",
    }


# ------------------------------------------------------- multi-variant OCR driver


def test_read_name_image_stops_at_the_first_confident_variant(monkeypatch) -> None:
    calls: list[bytes] = []

    def fake_ocr(png):
        calls.append(png)
        return OcrResult(text="YAMADA TARO SMITH", engine="onnxruntime_cpu", model="synthetic")

    monkeypatch.setattr("reader.ocr.name_ocr.get_ocr_engine", lambda: SimpleNamespace(recognize_name=fake_ocr))

    result = read_name_image(b"png")

    assert result["name_ocr_candidate"] == "YAMADA TARO SMITH"
    assert calls == [b"png"]


def test_read_name_image_keeps_the_best_variant_when_the_first_is_weak(monkeypatch) -> None:
    def fake_ocr(png):
        return OcrResult(text="YAMADA TARO SMITH", engine="onnxruntime_cpu", model="synthetic")

    monkeypatch.setattr("reader.ocr.name_ocr.get_ocr_engine", lambda: SimpleNamespace(recognize_name=fake_ocr))

    result = read_name_image(b"png")

    assert result["name_ocr_candidate"] == "YAMADA TARO SMITH"
    assert result["name_ocr_engine"] == "onnxruntime_cpu"


def test_read_name_image_raises_when_every_variant_fails(monkeypatch) -> None:
    def fake_ocr(png):
        return OcrResult(engine="unavailable", warnings=["Local OCR model assets are not packaged."])

    monkeypatch.setattr("reader.ocr.name_ocr.get_ocr_engine", lambda: SimpleNamespace(recognize_name=fake_ocr))

    result = read_name_image(b"png")

    assert result["name_ocr_candidate"] == ""
    assert result["name_ocr_engine"] == "unavailable"


def test_read_name_image_returns_an_empty_candidate_when_ocr_finds_no_name(monkeypatch) -> None:
    monkeypatch.setattr("reader.ocr.name_ocr.get_ocr_engine", lambda: SimpleNamespace(
        recognize_name=lambda png: OcrResult(text="在留カード", engine="onnxruntime_cpu", model="synthetic")
    ))

    result = read_name_image(b"png")

    assert result["name_ocr_candidate"] == ""

