from __future__ import annotations

from typing import Any


def read_current_card(reader_id: int, card_number: str) -> dict[str, Any]:
    from reader.residence_card_reader import read_residence_card

    return read_residence_card(reader_id, card_number)
