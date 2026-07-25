"""Field-specific OCR text normalization and safe review scoring."""

from __future__ import annotations

import re
import unicodedata

from reader.parsing.address_splitter import PREFECTURES

JAPANESE = r"\u3040-\u30ff\u3400-\u9fff"
_JP = f"[{JAPANESE}]"
_LATIN = r"[A-Za-z]"

# OCR can substitute a simplified Han glyph for the corresponding Japanese prefecture
# glyph. Generate every mixed Japanese/simplified spelling of a complete prefecture name.
# These are deliberately full prefecture strings, not global character replacements: a
# general Chinese-to-Japanese table would damage legitimate names and addresses.
_SIMPLIFIED_PREFECTURE_GLYPHS = {
    "愛": "爱", "広": "广", "島": "岛", "徳": "德", "沖": "冲", "縄": "绳",
    "長": "长", "賀": "贺", "鳥": "鸟", "児": "儿", "葉": "叶", "馬": "马",
    "県": "县",
}


def _prefecture_ocr_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for prefecture in PREFECTURES:
        replaceable = [index for index, char in enumerate(prefecture) if char in _SIMPLIFIED_PREFECTURE_GLYPHS]
        for mask in range(1, 1 << len(replaceable)):
            characters = list(prefecture)
            for bit, index in enumerate(replaceable):
                if mask & (1 << bit):
                    characters[index] = _SIMPLIFIED_PREFECTURE_GLYPHS[characters[index]]
            aliases["".join(characters)] = prefecture
    return aliases


PREFECTURE_OCR_ALIASES = _prefecture_ocr_aliases()


def normalize_address_line(text: str) -> str:
    """Normalize one address line without collapsing meaningful Latin word spacing."""
    normalized = unicodedata.normalize("NFKC", text).replace("\t", " ")
    for alias, canonical in PREFECTURE_OCR_ALIASES.items():
        normalized = normalized.replace(alias, canonical)
    # In an address component, an at-sign between digits is an OCR zero confusion.
    # Keep @ unchanged everywhere else (for example, a legitimate Latin building name).
    normalized = re.sub(r"(?<=\d)@(?=\d)", "0", normalized)
    normalized = re.sub(r"[ \u3000]+", " ", normalized).strip()
    for _ in range(3):
        normalized = re.sub(rf"(?<={_JP}) (?={_JP})", "", normalized)
        normalized = re.sub(rf"(?<={_JP}) (?=\d)", "", normalized)
        normalized = re.sub(rf"(?<=\d) (?={_JP})", "", normalized)
        normalized = re.sub(r"(?<=\d) (?=\d)", "", normalized)
    # OCR commonly inserts a space inside `No.`. Do not join a preceding building name.
    # A zero is deliberately not accepted as an "o": `N0.` is an OCR confusion that
    # must remain visible to the reviewer instead of becoming an unchecked repair.
    normalized = re.sub(r"\bN\s*[oO]\s*\.\s*(?=\d)", "No.", normalized, flags=re.IGNORECASE)
    return normalized


def normalize_address_text(text: str) -> list[str]:
    """Retain line boundaries until the address candidate has been analysed."""
    return [line for line in (normalize_address_line(part) for part in text.splitlines()) if line]


def join_address_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    joined = lines[0]
    for line in lines[1:]:
        # Adjacent Latin portions normally need a word separator; Japanese address units
        # normally continue without one. This is deliberately not a correction dictionary.
        separator = " " if re.search(rf"{_LATIN}$", joined) or re.match(_LATIN, line) else ""
        joined += separator + line
    return joined


def normalize_name_candidate(text: str) -> str:
    """Name-only normalization: retain Latin, Katakana, spaces, hyphens and apostrophes."""
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'").replace("‘", "'").replace("‐", "-")
    normalized = re.sub(r"[^A-Za-zァ-ヶー\s.'\-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -'.")
    return normalized.upper()


def confidence_category(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def address_candidate_score(text: str, confidence: float) -> float:
    """Rank address candidates with open-ended, non-dictionary validation heuristics."""
    score = confidence
    if any(text.startswith(prefecture) for prefecture in PREFECTURES):
        score += 0.18
    if re.search(r"[市区町村郡]", text):
        score += 0.08
    if re.search(r"\d+(?:丁目|番|番地|号|[-/−]\d)", text):
        score += 0.08
    if re.search(r"[A-Za-z]", text) and re.search(_JP, text):
        score += 0.02  # mixed building names are valid, not a reason to reject a candidate
    if re.search(r"[。、】【]{2,}|[!?]{2,}", text):
        score -= 0.15
    if re.search(r"N[0O]\.?\d", text):
        score -= 0.12
    if re.search(r"(?<!\d)[Il1](?=\d)|(?<=\d)[Il1](?!\d)", text):
        score -= 0.08
    if re.search(r"(?:^|\s)[A-Za-z](?:\s|$)", text):
        score -= 0.06
    return score


def address_review_reasons(text: str, confidence: float) -> list[str]:
    reasons: list[str] = []
    if confidence < 0.60:
        reasons.append("low_confidence")
    if not text:
        return reasons or ["empty_candidate"]
    if not any(text.startswith(prefecture) for prefecture in PREFECTURES):
        reasons.append("address_pattern_unconfirmed")
    if len(re.findall(r"[。、】【]{2,}|[!?]{2,}", text)):
        reasons.append("excessive_punctuation")
    if re.search(r"[A-Za-z][ぁ-んァ-ヶ]", text) or re.search(r"[ぁ-んァ-ヶ][A-Za-z]", text):
        reasons.append("mixed_script_confusion")
    if re.search(r"N[0O]\.?\d", text):
        reasons.append("room_number_confusion")
    if re.search(r"(?<!\d)[Il1](?=\d)|(?<=\d)[Il1](?!\d)", text):
        reasons.append("ambiguous_latin_numeric")
    if "ヾ" in text or "ゞ" in text:
        reasons.append("kana_voicing_confusion")
    if re.search(r"[ァ-ヶ][―ｰ−-][ァ-ヶ]", text):
        reasons.append("horizontal_mark_confusion")
    if re.search(r"[A-Za-z]rn[A-Za-z]", text):
        reasons.append("latin_rn_confusion")
    return reasons


def name_review_reasons(text: str, confidence: float) -> list[str]:
    reasons: list[str] = []
    if confidence < 0.60:
        reasons.append("low_confidence")
    if not text:
        return reasons or ["empty_candidate"]
    if re.search(r"[A-Z][ァ-ヶ]|[ァ-ヶ][A-Z]", text):
        reasons.append("mixed_script_confusion")
    if re.search(r"[Il1]{2,}|[0O]{2,}", text):
        reasons.append("character_confusion")
    return reasons
