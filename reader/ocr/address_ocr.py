from __future__ import annotations

from typing import Any

from reader.ocr.engine import OcrEngine, OcrResult
from reader.ocr.engines import get_ocr_engine
from reader.ocr.front_text import parse_front_ocr_text
from reader.ocr.normalization import (
    address_review_reasons,
    confidence_category,
    join_address_lines,
    normalize_address_text,
)
from reader.ocr.pipeline import recognize_address_candidates
from reader.parsing.address_splitter import split_japanese_address


def extract_address_ocr_candidate(text: str) -> dict[str, str]:
    lines = normalize_address_text(text)
    normalized = "\n".join(lines)
    address = join_address_lines(lines)
    # The parser is used only to isolate an address for compatibility callers that provide
    # a multi-line whole-card result. RC2 DFD1 itself is an address-only field.
    parsed = parse_front_ocr_text(normalized) if len(lines) > 1 else {}
    if parsed.get("address"):
        address = join_address_lines(normalize_address_text(parsed["address"]))
    split = split_japanese_address(address)
    return {
        "address_full_candidate": split["address_full"],
        "address_prefecture": split["address_prefecture"],
        "address_municipality": split["address_municipality"],
        "address_other": split["address_other"],
        "address_source": "front_ocr_candidate" if address else "",
    }


def build_address_ocr_result(result: OcrResult) -> dict[str, Any]:
    """Convert local OCR text to reviewed address candidates without exposing raw OCR."""
    candidate = extract_address_ocr_candidate(result.text)
    confidence = float(result.confidence or 0.0)
    suggested = str(candidate["address_full_candidate"])
    reasons = address_review_reasons(suggested, confidence)
    candidate["address_ocr_engine"] = result.engine
    candidate["address_ocr_model"] = result.model
    candidate["address_ocr_engine_confidence"] = str(result.confidence) if result.confidence is not None else ""
    candidate["address_ocr_confidence"] = str(round(confidence, 2))
    candidate["address_ocr_confidence_category"] = confidence_category(confidence)
    candidate["address_ocr_review_required"] = bool(reasons)
    candidate["address_ocr_review_reasons"] = reasons
    candidate["address_ocr_suggested_candidate"] = suggested
    return candidate


def read_address_image(image: bytes, *, engine: OcrEngine | None = None) -> tuple[dict[str, Any], OcrResult]:
    """Recognize a transient address image in memory, returning safe field candidates."""
    result = recognize_address_candidates(engine or get_ocr_engine(), image)
    return build_address_ocr_result(result), result
