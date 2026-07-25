"""Small, in-memory image preparation helpers for pre-cropped OCR fields."""

from __future__ import annotations

from io import BytesIO

VARIANT_NAMES = (
    "grayscale",
    "autocontrast",
    "upscaled_grayscale",
    "sharpened_upscale",
    "adaptive_threshold",
    "otsu_threshold",
    "inverted_threshold",
)


def _png(image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _crop_blank_margins(image):
    """Conservatively crop light, empty edges without removing character strokes."""
    from PIL import ImageChops

    # A thresholded copy makes a small amount of JPEG/MMR noise harmless.  The two-pixel
    # padding ensures a thin first/last character is not clipped.
    binary = image.point(lambda value: 0 if value < 242 else 255)
    bbox = ImageChops.invert(binary).getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    padding = 2
    return image.crop((max(0, left - padding), max(0, top - padding), min(image.width, right + padding), min(image.height, bottom + padding)))


def _estimate_skew(image) -> float:
    """Return a conservative deskew angle from horizontal ink projections."""
    import numpy as np

    if image.width < 24 or image.height < 12:
        return 0.0
    source = np.asarray(image, dtype="uint8") < 180
    best_angle = 0.0
    best_score = float(source.sum(axis=1).var())
    # Text lines become more concentrated in horizontal projections when level.  Keep the
    # search deliberately narrow: card field images should not need aggressive rotation.
    from PIL import Image
    for angle in (-1.5, -1.0, -0.5, 0.5, 1.0, 1.5):
        rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)
        projection = (np.asarray(rotated, dtype="uint8") < 180).sum(axis=1)
        score = float(projection.var())
        if score > best_score * 1.03:
            best_angle, best_score = angle, score
    return best_angle


def _adaptive_threshold(image):
    import numpy as np
    from PIL import Image, ImageFilter

    values = np.asarray(image, dtype="int16")
    # A blurred local background is a compact adaptive threshold suitable for small card
    # fields. It avoids pulling in OpenCV just for this one operation.
    background = np.asarray(image.filter(ImageFilter.BoxBlur(12)), dtype="int16")
    return Image.fromarray(np.where(values < background - 8, 0, 255).astype("uint8"))


def _otsu_threshold(image):
    import numpy as np
    from PIL import Image

    values = np.asarray(image, dtype="uint8")
    histogram = np.bincount(values.ravel(), minlength=256).astype("float64")
    total = histogram.sum()
    if not total:
        return image
    weights = histogram.cumsum()
    means = (histogram * np.arange(256)).cumsum()
    global_mean = means[-1]
    denominator = weights * (total - weights)
    variance = np.divide((global_mean * weights - means) ** 2, denominator, out=np.zeros(256), where=denominator > 0)
    threshold = int(variance.argmax())
    return Image.fromarray(np.where(values > threshold, 255, 0).astype("uint8"))


def prepare_image_variants(image_bytes: bytes) -> list[tuple[str, bytes]]:
    """Create the reusable OCR variants entirely in memory.

    Invalid input is intentionally represented by an empty list; callers then pass the
    original bytes to their OCR engine and let its normal safe-failure path report it.
    """
    try:
        from PIL import Image, ImageFilter, ImageOps
        with Image.open(BytesIO(image_bytes)) as source:
            grayscale = _crop_blank_margins(ImageOps.grayscale(source))
            angle = _estimate_skew(grayscale)
            if angle:
                grayscale = _crop_blank_margins(grayscale.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255))
            upscale = grayscale.resize((grayscale.width * 3, grayscale.height * 3), Image.Resampling.LANCZOS)
            autocontrast = ImageOps.autocontrast(grayscale)
            sharpened = ImageOps.autocontrast(upscale).filter(ImageFilter.UnsharpMask(radius=1.2, percent=160, threshold=2))
            otsu = _otsu_threshold(upscale)
            variants = {
                "grayscale": grayscale,
                "autocontrast": autocontrast,
                "upscaled_grayscale": upscale,
                "sharpened_upscale": sharpened,
                "adaptive_threshold": _adaptive_threshold(upscale),
                "otsu_threshold": otsu,
                "inverted_threshold": ImageOps.invert(otsu),
            }
            return [(name, _png(variants[name])) for name in VARIANT_NAMES]
    except Exception:
        return []


def segment_text_lines(image_bytes: bytes) -> list[bytes]:
    """Split a cropped address field by horizontal ink projections, in source order."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(BytesIO(image_bytes)) as source:
            image = _crop_blank_margins(source.convert("L"))
            ink = np.asarray(image, dtype="uint8") < 190
            rows = ink.sum(axis=1)
            occupied = rows >= max(1, int(image.width * 0.008))
            runs: list[tuple[int, int]] = []
            start: int | None = None
            for index, value in enumerate(occupied):
                if value and start is None:
                    start = index
                elif not value and start is not None:
                    if index - start >= 3:
                        runs.append((start, index))
                    start = None
            if start is not None and len(occupied) - start >= 3:
                runs.append((start, len(occupied)))
            # A single text run is not segmentation. Tiny speckles and very fragmented
            # results are safer left to the full-field recognizer.
            if not 2 <= len(runs) <= 6:
                return []
            output: list[bytes] = []
            for top, bottom in runs:
                padding = 2
                line = image.crop((0, max(0, top - padding), image.width, min(image.height, bottom + padding)))
                output.append(_png(line))
            return output
    except Exception:
        return []


def segment_front_card_text_lines(image_bytes: bytes) -> list[bytes]:
    """Extract likely printed text rows from a first-generation front-card image.

    The old-card file is a complete MMR card-face image rather than RC2's field crop.
    PP-OCRv6 is a recognizer, not a detector, so sending it the whole card is invalid.
    This conservative projection pass works over the entire card in memory. It examines
    three vertical bands so that a portrait cannot join all rows together, merges matching
    row fragments back into full text lines, and returns those lines in printed order.
    """
    try:
        import numpy as np
        from PIL import Image
        with Image.open(BytesIO(image_bytes)) as source:
            image = source.convert("L")
            width, height = image.size
            if width < 80 or height < 40:
                return []
            fragments: list[tuple[int, int, int, int]] = []
            # Non-overlapping bands preserve every part of the card while allowing a
            # tall portrait/noisy seal in one band to be discarded as non-text.
            for left, right in ((0, width // 3), (width // 3, (width * 2) // 3), ((width * 2) // 3, width)):
                region = image.crop((left, 0, right, height))
                ink = np.asarray(region, dtype="uint8") < 190
                occupied = ink.sum(axis=1) >= max(2, int(region.width * 0.008))
                start: int | None = None
                for index, value in enumerate(occupied.tolist() + [False]):
                    if value and start is None:
                        start = index
                    elif not value and start is not None:
                        if 3 <= index - start <= max(12, int(height * 0.11)):
                            line_ink = ink[start:index]
                            columns = np.where(line_ink.any(axis=0))[0]
                            if columns.size:
                                fragments.append((left + int(columns[0]), start, left + int(columns[-1]) + 1, index))
                        start = None
            if not fragments:
                return []
            fragments.sort(key=lambda item: (item[1], item[0]))
            rows: list[list[tuple[int, int, int, int]]] = []
            for fragment in fragments:
                if rows and fragment[1] <= max(item[3] for item in rows[-1]) + 3:
                    rows[-1].append(fragment)
                else:
                    rows.append([fragment])
            output: list[bytes] = []
            for row in rows[:20]:
                padding = 3
                x1 = max(0, min(item[0] for item in row) - padding)
                x2 = min(width, max(item[2] for item in row) + padding)
                y1 = max(0, min(item[1] for item in row) - padding)
                y2 = min(height, max(item[3] for item in row) + padding)
                output.append(_png(image.crop((x1, y1, x2, y2))))
            return output
    except Exception:
        return []
