"""
Signature verification against a synthetic CA.

No real MOJ card material is used. A throwaway P-384 CA signs a throwaway card certificate,
and the card signature is produced over the same `printed entries || face image || name image`
target the real cards use.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID

from reader.parsing.second_generation_fields import parse_signature_metadata
from reader.signature import rc_signature
from reader.signature.trust_store import TrustAnchor, TrustPath, TrustStoreError

P384_SCALAR_BYTES = 48


def _tlv(tag: str, value: bytes) -> bytes:
    if len(value) < 0x80:
        length = bytes([len(value)])
    elif len(value) <= 0xFF:
        length = bytes([0x81, len(value)])
    else:
        length = bytes([0x82, (len(value) >> 8) & 0xFF, len(value) & 0xFF])
    return bytes.fromhex(tag) + length + value


def _certificate(subject: str, key, issuer_name, issuer_key, *, is_ca: bool) -> x509.Certificate:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
    )
    return builder.sign(issuer_key, hashes.SHA256())


@pytest.fixture(scope="module")
def ca() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP384R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SYNTHETIC TEST CA")])
    return key, _certificate("SYNTHETIC TEST CA", key, name, key, is_ca=True)


@pytest.fixture(scope="module")
def card(ca) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    ca_key, ca_cert = ca
    key = ec.generate_private_key(ec.SECP384R1())
    return key, _certificate("SYNTHETIC TEST CARD", key, ca_cert.subject, ca_key, is_ca=False)


@pytest.fixture
def trust_anchor(monkeypatch, ca):
    _, ca_cert = ca
    anchor = TrustAnchor(
        anchor_id="synthetic-production-ca",
        generation="second_generation",
        profile="production",
        official_source_id="synthetic",
        historical_source_id=None,
        path=Path("synthetic"),
        sha256_fingerprint="00",
        subject="CN=SYNTHETIC TEST CA",
        issuer="CN=SYNTHETIC TEST CA",
        serial_number="01",
        valid_from="2026-01-01",
        valid_until="2036-01-01",
        public_key_algorithm="ECDSA P-384",
        signature_algorithm="ecdsa-with-SHA256",
        source_retrieval_date="2026-01-01",
        source_verification_status="synthetic",
        certificate_bytes=_der_bytes(ca_cert),
    )
    monkeypatch.setattr(rc_signature, "load_second_generation_trust_anchor", lambda *args, **kwargs: anchor)
    return anchor


PRINTED_ENTRIES = b"".join(
    [
        _tlv("C5", b"20310401"),
        _tlv("C6", b"20000102"),
        _tlv("C7", b"1"),
        _tlv("C8", b"392"),
        _tlv("CE", b"0200"),
        _tlv("C9", b"x" * 29),
    ]
)
FACE_IMAGE = b"\xff\xd8synthetic-face-image"
NAME_IMAGE = b"\x49\x49synthetic-name-image"


def _raw_signature(key: ec.EllipticCurvePrivateKey, target: bytes) -> bytes:
    """Cards store `DC` as a fixed 96-byte r||s pair, not as DER."""
    der = key.sign(target, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(P384_SCALAR_BYTES, "big") + s.to_bytes(P384_SCALAR_BYTES, "big")


def _der_bytes(certificate: x509.Certificate) -> bytes:
    from cryptography.hazmat.primitives.serialization import Encoding

    return certificate.public_bytes(Encoding.DER)


def _signed_target() -> bytes:
    return bytes(rc_signature.build_signed_target(PRINTED_ENTRIES, FACE_IMAGE, NAME_IMAGE))


def _verify(card, **overrides):
    card_key, card_cert = card
    kwargs = {
        "signature": _raw_signature(card_key, _signed_target()),
        "certificate_bytes": _der_bytes(card_cert),
        "printed_entries": PRINTED_ENTRIES,
        "face_image": FACE_IMAGE,
        "name_image": NAME_IMAGE,
        "full_validation_enabled": True,
    }
    kwargs.update(overrides)
    return rc_signature.verify_rc2_signature(**kwargs)


# ------------------------------------------------------------------ signed target


def test_printed_entries_target_strips_tlv_framing_and_pads_to_53_bytes() -> None:
    target = rc_signature.printed_entries_signed_target(PRINTED_ENTRIES)

    assert target.startswith(b"20310401200001021392")
    assert len(target) == rc_signature.SIGNED_PRINTED_ENTRIES_LENGTH
    assert not target.endswith(b"\x00")


def test_special_permanent_resident_printed_entries_are_the_only_padded_shape() -> None:
    target = rc_signature.printed_entries_signed_target(_tlv("C5", b"x" * 34))

    assert target == b"x" * 34 + b"\x00" * 19
    assert rc_signature.printed_entries_signed_target(_tlv("C5", b"x" * 35)) == b""


def test_signed_target_is_printed_entries_then_face_then_name() -> None:
    target = _signed_target()

    printed = rc_signature.printed_entries_signed_target(PRINTED_ENTRIES)
    padded_face = FACE_IMAGE + b"\x00" * max(0, 3000 - len(FACE_IMAGE))
    padded_name = NAME_IMAGE + b"\x00" * max(0, 2500 - len(NAME_IMAGE))
    assert target == printed + padded_face + padded_name


def test_wipe_zeroes_the_signed_target_buffer() -> None:
    buffer = rc_signature.build_signed_target(PRINTED_ENTRIES, FACE_IMAGE, NAME_IMAGE)

    rc_signature.wipe(buffer)

    assert bytes(buffer) == bytes(len(buffer))


# -------------------------------------------------------------------- happy path


def test_valid_signature_verifies_against_the_trust_anchor(trust_anchor, card) -> None:
    result = _verify(card)

    assert result["signature_verified"] is True
    assert result["signature_verification_status"] == "verified_production"
    assert result["certificate_chain_verified"] is True
    assert result["public_key_certificate_parse_status"] == "parsed"
    assert result["production_authenticity_verified"] is True


def test_der_encoded_signature_is_also_accepted(trust_anchor, card) -> None:
    card_key, _ = card
    der = card_key.sign(_signed_target(), ec.ECDSA(hashes.SHA256()))

    result = _verify(card, signature=der)

    assert result["signature_verified"] is True


def test_official_test_success_never_claims_production_authenticity(monkeypatch, trust_anchor, card) -> None:
    test_anchor = TrustAnchor(
        anchor_id="synthetic-official-test-ca",
        generation="second_generation",
        profile="official_test",
        official_source_id="synthetic",
        historical_source_id=None,
        path=trust_anchor.path,
        subject=trust_anchor.subject,
        issuer=trust_anchor.issuer,
        serial_number="01",
        valid_from=trust_anchor.valid_from,
        valid_until=trust_anchor.valid_until,
        public_key_algorithm="ECDSA P-384",
        signature_algorithm="ecdsa-with-SHA256",
        sha256_fingerprint="00",
        source_retrieval_date="2026-01-01",
        source_verification_status="synthetic",
        certificate_bytes=trust_anchor.certificate_bytes,
    )
    monkeypatch.setattr(
        rc_signature,
        "select_trust_path",
        lambda *args, **kwargs: TrustPath("matched", test_anchor.anchor_id, test_anchor, 1, "valid"),
    )

    result = _verify(card, trust_profile="official_test")

    assert result["signature_verification_status"] == "verified_official_test"
    assert result["signature_verified"] is True
    assert result["production_authenticity_verified"] is False
    assert result["trust_profile"] == "official_test"


def test_untrusted_official_test_profile_rejects_a_production_chain(monkeypatch, trust_anchor, card) -> None:
    monkeypatch.setattr(
        rc_signature,
        "select_trust_path",
        lambda *args, **kwargs: TrustPath("untrusted", "", None, 0, "not_evaluated"),
    )

    result = _verify(card, trust_profile="official_test")

    assert result["signature_verification_status"] == "untrusted_certificate"
    assert result["production_authenticity_verified"] is None


# ------------------------------------------------------------------- tamper paths


def test_tampered_face_image_fails_verification(trust_anchor, card) -> None:
    result = _verify(card, face_image=FACE_IMAGE + b"x")

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


def test_tampered_printed_entries_fail_verification(trust_anchor, card) -> None:
    tampered = PRINTED_ENTRIES.replace(
        b"20310401",
        b"20991231",
        1,
    )
    result = _verify(card, printed_entries=tampered)

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


def test_tampered_name_image_fails_verification(trust_anchor, card) -> None:
    result = _verify(card, name_image=b"different-name-image")
    print("DEBUG RESULT:", result)
    assert result["signature_verified"] is False


def test_signature_from_an_untrusted_card_key_fails(trust_anchor, card) -> None:
    stranger = ec.generate_private_key(ec.SECP384R1())

    result = _verify(card, signature=_raw_signature(stranger, _signed_target()))

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


def test_certificate_issued_by_an_unknown_ca_is_not_trusted(trust_anchor) -> None:
    other_ca_key = ec.generate_private_key(ec.SECP384R1())
    other_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OTHER CA")])
    _certificate("OTHER CA", other_ca_key, other_name, other_ca_key, is_ca=True)
    rogue_key = ec.generate_private_key(ec.SECP384R1())
    rogue_cert = _certificate("ROGUE CARD", rogue_key, other_name, other_ca_key, is_ca=False)

    result = rc_signature.verify_rc2_signature(
        signature=_raw_signature(rogue_key, _signed_target()),
        certificate_bytes=_der_bytes(rogue_cert),
        printed_entries=PRINTED_ENTRIES,
        face_image=FACE_IMAGE,
        name_image=NAME_IMAGE,
        full_validation_enabled=True,
    )

    assert result["certificate_chain_verified"] is False
    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "untrusted_certificate"


# ---------------------------------------------------------------- degraded paths


def test_disabled_config_reports_skipped_without_touching_images(trust_anchor, card) -> None:
    result = _verify(card, full_validation_enabled=False)

    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "skipped_by_config"
    assert result["signature_verification_note"] == "signature.skipped_by_config"


def test_missing_certificate_degrades_safely(trust_anchor, card) -> None:
    result = _verify(card, certificate_bytes=b"")

    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "missing_certificate"


def test_unparseable_certificate_degrades_safely(trust_anchor, card) -> None:
    result = _verify(card, certificate_bytes=b"not a certificate")

    assert result["public_key_certificate_parse_status"] == "invalid"
    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "certificate_invalid"


def test_missing_images_degrade_safely_instead_of_claiming_verified(trust_anchor, card) -> None:
    result = _verify(card, face_image=None)

    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "missing_signed_component"


def test_missing_trust_anchor_degrades_safely(monkeypatch, card) -> None:
    def missing(*args, **kwargs):
        raise TrustStoreError("anchor file not found")

    monkeypatch.setattr(rc_signature, "load_second_generation_trust_anchor", missing)

    result = _verify(card)

    assert result["certificate_chain_verified"] is None
    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "untrusted_certificate"


def test_non_ecdsa_card_key_is_rejected(monkeypatch, ca) -> None:
    ca_key, ca_cert = ca
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_cert = _certificate("RSA CARD", rsa_key, ca_cert.subject, ca_key, is_ca=False)
    anchor = TrustAnchor(
        anchor_id="synthetic-production-ca",
        generation="second_generation",
        profile="production",
        official_source_id="synthetic",
        historical_source_id=None,
        path=Path("synthetic"),
        sha256_fingerprint="00",
        subject="CN=SYNTHETIC TEST CA",
        issuer="CN=SYNTHETIC TEST CA",
        serial_number="01",
        valid_from="2026-01-01",
        valid_until="2036-01-01",
        public_key_algorithm="ECDSA P-384",
        signature_algorithm="ecdsa-with-SHA256",
        source_retrieval_date="2026-01-01",
        source_verification_status="synthetic",
        certificate_bytes=_der_bytes(ca_cert),
    )
    monkeypatch.setattr(rc_signature, "load_second_generation_trust_anchor", lambda *a, **k: anchor)

    result = rc_signature.verify_rc2_signature(
        signature=b"\x01" * 96,
        certificate_bytes=_der_bytes(rsa_cert),
        printed_entries=PRINTED_ENTRIES,
        face_image=FACE_IMAGE,
        name_image=NAME_IMAGE,
        full_validation_enabled=True,
    )

    assert result["signature_verified"] is None
    assert result["signature_verification_status"] == "certificate_invalid"


def test_malformed_signature_value_fails_rather_than_raising(trust_anchor, card) -> None:
    result = _verify(card, signature=b"\x00" * 20)

    assert result["signature_verified"] is False
    assert result["signature_verification_status"] == "signature_mismatch"


# ------------------------------------------------------------------- no leakage


def test_verification_result_never_contains_raw_material(trust_anchor, card) -> None:
    result = _verify(card)
    text = repr(result)

    assert "synthetic-face-image" not in text
    assert "synthetic-name-image" not in text
    for value in result.values():
        assert not isinstance(value, (bytes, bytearray))
    for key in result:
        assert "bytes" not in key
        assert "signed_target" not in key


# ------------------------------------------------- DF3/EF01 TLV entry point


def test_parse_signature_metadata_verifies_the_full_df3_file(trust_anchor, card) -> None:
    card_key, card_cert = card
    signature_file = _tlv("DC", _raw_signature(card_key, _signed_target())) + _tlv("DD", _der_bytes(card_cert))

    metadata = parse_signature_metadata(
        signature_file,
        printed_entries=PRINTED_ENTRIES,
        face_image=FACE_IMAGE,
        name_image=NAME_IMAGE,
        full_validation_enabled=True,
    )

    assert metadata["signature_present"] is True
    assert metadata["public_key_certificate_status"] == "present"
    assert metadata["signature_verified"] is True
    assert metadata["signature_verification_status"] == "verified_production"


def test_parse_signature_metadata_reports_skipped_when_disabled(trust_anchor, card) -> None:
    card_key, card_cert = card
    signature_file = _tlv("DC", _raw_signature(card_key, _signed_target())) + _tlv("DD", _der_bytes(card_cert))

    metadata = parse_signature_metadata(signature_file, full_validation_enabled=False)

    assert metadata["signature_verification_status"] == "skipped_by_config"
    assert metadata["signature_verified"] is None
