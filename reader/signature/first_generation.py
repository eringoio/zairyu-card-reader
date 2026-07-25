"""First-generation (`1`/`2`) residence-card signature verification.

The implementation follows the first-generation public specification only.  It is kept
apart from the ECDSA-based second-generation verifier because its TLV tags, signed target,
and RSA verification rule are different.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from reader.parsing.tlv import TlvParseError, parse_tlv_objects
from reader.signature.certificate_encoding import load_card_x509_certificate
from reader.signature.rc_signature import certificate_chain_metadata
from reader.signature.result import VerificationResult
from reader.signature.trust_store import PRODUCTION_PROFILE

SIGNATURE_TAG = "DA"
CERTIFICATE_TAG = "DB"
FRONT_IMAGE_TAG = "D0"
FACE_IMAGE_TAG = "D1"
SIGNED_FRONT_IMAGE_LENGTH = 7000
SIGNED_FACE_IMAGE_LENGTH = 3000
EXPECTED_SIGNATURE_LENGTH = 256
EXPECTED_RSA_KEY_BITS = 2048
IMPLEMENTATION_STATUS = "implemented_unverified_on_real_hardware"


def wipe(buffer: bytearray | None) -> None:
    """Best-effort overwrite for a controlled mutable transient buffer."""
    if buffer:
        for index in range(len(buffer)):
            buffer[index] = 0


def _result(**changes: Any) -> dict[str, Any]:
    result = VerificationResult(**changes).safe_dict()
    # Automated fixtures exercise the format only; physical-card validation is still open.
    result["implementation_status"] = IMPLEMENTATION_STATUS
    return result


def _padded_value(value: bytes | bytearray | None, expected_length: int) -> bytes | None:
    if value is None or len(value) > expected_length:
        return None
    return bytes(value) + bytes(expected_length - len(value))


def build_signed_target(front_image_value: bytes | bytearray | None, face_image_value: bytes | bytearray | None) -> bytearray | None:
    """Build exactly ``D0.value padded to 7000 || D1.value padded to 3000``.

    TLV tag and length bytes are excluded.  The public specification requires each value
    field to reach its fixed maximum length with trailing NUL bytes before concatenation.
    """
    front = _padded_value(front_image_value, SIGNED_FRONT_IMAGE_LENGTH)
    face = _padded_value(face_image_value, SIGNED_FACE_IMAGE_LENGTH)
    if front is None or face is None:
        return None
    return bytearray(front + face)


def parse_signature_file(data: bytes | bytearray) -> tuple[bytes, bytes]:
    """Return only DA/DB values from DF3/EF01; never expose source bytes to callers."""
    objects = parse_tlv_objects(bytes(data))
    by_tag = {item.tag_hex: item.value for item in objects}
    if any(item.tag_hex not in {SIGNATURE_TAG, CERTIFICATE_TAG} for item in objects):
        raise TlvParseError("Unexpected first-generation signature-file TLV tag.")
    if len(by_tag) != len(objects):
        raise TlvParseError("Duplicate first-generation signature-file TLV tag.")
    return by_tag.get(SIGNATURE_TAG, b""), by_tag.get(CERTIFICATE_TAG, b"")


def verify_first_generation_signature(
    *,
    signature: bytes | bytearray,
    certificate_bytes: bytes | bytearray,
    front_image_value: bytes | bytearray | None,
    face_image_value: bytes | bytearray | None,
    card_type_code: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify a first-generation DA/DB signature without returning sensitive bytes."""
    now = now or datetime.now(UTC)
    base = {
        "card_generation": "first_generation",
        "card_type_code": card_type_code,
        "trust_profile": PRODUCTION_PROFILE,
        "signature_present": bool(signature),
        "certificate_present": bool(certificate_bytes),
    }
    if card_type_code not in {"1", "2"}:
        return _result(**base, signature_status="verification_error", staff_message_key="signature.verification_error", technical_category="wrong_card_type")
    if not signature:
        return _result(**base, signature_status="missing_signature", staff_message_key="signature.missing_signature", technical_category="missing_signature")
    if not certificate_bytes:
        return _result(**base, signature_status="missing_certificate", staff_message_key="signature.missing_certificate", technical_category="missing_certificate")
    if len(signature) != EXPECTED_SIGNATURE_LENGTH:
        return _result(**base, signature_verified=False, signature_status="signature_mismatch", staff_message_key="signature.signature_mismatch", technical_category="signature_encoding_invalid")

    metadata = certificate_chain_metadata(
        bytes(certificate_bytes),
        trust_profile=PRODUCTION_PROFILE,
        card_generation="first_generation",
        now=now,
    )
    base.update({
        key: metadata[key]
        for key in (
            "selected_anchor_id", "certificate_parse_status", "trust_anchor_status",
            "certificate_chain_status", "certificate_validity_status", "anchor_validity_status",
            "certificate_field_length", "certificate_encoding_detected",
            "certificate_normalization_status", "certificate_trailing_padding_length",
        )
        if key in metadata
    })
    if metadata["certificate_parse_status"] != "parsed":
        return _result(**base, signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_invalid")
    if metadata["trust_anchor_status"] == "fingerprint_mismatch":
        return _result(**base, signature_status="anchor_fingerprint_mismatch", staff_message_key="signature.anchor_fingerprint_mismatch", technical_category="anchor_fingerprint_mismatch")
    if metadata["certificate_chain_status"] == "ambiguous":
        return _result(**base, signature_status="ambiguous_trust_path", staff_message_key="signature.ambiguous_trust_path", technical_category="ambiguous_trust_path")
    if metadata["certificate_chain_status"] != "verified":
        return _result(**base, signature_status="untrusted_certificate", staff_message_key="signature.untrusted_certificate", technical_category="untrusted_certificate")
    if metadata["certificate_validity_status"] == "expired":
        return _result(**base, signature_verified=False, signature_status="certificate_expired", staff_message_key="signature.certificate_expired", technical_category="certificate_expired")
    if metadata["certificate_validity_status"] == "not_yet_valid":
        return _result(**base, signature_verified=False, signature_status="certificate_not_yet_valid", staff_message_key="signature.certificate_not_yet_valid", technical_category="certificate_not_yet_valid")

    target = build_signed_target(front_image_value, face_image_value)
    if target is None:
        return _result(**base, signed_components_status="invalid_length", signature_status="verification_error", staff_message_key="signature.verification_error", technical_category="unexpected_signed_target_length")
    try:
        certificate = load_card_x509_certificate(bytes(certificate_bytes))
        public_key = certificate.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != EXPECTED_RSA_KEY_BITS:
            return _result(**base, signed_components_status="complete", signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_key_invalid")
        try:
            key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        except x509.ExtensionNotFound:
            key_usage = None
        if key_usage is not None and not key_usage.digital_signature:
            return _result(**base, signed_components_status="complete", signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_key_usage_invalid")
        public_key.verify(bytes(signature), bytes(target), padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        return _result(**base, signed_components_status="complete", signature_verified=False, signature_status="signature_mismatch", staff_message_key="signature.signature_mismatch", technical_category="signature_mismatch")
    except (UnsupportedAlgorithm, ValueError, TypeError):
        return _result(**base, signed_components_status="complete", signature_status="verification_error", staff_message_key="signature.verification_error", technical_category="verification_error")
    finally:
        wipe(target)

    return _result(
        **base,
        signed_components_status="complete",
        signature_verified=True,
        production_authenticity_verified=True,
        review_required=False,
        signature_status="verified_production",
        staff_message_key="signature.verified_production",
        technical_category="verified_production",
    )


def verify_first_generation_signature_file(
    *,
    signature_file: bytes | bytearray,
    front_image_value: bytes | bytearray | None,
    face_image_value: bytes | bytearray | None,
    card_type_code: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Parse DF3/EF01 and verify it, returning a safe normalized result."""
    try:
        signature, certificate = parse_signature_file(signature_file)
    except TlvParseError:
        return _result(
            card_generation="first_generation", card_type_code=card_type_code, trust_profile=PRODUCTION_PROFILE,
            signature_status="verification_error", staff_message_key="signature.verification_error",
            technical_category="signature_file_invalid",
        )
    return verify_first_generation_signature(
        signature=signature,
        certificate_bytes=certificate,
        front_image_value=front_image_value,
        face_image_value=face_image_value,
        card_type_code=card_type_code,
        now=now,
    )
