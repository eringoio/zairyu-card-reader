"""Build-time PP-OCRv6 asset staging. Never runs inside the application.

The model is not tracked in Git: at 76 MB it would dominate the repository and its history.
This tool downloads the pinned upstream revision and installs it under
``resources/ocr/ppocrv6/``.

``manifest.json`` **is** tracked, and is treated here as the reviewed record rather than as
output. When it is present, every staged artifact must match it exactly or nothing is
installed. That is what makes an untracked model safe: a download is only accepted if it
reproduces checksums that were reviewed and committed beforehand.

The Windows PowerShell command documented for release work is the supported Windows entry
point. This equivalent helper lets CI and non-Windows maintainers stage the same pinned
files without putting any download capability in the application package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REVISION = "4ca479517810450af7bcff5bac0e6c4616987d51"
MODEL_SHA256 = "9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba"
BASE_URL = f"https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx/resolve/{REVISION}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, target: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("Could not download pinned PP-OCRv6 assets; check network access and retry.") from exc


def load_reviewed_manifest(destination: Path) -> dict[str, object] | None:
    """Return the committed manifest, or ``None`` on a checkout that has never staged one."""
    path = destination / "manifest.json"
    if not path.is_file():
        return None
    try:
        reviewed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"The tracked manifest at {path} could not be read: {exc}") from exc
    return reviewed if isinstance(reviewed, dict) else None


def verify_against_reviewed_manifest(staged: dict[str, object], reviewed: dict[str, object]) -> None:
    """Refuse a staged set that does not reproduce the committed checksums.

    Checked field by field rather than by comparing whole documents, so a harmless
    formatting or key-order difference does not read as tampering, and a real mismatch
    names the artifact that differs.
    """
    checked = (
        "source_revision",
        "model_sha256",
        "metadata_sha256",
        "dictionary_sha256",
        "dictionary_entries",
        "model_name",
    )
    mismatches = [
        f"{field}: manifest says {reviewed[field]!r}, downloaded set produced {staged.get(field)!r}"
        for field in checked
        if field in reviewed and reviewed[field] != staged.get(field)
    ]
    if mismatches:
        raise RuntimeError(
            "The downloaded OCR assets do not match the reviewed manifest. Nothing was installed.\n  "
            + "\n  ".join(mismatches)
        )


def stage(destination: Path, source_dir: Path | None = None) -> dict[str, object]:
    reviewed = load_reviewed_manifest(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".ppocrv6-stage-", dir=destination.parent))
    backup = destination.with_name(f"{destination.name}.backup")
    moved_existing = False
    try:
        for source_name, target_name in (("inference.onnx", "model.onnx"), ("inference.yml", "inference.yml")):
            target = temporary / target_name
            if source_dir:
                source = source_dir / source_name
                if not source.is_file():
                    raise RuntimeError(f"Missing required source asset: {source_name}")
                shutil.copyfile(source, target)
            else:
                _download(f"{BASE_URL}/{source_name}", target)
        if sha256(temporary / "model.onnx") != MODEL_SHA256:
            raise RuntimeError("Downloaded inference.onnx does not match the reviewed SHA-256.")
        metadata = yaml.safe_load((temporary / "inference.yml").read_text(encoding="utf-8"))
        characters = metadata.get("PostProcess", {}).get("character_dict") if isinstance(metadata, dict) else None
        if not isinstance(characters, list) or not characters:
            raise RuntimeError("inference.yml has no PostProcess.character_dict entries.")
        # `newline="\n"` is required, not cosmetic. Without it Python translates each "\n"
        # to the platform line ending, so a Windows run would produce a CRLF dictionary
        # whose SHA-256 could never match a manifest written on Linux. The artifact is
        # checksum-verified, so its bytes must not depend on the operating system.
        (temporary / "dictionary.txt").write_text(
            "\n".join(str(value) for value in characters) + "\n", encoding="utf-8", newline="\n"
        )
        manifest: dict[str, object] = {
            "schema_version": 1,
            "model_name": "PP-OCRv6_medium_rec",
            "source": "PaddlePaddle/PP-OCRv6_medium_rec_onnx",
            "source_revision": REVISION,
            "source_url": BASE_URL,
            "license": "Apache-2.0",
            "model_file": "model.onnx",
            "model_sha256": sha256(temporary / "model.onnx"),
            "metadata_file": "inference.yml",
            "metadata_sha256": sha256(temporary / "inference.yml"),
            "dictionary_file": "dictionary.txt",
            "dictionary_sha256": sha256(temporary / "dictionary.txt"),
            "image_mode": "BGR",
            "input_dimensions": [3, 48, 320],
            "postprocess": "CTCLabelDecode",
            "dictionary_entries": len(characters),
        }
        if reviewed is not None:
            verify_against_reviewed_manifest(manifest, reviewed)
            # Keep the committed file byte-for-byte. Rewriting it would leave a spurious
            # diff in a working tree and would quietly make the download its own authority.
            manifest = reviewed
            (temporary / "manifest.json").write_text(
                json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        else:
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.replace(backup)
            moved_existing = True
        temporary.replace(destination)
        if backup.exists():
            shutil.rmtree(backup)
        return manifest
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        if moved_existing and not destination.exists() and backup.exists():
            backup.replace(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "resources" / "ocr" / "ppocrv6")
    parser.add_argument("--source-dir", type=Path, help="Use already-downloaded pinned inference.onnx/yml files")
    args = parser.parse_args()
    manifest = stage(args.destination, args.source_dir)
    print(f"staged {manifest['model_name']} ({manifest['model_sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
