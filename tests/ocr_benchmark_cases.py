"""Synthetic-only OCR benchmark corpus; no cardholder or card image data is included."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticOcrCase:
    name: str
    text: str
    field: str
    degradation: str


SYNTHETIC_OCR_CASES = (
    SyntheticOcrCase("japanese_address", "大阪府大阪市北区梅田一丁目1番3号", "address", "clean"),
    SyntheticOcrCase("katakana_building", "メディアパーク", "address", "broken_strokes"),
    SyntheticOcrCase("small_kana", "ディア", "address", "compression"),
    SyntheticOcrCase("dakuten_handakuten", "パーク", "address", "low_contrast"),
    SyntheticOcrCase("full_width_latin", "ｍａｉｓｏｎＩ　Ｎｏ．３７０５号", "address", "slight_skew"),
    SyntheticOcrCase("half_width_latin", "maisonI No.3705号", "address", "clean"),
    SyntheticOcrCase("room_number", "No.3705号", "address", "compression"),
    SyntheticOcrCase("hyphenated_address", "東京都新宿区西新宿2-8-1", "address", "low_contrast"),
    SyntheticOcrCase("mixed_lines", "大阪府大阪市北区\nMaison Park No.3705", "address", "slight_skew"),
    SyntheticOcrCase("latin_name", "O'Brien Mary-Jane", "name", "clean"),
    SyntheticOcrCase("katakana_name", "メディアパーク", "name", "broken_strokes"),
    SyntheticOcrCase("compressed_address", "愛知県名古屋市中区栄三丁目1番2号", "address", "compression"),
)
