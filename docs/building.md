# Building the Windows package

**[日本語版 →](building.ja.md)**

Produces `dist\zairyu-reader\zairyu-reader.exe`, a one-folder distribution that runs on a
Windows PC with no Python installed.

## Prerequisites

- A **Windows** development machine. The package cannot be cross-built.
- Python 3.11 or later, 64-bit.
- Dependencies installed and the OCR model staged — see
  [installation.md](installation.md).
- Internet access, for `pip install` and the model download. Not needed afterwards.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Options:

```powershell
scripts\build_windows.ps1 -SkipTests          # skip the test suite
scripts\build_windows.ps1 -Python "C:\Path\To\python.exe"
```

`-SkipTests` exists for iterating on packaging problems. Do not use it for a release build.

## What the build checks

The script refuses to produce a package when any of these fail, in this order:

1. **Dependencies** install, including PyInstaller.
2. **The staged OCR model** passes `tools\verify_ocr_assets.py`: every manifest hash, the
   metadata and dictionary ordering, the fixed BGR `[1, 3, 48, W]` recognition input, and
   the CTC output class mapping.
3. **The health contract** still returns `app == "zairyu-reader"`. The launcher uses this to
   tell its own server apart from an unrelated service on the same port; breaking it breaks
   process identification.
4. **The test suite** passes, unless `-SkipTests` was given.
5. **`static\local.js` parses**, if Node.js is available. Skipped with a message if not.
6. **The icon** regenerates.
7. **Expected runtime resources** are present in the bundle: the static page, the four OCR
   assets, the trust-anchor manifest, and the webview support directory.
8. **No script payload is bundled.** The build fails if any `.ps1`, `.bat` or `.cmd` file
   appears anywhere in `dist\`.

Check 8 is a security regression guard rather than a packaging check. An earlier version of
this application shipped a PowerShell OCR helper that wrote a card image to `%TEMP%` and ran
`powershell.exe -ExecutionPolicy Bypass`. That path was removed; this assertion makes its
return fail the build rather than ship quietly.

## What the package contains

- The reader stack, protocol modules, and signature verification.
- The static staff page.
- ONNX Runtime CPU native libraries and the verified PP-OCRv6 model, metadata, and
  dictionary.
- The Ministry of Justice trust anchors.
- pywebview.

It does **not** contain: a bundled Chromium or WebView2 runtime, any script for an external
interpreter, developer tools from `tools\`, tests, documentation, or the specification PDFs.

## Why one folder rather than one file

A one-file PyInstaller build re-extracts the entire bundle into `%TEMP%` on every launch.
With a 76 MB model that is slow, and antivirus software re-inspects the extracted files each
time. One-folder avoids both.

## Distributing it

Copy the whole `dist\zairyu-reader` folder. `zairyu-reader.exe` will not run without the
`_internal` folder beside it.

The executable is unsigned. Windows SmartScreen will warn on first run on a machine that has
not seen it before. Code signing is the maintainer's decision and is not part of this build.

## Windows Server 2016

Requires:

- Desktop Experience — **Server Core cannot display this UI**;
- an installed Chromium-family browser for the preferred app shell;
- a PC/SC-compatible reader driver and the Windows Smart Card service;
- the staged ONNX Runtime and model compatibility check to pass.

WebView2 remains an optional forced mode there, not the required shell.

## What the build does not prove

The Python test suite runs on synthetic data. **It does not prove** Windows Server 2016
compatibility, Chromium app-mode behaviour, ONNX Runtime or model compatibility on the
target hardware, WebView2 behaviour, or reader-driver compatibility.

Validate those manually on the target environment with authorised hardware. See
[testing-matrix.md](testing-matrix.md).

## Launcher lifecycle limitation

The launcher monitors only the exact Chromium process it started, and never terminates
unrelated Chrome or Edge processes. Chromium can delegate a new app window to an existing
process using the same profile, which makes the bootstrap process exit immediately. In that
case the launcher keeps its server alive for a short bounded grace period rather than
stopping at once — it cannot reliably detect when the delegated window later closes.

Close existing application windows before relaunching if precise automatic server shutdown
matters.

## Making an actual release

This document covers the build. Producing a release — clean environment, pinned
dependencies, archive, checksum, manual hardware checks, archive inspection, malware scan,
release notes, privacy review — is [releasing.md](releasing.md), with
[../RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) to record what you actually did.

Quick version:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -UseLockfile -Package -Version 0.2.1
```

`-UseLockfile` installs the hash-pinned dependency set. `-Package` writes
`dist\zairyu-reader-<version>-windows-x64.zip` and a matching `.sha256`. Neither publishes
anything.
