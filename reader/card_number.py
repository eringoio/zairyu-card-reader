from __future__ import annotations

import re
from typing import Any

CARD_NUMBER_RE = re.compile(r"^[A-Z]{2}\d{8}[A-Z]{2}$")


def normalize_card_number(card_number: Any) -> str:
    return str(card_number or "").strip().upper()


def card_number_is_valid(card_number: Any) -> bool:
    return bool(CARD_NUMBER_RE.fullmatch(normalize_card_number(card_number)))
