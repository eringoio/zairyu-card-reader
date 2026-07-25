# 2026-07-08 - RC2 labels and image OCR policy

## Summary

Improved second-generation (`05` / `06`) read output after real-card testing showed structured fields were readable but UI-facing labels and OCR status were incomplete.

## Changes

- Added `read_at` to RC2 successful read data.
- Added safe label helpers for nationality, period of stay, and residence-status codes.
- Mapped `PAK` to `Pakistan`.
- Interpreted period codes such as `0010` as `10 months` and `0000` as `Indefinite`.
- Made unmapped residence-status codes explicit instead of displaying the raw code as a label.
- Added local address OCR attempt from `DF1/EF04` / `DFD1`.
- Kept RC2 name OCR blocked by default when reading `DF1/EF03` would also expose `D1` face-image data.
- If transient name-image read is enabled, only `D0` is used for OCR and `D1` is discarded.
- Added `docs/specs/moj/code_maps_needed.md` for missing official code masters.

## Privacy notes

The implementation must not return, store, export, log, or trace raw APDU bytes, TLV values, image bytes, face photos, My Number/JPKI data, or raw chip dumps. OCR uses image bytes transiently in memory only.

## Verification

Checks run:

```bash
python3 -m py_compile reader/protocols/second_generation_card.py reader/parsing/second_generation_fields.py tests/test_second_generation_protocol.py tests/test_second_generation_fields.py
```

Focused pytest should be run in the Windows virtual environment before claiming test pass/fail status for hardware-adjacent behavior.
