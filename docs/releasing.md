# Releasing

[日本語版 →](releasing.ja.md)

This document is for maintainers preparing a public Windows release.

## Before building

1. Start from a clean, reviewed commit and update [CHANGELOG.md](../CHANGELOG.md).
2. Run the complete test suite and the release checks on the supported Windows environment.
3. Verify the bundled OCR model and trust anchors.
4. Review [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) and record the Windows version,
   reader model, driver version, and any real-card observations used for the release.

## Build and inspect

Build the Windows package with the repository's documented build script. Inspect the resulting
distribution before publishing: it must contain the application, required OCR model, and only
the intended runtime files. Test a freshly extracted archive on a Windows computer.

## Unsigned releases

This project currently publishes unsigned Windows builds. Windows may show a SmartScreen or
publisher warning. Never tell users to bypass a warning blindly. Publish a SHA-256 checksum
beside every archive, and instruct users to verify both the official release source and the
checksum before running it.

## Publish

Create a GitHub release from the reviewed tag. Attach the ZIP archive and its SHA-256 checksum.
State clearly whether the build is signed, list known limitations, and link to installation,
privacy, security, and troubleshooting documentation. Do not publish card data, screenshots
with personal information, private keys, or unpublished test material.
