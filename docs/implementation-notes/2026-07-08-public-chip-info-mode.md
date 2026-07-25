# 2026-07-08 - Public chip info mode

## Summary

Added a public metadata read path for residence-card chips that does not require the printed residence-card number.

## Behavior

- New endpoint: `POST /api/read-public-chip-info`.
- Reads only MF/EF01 common data and MF/EF02 card type through the existing public TLV helper.
- Returns `chip_version`, `card_type_code`, `card_type_label`, `generation`, and the fixed note that only public chip metadata can be read without the residence-card number.
- Does not attempt DF1, DF2, or DF3 reads.
- Does not include card number, raw APDU, raw TLV, image bytes, face photo, My Number/JPKI data.
- Browser UI now has a "Read public chip info" button and explanatory text near card checking.

## Verification

Added a focused API test for the response shape and absence of card-number/APDU detail.

Checks run:

```bash
python3 -m py_compile app.py tests/test_api.py reader/residence_card_reader.py
node --check static/app.js
```

Both passed.

Focused pytest could not run in this WSL shell because `python3` does not have `pytest`, and `.venv/Scripts/python.exe -m pytest tests/test_api.py -q` failed with the known WSL/Windows boundary error `UtilBindVsockAnyPort`.
