# Testing Matrix

Run `pytest` and `node --check static/local.js` (when Node.js is available) before a Windows build. Verify text-export fixtures, malformed/forbidden data, legacy-config migration, status endpoint field safety, removed endpoint 404s, and launcher health identity/lifecycle tests including browser discovery, app arguments, mode selection, and WebView2 fallback. Verify missing/invalid ONNX model behavior, ONNX session initialization failure, safe OCR result fields, name/address engine integration, absence of a default PowerShell subprocess, and lack of runtime network requests.

On Windows: build the one-folder package and confirm that the default executable opens the expected application-style window without a console, tabs, or address bar. On a desktop system verify WebView2; on Windows Server 2016 verify Chrome app mode and JavaScript initialization (language buttons, health status, and reader refresh). Close the application window and confirm an owned server exits, test reuse of an existing valid reader process, and confirm a different service on port 8787 is rejected. Test `--chrome-app`, `--webview`, `--browser`, `--no-browser`, and legacy `--headless`. Exercise the WebView2-missing fallback path and the no-compatible-Chromium bilingual error on suitable test machines.

Then fetch the reviewed PP-OCRv6 model, run `tools\verify_ocr_assets.py`, and build the package. Record the reported package size. Generate the synthetic-only field OCR corpus with `tools/generate_synthetic_ocr_benchmark.py` and record PP-OCRv6 results using `tools/benchmark_ocr_pipeline.py` (exact-line accuracy, CER, address-component preservation, and per-field latency). With authorized cards, manually validate RC2 name and Japanese address recognition, and verify that a first-generation (`1`/`2`) front image produces a reviewed name candidate from segmented text rows; check explicit staff correction, confidence category/review reasons, offline operation, PP-OCRv6 failure to Windows OCR fallback, and all-engines-unavailable paths. Then save a reader, test missing-reader messaging, development mock scan, exact single/multi text paste in Notepad and Excel, duplicate replace/cancel, clipboard fallback and clear, reload clearing the batch, and no hidden diagnostic/integration UI. With authorized cards, test old-generation and RC2 reads, signature states, OCR warnings, moved/absent-card errors, and reconnect.

Do not use unredacted personal data in screenshots, logs, documentation, or tickets.

For trust-store changes, run the signature/trust-store tests with synthetic certificates and
verify all manifest anchor fingerprints, each ZIP/direct first-generation equivalence pair,
production/test profile separation, missing or modified anchors, ambiguous paths, and
certificate/anchor validity reporting. Test `VERIFICATION_TRUST_PROFILE=official_test` in
the staff UI: the persistent warning must be visible and no result may say production
`確認済み`. Physical production and official sample-card tests require explicit authorization.

For first-generation verification, additionally run the synthetic RSA tests for valid and
tampered D0/D1 targets, wrong/missing certificate and signature, invalid certificate time,
unexpected target length, safe result fields, and both card types `1` and `2`. Manual
acceptance remains mandatory: with authorization, test one type `1` residence card and one
type `2` special permanent resident certificate when available; verify correct and incorrect
visible card numbers, successful authenticity, and one safely reproducible malformed or
unsupported condition. Record the card type and status only—never personal data, images,
certificates, or signatures.
