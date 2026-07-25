from __future__ import annotations

from typing import Any

from reader.models import reviewed_result_from_legacy
from reader.parsing.address_splitter import split_japanese_address
from reader.policy import POLICY_STATUS_FIELDS


def prepare_review_data(data: dict[str, Any]) -> dict[str, str]:
    prepared = reviewed_result_from_legacy(data).to_dict()
    if prepared["address_full"] and not prepared["address_prefecture"]:
        prepared.update(split_japanese_address(prepared["address_full"]))
    prepared.update(POLICY_STATUS_FIELDS)
    return prepared
