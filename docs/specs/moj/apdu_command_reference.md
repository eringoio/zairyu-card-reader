# APDU command reference for normal second-generation cards

Generated: 2026-07-07

Primary source: `001460711.pdf`, pp.18-32, sections 4.1-4.2, and Appendix 2 pp.36-39.

This is a focused implementation reference. Check the original PDF for full status-word tables.

## SELECT FILE

Source reference: `001460711.pdf`, section 4.2.1.

### Select DF by AID

```text
00 A4 04 0C 10 <16-byte AID>
```

Example select DF1:

```text
00 A4 04 0C 10 D3 92 F0 00 4F 02 00 00 00 00 00 00 00 00 00 00
```

No response data is expected; success is `90 00`.

### Select EF by EFID

The spec defines EF selection, but most reads in this project can use SFI-style P1 coding via READ BINARY after selecting the parent DF.

```text
00 A4 02 0C 02 <2-byte EFID>
```

## GET CHALLENGE

Source reference: `001460711.pdf`, pp.26-27, section 4.2.3.

Command:

```text
00 84 00 00 08
```

Response:

```text
<RND.ICC: 8 bytes> 90 00
```

Must be executed immediately before MUTUAL AUTHENTICATE.

## MUTUAL AUTHENTICATE

Source reference: `001460711.pdf`, pp.28-29, section 4.2.4; Appendix 1 pp.34-35.

Command:

```text
00 82 00 00 28 <E_IFD: 32 bytes> <M_IFD: 8 bytes> 00
```

Response:

```text
<E_ICC: 32 bytes> <M_ICC: 8 bytes> 90 00
```

Use AES-128-CBC and AES-CMAC as described in `rc2_second_generation_implementation_spec.md`.

If this command returns `63 00`, do **not** retry with first-generation 3DES/Retail MAC. It usually means the second-generation auth data is wrong or stale. Re-run from GET CHALLENGE.

## VERIFY with SM

Source reference: `001460711.pdf`, pp.24-25, section 4.2.2.

Purpose: verify the 12-byte residence-card number after session key exchange.

Build:

```text
plain = card_number_ascii_12_bytes || 80 00 00 00
encrypted = AES-128-CBC(KSenc, IV=00...00, plain)
```

Command:

```text
08 20 00 86 13 86 11 01 <encrypted: 16 bytes>
```

Response success:

```text
90 00
```

Response `63 00` means verification mismatch: the printed card number is wrong for this card.

## READ BINARY

Source reference: `001460711.pdf`, pp.30-32, section 4.2.5.

### Plain READ BINARY

Use for files that require auth but not SM, such as DF2 and DF3 entries after successful VERIFY.

```text
00 B0 P1 P2 00 XX XX
```

If `XX XX` is `00 00`, the target file’s full data is requested.

Example from Appendix 2: read DF3/EF01 after selecting DF3:

```text
00 B0 82 00 00 00 00
```

### SM READ BINARY

Use for access-right entries marked `Card-number auth & SM`, especially DF1 files.

```text
08 B0 P1 P2 00 00 04 96 02 XX XX 00 00
```

`96 02 XX XX` is the SM Le object. If `XX XX` is `00 00`, request full target data.

Example from Appendix 2: read DF1/EF03 after selecting DF1:

```text
08 B0 84 00 00 00 04 96 02 00 00 00 00
```

Response format:

```text
86 <L> 01 <encrypted data> 90 00
```

Decrypt `<encrypted data>` with AES-128-CBC using `KSenc` and IV all-zero, then remove ISO/IEC 7816 padding:

```text
80 00 ... 00
```

### P1 coding

After selecting the relevant parent:

| Current parent | P1 | Target |
|---|---|---|
| MF | `8B` | MF/EF01 common data |
| MF | `8A` | MF/EF02 card type |
| DF1 | `81` | DF1/EF01 card number |
| DF1 | `83` | DF1/EF02 printed entries |
| DF1 | `84` | DF1/EF03 name image + face image |
| DF1 | `86` | DF1/EF04 address image |
| DF2 | `81` | DF2/EF01 permission outside status, residence card only |
| DF2 | `82` | DF2/EF02 renewal/application status, residence card only |
| DF2 | `83` | DF2/EF03 other |
| DF3 | `82` | DF3/EF01 check code + public key certificate |

## Status words to handle explicitly

Common important status words:

| SW | Meaning / handling |
|---|---|
| `90 00` | Success |
| `63 00` | VERIFY mismatch, or mutual-auth data rejected depending on command context |
| `69 82` | Security status not satisfied; likely missing auth/VERIFY or wrong read mode |
| `68 82` | SM not supported for this command/class in current context |
| `69 88` | SM TLV/tag/order/data could not be processed |
| `6A 82` | File not found |
| `6A 86` | P1/P2 incorrect |
| `6B 00` | Offset outside EF range |

Use the original PDF for full command-specific status tables.
