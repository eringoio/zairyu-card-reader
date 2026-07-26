"""Byte-level integrity of the assets this application refuses to work without.

The OCR model, its metadata and dictionary, and every CA certificate are verified against
a recorded SHA-256 before use. That makes them sensitive to anything that rewrites bytes in
transit — most obviously Git's line-ending conversion.

That is not hypothetical. Before `.gitattributes` existed, `core.autocrlf` converted every
LF in `inference.yml` and `dictionary.txt` to CRLF on Windows checkouts. The recorded
hashes no longer matched, `OnnxOcrEngine.from_assets()` returned `UnavailableOcrEngine`,
OCR failed completely, and `scripts\\build_windows.ps1` failed its release gate. Nothing in
the test suite caught it, because the OCR tests stage synthetic assets rather than loading
the packaged ones.

These tests load the real packaged files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from reader.ocr.onnx_engine import MODEL_NAME, OnnxOcrEngine, UnavailableOcrEngine
from reader.signature.trust_store import load_trust_anchors

ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = ROOT / "resources" / "ocr" / "ppocrv6"
ANCHOR_MANIFEST = ROOT / "resources" / "moj" / "trust-anchors" / "manifest.json"

# `model.onnx` is not tracked in Git and is staged locally, so a fresh clone legitimately
# lacks it. Everything else here is tracked and must always be present and correct.
_model_required = pytest.mark.skipif(
    not (OCR_DIR / "model.onnx").is_file(),
    reason="model.onnx is staged locally, not tracked; run tools/fetch_ocr_assets.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _ocr_manifest() -> dict:
    return json.loads((OCR_DIR / "manifest.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ line endings


@pytest.mark.parametrize("name", ["inference.yml", "dictionary.txt"])
def test_checksum_verified_text_assets_contain_no_crlf(name: str) -> None:
    """A single CRLF here breaks OCR entirely. `.gitattributes` marks these `-text`."""
    path = OCR_DIR / name
    if not path.is_file():
        pytest.skip(f"{name} is staged locally; run tools/fetch_ocr_assets.py")
    assert b"\r\n" not in path.read_bytes(), (
        f"{name} contains CRLF. Its SHA-256 will not match the manifest and OCR will "
        f"refuse to load. Check .gitattributes and your Git core.autocrlf setting."
    )


def test_gitattributes_protects_every_checksum_verified_path() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    for path in ("resources/ocr/ppocrv6/**", "resources/moj/trust-anchors/**"):
        assert f"{path} -text" in attributes, f"{path} must be marked -text"


# ------------------------------------------------------------------- OCR assets


def test_ocr_metadata_and_dictionary_match_their_recorded_checksums() -> None:
    manifest = _ocr_manifest()
    for file_key, hash_key in (("metadata_file", "metadata_sha256"), ("dictionary_file", "dictionary_sha256")):
        path = OCR_DIR / manifest[file_key]
        if not path.is_file():
            pytest.skip(f"{manifest[file_key]} is staged locally")
        assert _sha256(path) == manifest[hash_key], f"{manifest[file_key]} does not match its manifest checksum"


@_model_required
def test_ocr_model_matches_its_recorded_checksum() -> None:
    manifest = _ocr_manifest()
    assert _sha256(OCR_DIR / manifest["model_file"]) == manifest["model_sha256"]


def test_the_dictionary_is_reproducible_from_the_metadata() -> None:
    """The dictionary is derived, not authored. It must be regenerable byte-for-byte."""
    manifest = _ocr_manifest()
    metadata_path = OCR_DIR / manifest["metadata_file"]
    dictionary_path = OCR_DIR / manifest["dictionary_file"]
    if not (metadata_path.is_file() and dictionary_path.is_file()):
        pytest.skip("OCR metadata is staged locally")

    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    characters = metadata["PostProcess"]["character_dict"]
    regenerated = "\n".join(str(value) for value in characters) + "\n"

    assert regenerated == dictionary_path.read_text(encoding="utf-8")
    assert len(characters) == manifest["dictionary_entries"]


def test_the_ocr_manifest_records_its_source_revision_and_licence() -> None:
    manifest = _ocr_manifest()
    assert manifest["model_name"] == MODEL_NAME
    assert manifest["source"] == "PaddlePaddle/PP-OCRv6_medium_rec_onnx"
    assert manifest["source_revision"] == "4ca479517810450af7bcff5bac0e6c4616987d51"
    assert manifest["model_sha256"] == "9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["input_dimensions"] == [3, 48, 320]
    assert manifest["image_mode"] == "BGR"
    assert manifest["postprocess"] == "CTCLabelDecode"


@_model_required
def test_the_packaged_model_actually_loads() -> None:
    """The check the release gate performs, and the one the CRLF bug defeated."""
    engine = OnnxOcrEngine.from_assets()
    if isinstance(engine, UnavailableOcrEngine):
        pytest.fail(f"packaged OCR assets did not load: {engine.recognize_name(b'').warnings}")
    assert engine.model_name == MODEL_NAME
    assert engine.input_width > 0
    assert len(engine.dictionary) == _ocr_manifest()["dictionary_entries"]


# --------------------------------------------------------------- trust anchors


def _anchor_manifest() -> dict:
    return json.loads(ANCHOR_MANIFEST.read_text(encoding="utf-8"))


def test_every_packaged_certificate_matches_its_recorded_fingerprint() -> None:
    for entry in _anchor_manifest()["anchors"]:
        path = ROOT / entry["path"]
        assert path.is_file(), f"missing packaged certificate: {entry['path']}"
        actual = ":".join(f"{byte:02X}" for byte in hashlib.sha256(path.read_bytes()).digest())
        assert actual == entry["sha256_fingerprint"], f"{entry['anchor_id']} fingerprint mismatch"


def test_the_anchor_manifest_is_complete_for_every_entry() -> None:
    required = {
        "anchor_id", "generation", "profile", "official_source_id", "path", "subject", "issuer",
        "serial_number", "valid_from", "valid_until", "public_key_algorithm", "signature_algorithm",
        "sha256_fingerprint", "source_retrieval_date", "source_verification_status",
    }
    for entry in _anchor_manifest()["anchors"]:
        missing = required - set(entry)
        assert not missing, f"{entry.get('anchor_id')} is missing {sorted(missing)}"


def test_anchor_ids_and_fingerprints_are_unique() -> None:
    anchors = _anchor_manifest()["anchors"]
    assert len({a["anchor_id"] for a in anchors}) == len(anchors)
    assert len({a["sha256_fingerprint"] for a in anchors}) == len(anchors)


def test_every_certificate_lives_under_a_directory_matching_its_profile() -> None:
    """Physical separation, not just a field in a JSON file."""
    for entry in _anchor_manifest()["anchors"]:
        path = entry["path"]
        if entry["profile"] == "official_test":
            assert "/official-test/" in path, f"{entry['anchor_id']} is not in the official-test directory"
        else:
            assert "/official-test/" not in path, f"production anchor {entry['anchor_id']} sits in official-test/"
            expected = "first-generation" if entry["generation"] == "first_generation" else "second-generation"
            assert f"/{expected}/" in path, f"{entry['anchor_id']} is not under {expected}/"


def test_the_production_profile_never_yields_official_test_material() -> None:
    for generation in ("first_generation", "second_generation"):
        anchors, failures = load_trust_anchors(profile="production", generation=generation)
        assert failures == []
        assert all(anchor.profile == "production" for anchor in anchors)
        assert all("official-test" not in str(anchor.path) for anchor in anchors)


def test_the_official_test_profile_holds_exactly_one_second_generation_anchor() -> None:
    first, _ = load_trust_anchors(profile="official_test", generation="first_generation")
    second, failures = load_trust_anchors(profile="official_test", generation="second_generation")

    assert first == [], "no official-test first-generation anchor should exist"
    assert failures == []
    assert [anchor.anchor_id for anchor in second] == ["moj-rc2-official-test-ca2-20260319"]


# ------------------------------------------------- specified-card material stays out


def test_no_specified_card_rsa_delivery_key_material_is_distributed() -> None:
    """Out of scope, and explicitly forbidden from being exposed."""
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        assert "smrsapub" not in name, f"specified-card RSA delivery key material present: {path}"
        assert name != "001462222.zip", f"specified-card RSA delivery key archive present: {path}"
    assert not (ROOT / "resources" / "moj" / "specified-card").exists()


def test_no_private_key_material_is_distributed() -> None:
    for suffix in (".key", ".pem", ".pfx", ".p12", ".bin"):
        found = [p for p in ROOT.rglob(f"*{suffix}") if ".venv" not in p.parts]
        assert found == [], f"unexpected key-like files: {found}"


def test_every_anchor_records_its_official_source_page_and_purpose() -> None:
    """Phase-5 provenance: a reader must be able to reach the original publication."""
    pages = {
        "first_generation": "https://www.moj.go.jp/isa/applications/disclosure/120424_01.html",
        "second_generation": "https://www.moj.go.jp/isa/publications/resources/120424_01_00003.html",
    }
    for entry in _anchor_manifest()["anchors"]:
        assert entry["official_source_page"] == pages[entry["generation"]]
        assert entry["purpose"].strip()
        if entry["profile"] == "official_test":
            assert "never report production authenticity" in entry["purpose"]


def test_the_manifest_records_specified_card_material_as_not_distributed() -> None:
    material = _anchor_manifest()["specified_card_material"]
    assert material["enabled"] is False
    assert material["distributed"] is False
    assert set(material["official_source_ids"]) == {"001460789.zip", "001462222.zip"}
