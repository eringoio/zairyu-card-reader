from __future__ import annotations

from typing import Any

from reader.card_type import CardTypeInfo
from reader.policy import POLICY_STATUS_FIELDS


def read_specified_residence_card(card_info: CardTypeInfo) -> dict[str, Any]:
    # Guardrail: specified cards may coexist with My Number card functions.
    # This module must only ever access the residence-card application/files.
    return {
        "success": False,
        "stage": "specified_card_blocked_by_policy",
        "message": (
            "Specified residence cards are blocked by project policy. My Number/JPKI functions, "
            "SET SESSION KEY, and RSA delivery-key flows were not accessed."
        ),
        "data": {
            **card_info.to_dict(),
            **POLICY_STATUS_FIELDS,
            "card_type": card_info.card_type_label,
            "scan_method": "blocked_by_policy",
            "read_note": "Specified-card protocol blocked. My Number/JPKI functions were not accessed.",
        },
    }
