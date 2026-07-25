# File Structure

- `app.py` — local FastAPI host, static serving, and the loopback request guard middleware.
- `launch_reader.py` — desktop launcher: loopback enforcement, WebView2 / Chromium app shell.
- `reader/local_api.py` — the staff API (`/api/local/*`).
- `reader/local_guard.py` — Host allowlisting, request token, provenance and size checks.
- `reader/local_config.py` — local-only configuration and legacy migration.
- `reader/policy.py` — forbidden-key denylist and recursive response sanitisation.
- `reader/display_fields.py` — staff-facing display values derived from parsed fields.
- `reader/text_export.py` — strict fixed-field tab-separated copy text.
- `reader/protocols/`, `reader/crypto/`, `reader/signature/`, `reader/ocr/` — card reading
  and verification support.
- `reader/runtime_paths.py` — the read-only resource root and the writable per-user root.
- `resources/moj/trust-anchors/` — packaged, checksum-verified CA certificates.
- `resources/ocr/ppocrv6/` — the OCR manifest; the model itself is staged, not tracked.
- `static/index.html`, `static/local.js`, `static/style.css` — the single staff screen.
- `tests/` — protocol, privacy, web-security, and copy-format regressions.
- `tools/` — build-time developer utilities. Nothing here runs at application runtime or is
  packaged into the distribution.
- `scripts/build_windows.ps1`, `zairyu-reader.spec` — Windows package.

No remote agent, remote client, school-management integration, JSON clipboard exporter, CSV
exporter, or diagnostic browser asset is part of the active runtime. The application never
spawns an external interpreter and never writes a card image to disk.
