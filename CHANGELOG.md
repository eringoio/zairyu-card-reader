# Changelog

## Unreleased

### Security hardening for the public release

- Removed the `Windows.Media.Ocr` fallback entirely. It wrote the preprocessed card image
  to `%TEMP%` as a real file and ran `powershell.exe -ExecutionPolicy Bypass` from a
  packaged desktop application, contradicting the project's own rules. PP-OCRv6 is now the
  only recognizer; when it cannot run, the result is "OCR unavailable" and structured
  IC-chip reading continues. `tools/windows_ocr.ps1` is deleted and no longer packaged, and
  the front-side text parsing it shared a module with moved to `reader/ocr/front_text.py`.
- A non-loopback `--host` is now a hard failure with a visible message in every mode.
  Previously `--no-browser`, `--browser` and `--headless` printed a stderr warning and
  continued, which a windowed build never shows.
- Added `Host`-header allowlisting, so a DNS-rebound page reaches the socket but not the
  application.
- Added a per-process request token, embedded in the served page and required on every
  `/api/local/*` request. It is never logged, never placed on a command line, and never
  returned by an API. `/api/health` stays exempt for launcher process identification.
- Added `Origin`/`Sec-Fetch-Site` provenance checks on state-changing requests, a 1 MiB
  request-body bound, and redacted error responses that carry no traceback or exception text.
- Serialised card reads: a second scan while one is in progress is refused with
  `read_already_in_progress` rather than corrupting the first reader session.
- Removed the eight unconditional `[DEBUG]` prints on the signature-verification path. They
  interpolated exceptions derived from card certificate bytes; every call site already
  returns the same classification as a structured status.
- Removed the `DEBUG_TRACE_UNSAFE_LOCAL_MODE` gate and the `include_raw_apdu`,
  `include_raw_tlv`, `include_image_bytes` and `include_personal_values` switches. Nothing
  read them, and a switch that can disable "do not store raw IC chip dumps" should not exist.
- Gated the per-scan console diagnostics block, resolved a relative `debug_traces` path
  under the per-user data directory instead of the process working directory, and dropped
  the `git rev-parse` subprocess from trace metadata.
- Removed the unused `GET /api/readers` and `POST /api/check-card` endpoints, which
  duplicated `/api/local/status` and took an unvalidated query parameter.
- Removed `docs/external/moj/certs/001462222.zip`, the specified-card RSA delivery key
  archive. Its identifier and SHA-256 remain recorded so the omission is verifiable.

- Added separate first-generation (`1`/`2`) SHA-256/RSA-2048 PKCS#1 v1.5 signature
  verification over the official padded D0/D1 target, using only checksum-validated
  first-generation CAs. It returns safe normalized statuses and remains marked
  `implemented_unverified_on_real_hardware` pending authorized physical-card validation.

- Replaced the single RC2 CA assumption with a checksum-validated, offline manifest for all
  four published first-generation production CAs, the RC2 production CA2, and an isolated
  official-test CA2. Added profile-aware trust-path selection and distinct verification,
  certificate-time, and anchor-time statuses.
- Added `VERIFICATION_TRUST_PROFILE=official_test` as an explicit local-only test mode with
  a persistent staff warning; test verification can never report production authenticity.

- Replaced normal PowerShell/Windows Runtime OCR selection with a local ONNX Runtime OCR
  engine abstraction, checksum-verified staged model resources, and visible unavailable
  statuses that do not interrupt chip reads.
- Added Chromium app-mode shell support (`--chrome-app`) with Chrome, Edge, and Chromium discovery, a dedicated local profile, and no remote-debugging or extension flags.
- Added `--webview`, Windows Server 2016 Chrome-app preference, and automatic Chromium fallback when the default WebView2 shell fails to initialize.
- Added launcher tests for browser discovery, mode selection, app-mode arguments, lifecycle ownership, and WebView2 fallback.

## 0.2.1 — 2026-07-15

- Added the default native Windows pywebview/WebView2 shell with browser and server-only fallback modes.
- Added identified local health checks, owned-server lifecycle handling, original application icon, and Windows executable metadata.
- Prevented Uvicorn console-formatter initialization from aborting the windowed executable.

## 0.2.0 — 2026-07-14

- Refactored to a standalone local residence-card reader.
- Removed remote integration, pairing, polling, direct submission, diagnostic browser UI, and JSON clipboard package.
- Added local-only config migration and fixed Japanese tab-separated single/batch copy text.
