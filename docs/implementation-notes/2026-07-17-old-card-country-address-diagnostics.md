# 2026-07-17 — Old-card country, address, and safe diagnostics

## Change

First-generation card OCR now uses explicit printed field labels before applying broad
fallback heuristics. In particular, nationality is read from the value after
`国籍・地域`/`Nationality`, and an address ends before the next printed card-field label.
This prevents a country value or a subsequent field from being appended to the address
when the recognizer joins adjacent rows.

The staff result includes a toggleable OCR diagnostics panel. It provides only safe scan
health metadata: OCR status, engine/model identifiers, aggregate confidence, detected text
row count, image dimensions, and review statuses. It never displays or returns the card
image or full raw OCR text. All image processing and row extraction remain in memory.

Old-card address candidates now use the same reviewed-address metadata as the dedicated
address path. The diagnostic distinguishes explicit-label extraction from a conservative
fallback, without revealing the extracted card contents.

Each detected old-card text row is recognized using bounded autocontrast and adaptive
threshold renderings, then the better local result is selected. A one-letter sex marker
is no longer allowed to become a nationality fallback; an unread country is left blank
and marked for review instead of being silently misreported.

Nationality parsing now preserves Japanese Katakana and English text after `男M.`/`女F.`.
It does not pass through an unrecognised Han-only nationality candidate. Address parsing
keeps only values anchored at a Japanese prefecture (or an explicitly recognized address
label); an unanchored fragment is rejected rather than presented as a credible address.

## Checks run

```bash
PYTHONPATH=/tmp/ppocrv6-test-deps python3 -m pytest -q -s \
  tests/test_old_card_ocr.py tests/test_onnx_ocr.py \
  tests/test_ocr_field_pipeline.py tests/test_name_ocr.py \
  tests/test_second_generation_protocol.py
node --check static/local.js
```

## Follow-up

Real first-generation card acceptance remains necessary. Do not retain real card images
or OCR transcripts as test fixtures; use the safe diagnostics fields and synthetic tests
to investigate a failed read.
