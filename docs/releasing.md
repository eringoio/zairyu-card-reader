# Releasing

How to produce a Windows release of `zairyu-card-reader`. Use
[../RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) to record that you actually did each
step; this document explains why each one exists.

**This process produces files. It does not publish them.** Nothing here creates a GitHub
release, uploads an artifact, or signs a binary.

---

## 1. A clean environment

Build from a **clean checkout** on a Windows machine, not from a working tree you have been
developing in. A stale `dist/`, a leftover `.env`, or an OCR asset set someone edited by hand
will otherwise end up in the package.

```powershell
git clone <repository-url> zairyu-card-reader-release
cd zairyu-card-reader-release
python -m venv .venv
.venv\Scripts\activate
```

Confirm `git status` is clean before going further.

## 2. Dependencies

Install the pinned, hash-verified set:

```powershell
pip install --require-hashes -r requirements.lock.txt
pip install -r requirements-dev.txt
```

`--require-hashes` makes pip refuse any artifact that does not match the recorded hash. Use
it for a release; `requirements.txt` alone is for development.

If the lockfile is out of date, regenerate it deliberately and review the diff:

```powershell
pip install pip-tools
pip-compile --generate-hashes --strip-extras --output-file=requirements.lock.txt requirements.txt
```

## 3. Retrieve and verify the OCR model

`model.onnx` is not tracked in Git. Stage it:

```powershell
powershell -ExecutionPolicy Bypass -File tools\fetch_ocr_assets.ps1
```

The tool downloads only the pinned revision and verifies **every** artifact — model,
metadata, and generated dictionary — against the committed
`resources/ocr/ppocrv6/manifest.json`. On any mismatch it names the artifact that differs and
installs nothing, leaving the previous set in place.

Then confirm the ONNX contract independently:

```powershell
python tools\verify_ocr_assets.py
```

Expect the model name, `input: [1, 3, 48, 320]`, the output class count, the dictionary
entry count, and the blank index. A non-zero exit here must stop the release.

## 4. Verify trust anchors

```powershell
pytest -q tests\test_packaged_assets_integrity.py
```

This recomputes every packaged certificate's SHA-256 against the manifest, checks the
manifest is complete, confirms the production and official-test profiles do not overlap
either logically or by directory, and confirms no specified-card key material is present.

`build_windows.ps1` runs it too, but run it yourself first so a failure is not buried in
build output.

## 5. Tests

```powershell
pytest -q --basetemp=.pytest-tmp
ruff check .
```

Both must pass. Do not build a release with `-SkipTests`; that switch exists for iterating
on packaging problems.

## 6. Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -UseLockfile -Package -Version 0.2.1
```

The script refuses to produce a package unless, in order: dependencies install, the OCR
assets verify, the trust anchors verify, the health contract still returns
`app == "zairyu-reader"`, the test suite passes, `static\local.js` parses (when Node.js is
available), the icon regenerates, every expected runtime resource is present in the bundle,
**no `.ps1`/`.bat`/`.cmd` payload is bundled**, the distribution inspection passes, and the
packaged trust anchors still match their fingerprints after packaging.

The last two matter most. The script payload check exists because an earlier revision
shipped a PowerShell OCR helper that wrote a card image to `%TEMP%`; the post-packaging
fingerprint check exists because a build machine with the wrong Git line-ending settings can
silently corrupt a checksum-verified asset.

Output:

```text
dist\zairyu-reader\zairyu-reader.exe
dist\zairyu-reader-0.2.1-windows-x64.zip
dist\zairyu-reader-0.2.1-windows-x64.zip.sha256
```

## 7. Manual hardware and OCR checks

**The test suite cannot do this.** It runs on synthetic data and proves nothing about a
reader, a driver, Windows Server 2016, WebView2, or OCR quality.

Work through the manual checklist in [../RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) §7
with authorised cards on the target hardware, and **record what you actually observed**.
Do not carry forward results from a previous release, and do not record a result for a check
you did not run.

## 8. Inspect the archive

Extract the archive somewhere clean and inspect the extracted copy — not `dist/` — because
the archive is what people download:

```powershell
Expand-Archive dist\zairyu-reader-0.2.1-windows-x64.zip -DestinationPath $env:TEMP\rc-inspect
python scripts\inspect_distribution.py $env:TEMP\rc-inspect\zairyu-reader
```

The inspection fails on: `.env`, logs, private keys, debug symbols, source maps, databases,
CSV exports, debug traces, specified-card key material, scripts for an external interpreter,
packaged `tests/`, `docs/`, `__pycache__` or `.git`, developer machine paths, card-number
shaped values other than the synthetic ones, missing runtime resources, and any packaged
certificate or OCR asset whose checksum no longer matches its manifest.

Also open the extracted folder and look at it. An automated check only finds what it was
told to look for.

## 9. Malware scan

Scan the archive before publishing:

- run the machine's own antivirus over the extracted folder;
- consider a multi-engine scan of the `.zip`.

Two caveats worth stating plainly. PyInstaller executables **routinely** produce false
positives, so a single-engine detection is not by itself evidence of a problem. And
uploading the archive to a public scanning service **publishes it** — do not do that for a
build you are not ready to release, and never for anything containing real data.

## 10. Checksums

`-Package` writes `<archive>.sha256` alongside the archive. Verify it, and publish the value
in the release notes so a recipient can check what they downloaded:

```powershell
Get-FileHash -Algorithm SHA256 dist\zairyu-reader-0.2.1-windows-x64.zip
Get-Content dist\zairyu-reader-0.2.1-windows-x64.zip.sha256
```

## 11. Code signing

Code signing is recommended but not a release requirement. If you defer it, use the normal
build command without signing parameters and include this statement in the release notes:

> This executable is not code-signed. Windows may warn before running it. The published
> SHA-256 confirms the exact archive downloaded, but does not establish who built it.

Do not describe an unsigned release as signed or publisher-verified.

Sign only with a real OV or EV code-signing certificate issued to the release publisher.
Do not use a self-signed certificate or a certificate borrowed from another organisation.
Import the certificate (or make its hardware-backed private key available) in either
`CurrentUser\My` or `LocalMachine\My`, then build and sign in one operation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 `
  -UseLockfile -Package -Version 0.2.1 `
  -SignCertificateThumbprint <40-hex-thumbprint> `
  -SignCertificateStoreLocation CurrentUser
```

The build invokes SignTool after PyInstaller creates `zairyu-reader.exe`, applies a SHA-256
Authenticode signature with an RFC 3161 timestamp, verifies that signature, and only then
creates the ZIP. By default it uses DigiCert's public timestamp service; pass
`-TimestampServer <URL>` to use your certificate provider's required service, or
`-SignToolPath <path>` when the Windows SDK Signing Tools are not on `PATH`.

Keep the signing certificate and private key out of the repository, build directory,
archive, logs, and release notes. Record only the public certificate subject, issuer, and
timestamp service in the release checklist. A signature identifies the publisher; the
archive SHA-256 still identifies the exact release download.

## 12. Release notes

Include: the version; the SHA-256 of the archive; what changed; the code-signing identity
or unsigned-binary warning; the requirement to keep the **whole folder** together; supported
Windows versions; the reader requirement (PC/SC, ISO/IEC 14443 **Type B**); known OCR
limitations with a pointer to [ocr.md](ocr.md); the signature-verification limitation; and
the non-affiliation disclaimer.

Do not include: any real card data, screenshots containing real data, hardware serial
numbers, or internal names.

## 13. Privacy review

Before publishing, confirm:

- no genuine card data anywhere in the archive, the release notes, or any screenshot;
- screenshots, if any, were produced in sample-data mode and every visible field checked;
- no developer machine path in the archive or the notes;
- the release notes do not overstate what signature verification proves;
- the release notes do not claim OCR accuracy the tool does not have.

## 14. Final source comparison

Confirm the tree you built from matches the tree you are publishing:

```powershell
git status --porcelain     # must be empty
git log -1 --format=%H     # record this commit in the release notes
```

Record that commit hash. It is what lets someone reproduce the build later.

---

## What this process does not give you

Being clear about the limits matters more than sounding thorough:

- **Not a reproducible build.** PyInstaller output is not bit-for-bit reproducible; two
  builds of the same commit will differ. The *inputs* are pinned — dependencies by hash, the
  OCR model by SHA-256, the certificates by fingerprint — but the output is not.
- **No proof of hardware compatibility.** Only the manual checks in §7 provide that, and only
  for the hardware you actually tested.
- **No supply-chain guarantee beyond the pinned set.** `pip-audit` reports known advisories
  at the time it runs.
- **No assurance from the checksum about the builder.** See §11.
