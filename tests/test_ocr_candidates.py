from __future__ import annotations

from reader.ocr.address_ocr import extract_address_ocr_candidate
from reader.ocr.name_ocr import extract_name_ocr_candidate


def test_name_ocr_candidate_returns_only_uppercase_roman_name() -> None:
    candidate = extract_name_ocr_candidate("在留カード\nYamada Taro-Smith\n山田太郎")

    assert candidate == "YAMADA TARO-SMITH"


def test_address_ocr_candidate_splits_preserved_address() -> None:
    candidate = extract_address_ocr_candidate(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000年01月02日 男 SAMPLELAND",
                "大阪府大阪市北区梅田一丁目1番3号",
                "留学",
            ]
        )
    )

    assert candidate["address_full_candidate"] == "大阪府大阪市北区梅田一丁目1番3号"
    assert candidate["address_prefecture"] == "大阪府"
    assert candidate["address_municipality"] == "大阪市北区"
    assert candidate["address_other"] == "梅田一丁目1番3号"
