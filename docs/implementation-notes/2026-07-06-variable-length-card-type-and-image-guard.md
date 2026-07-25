# 2026-07-06 — Variable-length card-type reading and front-image generation guard

## Goal

Fix two failures observed when a new-generation Japanese residence card (second-generation, no My Number) was presented:

1. `Invalid TLV value length for tag C1.` during card-type detection.
2. `APDU failed. command=00 82 00 00 28 ... status=63 00 response=` when reading the front image.

## Context

- The card-type EF was read with a hardcoded 3-byte APDU (`READ_CARD_TYPE = [0x00, 0xB0, 0x8A, 0x00, 0x03]`). That works for single-character codes (`C1 01 31`) but truncates two-character codes (`C1 02 30 35`), so the TLV parser saw `C1 02 30` and reported an invalid value length.
- The front-image OCR/preview paths called `start_access_control()` unconditionally. That function applies the old/current-card SHA-1/3DES mutual-authentication flow, which a second-generation card rejects with `63 00`.

## Assumptions

- Second-generation and specified-card secure-messaging protocols are still unverified, so no new authentication was implemented or guessed.
- Card-type and common-data public EFs are short BER-TLV objects; reading the 2-byte header first is enough to determine the full length.

## Decisions

- Added `read_short_tlv_file(connection, sfi_p1)` in `reader/residence_card_reader.py`: reads the tag/length header, supports short-form and long-form BER length, then reads exactly the full object. `_read_card_type_info` now uses it for both the common-data and card-type EFs.
- Added `_front_image_generation_guard(card_info)`: returns `None` for the current generation and a `front_image_not_implemented_for_card_generation` response for any other generation. Applied it in `read_front_image_preview` and `read_front_image_ocr` **before** `start_access_control`, so no `00 82` APDU is sent and no image bytes are read for newer generations.
- Fixed the same latent hardcoded-length bug in the (currently unused) `detect_card_type` helper in `reader/card_type.py` with an inline length-aware read (kept inline to avoid an import cycle).

## Files changed

- `reader/residence_card_reader.py`
- `reader/card_type.py`
- `tests/test_residence_card_reader.py`
- `tests/test_card_type.py`
- `docs/current-state.md`
- `docs/testing-matrix.md`

## Checks run

```bash
.venv/Scripts/python.exe -m pytest
```

Result: 65 passed, 1 warning.

## Checks skipped

- Real hardware read of an actual second-generation card (no card/reader available in this environment).

## Results

- Two-character card type codes (`05`/`06` → `second_generation`, `07`/`08` → `specified`) are read and classified without the `Invalid TLV value length` error.
- Front-image OCR/preview for non-current generations returns a clear not-implemented message and never attempts old/current-card authentication, so the confusing `63 00` APDU failure no longer occurs.
- Current-card behavior is unchanged; the current-card access-control flow still runs for card type `1`/`2`.

## Risks / follow-up

- Second-generation/specified protected-file reading remains unimplemented pending the official public specification.

## Suggested next step

- When the official second-generation specification is verified, implement its secure-messaging read behind the same card-type dispatch, keeping My Number/JPKI strictly out of scope.
