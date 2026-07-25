"""Safe, normalized signature-verification result model.

This model deliberately contains statuses and identifiers only.  Callers must never put
card images, signatures, certificates, TLVs, APDUs, or signed targets in it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from reader.signature.trust_store import PRODUCTION_PROFILE


@dataclass(frozen=True)
class VerificationResult:
    card_generation: str = "second_generation"
    card_type_code: str = ""
    trust_profile: str = PRODUCTION_PROFILE
    selected_anchor_id: str = ""
    signature_present: bool | None = None
    certificate_present: bool | None = None
    certificate_parse_status: str = "not_evaluated"
    trust_anchor_status: str = "not_applicable"
    certificate_chain_status: str = "not_evaluated"
    certificate_validity_status: str = "not_evaluated"
    anchor_validity_status: str = "not_evaluated"
    signed_components_status: str = "not_evaluated"
    signature_status: str = "verification_error"
    signature_verified: bool | None = None
    production_authenticity_verified: bool | None = None
    review_required: bool = True
    staff_message_key: str = "signature.unconfirmed"
    technical_category: str = "verification_error"
    certificate_field_length: int | None = None
    certificate_encoding_detected: str | None = None
    certificate_normalization_status: str | None = None
    certificate_trailing_padding_length: int | None = None

    def safe_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(
            {
                "public_key_certificate_status": "present" if self.certificate_present else "not_present",
                "public_key_certificate_parse_status": self.certificate_parse_status,
                "certificate_chain_verified": (
                    None if self.certificate_chain_status == "not_evaluated" else self.certificate_chain_status == "verified"
                ),
                "signature_verification_status": self.signature_status,
                "signature_verification_note": self.staff_message_key,
            }
        )
        return result
