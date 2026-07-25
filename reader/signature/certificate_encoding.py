"""Shared certificate loading and normalization helper for Japanese residence cards."""

from __future__ import annotations

from typing import Any

from cryptography import x509
from pyasn1.codec.ber import decoder as ber_decoder
from pyasn1.codec.der import encoder as der_encoder
from pyasn1_modules import rfc2459


class CardCertificateEncodingError(ValueError):
    """Exception raised for malformed card-certificate fields."""

    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


# Use a global registry keyed by object ID since cryptography Certificate instances
# in newer versions are Rust-backed and do not allow custom attribute assignment
# or weak references.
_metadata_registry: dict[int, dict[str, Any]] = {}


def get_certificate_metadata(cert: x509.Certificate) -> dict[str, Any]:
    """Retrieve diagnostic metadata for a successfully loaded certificate."""
    return _metadata_registry.get(id(cert), {})


def load_card_x509_certificate(raw: bytes) -> x509.Certificate:
    """Load an X.509 certificate from raw card bytes, supporting normalization of BER/CER and padded DER.

    Return the parsed cryptography.x509.Certificate. Diagnostic metadata can be retrieved
    via get_certificate_metadata(cert).
    """
    if not raw:
        metadata = {
            "certificate_field_length": 0,
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": 0,
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError("Empty certificate field", metadata)

    # 1. First support a normal exact DER certificate
    try:
        cert = x509.load_der_x509_certificate(raw)
        # Attach diagnostic metadata
        _metadata_registry[id(cert)] = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "der",
            "certificate_normalization_status": "exact_der",
            "certificate_trailing_padding_length": 0,
        }
        return cert
    except Exception:
        pass

    # 2. Safely decode the field as BER/CER ASN.1 X.509
    #
    # Each `raise ... from None` below is deliberate. These exceptions come from parsing
    # bytes read off a card, and an ASN.1 decoder's message can quote offsets, tags, and
    # fragments of the structure it choked on. Suppressing the chained cause keeps that
    # detail out of any traceback that might ever be produced; callers use the structured
    # `metadata` instead, which contains only lengths and status codes.
    try:
        cert_obj, rest = ber_decoder.decode(raw, asn1Spec=rfc2459.Certificate())
    except Exception as e:
        metadata = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": 0,
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError(f"Malformed certificate ASN.1 structure: {e}", metadata) from None

    # Extract original tbsCertificate bytes before normalization for signature verification
    try:
        original_tbs_bytes = der_encoder.encode(cert_obj.getComponentByName('tbsCertificate'))
    except Exception:
        original_tbs_bytes = None

    # 3. Reject any non-zero trailing bytes
    if any(b != 0 for b in rest):
        metadata = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": len(rest),
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError("Non-zero trailing bytes detected after certificate.", metadata)

    # 4. Normalize ECDSA signature algorithm parameters
    # ECDSA signature algorithms (OIDs starting with 1.2.840.10045.4) must have
    # parameters absent under strict DER (RFC 5480). Non-standard encoders sometimes
    # write NULL (05 00) parameters, which we unset here to satisfy strict DER parsers.
    try:
        for alg_id in [cert_obj.getComponentByName('signatureAlgorithm'),
                       cert_obj.getComponentByName('tbsCertificate').getComponentByName('signature')]:
            alg_oid = alg_id.getComponentByName('algorithm')
            if str(alg_oid).startswith("1.2.840.10045.4"):
                alg_id.setComponentByName('parameters')
    except Exception as e:
        metadata = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": len(rest),
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError(f"Failed to normalize signature algorithm: {e}", metadata) from None

    # 5. Re-encode the parsed certificate as canonical DER
    try:
        der_bytes = der_encoder.encode(cert_obj)
    except Exception as e:
        metadata = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": len(rest),
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError(f"Failed to re-encode normalized certificate: {e}", metadata) from None

    # 6. Load the normalized DER certificate using cryptography.x509
    try:
        cert = x509.load_der_x509_certificate(der_bytes)
    except Exception as e:
        metadata = {
            "certificate_field_length": len(raw),
            "certificate_encoding_detected": "unknown",
            "certificate_normalization_status": "failed",
            "certificate_trailing_padding_length": len(rest),
            "certificate_parse_status": "invalid",
            "technical_category": "certificate_invalid",
        }
        raise CardCertificateEncodingError(f"Failed to load normalized DER certificate: {e}", metadata) from None

    # Determine original encoding (excluding trailing zero padding)
    cert_len = len(raw) - len(rest)
    cert_part = raw[:cert_len]
    is_der = False
    try:
        x509.load_der_x509_certificate(cert_part)
        is_der = True
    except Exception:
        pass

    _metadata_registry[id(cert)] = {
        "certificate_field_length": len(raw),
        "certificate_encoding_detected": "der" if is_der else "ber_cer",
        "certificate_normalization_status": "normalized",
        "certificate_trailing_padding_length": len(rest),
        "original_tbs_certificate_bytes": original_tbs_bytes,
    }
    return cert
