# Current State

`zairyu-card-reader 0.2.1`

The application is one staff-facing local screen. It selects a PC/SC reader, checks a card, performs a real or explicitly enabled development mock scan, displays exactly 17 staff fields, and shows separate OCR/signature review warnings. Results are review-only and remain in current page memory. The normal Windows package starts the local FastAPI process on `127.0.0.1:8787` and displays that screen in WebView2 on supported desktop Windows, or in installed Chromium app mode on Windows Server 2016 and after WebView2 startup failure.

The app has no remote dashboard or browser diagnostic surface. Existing legacy configurations are replaced by local-only configuration while preserving `reader_id`. `--chrome-app` and `--webview` force the two application-style shells. `--browser` is a last fallback and `--no-browser`/legacy `--headless` are server-only modes; neither is the normal staff launch path.

Field testing on authorised cards has been completed with a Sony FeliCa RC-S300 reader on
Windows 10, Windows 11, and Windows Server 2016: more than 60 newer-generation and about
10 older-generation cards were read. This is practical acceptance evidence, not a guarantee
for every reader, driver, card condition, or OCR image.

Types `1` and `2` now have a separate official-format first-generation RSA verifier, using
only the pinned first-generation production CA set. Its synthetic implementation status is
`implemented_unverified_on_real_hardware`; broader first-generation coverage remains a
release acceptance concern despite the reported older-generation field tests.

The packaged offline trust store now includes all four official first-generation production
CA certificates, the normal second-generation CA2, and a separately selected official-test
CA2. Normal operation uses `production`; `official_test` is an explicit local configuration
with persistent UI warning and cannot produce a production-authenticity result. No physical
production or official sample card has been used by this repository's automated tests.
