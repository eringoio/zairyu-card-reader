# Release Checklist

Copy this file for each release and fill it in as you go. [docs/releasing.md](docs/releasing.md)
explains why each step exists.

**Record what you actually did.** Leave a box unticked and write why rather than ticking it
optimistically. A checklist that is always fully ticked tells nobody anything.

```text
Version:            ____________________
Commit (git log -1 --format=%H): ____________________________________________
Built by:           ____________________
Build date:         ____________________
Build machine OS:   ____________________
Python version:     ____________________
```

---

## 1. Clean environment

- [ ] Built from a **fresh clone**, not a working development tree
- [ ] `git status --porcelain` is empty
- [ ] No pre-existing `dist/`, `build/`, or `.env` in the tree
- [ ] Virtual environment created fresh for this build

## 2. Dependencies

- [ ] `pip install --require-hashes -r requirements.lock.txt` succeeded
- [ ] `pip install -r requirements-dev.txt` succeeded
- [ ] Lockfile is current for `requirements.txt` (regenerate and review the diff if not)
- [ ] `pip-audit --requirement requirements.lock.txt` reported no known vulnerabilities

```text
pip-audit result: ____________________________________________
```

## 3. OCR model retrieval and verification

- [ ] `tools\fetch_ocr_assets.ps1` completed successfully
- [ ] It reported no manifest mismatch (a mismatch means it installed **nothing** — investigate before retrying)
- [ ] `python tools\verify_ocr_assets.py` exited 0

```text
Reported model name:      ____________________
Reported input shape:     ____________________
Output classes / dict:    ____________________
```

## 4. Trust anchors

- [ ] `pytest -q tests\test_packaged_assets_integrity.py` passed
- [ ] No specified-card RSA delivery key material present anywhere in the tree

## 5. Tests and lint

- [ ] `pytest -q` passed — **not** with `-SkipTests`, and not with failures explained away

```text
Test result: ______ passed, ______ failed
```

- [ ] `ruff check .` passed
- [ ] `node --check static\local.js` passed (or Node.js unavailable — note which)

## 6. Build

- [ ] `scripts\build_windows.ps1 -UseLockfile -Package -Version <version>` completed
- [ ] Every automated gate passed: OCR assets, trust anchors, health contract, tests, JS syntax, icon, bundled resources, **no script payload**, distribution inspection, post-packaging certificate fingerprints

```text
Distribution size: ____________ MiB
Archive SHA-256:   ____________________________________________________________
```

## 7. Manual hardware and OCR checks

**The automated suite proves none of this.** Run these with authorised cards on the target
hardware and record what you observed. Do not carry results forward from a previous release.

### Environment

```text
Reader make/model:        ____________________
Reader driver version:    ____________________
Type B support stated?    ____________________
Windows version/build:    ____________________
WebView2 or Chromium:     ____________________
```

### Application startup

- [ ] `zairyu-reader.exe` launched by double-click on a machine with **no Python installed**
- [ ] The window opened without an address bar or console
- [ ] The reader appeared in the reader list and the selection saved

### Sample-data path

- [ ] A sample-data read filled all 17 fields with obviously synthetic values

### Real card — first generation (types `1`/`2`)

```text
Tested?  yes / no / not available
```

- [ ] Card detected
- [ ] Structured chip fields read and correct against the card
- [ ] Signature status observed: `____________________`
- [ ] Name OCR quality: `____________________`
- [ ] Address OCR quality: `____________________`

### Real card — second generation (types `05`/`06`)

```text
Tested?  yes / no / not available
```

- [ ] Card detected
- [ ] Structured chip fields read and correct against the card
- [ ] Signature status observed: `____________________`
- [ ] Name OCR quality: `____________________`
- [ ] Address OCR quality: `____________________`

### Behaviour under stress

- [ ] Card removed mid-read produces a clear staff message, not a traceback
- [ ] A second read attempted during a read is refused with `read_already_in_progress`
- [ ] An invalid card number is rejected before any reader access

### Log and disk inspection after real reads

- [ ] `%APPDATA%\ZairyuReader\config.json` contains only `config_version`, `reader_id`, `app_version`
- [ ] No card image, `.png`, or temporary image anywhere in `%TEMP%` after a read
- [ ] No `debug_traces` directory created
- [ ] No `.log` file created
- [ ] Console output (run with `--no-browser`) contains no name, address, or card number

```text
Anything unexpected observed: ____________________________________________
```

## 8. Archive inspection

- [ ] Archive extracted to a clean location
- [ ] `python scripts\inspect_distribution.py <extracted>\zairyu-reader` passed
- [ ] Extracted folder opened and looked at by a human, not only by the script

```text
Inspection result: ______ findings
```

## 9. Malware scan

- [ ] Local antivirus scanned the extracted folder
- [ ] Multi-engine scan considered — **and the consequence understood: uploading publishes the file**
- [ ] Any detection assessed rather than assumed to be a false positive (PyInstaller output commonly triggers these, which is a reason to check, not to dismiss)

```text
Scanner and result: ____________________________________________
```

## 10. Checksums

- [ ] `<archive>.sha256` generated and verified against a fresh `Get-FileHash`
- [ ] The SHA-256 will be published in the release notes

## 11. Release notes

- [ ] Version and archive SHA-256 included
- [ ] **Unsigned-binary warning included**, stating that a checksum proves what was downloaded, not who built it
- [ ] "Distribute the whole folder, not just the .exe" stated
- [ ] Supported Windows versions stated
- [ ] Reader requirement stated: PC/SC, ISO/IEC 14443 **Type B**
- [ ] Known OCR limitations stated, with a pointer to `docs/ocr.md`
- [ ] Signature-verification limitation stated — it does not prove a card is currently valid
- [ ] Non-affiliation disclaimer included
- [ ] Build commit hash recorded

## 12. Privacy review

- [ ] No genuine card data in the archive, the notes, or any screenshot
- [ ] Any screenshot was produced in sample-data mode, with every visible field checked
- [ ] No developer machine path in the archive or the notes
- [ ] Notes do not overstate what signature verification proves
- [ ] Notes do not claim OCR accuracy the tool does not have

## 13. Final source comparison

- [ ] `git status --porcelain` still empty after the build
- [ ] The published commit matches the tree that was built
- [ ] The tag, if any, points at that commit

---

## Sign-off

```text
Everything above is recorded honestly, including the steps that were skipped
and the checks that were not run.

Name:  ____________________
Date:  ____________________
```

## Not released by this checklist

Publishing is a separate, deliberate act. This checklist stops at "files exist and have
been verified". It does not create a GitHub release, upload anything, or sign a binary.
