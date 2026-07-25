# RC2 phase implementation

## Summary

Implemented the normal second-generation residence-card RC2 path for card type `05` / `06` using the derived MOJ Markdown specs.

Included:

- BER-TLV parsing for one-byte and two-byte tags, including `DFD1`.
- RC2 SHA-1 base-key derivation, AES-128-CBC, AES-CMAC, mutual-auth command building, encrypted VERIFY, and SM payload decryption helpers.
- Protocol dispatch from `05` / `06` into the RC2 module without calling the first-generation TDES/Retail-MAC access-control path.
- Plain and SM READ BINARY command builders.
- Structured business-field parsing for DF1/EF02 and DF2 fields.
- Runtime CA2 trust-anchor loading for future optional signature validation.
- Explicit policy block for specified cards `07` / `08`.
- UI text for RC2 stages and wrong-card-number errors.
- Safe config flags with raw APDU/TLV storage disabled by default.

## Policy notes

The default RC2 read skips `DF1/EF03`, because that EF contains both name image `D0` and face image `D1`. Face image bytes are not displayed, stored, exported, or returned.

Signature verification defaults to skipped because the signed target includes face-image data. The CA2 trust anchor is available for a future explicit local validation mode.

## Verification note

In this WSL shell, `pytest` is not installed for `python3`, PyCryptodome is not available for crypto-vector execution, and the Windows venv Python fails to launch with the known WSL/Windows boundary error. Syntax checks were run with `python3 -m py_compile` for changed Python files, and `node --check static/app.js` passed.
