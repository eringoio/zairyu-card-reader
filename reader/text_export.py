"""Strict, human-readable clipboard text for reviewed residence-card fields."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from reader.display_fields import build_display_fields
from reader.parsing.address_splitter import split_japanese_address
from reader.policy import forbidden_keys

MAX_CARDS = 100
MAX_OUTPUT_BYTES = 512 * 1024
MAX_VALUE_LENGTH = 4096

COPY_FIELDS = (
    ("在留カード番号", "card_number"), ("氏名", "display_name"), ("生年月日", "birth_date"),
    ("性別", "display_sex"), ("国籍・地域", "nationality_label"), ("在留資格", "residence_status_label"),
    ("在留期間", "display_period_of_stay"), ("在留期限", "residence_expiry_date"),
    ("カード有効期限", "card_expiry_date"), ("許可日", "permission_date"),
    ("都道府県", "address_prefecture"), ("市区町村", "address_municipality"), ("以降の住所", "address_other"),
    ("就労制限", "work_restriction_label"),
    ("資格外活動許可", "display_qualification_activity_permission"),
    ("資格外活動許可の詳細", "display_qualification_activity_permission_detail"),
    ("署名検証", "display_signature_status"),
)

_INPUT_FIELDS = {
    "card_number", "name_ocr_candidate", "birth_date", "sex_code", "sex_label", "nationality_label", "residence_status_label",
    "period_of_stay_raw", "period_of_stay_label", "residence_expiry_date", "card_expiry_date", "permission_date",
    "address_full", "address_prefecture", "address_municipality", "address_other", "work_restriction_label",
    "comprehensive_permission_code", "comprehensive_permission_label", "individual_permission_code",
    "individual_permission_label", "signature_verification_status", "signature_verified",
}
_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TextExportError(ValueError):
    """A deliberately value-free validation error safe to return to the browser."""


def normalize_export_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    text = str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    text = _CONTROLS.sub("", text).strip()
    if len(text) > MAX_VALUE_LENGTH:
        raise TextExportError("A copied value exceeds the permitted length.")
    return text


def _prepared(card: Mapping[str, Any]) -> dict[str, Any]:
    if forbidden_keys(card):
        raise TextExportError("The card contains a field that cannot be copied.")
    if set(card) - _INPUT_FIELDS:
        raise TextExportError("The card contains an unsupported field.")
    data = {key: card.get(key, "") for key in _INPUT_FIELDS}
    if data["address_full"] and not data["address_prefecture"]:
        data.update(split_japanese_address(str(data["address_full"])))
    # Browser-provided display_* fields are not accepted; these labels are always server derived.
    data.update(build_display_fields(data, "ja"))
    return data


def build_card_text(card: Mapping[str, Any]) -> str:
    data = _prepared(card)
    return "\n".join(f"{label}\t{normalize_export_value(data.get(key))}" for label, key in COPY_FIELDS)


def build_batch_text(cards: Sequence[Mapping[str, Any]]) -> str:
    if not cards:
        raise TextExportError("At least one card is required.")
    if len(cards) > MAX_CARDS:
        raise TextExportError("The card count exceeds the 100-card limit.")
    blocks = [build_card_text(card) for card in cards]
    text = blocks[0] if len(blocks) == 1 else "\n\n".join(
        f"【在留カード {index}/{len(blocks)}】\n{block}" for index, block in enumerate(blocks, 1)
    )
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise TextExportError("The copied text exceeds the 512 KB limit.")
    return text
