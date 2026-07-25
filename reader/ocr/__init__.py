from __future__ import annotations

from reader.ocr.address_ocr import extract_address_ocr_candidate, read_address_image
from reader.ocr.engine import OcrEngine, OcrResult
from reader.ocr.engines import get_ocr_engine
from reader.ocr.front_text import (
    OcrError,
    compact_japanese_spacing,
    normalize_ocr_text,
    parse_front_ocr_text,
    repair_mojibake,
)
from reader.ocr.name_ocr import extract_name_ocr_candidate
from reader.ocr.onnx_engine import OnnxOcrEngine, UnavailableOcrEngine
from reader.ocr.pipeline import recognize_front_card_text

__all__ = [
    "OcrEngine",
    "OcrError",
    "OcrResult",
    "OnnxOcrEngine",
    "UnavailableOcrEngine",
    "compact_japanese_spacing",
    "extract_address_ocr_candidate",
    "extract_name_ocr_candidate",
    "get_ocr_engine",
    "normalize_ocr_text",
    "parse_front_ocr_text",
    "read_address_image",
    "recognize_front_card_text",
    "repair_mojibake",
]
