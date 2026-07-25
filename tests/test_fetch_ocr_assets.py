"""The staging tool must treat the tracked manifest as authority, not as output.

`model.onnx` is not tracked in Git, so the committed `manifest.json` is the only thing
standing between a staged download and whatever an upstream host happens to serve. These
tests cover that boundary; they never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import fetch_ocr_assets

REVIEWED = {
    "schema_version": 1,
    "model_name": "PP-OCRv6_medium_rec",
    "source_revision": "4ca479517810450af7bcff5bac0e6c4616987d51",
    "model_sha256": "a" * 64,
    "metadata_sha256": "b" * 64,
    "dictionary_sha256": "c" * 64,
    "dictionary_entries": 18708,
}


def _staged(**overrides: object) -> dict[str, object]:
    staged = dict(REVIEWED)
    staged.update(overrides)
    return staged


def test_a_matching_staged_set_is_accepted() -> None:
    fetch_ocr_assets.verify_against_reviewed_manifest(_staged(), REVIEWED)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_sha256", "d" * 64),
        ("metadata_sha256", "d" * 64),
        ("dictionary_sha256", "d" * 64),
        ("dictionary_entries", 18707),
        ("source_revision", "0000000000000000000000000000000000000000"),
        ("model_name", "PP-OCRv6_small_rec"),
    ],
)
def test_any_divergence_from_the_reviewed_manifest_is_refused(field: str, value: object) -> None:
    with pytest.raises(RuntimeError, match="do not match the reviewed manifest"):
        fetch_ocr_assets.verify_against_reviewed_manifest(_staged(**{field: value}), REVIEWED)


def test_the_refusal_names_the_artifact_that_differs() -> None:
    with pytest.raises(RuntimeError) as error:
        fetch_ocr_assets.verify_against_reviewed_manifest(_staged(model_sha256="d" * 64), REVIEWED)
    message = str(error.value)
    assert "model_sha256" in message
    assert "Nothing was installed" in message


def test_extra_or_reordered_manifest_fields_are_not_treated_as_tampering() -> None:
    """A formatting or key-order change must not read as a corrupted download."""
    staged = _staged(source_url="https://example.invalid/elsewhere", image_mode="BGR")
    fetch_ocr_assets.verify_against_reviewed_manifest(staged, REVIEWED)


def test_a_checkout_with_a_tracked_manifest_loads_it(tmp_path: Path) -> None:
    destination = tmp_path / "ppocrv6"
    destination.mkdir()
    (destination / "manifest.json").write_text(json.dumps(REVIEWED), encoding="utf-8")

    assert fetch_ocr_assets.load_reviewed_manifest(destination) == REVIEWED


def test_a_checkout_without_a_manifest_stages_without_one(tmp_path: Path) -> None:
    assert fetch_ocr_assets.load_reviewed_manifest(tmp_path / "missing") is None


def test_an_unreadable_manifest_is_an_error_rather_than_a_silent_skip(tmp_path: Path) -> None:
    destination = tmp_path / "ppocrv6"
    destination.mkdir()
    (destination / "manifest.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="could not be read"):
        fetch_ocr_assets.load_reviewed_manifest(destination)


def test_the_repository_manifest_still_matches_the_pinned_revision() -> None:
    """The tracked manifest and the tool's pinned constants must not drift apart."""
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "resources" / "ocr" / "ppocrv6" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["source_revision"] == fetch_ocr_assets.REVISION
    assert manifest["model_sha256"] == fetch_ocr_assets.MODEL_SHA256


# ------------------------------------------------ staging must be byte-deterministic


def test_the_staged_dictionary_uses_LF_on_every_platform(tmp_path: Path, monkeypatch) -> None:
    """A CRLF dictionary can never match a manifest hash computed anywhere else.

    `Path.write_text` translates "\n" to the platform line ending unless told otherwise,
    and PowerShell's `WriteAllLines` emits CRLF on Windows. Both produced a dictionary
    whose SHA-256 depended on the operating system that staged it, which is unusable for
    a checksum-verified artifact.
    """
    source = tmp_path / "source"
    source.mkdir()
    model_bytes = b"synthetic-onnx-payload"
    (source / "inference.onnx").write_bytes(model_bytes)
    (source / "inference.yml").write_bytes(
        b"PostProcess:\n  character_dict:\n  - a\n  - b\n  - c\n"
    )
    monkeypatch.setattr(fetch_ocr_assets, "MODEL_SHA256", hashlib.sha256(model_bytes).hexdigest())

    destination = tmp_path / "ppocrv6"
    manifest = fetch_ocr_assets.stage(destination, source_dir=source)

    dictionary = (destination / "dictionary.txt").read_bytes()
    assert b"\r\n" not in dictionary
    assert dictionary == b"a\nb\nc\n"
    assert manifest["dictionary_entries"] == 3
    assert manifest["dictionary_sha256"] == hashlib.sha256(b"a\nb\nc\n").hexdigest()


def test_staging_refuses_and_restores_when_the_reviewed_manifest_disagrees(tmp_path: Path, monkeypatch) -> None:
    """A mismatch must leave the previous, known-good asset set in place."""
    source = tmp_path / "source"
    source.mkdir()
    model_bytes = b"synthetic-onnx-payload"
    (source / "inference.onnx").write_bytes(model_bytes)
    (source / "inference.yml").write_bytes(b"PostProcess:\n  character_dict:\n  - a\n")
    monkeypatch.setattr(fetch_ocr_assets, "MODEL_SHA256", hashlib.sha256(model_bytes).hexdigest())

    destination = tmp_path / "ppocrv6"
    destination.mkdir()
    reviewed = dict(REVIEWED)
    reviewed["model_sha256"] = "f" * 64          # will not match the staged payload
    (destination / "manifest.json").write_text(json.dumps(reviewed), encoding="utf-8")
    (destination / "sentinel.txt").write_text("previous asset set", encoding="utf-8")

    with pytest.raises(RuntimeError, match="do not match the reviewed manifest"):
        fetch_ocr_assets.stage(destination, source_dir=source)

    assert (destination / "sentinel.txt").read_text(encoding="utf-8") == "previous asset set"
    assert json.loads((destination / "manifest.json").read_text(encoding="utf-8")) == reviewed
