"""Selection for the local OCR engine. No selection path performs network I/O.

Recognition is local ONNX Runtime CPU inference against the packaged, checksum-verified
PP-OCRv6 recognizer, and nothing else. There is deliberately no second engine: an OCR
fallback that shells out to PowerShell would write a card image to disk and spawn an
interpreter from a packaged desktop application. When the packaged model cannot be used,
the honest result is "unavailable" — structured IC-chip reading is unaffected, and staff
review every OCR-derived field anyway.
"""

from __future__ import annotations

from reader.config import get_ocr_config
from reader.ocr.engine import OcrEngine
from reader.ocr.onnx_engine import OnnxOcrEngine, UnavailableOcrEngine


def get_ocr_engine() -> OcrEngine:
    config = get_ocr_config()
    if config.engine == "onnx":
        return OnnxOcrEngine.from_assets()
    return UnavailableOcrEngine("ppocrv6", "Local OCR is disabled by configuration.")
