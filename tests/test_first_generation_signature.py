"""Synthetic tests for the official first-generation RSA signature format."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from reader.signature import first_generation

FRONT = b"synthetic-front-image"
FACE = b"synthetic-face-image"


def _tlv(tag: str, value: bytes) -> bytes:
    length = len(value)
    if length < 0x80:
        encoded = bytes([length])
    elif length <= 0xFF:
        encoded = b"\x81" + bytes([length])
    else:
        encoded = b"\x82" + length.to_bytes(2, "big")
    return bytes.fromhex(tag) + encoded + value


def _certificate(subject: str, key, issuer, issuer_key, *, before=None, after=None):
    before = before or datetime.now(UTC) - timedelta(days=1)
    after = after or datetime.now(UTC) + timedelta(days=1)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(before)
        .not_valid_after(after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .sign(issuer_key, hashes.SHA256())
    )


@pytest.fixture
def card(monkeypatch):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SYNTHETIC RC1 CA")])
    card_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificate = _certificate("SYNTHETIC RC1 CARD", card_key, ca_name, ca_key)
    certificate_bytes = certificate.public_bytes(serialization.Encoding.DER)
    # Pad certificate to 1200 bytes representing the fixed-width card format (DB tag)
    certificate_bytes = certificate_bytes + b"\x00" * (1200 - len(certificate_bytes))

    def chain_metadata(*args, **kwargs):
        return {
            "selected_anchor_id": "synthetic-rc1-ca",
            "certificate_parse_status": "parsed",
            "trust_anchor_status": "matched",
            "certificate_chain_status": "verified",
            "certificate_validity_status": "valid",
            "anchor_validity_status": "valid",
        }

    monkeypatch.setattr(first_generation, "certificate_chain_metadata", chain_metadata)
    target = first_generation.build_signed_target(FRONT, FACE)
    assert target is not None
    try:
        signature = card_key.sign(bytes(target), padding.PKCS1v15(), hashes.SHA256())
    finally:
        first_generation.wipe(target)
    return {"ca_key": ca_key, "ca_name": ca_name, "key": card_key, "certificate": certificate_bytes, "signature": signature}


def _verify(card, **changes):
    values = {
        "signature": card["signature"],
        "certificate_bytes": card["certificate"],
        "front_image_value": FRONT,
        "face_image_value": FACE,
        "card_type_code": "1",
    }
    values.update(changes)
    return first_generation.verify_first_generation_signature(**values)


@pytest.mark.parametrize("card_type_code", ["1", "2"])
def test_valid_first_generation_signature_verifies(card, card_type_code) -> None:
    result = _verify(card, card_type_code=card_type_code)

    assert result["signature_verification_status"] == "verified_production"
    assert result["signature_verified"] is True
    assert result["production_authenticity_verified"] is True
    assert result["implementation_status"] == "implemented_unverified_on_real_hardware"


def test_signed_target_is_values_only_fixed_length_and_wiped() -> None:
    front = b"D0-not-a-tag"
    face = b"D1-not-a-tag"
    target = first_generation.build_signed_target(front, face)

    assert target is not None
    assert len(target) == 10000
    assert bytes(target[: len(front)]) == front
    assert target[7000 : 7000 + len(face)] == face
    first_generation.wipe(target)
    assert not any(target)


@pytest.mark.parametrize("field", ["front_image_value", "face_image_value"])
def test_modified_signed_component_fails(card, field: str) -> None:
    result = _verify(card, **{field: b"modified"})

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


def test_missing_signature_and_certificate_are_explicit(card) -> None:
    assert _verify(card, signature=b"")["signature_verification_status"] == "missing_signature"
    assert _verify(card, certificate_bytes=b"")["signature_verification_status"] == "missing_certificate"


def test_wrong_signature_encoding_and_target_length_fail_safely(card) -> None:
    malformed = _verify(card, signature=b"not-rsa-signature")
    too_long = _verify(card, front_image_value=b"x" * 7001)

    assert malformed["technical_category"] == "signature_encoding_invalid"
    assert too_long["technical_category"] == "unexpected_signed_target_length"
    assert too_long["signature_verified"] is None


def test_wrong_card_certificate_cannot_validate_the_signature(card) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_certificate = _certificate("OTHER SYNTHETIC CARD", other_key, card["ca_name"], card["ca_key"])
    result = _verify(card, certificate_bytes=other_certificate.public_bytes(serialization.Encoding.DER))

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


def test_wrong_anchor_and_certificate_validity_are_reported(monkeypatch, card) -> None:
    monkeypatch.setattr(
        first_generation,
        "certificate_chain_metadata",
        lambda *args, **kwargs: {
            "selected_anchor_id": "",
            "certificate_parse_status": "parsed",
            "trust_anchor_status": "untrusted",
            "certificate_chain_status": "untrusted",
            "certificate_validity_status": "valid",
            "anchor_validity_status": "not_evaluated",
        },
    )
    assert _verify(card)["signature_verification_status"] == "untrusted_certificate"

    monkeypatch.setattr(
        first_generation,
        "certificate_chain_metadata",
        lambda *args, **kwargs: {
            "selected_anchor_id": "synthetic-rc1-ca",
            "certificate_parse_status": "parsed",
            "trust_anchor_status": "matched",
            "certificate_chain_status": "verified",
            "certificate_validity_status": "expired",
            "anchor_validity_status": "historical_evaluation_required",
        },
    )
    assert _verify(card)["signature_verification_status"] == "certificate_expired"

    monkeypatch.setattr(
        first_generation,
        "certificate_chain_metadata",
        lambda *args, **kwargs: {
            "selected_anchor_id": "synthetic-rc1-ca",
            "certificate_parse_status": "parsed",
            "trust_anchor_status": "matched",
            "certificate_chain_status": "verified",
            "certificate_validity_status": "not_yet_valid",
            "anchor_validity_status": "valid",
        },
    )
    assert _verify(card)["signature_verification_status"] == "certificate_not_yet_valid"


def test_invalid_certificate_and_signature_file_are_safe(monkeypatch, card) -> None:
    monkeypatch.setattr(
        first_generation,
        "certificate_chain_metadata",
        lambda *args, **kwargs: {
            "selected_anchor_id": "",
            "certificate_parse_status": "invalid",
            "trust_anchor_status": "not_applicable",
            "certificate_chain_status": "invalid",
            "certificate_validity_status": "not_evaluated",
            "anchor_validity_status": "not_evaluated",
        },
    )
    invalid = _verify(card, certificate_bytes=b"not a certificate")
    monkeypatch.setattr(
        first_generation,
        "certificate_chain_metadata",
        lambda *args, **kwargs: {
            "selected_anchor_id": "synthetic-rc1-ca",
            "certificate_parse_status": "parsed",
            "trust_anchor_status": "matched",
            "certificate_chain_status": "verified",
            "certificate_validity_status": "valid",
            "anchor_validity_status": "valid",
        },
    )
    signature_file = _tlv("DA", card["signature"]) + _tlv("DB", card["certificate"])
    parsed = first_generation.verify_first_generation_signature_file(
        signature_file=signature_file,
        front_image_value=FRONT,
        face_image_value=FACE,
        card_type_code="1",
    )
    malformed_file = first_generation.verify_first_generation_signature_file(
        signature_file=b"\xDA\x82\x01",
        front_image_value=FRONT,
        face_image_value=FACE,
        card_type_code="1",
    )

    assert invalid["signature_verification_status"] == "certificate_invalid"
    assert parsed["signature_verified"] is True
    assert malformed_file["technical_category"] == "signature_file_invalid"


def test_safe_result_contains_no_sensitive_fixture_bytes(card) -> None:
    result = _verify(card)
    rendered = repr(result).encode("utf-8")

    assert FRONT not in rendered
    assert FACE not in rendered
    assert card["signature"] not in rendered
    assert card["certificate"] not in rendered
