"""Offline, profile-separated MOJ certificate trust anchors.

Only this module reads packaged anchor bytes.  Callers receive an anchor internally for
cryptographic verification and return only the safe ``anchor_id`` and status values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from reader.runtime_paths import resource_root, trust_anchor_manifest
from reader.signature.certificate_encoding import load_card_x509_certificate

BASE_DIR = resource_root()
MANIFEST_PATH = trust_anchor_manifest()
PRODUCTION_PROFILE = "production"
OFFICIAL_TEST_PROFILE = "official_test"
TRUST_PROFILES = frozenset({PRODUCTION_PROFILE, OFFICIAL_TEST_PROFILE})


class TrustStoreError(RuntimeError):
    def __init__(self, message: str, *, status: str = "missing") -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class TrustAnchor:
    anchor_id: str
    generation: str
    profile: str
    official_source_id: str
    historical_source_id: str | None
    path: Path
    subject: str
    issuer: str
    serial_number: str
    valid_from: str
    valid_until: str
    public_key_algorithm: str
    signature_algorithm: str
    sha256_fingerprint: str
    source_retrieval_date: str
    source_verification_status: str
    certificate_bytes: bytes

    # Compatibility with the original single-anchor test surface.
    @property
    def name(self) -> str:
        return self.anchor_id

    @property
    def subject_cn(self) -> str:
        return self.subject.split(",", 1)[0].removeprefix("CN=")


@dataclass(frozen=True)
class TrustPath:
    status: str
    selected_anchor_id: str
    anchor: TrustAnchor | None
    candidate_count: int
    anchor_validity_status: str


def _normalize_fingerprint(value: str) -> str:
    return value.replace(":", "").lower()


def _sha256_fingerprint(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest().upper()
    return ":".join(digest[index : index + 2] for index in range(0, len(digest), 2))


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        raise TrustStoreError(f"Trust-anchor manifest not found: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrustStoreError("Trust-anchor manifest could not be read.") from exc
    if manifest.get("manifest_version") != 2 or not isinstance(manifest.get("anchors"), list):
        raise TrustStoreError("Trust-anchor manifest has an unsupported schema.")
    return manifest


def _certificate_path(metadata: dict[str, Any], manifest_path: Path) -> Path:
    path = Path(str(metadata["path"]))
    return path if path.is_absolute() else BASE_DIR / path


def load_anchor(metadata: dict[str, Any], *, manifest_path: Path = MANIFEST_PATH) -> TrustAnchor:
    required = {
        "anchor_id", "generation", "profile", "official_source_id", "path", "subject", "issuer",
        "serial_number", "valid_from", "valid_until", "public_key_algorithm", "signature_algorithm",
        "sha256_fingerprint", "source_retrieval_date", "source_verification_status",
    }
    missing = required.difference(metadata)
    if missing:
        raise TrustStoreError("Trust-anchor metadata is incomplete.")
    cert_path = _certificate_path(metadata, manifest_path)
    if not cert_path.exists():
        raise TrustStoreError(f"Trust anchor not found: {cert_path}", status="missing")
    cert_bytes = cert_path.read_bytes()
    actual = _sha256_fingerprint(cert_bytes)
    if _normalize_fingerprint(actual) != _normalize_fingerprint(str(metadata["sha256_fingerprint"])):
        raise TrustStoreError("Trust-anchor SHA-256 fingerprint mismatch.", status="fingerprint_mismatch")
    return TrustAnchor(
        anchor_id=str(metadata["anchor_id"]), generation=str(metadata["generation"]), profile=str(metadata["profile"]),
        official_source_id=str(metadata["official_source_id"]), historical_source_id=metadata.get("historical_source_id"),
        path=cert_path, subject=str(metadata["subject"]), issuer=str(metadata["issuer"]), serial_number=str(metadata["serial_number"]),
        valid_from=str(metadata["valid_from"]), valid_until=str(metadata["valid_until"]),
        public_key_algorithm=str(metadata["public_key_algorithm"]), signature_algorithm=str(metadata["signature_algorithm"]),
        sha256_fingerprint=actual, source_retrieval_date=str(metadata["source_retrieval_date"]),
        source_verification_status=str(metadata["source_verification_status"]), certificate_bytes=cert_bytes,
    )


def load_trust_anchors(
    *, profile: str, generation: str, path: Path = MANIFEST_PATH
) -> tuple[list[TrustAnchor], list[str]]:
    """Load only anchors explicitly permitted by one non-overlapping profile."""
    if profile not in TRUST_PROFILES:
        raise TrustStoreError("Unknown verification trust profile.", status="wrong_profile")
    anchors: list[TrustAnchor] = []
    failures: list[str] = []
    for metadata in load_manifest(path)["anchors"]:
        if metadata.get("profile") != profile or metadata.get("generation") != generation:
            continue
        try:
            anchors.append(load_anchor(metadata, manifest_path=path))
        except TrustStoreError as exc:
            failures.append(exc.status)
    return anchors, failures


def load_second_generation_trust_anchor(path: Path = MANIFEST_PATH) -> TrustAnchor:
    """Compatibility helper for callers that require the production CA2 anchor."""
    anchors, failures = load_trust_anchors(profile=PRODUCTION_PROFILE, generation="second_generation", path=path)
    ca2 = next((anchor for anchor in anchors if anchor.anchor_id == "moj-rc2-production-ca2-20260420"), None)
    if ca2 is not None:
        return ca2
    status = failures[0] if failures else "missing"
    raise TrustStoreError("Second-generation production trust anchor unavailable.", status=status)


def _extension(certificate: x509.Certificate, extension_type):
    try:
        return certificate.extensions.get_extension_for_class(extension_type).value
    except x509.ExtensionNotFound:
        return None


def _verify_certificate_signature(certificate: x509.Certificate, issuer: x509.Certificate) -> bool:
    public_key = issuer.public_key()
    from reader.signature.certificate_encoding import get_certificate_metadata
    tbs_bytes = get_certificate_metadata(certificate).get("original_tbs_certificate_bytes") or certificate.tbs_certificate_bytes
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(certificate.signature, tbs_bytes, padding.PKCS1v15(), certificate.signature_hash_algorithm)
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(certificate.signature, tbs_bytes, ec.ECDSA(certificate.signature_hash_algorithm))
        else:
            return False
    except (InvalidSignature, UnsupportedAlgorithm, TypeError, ValueError):
        return False
    return True


def _candidate_anchors(certificate: x509.Certificate, anchors: Iterable[TrustAnchor]) -> list[TrustAnchor]:
    candidates = list(anchors)
    issuer_matches = [anchor for anchor in candidates if certificate.issuer.rfc4514_string() == anchor.subject]
    if issuer_matches:
        candidates = issuer_matches
    aki = _extension(certificate, x509.AuthorityKeyIdentifier)
    if aki and aki.key_identifier:
        ski_matches = []
        for anchor in candidates:
            anchor_cert = load_card_x509_certificate(anchor.certificate_bytes)
            ski = _extension(anchor_cert, x509.SubjectKeyIdentifier)
            if ski and ski.digest == aki.key_identifier:
                ski_matches.append(anchor)
        if ski_matches:
            candidates = ski_matches
    return candidates


def select_trust_path(
    certificate: x509.Certificate, *, profile: str, generation: str, path: Path = MANIFEST_PATH
) -> TrustPath:
    """Select exactly one cryptographically-valid issuer; certificate dates are separate."""
    # Both failure paths return a `TrustPath` whose status names the reason. The exception
    # text is derived from card certificate bytes, so it is deliberately not printed.
    try:
        anchors, failures = load_trust_anchors(profile=profile, generation=generation, path=path)
    except TrustStoreError as exc:
        return TrustPath(exc.status, "", None, 0, "not_evaluated")
    try:
        candidates = _candidate_anchors(certificate, anchors)
        verified = []
        for anchor in candidates:
            issuer_cert = load_card_x509_certificate(anchor.certificate_bytes)
            if _verify_certificate_signature(certificate, issuer_cert):
                verified.append(anchor)
    except ValueError:
        return TrustPath("missing", "", None, 0, "not_evaluated")
    if len(verified) == 1:
        return TrustPath("matched", verified[0].anchor_id, verified[0], len(candidates), "not_evaluated")
    if len(verified) > 1:
        return TrustPath("ambiguous", "", None, len(candidates), "not_evaluated")
    if failures and not anchors:
        status = "fingerprint_mismatch" if "fingerprint_mismatch" in failures else "missing"
        return TrustPath(status, "", None, len(candidates), "not_evaluated")
    return TrustPath("untrusted", "", None, len(candidates), "not_evaluated")
