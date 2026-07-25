"""Multiple local OCR passes with field-aware, image-free result selection."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from reader.ocr.engine import OcrEngine, OcrResult
from reader.ocr.normalization import (
    address_candidate_score,
    normalize_address_text,
    normalize_name_candidate,
)
from reader.ocr.preprocessing import prepare_image_variants, segment_front_card_text_lines, segment_text_lines


@dataclass(frozen=True)
class _Candidate:
    # Both forms are internal: an engine's raw reading never becomes a staff/API value.
    ocr_raw_candidate: str
    ocr_normalized_candidate: str
    confidence: float
    variant: str


def _score(text: str, confidence: float, *, field: str) -> float:
    if field == "address":
        return address_candidate_score(text, confidence)
    value = confidence
    if text:
        value += min(len(text), 32) / 320
    if field == "name" and any(character.isalpha() for character in text):
        value += 0.04
    return value


def _normalize_candidate(text: str, *, field: str) -> str:
    if field == "address":
        # Keep source line boundaries until address-specific parsing decides whether a
        # separator is meaningful (for example, in a Latin building name).
        return "\n".join(normalize_address_text(text))
    return normalize_name_candidate(text)


def _best_result(engine: OcrEngine, image: bytes, *, field: str) -> OcrResult:
    variants = prepare_image_variants(image) or [("original", image)]
    candidates: list[_Candidate] = []
    engine_name = "unavailable"
    model = ""
    warnings: list[str] = []
    for variant, prepared in variants:
        result = engine.recognize_address(prepared) if field == "address" else engine.recognize_name(prepared)
        engine_name, model = result.engine, result.model
        warnings.extend(result.warnings)
        if result.text:
            normalized = _normalize_candidate(result.text, field=field)
            if normalized:
                candidates.append(
                    _Candidate(
                        ocr_raw_candidate=result.text,
                        ocr_normalized_candidate=normalized,
                        confidence=float(result.confidence or 0.0),
                        variant=variant,
                    )
                )
        # Model unavailability cannot be improved by a different rendering of the same crop.
        if result.engine == "unavailable":
            break
    if not candidates:
        return OcrResult(engine=engine_name, model=model, warnings=list(dict.fromkeys(warnings)))
    best = max(
        candidates,
        key=lambda item: (
            _score(item.ocr_normalized_candidate, item.confidence, field=field),
            item.confidence,
            item.ocr_normalized_candidate,
        ),
    )
    return OcrResult(
        text=best.ocr_normalized_candidate,
        lines=[line for line in best.ocr_normalized_candidate.splitlines() if line],
        confidence=best.confidence,
        engine=engine_name,
        model=model,
        warnings=list(dict.fromkeys(warnings)),
    )


def recognize_name_candidates(engine: OcrEngine, image: bytes) -> OcrResult:
    return _best_result(engine, image, field="name")


def recognize_address_candidates(engine: OcrEngine, image: bytes) -> OcrResult:
    lines = segment_text_lines(image)
    if not lines:
        return _best_result(engine, image, field="address")
    results = [_best_result(engine, line, field="address") for line in lines]
    successful = [result for result in results if result.text]
    if not successful:
        return _best_result(engine, image, field="address")
    return OcrResult(
        text="\n".join(result.text for result in successful),
        lines=[result.text for result in successful],
        confidence=round(mean(result.confidence or 0.0 for result in successful), 4),
        engine=successful[0].engine,
        model=successful[0].model,
        warnings=list(dict.fromkeys(warning for result in successful for warning in result.warnings)),
    )


def recognize_front_card_text(engine: OcrEngine, image: bytes) -> OcrResult:
    """Recognize an old-card full front image one detected text row at a time.

    The protected first-generation image is usually low-contrast MMR/TIFF data.  Unlike
    an RC2 field image, a full card has no independently stored address crop, so use two
    complementary local renderings of each detected row.  This stays bounded (two passes
    per row) while making faint Japanese address strokes materially more readable.
    """
    crops = segment_front_card_text_lines(image)
    if not crops:
        return OcrResult(engine="unavailable", warnings=["No readable text rows were found in the protected front image."])
    results: list[OcrResult] = []
    for crop in crops:
        variants = dict(prepare_image_variants(crop))
        candidates: list[OcrResult] = []
        # Autocontrast preserves grayscale detail; adaptive threshold helps the printed
        # Japanese address strokes on older MMR scans.  The original crop remains the
        # safe fallback if Pillow preprocessing cannot run.
        for prepared in (variants.get("autocontrast", crop), variants.get("adaptive_threshold")):
            if not prepared:
                continue
            result = engine.recognize_address(prepared)
            if result.engine == "unavailable":
                return result
            if result.text:
                candidates.append(result)
        if candidates:
            results.append(
                max(
                    candidates,
                    key=lambda item: (_score(item.text, float(item.confidence or 0.0), field="address"), float(item.confidence or 0.0)),
                )
            )
    if not results:
        first = engine.recognize_address(crops[0])
        return OcrResult(engine=first.engine, model=first.model, warnings=first.warnings)
    return OcrResult(
        text="\n".join(result.text for result in results),
        lines=[result.text for result in results],
        confidence=round(mean(result.confidence or 0.0 for result in results), 4),
        engine=results[0].engine,
        model=results[0].model,
        warnings=list(dict.fromkeys(warning for result in results for warning in result.warnings)),
    )
