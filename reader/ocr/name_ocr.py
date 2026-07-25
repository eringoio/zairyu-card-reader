"""
Name-candidate extraction from the RC2 `D0` name image.

The local recognizer returns the name as one line, two lines, or a line-per-word depending
on the scan quality, and it happily emits nearby card headings as extra lines. Picking
`max(candidates, key=len)` therefore returned "RESIDENCE CARD" as often as a name.

Candidates are built from single lines and from runs of adjacent lines, then ranked: more
words and more letters score higher, headings and punctuation noise score lower. Only the
winning string leaves this module. Full OCR text and image bytes never do.
"""

from __future__ import annotations

import re
from typing import Any

from reader.i18n import DEFAULT_LOCALE, translate
from reader.ocr.engine import OcrEngine, OcrResult
from reader.ocr.engines import get_ocr_engine
from reader.ocr.front_text import normalize_ocr_text
from reader.ocr.normalization import confidence_category, name_review_reasons, normalize_name_candidate
from reader.ocr.pipeline import recognize_name_candidates

# Words printed on the card around the name. A candidate containing one of these is almost
# certainly a heading the OCR engine picked up, not a person's name.
HEADING_TOKENS = frozenset(
    {
        "ADDRESS",
        "BIRTH",
        "CARD",
        "DATE",
        "EXPIRATION",
        "EXPIRY",
        "GOVERNMENT",
        "JAPAN",
        "JUSTICE",
        "MINISTER",
        "NAME",
        "NATIONALITY",
        "NUMBER",
        "PERIOD",
        "PERMISSION",
        "REGION",
        "RESIDENCE",
        "RESTRICTION",
        "SEX",
        "STATUS",
        "STAY",
        "VALID",
        "VALIDITY",
        "WORK",
    }
)

# Longest run of adjacent OCR lines merged into one candidate. Three covers
# surname / given / middle split across separate detections.
MAX_MERGE_LINES = 3
MIN_LETTERS = 4
# Names longer than this are almost certainly a merge that swallowed something else.
MAX_PLAUSIBLE_WORDS = 5
LOW_CONFIDENCE_THRESHOLD = 0.5
# Score of a clean two-word Roman name; used to normalize the score into 0..1.
CONFIDENCE_SCALE = 45.0

WORD_BONUS = 8.0
HEADING_PENALTY = 40.0
# A real name does not repeat a word. A merge that produces "TARO YAMADA TARO SMITH" glued
# two readings of the same name together, so it must lose to the better of the two.
DUPLICATE_WORD_PENALTY = 25.0
# Merging extra lines adds words, and words add score. Without a toll every merge would beat
# every single line, and a full name sitting on one line could never win.
MERGE_LINE_PENALTY = 6.0
SINGLE_LETTER_PENALTY = 3.0
LONG_NAME_PENALTY = 10.0
PUNCTUATION_PENALTY = 5.0
UPPER_REGION_BONUS = 4.0

_LETTERS = re.compile(r"[^A-Z]")


def _clean_line(line: str) -> str:
    """Apply name-only normalization; address spacing logic is never used here."""
    return normalize_name_candidate(line)


def _tokens(candidate: str) -> list[str]:
    return [token for token in candidate.split(" ") if token]


def _is_heading_token(token: str) -> bool:
    return _LETTERS.sub("", token) in HEADING_TOKENS


def _letter_count(candidate: str) -> int:
    return sum(1 for character in candidate if character.isalpha())


def score_name_candidate(candidate: str, merged_lines: int = 1) -> float:
    """
    Rank a cleaned candidate. Returns a negative score for anything unusable.

    Word count dominates letter count so that a full "YAMADA TARO SMITH" beats a partial
    "YAMADA" even though both are plausible names.
    """
    tokens = _tokens(candidate)
    letters = _letter_count(candidate)
    if letters < MIN_LETTERS or not tokens:
        return -1.0

    words = sum(1 for token in tokens if sum(character.isalpha() for character in token) >= 2)
    if words == 0:
        return -1.0

    score = float(letters) + WORD_BONUS * words
    score -= HEADING_PENALTY * sum(1 for token in tokens if _is_heading_token(token))
    score -= DUPLICATE_WORD_PENALTY * (len(tokens) - len(set(tokens)))
    score -= MERGE_LINE_PENALTY * max(0, merged_lines - 1)
    score -= LONG_NAME_PENALTY * max(0, words - MAX_PLAUSIBLE_WORDS)
    # Over-segmented OCR ("Y A M A D A") should lose to a clean reading.
    score -= SINGLE_LETTER_PENALTY * sum(1 for token in tokens if len(token) == 1 and token.isalpha())
    punctuation = sum(1 for character in candidate if character in "-'.")
    if punctuation > words:
        score -= PUNCTUATION_PENALTY * (punctuation - words)
    return score


def _line_texts(text: str, line_details: list[dict[str, Any]] | None) -> list[str]:
    if line_details:
        return [str(detail.get("text", "")) for detail in line_details]
    return normalize_ocr_text(text).splitlines()


def _region_bonus(line_details: list[dict[str, Any]] | None, index: int) -> float:
    """
    Small nudge toward lines in the upper part of the detected region.

    The name image is cropped to the name, so a stray heading detection sits below it more
    often than above. Absent bounding boxes this contributes nothing.
    """
    if not line_details or index >= len(line_details):
        return 0.0
    tops = [float(detail.get("y", 0.0)) for detail in line_details]
    bottoms = [float(detail.get("y", 0.0)) + float(detail.get("height", 0.0)) for detail in line_details]
    span = max(bottoms, default=0.0) - min(tops, default=0.0)
    if span <= 0:
        return 0.0
    relative = (tops[index] - min(tops)) / span
    return UPPER_REGION_BONUS if relative <= 0.5 else 0.0


def rank_name_candidates(
    text: str,
    line_details: list[dict[str, Any]] | None = None,
) -> list[tuple[str, float]]:
    """Build single-line and merged-line candidates, best first."""
    raw_lines = _line_texts(text, line_details)
    cleaned = [_clean_line(line) for line in raw_lines]
    heading_line = [
        ("在留カード" in raw_lines[index])
        or (bool(_tokens(line)) and any(_is_heading_token(token) for token in _tokens(line)))
        for index, line in enumerate(cleaned)
    ]

    ranked: dict[str, float] = {}
    for start in range(len(cleaned)):
        if heading_line[start]:
            continue
        parts: list[str] = []
        for offset in range(MAX_MERGE_LINES):
            index = start + offset
            if index >= len(cleaned):
                break
            # A heading never anchors or extends a name run. Merging one in could only glue
            # the wrong words onto a name.
            if offset > 0 and (heading_line[index] or heading_line[start]):
                break
            if cleaned[index]:
                parts.append(cleaned[index])
            if not parts:
                continue
            candidate = " ".join(parts)
            score = score_name_candidate(candidate, len(parts)) + _region_bonus(line_details, start)
            if score > ranked.get(candidate, float("-inf")):
                ranked[candidate] = score

    return sorted(
        ((candidate, score) for candidate, score in ranked.items() if score > 0),
        key=lambda item: (-item[1], -len(item[0]), item[0]),
    )


def extract_name_ocr_candidate(text: str, line_details: list[dict[str, Any]] | None = None) -> str:
    """Return a normalized Latin or Katakana name candidate for staff review."""
    ranked = rank_name_candidates(text, line_details)
    return ranked[0][0] if ranked else ""


def name_candidate_confidence(score: float) -> float:
    if score <= 0:
        return 0.0
    return min(1.0, round(score / CONFIDENCE_SCALE, 2))


def build_name_ocr_result(
    text: str,
    line_details: list[dict[str, Any]] | None = None,
    *,
    locale: str = DEFAULT_LOCALE,
    max_candidates: int = 3,
) -> dict[str, Any]:
    """
    Shape the OCR outcome for the read result.

    Only names come out: no OCR full text, no bounding boxes, no image data.
    """
    ranked = rank_name_candidates(text, line_details)
    if not ranked:
        return {
            "name_ocr_candidate": "",
            "name_ocr_candidates": [],
            "name_ocr_confidence": "0.0",
            "name_ocr_confidence_category": "low",
            "name_ocr_review_required": True,
            "name_ocr_review_reasons": ["empty_candidate"],
            "name_ocr_suggested_candidate": "",
            "name_ocr_note": translate("ocr.name.low_confidence", locale),
        }

    best, score = ranked[0]
    confidence = name_candidate_confidence(score)
    result: dict[str, Any] = {
        "name_ocr_candidate": best,
        "name_ocr_candidates": [candidate for candidate, _ in ranked[:max_candidates]],
        "name_ocr_confidence": str(confidence),
        "name_ocr_confidence_category": confidence_category(confidence),
    }
    reasons = name_review_reasons(best, confidence)
    result["name_ocr_review_required"] = bool(reasons)
    result["name_ocr_review_reasons"] = reasons
    result["name_ocr_suggested_candidate"] = best
    if reasons:
        result["name_ocr_note"] = translate("ocr.name.low_confidence", locale)
    return result


def _name_result_from_ocr(ocr: OcrResult, *, locale: str) -> dict[str, Any]:
    result = build_name_ocr_result(ocr.text, None, locale=locale)
    result["name_ocr_engine"] = ocr.engine
    result["name_ocr_model"] = ocr.model
    if ocr.warnings:
        result["name_ocr_availability_warning"] = ocr.warnings[0]
    if ocr.confidence is not None:
        result["name_ocr_engine_confidence"] = str(ocr.confidence)
    return result


def read_name_image(
    png: bytes,
    *,
    locale: str = DEFAULT_LOCALE,
    engine: OcrEngine | None = None,
) -> dict[str, Any]:
    """
    OCR the transient name image through the configured local engine.

    `png` stays in the caller's memory; nothing derived from it except the ranked name
    strings is returned. The legacy PowerShell implementation is available only when a
    developer explicitly selects its separate engine.
    """
    return _name_result_from_ocr(recognize_name_candidates(engine or get_ocr_engine(), png), locale=locale)
