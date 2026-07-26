# Release Checklist

[日本語版 →](RELEASE_CHECKLIST.ja.md)

Copy this checklist for each public release and record what was actually checked.

```text
Version:            ____________________
Commit:             ____________________
Build date:         ____________________
Build Windows:      ____________________
Python version:     ____________________
```

## Source and dependencies

- [ ] Built from a clean, reviewed commit.
- [ ] Full test suite passed.
- [ ] JavaScript syntax and packaged-asset integrity checks passed.
- [ ] OCR model and trust anchors verified.
- [ ] No real card data, private keys, unpublished test material, or internal documentation is
  present in the release tree.

## Package

- [ ] Built the Windows package using the documented build procedure.
- [ ] Inspected the distribution and a freshly extracted ZIP.
- [ ] Confirmed the application runs on Windows without Python installed.
- [ ] Recorded the archive SHA-256 checksum.

```text
Archive filename:    ____________________
Archive SHA-256:     ____________________
Code-signing status: signed / unsigned
```

## Hardware and real-card checks

Use authorised cards only. Do not put personal data in this checklist or in the repository.

- [ ] Recorded Windows version, reader model, and driver version.
- [ ] Confirmed reader detection and a normal card read.
- [ ] Confirmed the 17 reviewed fields are displayed as expected.
- [ ] Checked signature-verification behaviour for the available card generations.
- [ ] Checked OCR results and recorded relevant limitations.
- [ ] Confirmed no card image, raw card data, or personal data is written to disk or logs.

## Publish

- [ ] Updated [CHANGELOG.md](CHANGELOG.md).
- [ ] Release notes state known limitations and whether the build is unsigned.
- [ ] Attached the ZIP and SHA-256 checksum to the reviewed GitHub release tag.
- [ ] Release notes link to installation, privacy, security, and troubleshooting documents.
