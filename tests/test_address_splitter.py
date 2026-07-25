from __future__ import annotations

from reader.parsing.address_splitter import split_japanese_address


def test_split_japanese_address_preserves_original_wording() -> None:
    address = "愛知県名古屋市中区栄三丁目1番2号"

    assert split_japanese_address(address) == {
        "address_full": address,
        "address_prefecture": "愛知県",
        "address_municipality": "名古屋市中区",
        "address_other": "栄三丁目1番2号",
    }
