# 2026-07-07 - RC2 diagnostic trace hardening

## Summary

Added a safe-by-default diagnostic trace helper and `POST /api/read-card-diagnostic` for local troubleshooting of current, second-generation, specified, and failed read flows.

## Privacy behavior

- Trace output includes stages, APDU command headers, status words, response lengths, TLV tag summaries, field presence, and failure classifications.
- Trace output does not include raw APDU response bytes, raw TLV values, image bytes, My Number/JPKI data, raw certificate bytes by default.
- Optional trace files are written only when `DEBUG_TRACE_WRITE_TO_FILE=true`, under local gitignored `debug_traces/`.

## RC2 hardening

- `nationality_label` now falls back to `nationality_region_code`.
- RC2 read failures now include safe failure classifications.
- Extended-length READ BINARY attempts retry with full-read mode where applicable.
- Second-generation image/OCR messages now report a default privacy-policy block instead of "not implemented".
- Signature validation remains metadata-only until the image/signature target policy changes.

## Verification

Run in this WSL shell:

```bash
python3 -m py_compile reader/config.py reader/diagnostics.py reader/protocols/second_generation_card.py reader/residence_card_reader.py reader/parsing/second_generation_fields.py app.py tests/test_second_generation_protocol.py tests/test_residence_card_reader.py tests/test_api.py tests/test_config.py
```

Result: passed.

Skipped:

- Focused pytest could not run because WSL Python lacks `pytest`.
- `.venv/Scripts/python.exe -m pytest ...` failed from WSL with the known Windows/WSL boundary error: `UtilBindVsockAnyPort`.
