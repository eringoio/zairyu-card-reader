# RC2 implementation checklist

Generated: 2026-07-07

## Prep

- [ ] Place original MOJ PDFs under `docs/external/moj/specs/`.
- [ ] Place original certificate ZIPs under `docs/external/moj/cert-zips/`.
- [x] Extract runtime trust anchors into `resources/moj/trust-anchors/`.
- [x] Do not distribute specified-card RSA delivery key material at all.
- [x] Add a manifest with certificate fingerprints.

## TLV parser

- [x] Support 1-byte and 2-byte tags.
- [x] Support `00..7F` length form.
- [x] Support `81 xx` length form.
- [x] Support `82 xx xx` length form.
- [x] Preserve tag bytes/hex strings.
- [x] Ignore trailing null padding.
- [x] Test `C1 02 30 35`.
- [x] Test `D0 82 09 C4 ...`.
- [x] Test `D1 82 0B B8 ...`.
- [x] Test `DF D1 82 09 C4 ...`.
- [x] Test `DC 60 ...`.
- [x] Test `DD 82 02 56 ...`.

## Card type detection

- [ ] Read public MF/EF01.
- [ ] Read public MF/EF02 with length-aware TLV read.
- [x] Detect `05` as normal second-generation residence card.
- [x] Detect `06` as normal second-generation special permanent resident certificate.
- [x] Block `07` and `08` as specified-card path.
- [ ] Keep first-generation `1` and `2` regression behavior.

## First-generation signature/certificate (types `1` / `2`)

- [x] Document `DF1/EF01:D0`, `DF1/EF02:D1`, and `DF3/EF01:DA/DB` from
  `001414093.pdf` §§3.3.4.3-3.3.4.4, 3.3.4.9, and 3.4.3.1 (pp. 10, 13-14).
- [x] Read only D0, D1, and DF3/EF01 after old-generation card-number authentication.
- [x] Reconstruct `pad(D0.value,7000) || pad(D1.value,3000)` without TLV headers.
- [x] Verify SHA-256 RSA-2048 PKCS#1 v1.5 `DA` signatures with `DB` X.509 v3 certificate.
- [x] Require exactly one checksum-validated first-generation production CA path.
- [x] Wipe controlled face/image/signature/target buffers and return safe normalized results.
- [x] Keep business fields when authenticity verification fails.
- [x] Cover synthetic valid/tampered type `1` and `2` paths.
- [ ] Perform authorized physical type `1` test.
- [ ] Perform authorized physical type `2` test when available.

## RC2 crypto

- [x] Normalize card number to uppercase 12-byte ASCII.
- [x] Derive `Kenc` and `Kmac` as first 16 bytes of SHA-1(card number).
- [x] Implement AES-128-CBC with zero IV.
- [x] Implement AES-CMAC and truncate to 8 bytes where required.
- [x] Generate `RND.IFD` 8 bytes.
- [x] Generate `K.IFD` 16 bytes.
- [x] GET CHALLENGE and store `RND.ICC`.
- [x] Build `E_IFD`.
- [x] Build `M_IFD`.
- [x] Send MUTUAL AUTHENTICATE.
- [x] Verify `M_ICC`.
- [x] Decrypt `E_ICC`.
- [x] Verify returned `RND.ICC` and `RND.IFD`.
- [x] Derive `KSenc`.
- [x] Unit-test all official Appendix 2 vectors.

## VERIFY

- [x] Build `card_number || 80 00 00 00`.
- [x] Encrypt with `KSenc` using AES-128-CBC zero IV.
- [x] Send `08 20 00 86 13 86 11 01 <encrypted>`.
- [x] Treat `63 00` as wrong card number.
- [x] Unit-test official VERIFY encrypted value.

## READ BINARY

- [x] Implement plain READ BINARY `00 B0 P1 P2 00 XX XX`.
- [x] Implement SM READ BINARY `08 B0 P1 P2 00 00 04 96 02 XX XX 00 00`.
- [x] Parse SM response tag `86`.
- [x] Verify first value byte `01`.
- [x] AES-decrypt encrypted data with `KSenc` zero IV.
- [x] Remove `80 00 ... 00` padding.
- [x] Parse decrypted BER-TLV.
- [x] Retry with full-read `00 00` mode when explicit extended-length READ BINARY fails.
- [x] Test Appendix 2 command shapes.

## Business fields

- [x] Parse DF1/EF02 printed entries.
- [x] Decode second-generation text fields as UTF-8 without BOM.
- [x] Parse DF2/EF01, DF2/EF02, DF2/EF03 for card type `05`.
- [x] Parse reduced DF2 for card type `06`.
- [x] Map work restriction values.
- [x] Map comprehensive permission values.
- [x] Keep raw/unmapped codes in output alongside labels.

## Images and privacy

- [x] Do not read DF1/EF03 by default.
- [x] If name image OCR is enabled, handle `D0` only and discard `D1`.
- [x] Attempt RC2 address OCR from `DF1/EF04` / `DFD1` without returning image bytes.
- [x] Immediately discard `D1` face image.
- [x] Never display/store/export face image.
- [x] Never put image bytes into an API response or copied text.
- [x] Add privacy tests.

## Signature/certificate

- [ ] Read DF3/EF01 after auth.
- [ ] Parse `DC` and `DD`.
- [x] Load all published production CAs and isolated official-test CA2 from runtime resources.
- [x] Validate every selected anchor fingerprint before use.
- [x] Validate RC2 card-certificate chain to exactly one profile-allowed anchor.
- [x] Report certificate validity and anchor validity separately; keep expired-root historical semantics unresolved.
- [x] Keep official test verification separate from production authenticity.
- [x] Default full signature verification skipped because face image is part of target.
- [ ] Add optional full verification behind explicit config.

## Specified cards

- [x] Return `specified_card_blocked_by_policy` for `07`/`08`.
- [x] Do not select My Number/JPKI applications.
- [x] Do not use RSA delivery key for `05`/`06`.
- [x] Add tests proving `07`/`08` are blocked.

## Docs and diagnostics

- [x] Update README.
- [x] Update the current-state document.
- [x] Add hardware diagnostic mode that logs only status/stage metadata, not raw personal data.
- [x] Add clear error messages for auth, verify, SM read, TLV parse, and policy-blocked image cases.
- [x] Keep diagnostic files local under gitignored `debug_traces/` when enabled.
