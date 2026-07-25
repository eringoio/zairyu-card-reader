"""Inspect a built Windows distribution for anything that must not ship.

Run against `dist/zairyu-reader` after a build, and again against the extracted release
archive before publishing. `scripts/build_windows.ps1` runs it automatically.

This is a release gate, not a linter: every finding below is something that should never
reach a staff machine or a public download. Exit status is non-zero if any is found.

    python scripts/inspect_distribution.py dist/zairyu-reader
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Files that must never appear in a distribution, by name or extension.
FORBIDDEN_SUFFIXES = (
    ".log",        # runtime logs
    ".key", ".pem", ".pfx", ".p12",   # private key material
    ".env",
    ".pdb",        # debug symbols
    ".map",        # source maps
    ".csv",        # a stray export
    ".db", ".sqlite", ".sqlite3",
)

FORBIDDEN_NAMES = {
    ".env",
    "config.json",          # a staff machine's local settings, if one were ever copied in
    "001462222.zip",        # specified-card RSA delivery key archive
    "001460789.zip",
}

FORBIDDEN_NAME_FRAGMENTS = (
    "smrsapub",     # specified-card RSA delivery key
    "debug_trace",
    "zairyu_trace",
)

# Directories that indicate development material was packaged.
FORBIDDEN_DIR_NAMES = {
    "tests", "docs", "__pycache__", ".git", ".github", ".pytest_cache", ".ruff_cache",
    "debug_traces", "exports", "node_modules",
}

# Scripts for an external interpreter. The application must never hand a file to one; an
# earlier revision shipped a PowerShell OCR helper that wrote a card image to %TEMP%.
SCRIPT_SUFFIXES = (".ps1", ".bat", ".cmd", ".sh", ".vbs")

# Text that would reveal a developer's machine or a real person. `C:\Users\staff` is an
# intentional placeholder and is allowed.
PERSONAL_PATTERNS = (
    re.compile(rb"[Cc]:\\+[Uu]sers\\+(?!staff\b)[A-Za-z0-9._-]+"),
    re.compile(rb"/home/[a-z][a-z0-9._-]*"),
    re.compile(rb"/Users/[A-Za-z0-9._-]+"),
    re.compile(rb"/mnt/[a-z]/Projects"),
    re.compile(rb"[A-Za-z]:\\+Projects\\+"),
)

# A residence card number: two letters, eight digits, two letters. The synthetic values the
# project uses are allowed; anything else shaped like a card number is not.
CARD_NUMBER = re.compile(rb"\b[A-Z]{2}[0-9]{8}[A-Z]{2}\b")
ALLOWED_CARD_NUMBERS = {b"AB12345678AJ", b"AB12345678CD", b"AA12345678BB", b"CD12345678EF"}

# Only inspect the contents of files that are plausibly text. A 76 MB model is scanned by
# checksum, not by regex.
TEXT_SUFFIXES = (".py", ".txt", ".json", ".yml", ".yaml", ".js", ".css", ".html", ".md", ".cfg", ".ini", ".toml")
MAX_TEXT_BYTES = 4 * 1024 * 1024


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def check_forbidden_files(root: Path) -> list[str]:
    findings = []
    for path in _iter_files(root):
        relative = path.relative_to(root)
        name = path.name.lower()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden file type: {relative}")
        if name in FORBIDDEN_NAMES:
            findings.append(f"forbidden file: {relative}")
        if any(fragment in name for fragment in FORBIDDEN_NAME_FRAGMENTS):
            findings.append(f"forbidden file name: {relative}")
        if path.suffix.lower() in SCRIPT_SUFFIXES:
            findings.append(f"script payload for an external interpreter: {relative}")
    return findings


def check_forbidden_directories(root: Path) -> list[str]:
    findings = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and path.name in FORBIDDEN_DIR_NAMES:
            findings.append(f"development directory packaged: {path.relative_to(root)}")
    return findings


def check_text_contents(root: Path) -> list[str]:
    findings = []
    for path in _iter_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_TEXT_BYTES:
            continue
        blob = path.read_bytes()
        relative = path.relative_to(root)
        for pattern in PERSONAL_PATTERNS:
            match = pattern.search(blob)
            if match:
                findings.append(f"developer path in {relative}: {match.group(0)!r}")
        for match in CARD_NUMBER.finditer(blob):
            if match.group(0) not in ALLOWED_CARD_NUMBERS:
                findings.append(f"card-number-shaped value in {relative}: {match.group(0)!r}")
    return findings


def check_expected_resources(root: Path) -> list[str]:
    """A distribution missing a runtime resource is as broken as one carrying a forbidden file."""
    required = [
        "_internal/static/index.html",
        "_internal/static/local.js",
        "_internal/resources/ocr/ppocrv6/manifest.json",
        "_internal/resources/ocr/ppocrv6/model.onnx",
        "_internal/resources/ocr/ppocrv6/inference.yml",
        "_internal/resources/ocr/ppocrv6/dictionary.txt",
        "_internal/resources/moj/trust-anchors/manifest.json",
        "zairyu-reader.exe",
    ]
    return [f"missing required resource: {item}" for item in required if not (root / item).exists()]


def check_packaged_checksums(root: Path) -> list[str]:
    """Verify the packaged trust anchors and OCR assets against their manifests."""
    findings = []

    anchors = root / "_internal" / "resources" / "moj" / "trust-anchors" / "manifest.json"
    if anchors.is_file():
        manifest = json.loads(anchors.read_text(encoding="utf-8"))
        for entry in manifest["anchors"]:
            packaged = root / "_internal" / entry["path"]
            if not packaged.is_file():
                findings.append(f"packaged trust anchor missing: {entry['anchor_id']}")
                continue
            digest = ":".join(f"{b:02X}" for b in hashlib.sha256(packaged.read_bytes()).digest())
            if digest != entry["sha256_fingerprint"]:
                findings.append(f"packaged trust anchor fingerprint mismatch: {entry['anchor_id']}")

    ocr = root / "_internal" / "resources" / "ocr" / "ppocrv6"
    ocr_manifest = ocr / "manifest.json"
    if ocr_manifest.is_file():
        manifest = json.loads(ocr_manifest.read_text(encoding="utf-8"))
        for file_key, hash_key in (
            ("model_file", "model_sha256"),
            ("metadata_file", "metadata_sha256"),
            ("dictionary_file", "dictionary_sha256"),
        ):
            target = ocr / manifest[file_key]
            if not target.is_file():
                findings.append(f"packaged OCR asset missing: {manifest[file_key]}")
                continue
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != manifest[hash_key]:
                findings.append(f"packaged OCR asset checksum mismatch: {manifest[file_key]}")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("distribution", type=Path, help="Path to dist/zairyu-reader, or an extracted archive")
    arguments = parser.parse_args()

    root = arguments.distribution
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    checks = [
        ("forbidden files", check_forbidden_files),
        ("development directories", check_forbidden_directories),
        ("required resources", check_expected_resources),
        ("packaged checksums", check_packaged_checksums),
        ("text contents", check_text_contents),
    ]

    total = 0
    for label, check in checks:
        findings = check(root)
        total += len(findings)
        status = "FAIL" if findings else "ok  "
        print(f"  {status} {label}")
        for finding in findings:
            print(f"         - {finding}")

    file_count = sum(1 for _ in _iter_files(root))
    size = sum(path.stat().st_size for path in _iter_files(root))
    print(f"\n  {file_count} files, {size / (1024 * 1024):.1f} MiB")

    if total:
        print(f"\nDistribution inspection FAILED with {total} finding(s). Do not release this build.")
        return 1
    print("\nDistribution inspection passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
