# Decision Log

Architecture and product decisions that still describe the current application, newest
first. Each entry records what was decided and why, so a later change is a deliberate
reversal rather than an accident.

Decisions belonging to a superseded design — the school-management companion agent,
device pairing, job polling, remote submission, the JSON clipboard package, and CSV export
— have been removed rather than archived. None of those features exist, and keeping their
rationale in a public repository would advertise an architecture this product must not
acquire.

## 2026-07-25 — Loopback binding is not the whole security boundary

Decision: A non-loopback `--host` is a hard failure in every mode. On top of that, the
server allowlists the `Host` header, requires a per-process token on every `/api/local/*`
request, checks `Origin`/`Sec-Fetch-Site` on state-changing requests, bounds request
bodies, emits no CORS headers, and returns fixed error messages with no exception text.

Reason: Binding to `127.0.0.1` keeps other machines out but does not keep a *browser* out.
A page staff visit can resolve a hostname it controls to `127.0.0.1` (DNS rebinding) and
then reach `POST /api/local/manual-scan`, which reads a physical card. Absent CORS does not
help, because after rebinding the browser believes the request is same-origin. The `Host`
allowlist is what actually ends that attack — the header still names the host the client
dialled. The token is defence in depth, and is injected into the served page rather than
offered by an endpoint, because an endpoint that hands out the token would hand it to a
rebound origin too.

The previous behaviour warned on stderr and continued, which a windowed build never shows.

## 2026-07-25 — One card read at a time, refused rather than queued

Decision: `POST /api/local/manual-scan` takes a non-blocking lock and returns
`read_already_in_progress` when a read is already running. Mock scans do not take the lock.

Reason: Uvicorn runs synchronous endpoints in a thread pool, so two scans genuinely
overlap, and a PC/SC session is not reentrant — a second read mid-session corrupts the
first one's secure messaging and could return one card's fields under the other's requested
number. Refusing beats queueing because a staff member holding a card on the reader needs
an answer now, and a queued read would run against whatever card is present by the time it
started.

## 2026-07-25 — PP-OCRv6 is the only OCR engine; there is no fallback

Decision: Remove the `Windows.Media.Ocr` fallback entirely. When the packaged recognizer
cannot run, the affected field is shown as "could not be read" and structured IC-chip
reading continues.

Reason: The fallback wrote the preprocessed card image to `%TEMP%` as a real file and ran
`powershell.exe -ExecutionPolicy Bypass` from a packaged desktop application. Cleanup ran
in a `finally` block, which does not survive a crash, a forced termination, or the
launcher's immediate process exit — so a residence-card image could be left on disk, while
the documentation promised image processing was transient in memory. Structured chip fields
are unaffected by an OCR failure, and every OCR-derived field requires staff review anyway,
so the fallback bought little and cost a documented privacy guarantee.

This supersedes the 2026-07-17 decision to keep Windows OCR as a failover.

## 2026-07-25 — No configuration switch may disable a privacy rule

Decision: Remove `DEBUG_TRACE_UNSAFE_LOCAL_MODE` and the `include_raw_apdu`,
`include_raw_tlv`, `include_image_bytes` and `include_personal_values` switches. Diagnostic
traces record structure only: APDU headers, status words, response lengths, TLV tags and
field-presence booleans.

Reason: "Do not store raw IC chip dumps" is a product rule, not a default. Nothing read
these flags, so removing them changed no behaviour — but a public repository that ships a
documented path to raw-chip-dump capture is judged on the existence of the path, not the
difficulty of reaching it.

## 2026-07-17 — Separate production and official-test certificate stores

The offline trust manifest has non-overlapping `production` and `official_test` profiles.
The default production store contains all published first-generation production CAs plus
the normal RC2 CA2. The official test CA is selected only by explicit local environment
configuration and cannot set production authenticity. Specified-card RSA delivery keys are
not certificate anchors and remain outside normal `05`/`06` support.

## 2026-07-17 — Pin PP-OCRv6 medium

Decision: Replace the PP-OCRv5 profile design with the official
`PP-OCRv6_medium_rec_onnx` artifact at revision `4ca479517810450af7bcff5bac0e6c4616987d51`.
The build stages its metadata-derived dictionary and validates all hashes and the ONNX
contract before packaging.

Reason: a pinned upstream ONNX artifact removes the prior local export/dictionary mismatch
surface.

> The original entry also kept Windows OCR as a failover. That half was reversed on
> 2026-07-25; see above.

## 2026-07-16 — Use a checksum-verified local ONNX OCR engine

Decision: OCR is an offline ONNX Runtime CPU engine selected through a narrow `OcrEngine`
interface. It accepts only transient image bytes and returns an image-free result.
Models and dictionaries are staged before the Windows build with a manifest and SHA-256
verification; the executable never downloads model assets.

Reason: A packaged, reviewed model gives a consistent local runtime while preserving the
rule that all OCR candidates require staff review. Missing OCR assets must be
distinguishable from, and non-blocking to, structured chip reads.

## 2026-07-16 — Use installed Chromium app mode as the WebView2 compatibility shell

Decision: Keep the local FastAPI and plain web UI unchanged, but add a Chrome/Edge/Chromium
`--app` shell. Windows Server 2016 prefers it; supported desktop Windows still tries
WebView2 first and falls back to it if WebView2 cannot initialize. `--chrome-app` and
`--webview` are explicit diagnostic modes.

Reason: The affected Server 2016 host can render HTML in WebView2 without running the UI
JavaScript, while the same local page works in Chrome. App mode preserves an
application-style window without replacing the backend or frontend. It uses a dedicated
local browser profile and local URLs only; no remote debugging, extension installation,
JavaScript bridge, cloud access, or card-data persistence is introduced.

Lifecycle limit: The launcher only observes the precise Chromium bootstrap process it
starts. Chromium may delegate an app window to an existing process using the same profile,
so the launcher uses a brief bounded grace period rather than killing unrelated browser
processes or stopping its server immediately. This does not provide perfect close detection
for delegated windows.

## 2026-07-14 — Use a thin pywebview/WebView2 desktop shell for the Windows package

Decision: Keep the existing local FastAPI application and plain HTML/CSS/JavaScript UI, and
host it in a native pywebview window using the Edge Chromium/WebView2 renderer by default.

Reason: It removes browser chrome and the console from normal staff use without rewriting
the proven reader, OCR, parsing, cryptographic, privacy, and copy-text workflows. The shell
starts or validates the loopback server by its additive health identity and stops only a
server it owns.

## 2026-07-09 — Treat `SCARD_W_REMOVED_CARD` at presence-check time as "no card"

Decision: `classify_card_error` never returns `card_moved`. A moved card is only reported
by `classify_read_failure`, after a read has started.

Reason: Real PC/SC readers return `SCARD_W_REMOVED_CARD` (`0x80100069`) when connecting
with no card on the reader at all. Verified on a SONY PaSoRi: the most common staff
situation would otherwise show `読み取り中にカードが動きました` instead of
`在留カードをリーダーに置いてください`.

## 2026-05-30 — Use a local backend instead of browser NFC

Decision: Use a local backend/native layer for reader access rather than a browser NFC API.

Reason: Browser NFC is not suitable for low-level residence-card IC communication.

## 2026-05-30 — Do not store raw chip data or face photos

Decision: The application does not store raw chip dumps or face photos.

Reason: The goal is reading a small set of printed business fields. Everything beyond that
is avoidable privacy risk.
