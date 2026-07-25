from __future__ import annotations

from reader.card_number import card_number_is_valid, normalize_card_number


def test_card_number_normalization_and_validation() -> None:
    assert normalize_card_number(" ab12345678cd ") == "AB12345678CD"
    assert card_number_is_valid(" ab12345678cd ")
    assert not card_number_is_valid("A12345678CD")
    assert not card_number_is_valid("AB1234567CDE")
