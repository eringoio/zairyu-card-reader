# Specified-card reference — do not implement in the RC2 path

Generated: 2026-07-07

Primary source:

```text
001460712.pdf
特定在留カード等仕様書（一般公開用） Ver 1.1
```

## Purpose of this document

This document exists to prevent mixing up two different card families:

| Card type | Meaning | Implementation status |
|---|---|---|
| `05` | Normal second-generation residence card | Implement in RC2 module |
| `06` | Normal second-generation special permanent resident certificate | Implement in RC2 module |
| `07` | Specified residence card | Block by policy |
| `08` | Specified special permanent resident certificate | Block by policy |

The user’s target card is the new residence card **without My Number**, so use `001460711.pdf`, not this specified-card spec.

## Why specified cards are separate

Source reference: `001460712.pdf`, pp.6, 8-9, 25, 31-33.

Specified cards are based on a My Number-card-style structure. The spec says the residence AP is placed under a future-use SSD area beneath the My Number card ISD. It has a separate `在留 AP` AID that must be selected before selecting DF1/DF2/DF3.

Specified-card AIDs:

| File | AID |
|---|---|
| 在留 AP | `D3 92 F0 00 4F 01 00 00 00 00 00 00 00 00 00 00` |
| DF1 | `D3 92 F0 00 4F 02 00 00 00 00 00 00 00 00 00 00` |
| DF2 | `D3 92 F0 00 4F 03 00 00 00 00 00 00 00 00 00 00` |
| DF3 | `D3 92 F0 00 4F 04 00 00 00 00 00 00 00 00 00 00` |

Normal RC2 cards (`05`/`06`) do **not** use the `在留 AP` select.

## Security flow difference

Normal second-generation cards use:

```text
GET CHALLENGE
MUTUAL AUTHENTICATE
VERIFY with SM
```

Specified cards use:

```text
SET SESSION KEY
VERIFY with SM
READ BINARY
```

The specified-card spec defines:

```text
SET SESSION KEY command: 80 AE 00 00 ...
RSA 2048-bit key delivery
RSA-OAEP (PKCS#1 v2.2)
AES-128-CBC
AES-CMAC
message counter / IV derivation for SM
```

The uploaded `keys_smrsapub_001.bin` is the RSA delivery key for this path only.

## Project policy

For this project, specified cards should return:

```text
specified_card_blocked_by_policy
```

Do not:

- select the My Number/JPKI applications;
- access certificates/user certificates;
- attempt specified-card AP access unless a separate, reviewed project decision is made;
- use `keys_smrsapub_001.bin` for normal RC2 cards;
- route card type `05`/`06` into the specified-card implementation.

## If specified cards are implemented later

Create a separate module:

```text
reader/protocols/specified_residence_card.py
```

and keep a hard runtime guard that only allows residence AP AID access, never My Number/JPKI apps.
