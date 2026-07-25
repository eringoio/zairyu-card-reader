"""Tests for the shared certificate loader and normalization helper."""

from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from reader.signature.certificate_encoding import (
    CardCertificateEncodingError,
    get_certificate_metadata,
    load_card_x509_certificate,
)
from reader.signature.rc_signature import verify_rc2_signature
from reader.signature.trust_store import TrustAnchor


@pytest.fixture(scope="module")
def synthetic_cert_and_keys():
    # Generate a key pair
    private_key = ec.generate_private_key(ec.SECP384R1())
    public_key = private_key.public_key()

    # Generate a synthetic self-signed certificate
    name = x509.Name([
        x509.NameAttribute(x509.NameOID.COMMON_NAME, "SYNTHETIC CARD TEST"),
        x509.NameAttribute(x509.NameOID.COUNTRY_NAME, "JP"),
    ])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    der_bytes = cert.public_bytes(serialization.Encoding.DER)
    return cert, der_bytes, private_key


def _make_indefinite_length_ber(der: bytes) -> bytes:
    """Manually convert a top-level SEQUENCE in DER to indefinite length BER."""
    assert der[0] == 0x30
    if der[1] < 0x80:
        header_len = 2
    else:
        header_len = 2 + (der[1] & 0x7f)
    return b"\x30\x80" + der[header_len:] + b"\x00\x00"


def test_1_exact_der_certificate(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    cert = load_card_x509_certificate(der_bytes)
    assert isinstance(cert, x509.Certificate)

    meta = get_certificate_metadata(cert)
    assert meta["certificate_encoding_detected"] == "der"
    assert meta["certificate_normalization_status"] == "exact_der"
    assert meta["certificate_trailing_padding_length"] == 0
    assert meta["certificate_field_length"] == len(der_bytes)


def test_2_der_certificate_followed_by_zero_padding(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    padded = der_bytes + b"\x00" * 128
    cert = load_card_x509_certificate(padded)
    assert isinstance(cert, x509.Certificate)

    meta = get_certificate_metadata(cert)
    assert meta["certificate_encoding_detected"] == "der"
    assert meta["certificate_normalization_status"] == "normalized"
    assert meta["certificate_trailing_padding_length"] == 128
    assert meta["certificate_field_length"] == len(padded)


def test_3_ber_indefinite_length_certificate_normalizes(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    ber_bytes = _make_indefinite_length_ber(der_bytes)

    cert = load_card_x509_certificate(ber_bytes)
    assert isinstance(cert, x509.Certificate)

    meta = get_certificate_metadata(cert)
    assert meta["certificate_encoding_detected"] == "ber_cer"
    assert meta["certificate_normalization_status"] == "normalized"
    assert meta["certificate_trailing_padding_length"] == 0


def test_4_ber_indefinite_length_certificate_followed_by_zero_padding(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    ber_bytes = _make_indefinite_length_ber(der_bytes)

    padded = ber_bytes + b"\x00" * 64
    cert = load_card_x509_certificate(padded)
    assert isinstance(cert, x509.Certificate)

    meta = get_certificate_metadata(cert)
    assert meta["certificate_encoding_detected"] == "ber_cer"
    assert meta["certificate_normalization_status"] == "normalized"
    assert meta["certificate_trailing_padding_length"] == 64


def test_5_non_zero_trailing_bytes_are_rejected(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    # DER with non-zero trailing
    with pytest.raises(CardCertificateEncodingError) as exc_info:
        load_card_x509_certificate(der_bytes + b"\x01")
    assert "Non-zero trailing bytes" in str(exc_info.value)
    assert exc_info.value.metadata["certificate_trailing_padding_length"] == 1

    # BER with non-zero trailing
    ber_bytes = _make_indefinite_length_ber(der_bytes)
    with pytest.raises(CardCertificateEncodingError) as exc_info:
        load_card_x509_certificate(ber_bytes + b"\x00\x00\x02\x00")
    assert "Non-zero trailing bytes" in str(exc_info.value)
    assert exc_info.value.metadata["certificate_trailing_padding_length"] == 4


def test_6_truncated_certificate_is_rejected(synthetic_cert_and_keys) -> None:
    _, der_bytes, _ = synthetic_cert_and_keys
    truncated = der_bytes[:-10]
    with pytest.raises(CardCertificateEncodingError) as exc_info:
        load_card_x509_certificate(truncated)
    assert exc_info.value.metadata["certificate_parse_status"] == "invalid"


def test_7_random_bytes_are_rejected() -> None:
    with pytest.raises(CardCertificateEncodingError) as exc_info:
        load_card_x509_certificate(b"random garbage bytes here")
    assert exc_info.value.metadata["certificate_parse_status"] == "invalid"


def test_8_empty_certificate_field_is_rejected() -> None:
    with pytest.raises(CardCertificateEncodingError) as exc_info:
        load_card_x509_certificate(b"")
    assert exc_info.value.metadata["certificate_parse_status"] == "invalid"
    assert exc_info.value.metadata["certificate_field_length"] == 0


def test_9_normalized_certificate_preserves_fields(synthetic_cert_and_keys) -> None:
    original_cert, der_bytes, _ = synthetic_cert_and_keys
    ber_bytes = _make_indefinite_length_ber(der_bytes)

    normalized_cert = load_card_x509_certificate(ber_bytes)

    assert normalized_cert.subject == original_cert.subject
    assert normalized_cert.issuer == original_cert.issuer
    assert normalized_cert.serial_number == original_cert.serial_number
    assert normalized_cert.not_valid_before_utc == original_cert.not_valid_before_utc
    assert normalized_cert.not_valid_after_utc == original_cert.not_valid_after_utc
    assert normalized_cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) == original_cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def test_10_no_raw_certificate_bytes_appear_in_verification_result(monkeypatch, synthetic_cert_and_keys) -> None:
    cert, der_bytes, key = synthetic_cert_and_keys

    # Setup monkeypatched trust store
    from pathlib import Path
    anchor = TrustAnchor(
        anchor_id="synthetic-production-ca",
        generation="second_generation",
        profile="production",
        official_source_id="synthetic",
        historical_source_id=None,
        path=Path("synthetic"),
        sha256_fingerprint="00",
        subject=cert.issuer.rfc4514_string(),
        issuer=cert.issuer.rfc4514_string(),
        serial_number=hex(cert.serial_number),
        valid_from="2026-01-01",
        valid_until="2036-01-01",
        public_key_algorithm="ECDSA P-384",
        signature_algorithm="ecdsa-with-SHA256",
        source_retrieval_date="2026-01-01",
        source_verification_status="synthetic",
        certificate_bytes=der_bytes,
    )
    monkeypatch.setattr("reader.signature.rc_signature.load_second_generation_trust_anchor", lambda *a, **k: anchor)

    from tests.test_signature import FACE_IMAGE, NAME_IMAGE, PRINTED_ENTRIES, _raw_signature, _signed_target
    sig = _raw_signature(key, _signed_target())

    # Verify signature
    result = verify_rc2_signature(
        signature=sig,
        certificate_bytes=der_bytes + b"\x00" * 64, # Padded raw certificate
        printed_entries=PRINTED_ENTRIES,
        face_image=FACE_IMAGE,
        name_image=NAME_IMAGE,
        full_validation_enabled=True,
    )

    # Check for raw bytes leakage
    rendered = repr(result)
    assert "different-name-image" not in rendered
    assert "synthetic-face-image" not in rendered
    assert "synthetic-name-image" not in rendered
    # Raw certificate bytes should not be in the dictionary values or keys
    for k, v in result.items():
        assert not isinstance(v, (bytes, bytearray))
        assert "bytes" not in k
        assert "signed_target" not in k

    # Diagnostic metadata should be populated
    assert result["certificate_field_length"] == len(der_bytes) + 64
    assert result["certificate_encoding_detected"] == "der"
    assert result["certificate_normalization_status"] == "normalized"
    assert result["certificate_trailing_padding_length"] == 64
