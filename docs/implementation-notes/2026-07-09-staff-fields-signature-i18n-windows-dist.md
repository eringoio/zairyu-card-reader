# 2026-07-09 — Staff fields, signature verification, i18n, Windows dist

## Scope

Five changes, in dependency order:

1. Fix missing and wrong fields in `かんたんモード`.
2. Make the canonical period-of-stay label Japanese.
3. Improve name OCR quality.
4. Implement full card-signature verification.
5. Make the whole app bilingual and shippable as a Windows executable.

## Decisions

### A display-normalization layer, not browser-side mapping

`reader/display_fields.py` derives `display_name`, `display_sex`, `display_period_of_stay`, `display_qualification_activity_permission`, `display_qualification_activity_permission_detail`, and `display_signature_status` from the raw chip codes.

The alternative was to map codes in `static/local.js`. Rejected: card semantics (two different work-permission codes, `0000` meaning indefinite) are business rules, not presentation.

`allowlisted_agent_result()` re-derives display fields on every call. A payload that round-trips through the browser therefore cannot smuggle in a doctored `display_sex`; the raw `sex_code` always wins. `tests/test_local_api.py::test_send_manual_scan_re_derives_display_fields_and_ignores_doctored_labels` pins this.

### The 資格外活動許可 bug

Simple mode read only `individual_permission_code`, so a student holding the ordinary comprehensive 週28時間 permission (`comprehensive_permission_code = 1`) saw `なし`. This is the field staff most need to be right. The rule is now: `あり` when the comprehensive code is `1` or `2`, **or** the individual code is `1`.

The mock data carried `part_time_permission: "あり"` but no codes, which is how the bug survived a demo. `reader/mock_reader.py` now carries the structured codes a real RC2 read produces, so mock mode exercises the same path as a card.

### Signature verification reads the face image, deliberately

The MOJ signed target is `printed entries || face image || name image`. There is no way to verify the signature without the face image. Previously the code parsed the certificate and reported `signature_verified: null` with a note saying the check was skipped because policy does not read face-image data.

That is a real gap: staff had no way to know whether a card was genuine. The rule is now drawn around *retention*, not around the read:

- the face image lives only as a local `bytearray` in `reader/protocols/second_generation_card.py`;
- it is passed to `rc_signature.verify_rc2_signature()` to rebuild the signed target;
- the image buffers and the signed-target buffer are zeroed in `finally` blocks before the result dict reaches any caller;
- the result contains no bytes at all — only booleans, statuses, and notes.

`RC2_ENABLE_FULL_SIGNATURE_VALIDATION` now defaults to `true`. `face_photo_status` stays `not_read_by_policy` because nothing is ever retained.

CPython cannot guarantee erasure; the allocator may already have copied the bytes. Zeroing the buffers we control removes the obvious long-lived copy. This is documented as a mitigation, not a proof.

### `signature_verified` needed three states, not two

`str(None)` renders as the literal `"None"`, which reads as a value. "Not checked" and "not valid" are different answers and conflating them is the kind of thing that gets a genuine card rejected at a front desk. `reader/models.py::_tristate` renders `True`/`False`/`None` as `"true"`/`"false"`/`""`, and `signature_verification_status` carries the reason.

### Name OCR: scoring, not `max(len)`

The old extractor cleaned each OCR line to `[A-Z '-]` and returned the longest. On a real card image that picks `RESIDENCE CARD` as often as a name, and truncates a name split across two OCR detections.

Candidates are now built from single lines *and* from runs of up to three adjacent lines, then scored. The tuning that mattered:

- **word count dominates letter count** (`+8` per word), so `YAMADA TARO SMITH` beats `YAMADA`;
- **repeated words cost `-25`**, so a merge that glues two readings of the same name (`TARO` + `YAMADA TARO SMITH`) loses to the better single line;
- **each merged line costs `-6`**, so a merge must pay for itself and a clean single line wins a tie;
- **heading tokens cost `-40`**, and a heading never anchors or extends a merge.

The duplicate-word and merge penalties were both added after tests showed the greedy merge always won: more words always meant more score. Without them the extractor would happily return `RESIDENCE CARD YAMADA TARO`.

Confidence is the score normalized against a clean two-word name (`45.0`). Below `0.5` the result carries a review note.

### i18n: message keys, not translated payloads

Backend responses carry a stable `error_code`, a stable `message_key`, **and** a rendered `message`. The browser prefers the key; `message` is the fallback for clients that cannot translate. Existing `error_code` values and Japanese `message` text are unchanged, so the API stays backward compatible.

`locale_from_accept_language(None)` returns Japanese, not English. An absent header is the absence of a signal, not an unknown locale — this is a Japanese-workplace tool, and every browser sends the header. `resolve_locale("fr")` returns English, which is the rule the spec actually asked for. The two functions are separate so the distinction is testable.

`static/i18n.js` is loaded at the **end of `<body>`**, before `app.js` and `local.js`, and applies translations synchronously. Loading it in `<head>` with a `DOMContentLoaded` listener would have fired *after* `app.js` wrote its first dynamic values and overwritten them with placeholders.

`tests/test_i18n.py` parses `static/i18n.js` and asserts that every backend `message_key` is translatable by the frontend, and that both catalogues define the same keys. A drifting key would otherwise silently fall back to the server's locale.

### Windows dist: one folder, two roots

`reader/runtime_paths.py` is the single place that resolves paths. `resource_root()` is read-only and becomes `sys._MEIPASS` when frozen; `user_data_root()` is writable and stays at `%APPDATA%\ZairyuReaderAgent`. Exports move out of the bundle in a frozen build, because the bundle is wiped on exit and may sit under `Program Files`.

One-folder rather than `--onefile`: a one-file build re-extracts into `%TEMP%` on every launch, which antivirus re-inspects each time, and the path to `tools/windows_ocr.ps1` changes between runs.

`launch_reader.py` passes the app object directly to uvicorn when frozen; the `"app:app"` import string needs a module search path that does not exist in the bundle.

## Bugs found while implementing

- `EllipticCurvePublicKey.verify()` takes `(signature, data)`. The first draft passed `(data, signature)`. Every tamper test still passed — they expect `False` — and only the happy-path test caught it. Worth remembering that negative crypto tests prove almost nothing on their own.
- `_not_valid_before` used `getattr(cert, "not_valid_before_utc", cert.not_valid_before)`, which evaluates the deprecated naive-datetime property eagerly and emitted a `CryptographyDeprecationWarning` on every parse. Replaced with an explicit `hasattr` check.
- The two pre-existing `tests/test_residence_card_reader.py` failures were in scope and trivial: the fake `read_second_generation_card` took three arguments while the caller passed a fourth (`trace`).

## Verification

359 tests pass. Beyond the suite:

- ran the app and exercised `/api/local/manual-scan` in both locales, confirming the display fields, message keys, and step labels;
- checked the manual-scan payload against `forbidden_keys()` — 58 fields, none forbidden, all strings;
- syntax-checked and executed `static/i18n.js` under Node to confirm locale detection matches `reader/i18n.py`, key parity, and `message_key` preference with `message` fallback;
- built `dist\zairyu-reader\zairyu-reader.exe`, ran it, and confirmed it serves the UI, resolves bundled resources, performs a mock scan, and detects a real PC/SC reader (SONY PaSoRi) with pyscard bundled.

## Still untested against hardware

Real signature verification has never run against a physical card. The signed-target byte layout — TLV values concatenated and NUL-padded to 53 bytes — is derived from the MOJ Markdown specs in `docs/specs/moj/`, not confirmed on a card. Whether the real `DC` value is raw 96-byte `r‖s` or DER is also unconfirmed; both are accepted, so either works, but only one is real.

This is the highest-risk assumption in the change. See `docs/testing-matrix.md`.
