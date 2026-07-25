# RC2 second-generation residence-card implementation spec

Generated: 2026-07-07

## Scope

Implement **normal second-generation Japanese residence cards** and **second-generation special permanent resident certificates**.

Source of truth:

```text
001460711.pdf
第２世代在留カード等仕様書（一般公開用） Ver 1.1, 令和8年4月
```

Use this file for card types:

| Card type code | Meaning | Implement in this task? |
|---|---|---:|
| `05` | 第２世代在留カード | Yes |
| `06` | 第２世代特別永住者証明書 | Yes |
| `07` | 特定在留カード | No |
| `08` | 特定特別永住者証明書 | No |

Source reference: `001460711.pdf`, p.10, section 3.3.4.2.

## Non-scope

Do **not** implement specified cards (`07`/`08`) in the RC2 module.
Specified cards use the separate `001460712.pdf` flow with a `在留 AP` and `SET SESSION KEY` / RSA delivery-key path. See `specified_card_reference_do_not_implement.md`.

## Key protocol differences from first-generation cards

The first-generation implementation in the existing repo uses:

```text
3DES / TDES2Key
Retail MAC
8-byte block size
```

The second-generation specification uses:

```text
SHA-1 for deriving base keys from the 12-byte card number
AES-128-CBC
AES-CMAC, truncated to 8 bytes where used in mutual authentication
16-byte block size
```

Source reference: `001460711.pdf`, pp.34-35, Appendix 1.

## File structure

Source reference: `001460711.pdf`, pp.8-9, sections 3.3.1-3.3.3.

### Second-generation residence card, card type `05`

| Parent | EF | Content | Capacity bytes | Access |
|---|---|---|---:|---|
| MF | EF01 | Common data | 6 | Free |
| MF | EF02 | Card type | 4 | Free |
| DF1 | EF01 | Residence-card number | 14 | Card-number auth + SM |
| DF1 | EF02 | Printed entries | 73 | Card-number auth + SM |
| DF1 | EF03 | Name image + face image | 5508 | Card-number auth + SM |
| DF1 | EF04 | Address image | 2505 | Card-number auth + SM |
| DF2 | EF01 | Permission outside status | 22 | Card-number auth |
| DF2 | EF02 | Renewal/application status code | 3 | Card-number auth |
| DF2 | EF03 | Other | 207 | Card-number auth |
| DF3 | EF01 | Signature for name image + printed entries + face image | 704 | Card-number auth |

### Second-generation special permanent resident certificate, card type `06`

| Parent | EF | Content | Capacity bytes | Access |
|---|---|---|---:|---|
| MF | EF01 | Common data | 6 | Free |
| MF | EF02 | Card type | 4 | Free |
| DF1 | EF01 | Card number | 14 | Card-number auth + SM |
| DF1 | EF02 | Printed entries | 46 | Card-number auth + SM |
| DF1 | EF03 | Name image + face image | 5508 | Card-number auth + SM |
| DF1 | EF04 | Address image | 2505 | Card-number auth + SM |
| DF2 | EF01 | Other | 207 | Card-number auth |
| DF3 | EF01 | Signature for name image + printed entries + face image | 704 | Card-number auth |

## AIDs

Source reference: `001460711.pdf`, p.9, section 3.3.2.

| DF | AID |
|---|---|
| DF1 | `D3 92 F0 00 4F 02 00 00 00 00 00 00 00 00 00 00` |
| DF2 | `D3 92 F0 00 4F 03 00 00 00 00 00 00 00 00 00 00` |
| DF3 | `D3 92 F0 00 4F 04 00 00 00 00 00 00 00 00 00 00` |

There is **no separate `在留 AP` select** in the normal second-generation spec. The `在留 AP` AID belongs to the specified-card spec, not this one.

## BER-TLV requirements

Source reference: `001460711.pdf`, p.7, section 3.2.3.1.

The second-generation specification defines data objects as BER-TLV:

| Part | Size |
|---|---:|
| Tag `T` | 1-2 bytes |
| Length `L` | 1-3 bytes |
| Value `V` | L bytes |

Supported length forms:

```text
00..7F      short form, value length 0..127
81 00..FF   long form, one subsequent length byte, value length 0..255
82 00 00..82 FF FF  long form, two subsequent length bytes, big-endian, value length 0..65535
```

Implementation consequence: do not use a parser that assumes one-byte tags or one-byte lengths. Tag `DFD1` is two bytes.

## Text encoding

Source reference: `001460711.pdf`, p.10, section 3.3.4.

For text fields in sections 3.3.4.1-3.3.4.4 and 3.3.4.7-3.3.4.9, the `符号化` column describes the **character range**, while the actual encoding is:

```text
UTF-8 without BOM
```

Do not decode these fields as Shift-JIS for second-generation cards.

## TLV tags and field meanings

See `tlv_tag_reference.md` for the table. Summary:

| Tag | EF | Meaning |
|---|---|---|
| `C0` | MF/EF01 | Spec version |
| `C1` | MF/EF02 | Card type |
| `C2` | DF1/EF01 | Card number |
| `C5`..`CD`, `CE` | DF1/EF02 | Printed entries |
| `D0` | DF1/EF03 | Name image, MMR TIFF |
| `D1` | DF1/EF03 | Face image, JPEG2000 |
| `DFD1` | DF1/EF04 | Address image, MMR TIFF |
| `D5`..`D8` | DF2 | Permission/application fields |
| `D9`, `DE` | DF2 | Other fields |
| `DC`, `DD` | DF3/EF01 | Signature and public-key certificate |

## Authentication and secure messaging overview

Source reference: `001460711.pdf`, pp.17, 24-28, 34-37, sections 3.5.2, 4.2.2-4.2.4, Appendix 1-2.

Sequence:

```text
1. GET CHALLENGE -> obtain RND.ICC, 8 bytes
2. Generate RND.IFD, 8 bytes
3. Generate K.IFD, 16 bytes
4. Build E_IFD and M_IFD using AES/CMAC
5. MUTUAL AUTHENTICATE -> receive E_ICC and M_ICC
6. Verify M_ICC and decrypt E_ICC
7. Derive KSenc
8. VERIFY with SM using encrypted card number
9. SELECT DF
10. READ BINARY plain or SM depending on EF access rights
```

### Card-number base key derivation

Normalize card number to uppercase ASCII. It must be exactly 12 bytes.

```text
Kenc = first 16 bytes of SHA-1(card_number_ascii_12_bytes)
Kmac = Kenc
```

### Mutual authentication

Inputs:

```text
RND.IFD = 8 bytes random generated by terminal
K.IFD   = 16 bytes random generated by terminal
RND.ICC = 8 bytes from GET CHALLENGE
```

Build:

```text
E_IFD = AES-128-CBC(Kenc, IV=00...00, RND.IFD || RND.ICC || K.IFD)
M_IFD = AES-CMAC(Kmac, E_IFD), first 8 bytes
```

Send:

```text
00 82 00 00 28 || E_IFD || M_IFD || 00
```

Receive:

```text
E_ICC || M_ICC
```

Verify:

```text
AES-CMAC(Kmac, E_ICC), first 8 bytes == M_ICC
```

Decrypt:

```text
P_ICC = AES-128-CBC-Decrypt(Kenc, IV=00...00, E_ICC)
P_ICC = RND.ICC || RND.IFD || K.ICC
```

Then verify the returned `RND.ICC` and `RND.IFD` match the expected values.

### Session key derivation

```text
KSenc = first 16 bytes of SHA-1((K.IFD XOR K.ICC) || 00 00 00 01)
```

Only `KSenc` is specified for subsequent SM encryption/decryption in the normal RC2 flow.

### VERIFY with SM

Source reference: `001460711.pdf`, pp.24-25, section 4.2.2.

Build encrypted card number:

```text
plain = card_number_ascii_12_bytes || 80 00 00 00
encrypted = AES-128-CBC(KSenc, IV=00...00, plain)
```

Command:

```text
08 20 00 86 13 86 11 01 || encrypted
```

If response is `63 00`, the printed card number does not match the chip’s simple authentication code.

## Official crypto test vectors

Source reference: `001460711.pdf`, pp.36-38, Appendix 2.

Use these in unit tests.

```text
card_number = 41 41 31 32 33 34 35 36 37 38 42 42
SHA-1(card_number) = 65 22 B4 E1 71 19 5B B2 18 22 3A 97 6C 04 01 11 BD C4 AA 25
Kenc = Kmac = 65 22 B4 E1 71 19 5B B2 18 22 3A 97 6C 04 01 11

RND.IFD = 11 22 33 44 55 66 77 88
K.IFD   = 40 41 42 43 44 45 46 47 48 49 4A 4B 4C 4D 4E 4F
RND.ICC = 92 1C E2 77 32 3D A0 57

E_IFD =
4A D3 C7 B6 BB 48 4A 52 77 19 77 DE D6 18 B4 1D
F8 41 FA 04 76 A0 5F BE 04 1D EA D6 10 9E 77 3B

M_IFD = AC 85 46 17 63 4F 53 97

MUTUAL AUTHENTICATE command =
00 82 00 00 28 4A D3 C7 B6 BB 48 4A 52 77 19 77
DE D6 18 B4 1D F8 41 FA 04 76 A0 5F BE 04 1D EA
D6 10 9E 77 3B AC 85 46 17 63 4F 53 97 00

E_ICC =
28 9A 96 B1 DA 6A E3 DA 87 77 04 19 BF D1 4F 0B
DA D1 5F 36 43 2B 5A 94 6C 18 8C 72 21 75 9A 62

M_ICC = FA 94 2E C5 1E 62 FF 5F

E_ICC decrypted =
92 1C E2 77 32 3D A0 57 11 22 33 44 55 66 77 88
2C C6 AF 9B 8B 60 7C 66 2F DC AD 27 B4 01 D0 8B

K.IFD XOR K.ICC = 6C 87 ED D8 CF 25 3A 21 67 95 E7 6C F8 4C 9E C4
SHA-1((K.IFD XOR K.ICC) || 00 00 00 01) =
C1 9C F1 3D 3D 7F BE E9 EA 29 3D 83 4C 88 95 2F AD 53 37 F2

KSenc = C1 9C F1 3D 3D 7F BE E9 EA 29 3D 83 4C 88 95 2F

VERIFY encrypted card number = EE 0B 31 EF 87 7F 68 D0 71 C5 6D 58 C7 2E 67 48
VERIFY command =
08 20 00 86 13 86 11 01 EE 0B 31 EF 87 7F 68 D0
71 C5 6D 58 C7 2E 67 48
```

## READ BINARY

See `apdu_command_reference.md` for details.

Important examples from `001460711.pdf`, pp.38-39, Appendix 2:

### Read DF1/EF03 name image + face image using SM

After selecting DF1:

```text
Send -> 08 B0 84 00 00 00 04 96 02 00 00 00 00
Recv <- 86 82 15 91 01 [encrypted name-image + face-image DO, 5520 bytes including padding] 90 00
```

After AES decrypt with `KSenc` and padding removal:

```text
D0 82 09 C4 [name image]
D1 82 0B B8 [face image]
80 00 00 ...
```

### Read DF3/EF01 signature and certificate in plain mode

After selecting DF3:

```text
Send -> 00 B0 82 00 00 00 00
Recv <- DC 60 [96-byte signature]
        DD 82 02 56 [598-byte public key certificate] [00 padding x4] 90 00
```

Certificate may be 599 bytes; then padding is 3 bytes.

## Privacy-conscious reading policy

Default business read must not display, export, or persist face photo data.

Recommended default behavior:

1. Authenticate.
2. VERIFY.
3. Read DF1/EF02 printed entries with SM.
4. Read DF2 fields as required.
5. Read DF3/EF01 only for signature/certificate metadata or optional verification.
6. Avoid reading DF1/EF03 unless name image OCR is explicitly enabled.
7. If reading DF1/EF03 is needed for name image, attempt to discard `D1` immediately and never decode/display/store/export it.

Important caveat: `D0` and `D1` are stored in the same EF (`DF1/EF03`). The official example reads the whole EF. If partial SM reads prove unreliable on hardware, the app must decide by policy whether transient full EF read is acceptable.

Config recommendation:

```text
RC2_ENABLED=true
RC2_READ_PRINTED_ENTRIES=true
RC2_READ_NAME_IMAGE=false
RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME=false
RC2_ENABLE_FULL_SIGNATURE_VALIDATION=false
RC2_STORE_RAW_APDU=false
RC2_STORE_RAW_TLV=false
```

## Signature verification

Source reference: `001460711.pdf`, pp.13, 15, sections 3.3.4.10 and 3.4.3.1.

DF3/EF01 contains:

| Tag | Meaning | Max length | Format |
|---|---|---:|---|
| `DC` | Check code / signature value | 96 | ASN.1 |
| `DD` | Public key certificate | 602 | X.509 v3, ECDSA NIST P-384 SHA256, actual 598 or 599 bytes |

Signature target data:

```text
printed entries || face image || name image
```

For residence cards, printed-entry target length is 53 bytes. For special permanent resident certificates it is 34 bytes padded to 53 with null bytes.

The signature algorithm is:

```text
SHA256WithECDSA
curve: secp384r1 / NIST P-384
```

Default mode should set:

```text
signature_verified = null
signature_verification_note = "Skipped because default policy does not read face image data required by the signature target."
```

Full verification may be added behind a local-only opt-in that transiently reads face-image data for cryptographic verification only and discards it immediately.

## Implementation modules

Suggested modules:

```text
reader/protocols/second_generation_card.py
reader/crypto/aes_cmac.py
reader/crypto/aes_sm.py
reader/parsing/tlv.py
reader/parsing/second_generation_fields.py
reader/signature/rc_signature.py
```

## Expected high-level API behavior

For card type `05` / `06`:

```text
stage = second_generation_read_completed
```

Possible failure stages:

```text
second_generation_auth_failed
second_generation_verify_failed_wrong_card_number
second_generation_sm_read_failed
second_generation_tlv_parse_failed
second_generation_policy_blocked_face_image
second_generation_signature_skipped_by_policy
```

For card type `07` / `08`:

```text
stage = specified_card_blocked_by_policy
```
