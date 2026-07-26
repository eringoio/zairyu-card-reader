# Privacy and Security

The technical detail behind [PRIVACY.md](../PRIVACY.md). If you want the plain-language
version of what the application does with card data, read that first. This document
describes the mechanisms and, just as importantly, their limits.

Use only cards whose holder has consented or whose verification you are authorised to
perform.

## Output policy

Never copy, persist, display in the staff UI, log, or transmit: raw APDU/TLV/IC material,
card or face-image bytes, My Number/JPKI data, raw OCR text, certificate or signature bytes,
signed targets, personal debug traces, or remote credentials. The UI presents only reviewed
business fields and human-readable signature/OCR warnings.

Two independent mechanisms enforce this, in this order:

1. **A denylist.** `reader/policy.py` rejects any key whose name contains one of 39
   forbidden fragments — `face_photo`, `my_number`, `jpki`, `raw_apdu`, `raw_tlv`,
   `ocr_text`, `certificate_bytes`, `signed_target`, and so on. It recurses into nested
   mappings and into lists, so a forbidden key three levels down inside an array is still
   removed.
2. **An allowlist.** `reader/local_api.py` then keeps only the ~60 named keys the staff UI
   actually uses. Anything not named is dropped, including anything new that a future change
   might introduce.

A denylist alone would fail on an unforeseen key name; an allowlist alone would silently
pass a forbidden value that happened to be listed. Both, in that order, is the point.

## The loopback boundary

Binding to `127.0.0.1` keeps other machines out. It does not, by itself, keep a *browser*
out: a page the staff member visits can point a hostname it controls at `127.0.0.1` (DNS
rebinding) and then talk to this server as though it were same-origin. Cross-origin rules do
not help, because after rebinding the browser believes the request *is* same-origin. None of
these endpoints authenticate a user, because a card reader has no user to authenticate.

Four controls close that gap:

- **Loopback-only binding, enforced.** `--host` accepts `127.0.0.1`, `localhost` and `::1`
  and nothing else. Any other value is a hard failure with a visible message in every mode,
  including `--no-browser`. LAN hosting, tunnels, reverse proxies and public deployment are
  not supported and are not reachable by configuration.
- **`Host` allowlisting.** A rebound request still carries the attacker's hostname in its
  `Host` header, so every request whose `Host` is not a loopback name is refused with `400`
  before any handler runs. This is the control that actually ends the attack.
- **A per-process request token.** Minted at startup with `secrets.token_urlsafe(32)`,
  embedded in the page this server itself serves, and required on every `/api/local/*`
  request. It is never logged, never placed on a command line, and never returned by an
  API — an endpoint that handed the token out on request would hand it to a rebound origin
  too. Only `/api/health` is exempt, because the launcher probes it to identify this process
  before any page exists, and it returns no card, reader, or configuration data.
- **Provenance checks.** A state-changing request carrying a foreign `Origin`, or
  `Sec-Fetch-Site: cross-site`, is refused.

Request bodies are bounded to 1 MiB before they are read. No CORS headers are emitted at
all. Unexpected failures return a fixed message with no traceback, no exception text, and no
path — Python exception text routinely contains card values and local paths.

Every response carries `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`;
`/` and `/static/*` additionally carry a same-origin `Content-Security-Policy` and
`Cache-Control: no-store`.

**This is a reasonable local boundary. It is not a claim that the application is safe to
expose to a network — it is not designed to be, and must not be.** In particular, the token
is readable by any process running as the same Windows user, because that process can read
the same page a browser reads. That is inherent to a local service with no user accounts.

## Concurrency

A PC/SC session is not reentrant. `POST /api/local/manual-scan` takes a non-blocking lock
and refuses a second read with `read_already_in_progress` rather than queueing it: a queued
read would run against whatever card happened to be on the reader by the time it started,
which could return one card's fields under another's requested number.

## The desktop shell

The packaged desktop shell hosts the same FastAPI UI only on `127.0.0.1`. It has no
pywebview JavaScript bridge, disables embedded downloads, and uses WebView2 rather than an
obsolete browser renderer where available.

The Chromium app-mode fallback launches only the local loopback URL with `--app`, a
dedicated `%LOCALAPPDATA%\ZairyuReader\BrowserProfile`, and flags that disable first-run
setup, extensions, sync, and background networking. It does not enable remote debugging,
does not install extensions, and never places card data in command-line arguments.

## OCR

OCR uses the packaged PP-OCRv6 ONNX Runtime CPU recognizer and transient in-memory image
bytes. It performs no runtime model download and no external API request, and it is the
**only** recognizer: when it cannot run, the result is an OCR-only failure that does not
prevent structured chip fields from being read.

**No card image is written to disk at any point, and the application never spawns
PowerShell or any other interpreter.** An earlier `Windows.Media.Ocr` fallback did both —
it wrote the preprocessed card image to `%TEMP%` and ran `powershell.exe -ExecutionPolicy
Bypass` — and was removed rather than documented. A test asserts that nothing under
`reader/ocr/` imports `subprocess` or `tempfile`, so the pattern cannot return unnoticed.
See [ocr.md](ocr.md).

## Trust anchors

Trust-anchor certificates are packaged public material and are verified against a recorded
SHA-256 fingerprint before use; a mismatch refuses the anchor rather than falling back to it.

The `production` and `official_test` stores are deliberately non-overlapping, filtered by
both profile and card generation. `VERIFICATION_TRUST_PROFILE=official_test` is a local
diagnostic setting; the UI remains visibly marked and its results are never presented as
production authenticity. Raw certificates, fingerprints, signatures, and selected-card
certificate details do not reach ordinary staff API responses. Specified-card RSA delivery
keys are not distributed with this project and are never loaded by the normal `05`/`06`
path.

See [official-certificates.md](official-certificates.md).

## The transient face read

First-generation authenticity verification transiently reads `D0` (front image), `D1` (face
image), and `DA`/`DB`, only after authorised card-number authentication. Second-generation
verification reads the name and face images from the same file for the same reason: the
card's signature is computed over the printed entries plus the face image plus the name
image, so the face image is part of the signed target and verification is impossible
without it.

The application creates controlled mutable buffers for the face, image, signature and
target values and overwrites them immediately after verification. None of them cross the
API, the UI, diagnostics, or logs.

**CPython memory erasure is best effort only.** Immutable values and copies made by the
allocator or the interpreter cannot be proven erased. This is a documented mitigation, not
a claim of guaranteed memory sanitisation.

## Diagnostics

Diagnostic traces are off by default. When enabled they record structure only: APDU header
bytes, status words, response lengths, TLV tags, and field-presence booleans. There is
**no configuration switch** that can make a trace contain raw APDU or TLV bytes, image
bytes, or personal values — the switches that once existed were removed rather than
defaulted off, because a privacy rule with an off switch is a default, not a rule.

When file output is explicitly enabled, traces are written under the per-user data directory
rather than the process working directory, which for a double-clicked executable is
unpredictable.

## What this does not defend against

- A compromised Windows account, or another process running as the same user.
- Physical access to an unlocked machine.
- A malicious card. Signature verification confirms a cryptographic relationship; it does
  not confirm that a card is currently valid or has not been invalidated.

Report a vulnerability privately — see [SECURITY.md](../SECURITY.md).
