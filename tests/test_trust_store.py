from __future__ import annotations

from pathlib import Path

import pytest

from reader.signature.trust_store import (
    TrustStoreError,
    compare_archive_and_historical_certificate,
    load_anchor,
    load_second_generation_trust_anchor,
    load_trust_anchors,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_published_production_anchors_are_packaged_and_validated() -> None:
    anchors, failures = load_trust_anchors(profile="production", generation="first_generation")

    assert failures == []
    assert [anchor.anchor_id for anchor in anchors] == [
        "moj-rc1-production-ca-20150606",
        "moj-rc1-production-ca-20180407",
        "moj-rc1-production-ca-20210527",
        "moj-rc1-production-ca-20240508",
    ]
    assert all(anchor.profile == "production" and anchor.certificate_bytes for anchor in anchors)


def test_archive_and_historical_first_generation_certificates_are_identical() -> None:
    pairs = [
        ("001460774.zip", "930001756.crt"),
        ("001460775.zip", "930001757.crt"),
        ("001460776.zip", "001353372.crt"),
        ("001460777.zip", "001421582.crt"),
    ]
    for archive, direct in pairs:
        assert compare_archive_and_historical_certificate(
            ROOT / "docs/external/moj/certs" / archive,
            ROOT / "docs/external/moj/certs" / direct,
        )


def test_production_and_official_test_profiles_do_not_overlap() -> None:
    production, _ = load_trust_anchors(profile="production", generation="second_generation")
    official_test, _ = load_trust_anchors(profile="official_test", generation="second_generation")

    assert [anchor.anchor_id for anchor in production] == ["moj-rc2-production-ca2-20260420"]
    assert [anchor.anchor_id for anchor in official_test] == ["moj-rc2-official-test-ca2-20260319"]
    assert {anchor.sha256_fingerprint for anchor in production}.isdisjoint(
        {anchor.sha256_fingerprint for anchor in official_test}
    )


def test_load_second_generation_trust_anchor_from_runtime_resources() -> None:
    anchor = load_second_generation_trust_anchor()

    assert anchor.subject_cn == "ZairyuCard CA2"
    assert anchor.sha256_fingerprint == "11:E6:AD:8B:8E:64:F0:CD:B1:D8:BA:9E:36:89:92:6C:80:E8:47:9A:2F:09:86:16:F6:74:A2:35:82:BE:C1:3B"
    assert anchor.path.name == "zairyucard_ca2_20260420_20390720.crt"
    assert anchor.certificate_bytes


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(TrustStoreError) as error:
        load_trust_anchors(profile="combined", generation="second_generation")
    assert error.value.status == "wrong_profile"


def test_modified_or_missing_anchor_is_reported_without_crashing(tmp_path) -> None:
    metadata = {
        "anchor_id": "synthetic", "generation": "second_generation", "profile": "production",
        "official_source_id": "synthetic", "path": str(tmp_path / "missing.crt"),
        "subject": "CN=synthetic", "issuer": "CN=synthetic", "serial_number": "01",
        "valid_from": "2026-01-01T00:00:00Z", "valid_until": "2036-01-01T00:00:00Z",
        "public_key_algorithm": "ECDSA P-384", "signature_algorithm": "ecdsa-with-SHA256",
        "sha256_fingerprint": "00", "source_retrieval_date": "2026-01-01",
        "source_verification_status": "synthetic",
    }
    with pytest.raises(TrustStoreError) as missing:
        load_anchor(metadata)
    assert missing.value.status == "missing"

    path = tmp_path / "modified.crt"
    path.write_bytes(b"not the expected certificate")
    metadata["path"] = str(path)
    with pytest.raises(TrustStoreError) as modified:
        load_anchor(metadata)
    assert modified.value.status == "fingerprint_mismatch"
