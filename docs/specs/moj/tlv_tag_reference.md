# TLV tag reference for normal second-generation cards

Generated: 2026-07-07

Primary source: `001460711.pdf`, pp.7, 10-13, sections 3.2.3.1 and 3.3.4.

## Parser requirements

The second-generation spec uses BER-TLV data objects:

| Component | Size |
|---|---:|
| Tag `T` | 1-2 bytes |
| Length `L` | 1-3 bytes |
| Value `V` | L bytes |

Length encoding:

| Encoding | Meaning |
|---|---|
| `00`..`7F` | length 0..127 |
| `81 xx` | length `xx`, 0..255 |
| `82 xx yy` | big-endian length `xxyy`, 0..65535 |

The parser must preserve tag bytes. Do not convert everything to one-byte integers.

## Common and card type

| Parent/EF | Tag | Max value length | Field | Encoding / format | Detail |
|---|---|---:|---|---|---|
| MF/EF01 | `C0` | 4 | Spec version | UTF-8 / JIS X0201 range | Examples: `0001`, `0002`, ... |
| MF/EF02 | `C1` | 2 | Card type | UTF-8 / JIS X0201 range | `05`, `06`, `07`, `08` |

Card type values:

| Value | Meaning |
|---|---|
| `05` | 第２世代在留カード |
| `06` | 第２世代特別永住者証明書 |
| `07` | 特定在留カード |
| `08` | 特定特別永住者証明書 |

## DF1 tags

| Parent/EF | Tag | Max value length | Field | Encoding / format | Detail |
|---|---|---:|---|---|---|
| DF1/EF01 | `C2` | 12 | Residence-card/certificate number | UTF-8 / JIS X0201 range | 12-byte alphanumeric card number |
| DF1/EF02 | `C5` | 8 | Card expiry date | UTF-8 / JIS X0201 range | `YYYYMMDD` |
| DF1/EF02 | `C6` | 8 | Birth date | UTF-8 / JIS X0201 range | `YYYYMMDD` |
| DF1/EF02 | `C7` | 1 | Sex code | UTF-8 / JIS X0201 range | `1` male, `2` female, `3` unspecified |
| DF1/EF02 | `C8` | 3 | Nationality/region | UTF-8 / JIS X0201 range | Nationality/region code |
| DF1/EF02 | `C9` | 10 | Residence status | UTF-8 / JIS X0201 range | Residence status period code |
| DF1/EF02 | `CE` | 4 | Period of stay | UTF-8 / JIS X0201 range | `YYMM` or `DDD`; `0000` when indefinite |
| DF1/EF02 | `CA` | 2 | Permission type | UTF-8 / JIS X0201 range | Residence cards only |
| DF1/EF02 | `CB` | 8 | Permission date | UTF-8 / JIS X0201 range | `YYYYMMDD`; residence cards only |
| DF1/EF02 | `CC` | 1 | Work restriction | UTF-8 / JIS X0201 range | See below |
| DF1/EF02 | `CD` | 8 | Residence period expiry date | UTF-8 / JIS X0201 range | `YYYYMMDD`; residence cards only |
| DF1/EF03 | `D0` | 2500 | Name image | Binary | MMR-compressed TIFF |
| DF1/EF03 | `D1` | 3000 | Face image | Binary | JPEG2000 color image |
| DF1/EF04 | `DFD1` | 2500 | Address image | Binary | MMR-compressed TIFF |

Work restriction (`CC`) values:

| Value | Meaning |
|---|---|
| `1` | No work restriction |
| `2` | Work only under residence status |
| `4` | Work only as designated by designation document |
| `9` | Work not permitted |

## DF2 tags

| Parent/EF | Tag | Max value length | Field | Encoding / format | Detail |
|---|---|---:|---|---|---|
| DF2/EF01 | `D5` | 7, but actual written data is 1 byte | Comprehensive permission | UTF-8 / JIS X0201 range | `0`, `1`, `2`; residence cards only |
| DF2/EF01 | `D6` | 8 | Comprehensive permission expiry | UTF-8 / JIS X0201 range | `YYYYMMDD`; residence cards only |
| DF2/EF01 | `D7` | 1 | Individual permission | UTF-8 / JIS X0201 range | `0` none, `1` exists; residence cards only |
| DF2/EF02 | `D8` | 1 | Renewal/application status | UTF-8 / JIS X0201 range | `0` none, `1` pending; residence cards only |
| DF2/EF03 | `D9` | 1 | ISA Commissioner note flag | UTF-8 / JIS X0201 range | `0` none, `1` recorded |
| DF2/EF03 | `DE` | 200 | Reserved text | UTF-8 / JIS X0213 range | Max 100 chars assumed |

Comprehensive permission (`D5`) values:

| Value | Meaning |
|---|---|
| `0` | None |
| `1` | Permitted within 28 hours/week, adult entertainment prohibited |
| `2` | Permitted within 28 hours/week for education etc. |

## DF3 tags

| Parent/EF | Tag | Max value length | Field | Encoding / format | Detail |
|---|---|---:|---|---|---|
| DF3/EF01 | `DC` | 96 | Check code / signature value | Binary | ASN.1 format |
| DF3/EF01 | `DD` | 602 | Public key certificate | Binary | X.509 v3, ECDSA NIST P-384 SHA256, actual 598 or 599 bytes |

## Test TLV examples

Add parser tests for:

```text
C1 02 30 35
D0 82 09 C4 [2500 bytes]
D1 82 0B B8 [3000 bytes]
DF D1 82 09 C4 [2500 bytes]
DC 60 [96 bytes]
DD 82 02 56 [598 bytes]
```

## Padding

Files may be padded with null bytes (`00`). The TLV parser should ignore trailing zero padding after complete TLV objects.
