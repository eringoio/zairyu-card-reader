from __future__ import annotations

import re

PREFECTURES = (
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
)


def split_japanese_address(address: str) -> dict[str, str]:
    full = address.strip()
    result = {
        "address_full": full,
        "address_prefecture": "",
        "address_municipality": "",
        "address_other": full,
    }
    prefecture = next((candidate for candidate in PREFECTURES if full.startswith(candidate)), "")
    if not prefecture:
        return result

    rest = full[len(prefecture) :]
    match = re.match(r"(.+?市.+?区)(.+)$", rest)
    if match is None:
        match = re.match(r"(.+?[市区町村])(.+)$", rest)
    municipality = match.group(1) if match else rest
    other = match.group(2) if match else ""
    return {
        "address_full": full,
        "address_prefecture": prefecture,
        "address_municipality": municipality,
        "address_other": other,
    }
