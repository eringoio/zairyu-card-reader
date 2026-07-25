"""Generate deliberately degraded synthetic OCR images for a staged local benchmark."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from tests.ocr_benchmark_cases import SYNTHETIC_OCR_CASES


def degrade(image: Image.Image, mode: str, seed: int) -> Image.Image:
    random.seed(seed)
    if mode == "low_contrast":
        return ImageEnhance.Contrast(image).enhance(0.45)
    if mode == "broken_strokes":
        return image.filter(ImageFilter.MinFilter(3))
    if mode == "compression":
        # JPEG round-trip is intentional only for generated synthetic images.
        from io import BytesIO
        output = BytesIO()
        image.save(output, format="JPEG", quality=28)
        output.seek(0)
        return Image.open(output).convert("L")
    if mode == "slight_skew":
        # Synthetic benchmark images only; nothing here is a security decision.
        return image.rotate(random.choice((-1.2, -0.8, 0.8, 1.2)), fillcolor=255)  # noqa: S311
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True, help="A locally installed font covering Japanese glyphs.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(args.font), 36)
    for index, case in enumerate(SYNTHETIC_OCR_CASES):
        lines = case.text.splitlines()
        image = Image.new("L", (900, 72 * len(lines) + 24), color=255)
        draw = ImageDraw.Draw(image)
        for line_index, line in enumerate(lines):
            draw.text((16, 12 + line_index * 68), line, fill=0, font=font)
        degrade(image, case.degradation, index).save(args.output / f"{index:02d}-{case.name}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
