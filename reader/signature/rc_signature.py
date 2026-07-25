"""Second-generation signature verification with safe, profile-aware reporting."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

from reader.parsing.tlv import TlvParseError, parse_tlv_objects
from reader.signature.certificate_encoding import get_certificate_metadata, load_card_x509_certificate
from reader.signature.result import VerificationResult
from reader.signature.trust_store import (
    PRODUCTION_PROFILE,
    TrustStoreError,
    load_second_generation_trust_anchor,
    select_trust_path,
)

SIGNED_PRINTED_ENTRIES_LENGTH = 53
EXPECTED_CURVE_NAME = "secp384r1"
EXPECTED_SIGNATURE_ALGORITHM = "SHA256withECDSA"


def _not_valid_before(certificate: x509.Certificate) -> datetime:
    return certificate.not_valid_before_utc if hasattr(certificate, "not_valid_before_utc") else certificate.not_valid_before.replace(tzinfo=UTC)


def _not_valid_after(certificate: x509.Certificate) -> datetime:
    return certificate.not_valid_after_utc if hasattr(certificate, "not_valid_after_utc") else certificate.not_valid_after.replace(tzinfo=UTC)


def _certificate_validity(certificate: x509.Certificate, now: datetime) -> str:
    if now < _not_valid_before(certificate):
        return "not_yet_valid"
    if now > _not_valid_after(certificate):
        return "expired"
    return "valid"


def _anchor_validity(anchor, now: datetime) -> str:
    try:
        certificate = load_card_x509_certificate(anchor.certificate_bytes)
    except Exception:
        return "not_evaluated"
    if now < _not_valid_before(certificate):
        return "not_yet_valid"
    if now > _not_valid_after(certificate):
        # The supplied official specification does not define retrospective root-date
        # semantics.  Keep this visible without declaring an otherwise valid path invalid.
        return "historical_evaluation_required"
    return "valid"


def certificate_chain_metadata(
    certificate_bytes: bytes,
    *,
    trust_profile: str | None = None,
    card_generation: str = "second_generation",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return safe chain statuses.  The ``None`` profile keeps an old test hook usable."""
    now = now or datetime.now(UTC)
    try:
        certificate = load_card_x509_certificate(certificate_bytes)
        diag = get_certificate_metadata(certificate)
    except Exception as exc:
        # The exception text here is derived from card certificate bytes and can quote
        # ASN.1 offsets, tags, and fragments of the structure being parsed. The caller
        # already receives the same classification through the returned status fields,
        # so nothing is printed or logged.
        diag = getattr(exc, "metadata", {})
        diag_keys = {"certificate_field_length", "certificate_encoding_detected", "certificate_normalization_status", "certificate_trailing_padding_length"}
        clean_diag = {k: v for k, v in diag.items() if k in diag_keys}
        return VerificationResult(
            certificate_present=True,
            certificate_parse_status="invalid",
            trust_anchor_status="not_applicable",
            certificate_chain_status="invalid",
            signature_status="certificate_invalid",
            staff_message_key="signature.certificate_invalid",
            technical_category="certificate_invalid",
            **clean_diag,
        ).safe_dict()

    if trust_profile is None:
        # Compatibility injection point used by the existing synthetic certificate tests.
        try:
            anchor = load_second_generation_trust_anchor()
            issuer = load_card_x509_certificate(anchor.certificate_bytes)
            matched = certificate.issuer == issuer.subject and _verify_certificate_signature(certificate, issuer)
            selected_anchor_id = anchor.anchor_id if matched else ""
            anchor_status = "matched" if matched else "untrusted"
            chain_status = "verified" if matched else "untrusted"
            anchor_validity = _anchor_validity(anchor, now) if matched else "not_evaluated"
        except (TrustStoreError, ValueError):
             selected_anchor_id, anchor_status, chain_status, anchor_validity = "", "missing", "not_evaluated", "not_evaluated"
        profile = PRODUCTION_PROFILE
    else:
        path = select_trust_path(certificate, profile=trust_profile, generation=card_generation)
        selected_anchor_id = path.selected_anchor_id
        anchor_status = path.status
        chain_status = "verified" if path.status == "matched" else ("ambiguous" if path.status == "ambiguous" else "untrusted")
        anchor_validity = _anchor_validity(path.anchor, now) if path.anchor else "not_evaluated"
        profile = trust_profile
    diag_keys = {"certificate_field_length", "certificate_encoding_detected", "certificate_normalization_status", "certificate_trailing_padding_length"}
    clean_diag = {k: v for k, v in diag.items() if k in diag_keys}
    return VerificationResult(
        card_generation=card_generation,
        trust_profile=profile,
        selected_anchor_id=selected_anchor_id,
        certificate_present=True,
        certificate_parse_status="parsed",
        trust_anchor_status=anchor_status,
        certificate_chain_status=chain_status,
        certificate_validity_status=_certificate_validity(certificate, now),
        anchor_validity_status=anchor_validity,
        signature_status="verification_error",
        **clean_diag,
    ).safe_dict()


def _verify_certificate_signature(certificate: x509.Certificate, issuer: x509.Certificate) -> bool:
    from reader.signature.trust_store import _verify_certificate_signature as verify

    return verify(certificate, issuer)


def printed_entries_signed_target(printed_entries_file: bytes) -> bytes:
    try:
        values = b"".join(tlv.value for tlv in parse_tlv_objects(printed_entries_file))
    except TlvParseError:
        return b""
    if len(values) == SIGNED_PRINTED_ENTRIES_LENGTH:
        return values
    # The normal card has 53 bytes; the special permanent-resident certificate has 34
    # bytes and is explicitly NUL-padded to the same target length by the specification.
    if len(values) == 34:
        return values + bytes(SIGNED_PRINTED_ENTRIES_LENGTH - len(values))
    return b""


def build_signed_target(printed_entries_file: bytes, face_image: bytes, name_image: bytes) -> bytearray:
    padded_face = face_image + b"\x00" * max(0, 3000 - len(face_image))
    padded_name = name_image + b"\x00" * max(0, 2500 - len(name_image))
    return bytearray(printed_entries_signed_target(printed_entries_file) + padded_face + padded_name)


def wipe(buffer: bytearray | None) -> None:
    if buffer:
        for index in range(len(buffer)):
            buffer[index] = 0


def _der_signature(signature: bytes) -> bytes | None:
    try:
        decode_dss_signature(signature)
        return signature
    except (ValueError, TypeError):
        pass
    if len(signature) != 96:
        return None
    half = len(signature) // 2
    r, s = int.from_bytes(signature[:half], "big"), int.from_bytes(signature[half:], "big")
    return encode_dss_signature(r, s) if r and s else None


def _result(**changes: Any) -> dict[str, Any]:
    return VerificationResult(**changes).safe_dict()


def verify_rc2_signature(
    *,
    signature: bytes,
    certificate_bytes: bytes,
    printed_entries: bytes | None,
    face_image: bytes | None,
    name_image: bytes | None,
    full_validation_enabled: bool,
    trust_profile: str | None = None,
    card_type_code: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify exactly ``printed entries || face image || name image`` without leakage."""
    now = now or datetime.now(UTC)
    profile = trust_profile or PRODUCTION_PROFILE
    base = {"card_generation": "second_generation", "card_type_code": card_type_code, "trust_profile": profile,
            "signature_present": bool(signature), "certificate_present": bool(certificate_bytes)}
    if not full_validation_enabled:
        return _result(**base, signature_status="skipped_by_config", staff_message_key="signature.skipped_by_config", technical_category="skipped_by_config")
    if not signature:
        return _result(**base, signature_status="missing_signature", staff_message_key="signature.missing_signature", technical_category="missing_signature")
    if not certificate_bytes:
        return _result(**base, signature_status="missing_certificate", staff_message_key="signature.missing_certificate", technical_category="missing_certificate")

    metadata = certificate_chain_metadata(certificate_bytes, trust_profile=trust_profile, now=now)
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
    if not printed_entries or not printed_entries_signed_target(printed_entries) or not face_image or not name_image:
        return _result(**base, signed_components_status="missing", signature_status="missing_signed_component", staff_message_key="signature.missing_signed_component", technical_category="missing_signed_component")

    certificate = load_card_x509_certificate(certificate_bytes)
    public_key = certificate.public_key()
    # Every rejection below carries its own `technical_category`. That is the diagnostic
    # channel. Printing card-derived key, algorithm, or exception detail to a console the
    # windowed build never shows is not.
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or public_key.curve.name != EXPECTED_CURVE_NAME:
        return _result(**base, signed_components_status="complete", signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_key_invalid")
    if certificate.signature_hash_algorithm is None or certificate.signature_hash_algorithm.name != "sha256":
        return _result(**base, signed_components_status="complete", signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_signature_algorithm_invalid")
    try:
        key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
    except x509.ExtensionNotFound:
        key_usage = None
    if key_usage is not None and not key_usage.digital_signature:
        return _result(**base, signed_components_status="complete", signature_status="certificate_invalid", staff_message_key="signature.certificate_invalid", technical_category="certificate_key_usage_invalid")
    der = _der_signature(signature)
    if der is None:
        return _result(**base, signed_components_status="complete", signature_verified=False, signature_status="signature_mismatch", staff_message_key="signature.signature_mismatch", technical_category="signature_mismatch")

    target = build_signed_target(printed_entries, face_image, name_image)
    try:
        public_key.verify(der, bytes(target), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return _result(**base, signed_components_status="complete", signature_verified=False, signature_status="signature_mismatch", staff_message_key="signature.signature_mismatch", technical_category="signature_mismatch")
    except (UnsupportedAlgorithm, ValueError, TypeError):
        return _result(**base, signed_components_status="complete", signature_status="verification_error", staff_message_key="signature.verification_error", technical_category="verification_error")
    finally:
        wipe(target)

    is_production = profile == PRODUCTION_PROFILE
    status = "verified_production" if is_production else "verified_official_test"
    return _result(
        **base, signed_components_status="complete", signature_verified=True,
        production_authenticity_verified=is_production, review_required=not is_production,
        signature_status=status, staff_message_key=f"signature.{status}", technical_category=status,
    )
