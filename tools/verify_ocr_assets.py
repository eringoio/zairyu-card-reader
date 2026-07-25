"""Verify the sole bundled PP-OCRv6 asset set before producing a release."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reader.ocr.onnx_engine import OnnxOcrEngine


def main() -> int:
    engine = OnnxOcrEngine.from_assets()
    if not isinstance(engine, OnnxOcrEngine):
        print(engine.recognize_name(b"").warnings[0])
        return 1
    print(f"verified {engine.model_name}")
    print(f"input: [1, 3, 48, {engine.input_width}]")
    print(f"output classes: {engine.class_count}; dictionary entries: {len(engine.dictionary)}; blank index: {engine.blank_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
