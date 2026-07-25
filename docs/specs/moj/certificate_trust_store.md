# Certificate and public-key material trust store

Generated: 2026-07-07

> Superseded in part on 2026-07-17: the runtime manifest is now version 2 and holds
> multiple explicit trust anchors. The examples below describe the earlier single-anchor
> layout; `resources/moj/trust-anchors/manifest.json` and the source register are current.

## Current trust-store rules

`production` is the default, offline profile. It includes the four first-generation RSA
production CAs and the second-generation ECDSA CA2. `official_test` contains only the
separate `001460788.zip` test CA2; it never imports production anchors. Every certificate
is SHA-256-checked before use.

Issuer/subject narrowing is followed by AKI/SKI narrowing when present, then issuer-key
signature verification. Exactly one valid path is required; zero paths are `untrusted` and
multiple paths are `ambiguous`. The newest first-generation CA is never selected merely
because it is newer.

Card-certificate time is evaluated at verification time and reported separately. A root
whose displayed validity period has ended produces `historical_evaluation_required` rather
than an invented rejection rule: the public normal-card specification in this repository
does not state retrospective root-validity semantics. Card expiry and chip signature
verification remain separate checks.

## First-generation verification binding

The `first_generation` manifest entries are the only permitted anchors for card types `1`
and `2`. Their provenance, subject, validity, path, and SHA-256 fingerprints are recorded
per anchor in `resources/moj/trust-anchors/manifest.json` and in the source register in
`source_materials.md`. The runtime reads the packaged DER certificate and compares its
SHA-256 fingerprint before using it. Issuer/subject and AKI/SKI narrowing then require
exactly one cryptographically valid card-certificate issuer signature.

The governing old-generation format is `001414093.pdf`, Ver. 1.5, §§3.3.4.9 and 3.4.3.1
(pp. 13-14): `DB` is the X.509 v3 card certificate and `DA` is the 2048-bit RSA check
code. CA2 and specified-card RSA delivery keys are never candidates for this path.

## Purpose

The certificates are not needed to perform card-number authentication or read chip fields. They are needed for **authenticity / signature verification** of the signed card data.

The runtime app should load trust anchors from `resources/moj/trust-anchors/`, not directly from arbitrary ZIP files in `docs/external/moj/`.

## Recommended file placement

```text
resources/
  moj/
    trust-anchors/
      first-generation/
        zairyucard_ca_20240508_20340808.crt
      second-generation/
        zairyucard_ca2_20260420_20390720.crt
```

No `specified-card/` directory exists. Specified-card RSA delivery key material is not
distributed with this project at all.

Keep the original ZIP files under:

```text
docs/external/moj/cert-zips/
```

## Uploaded public key materials

### First-generation public-key certificate ZIP

Uploaded ZIP:

```text
001460777.zip
公開鍵証明書（有効期間2024年5月8日～2034年8月8日）
```

Extracted certificate metadata:

| Field | Value |
|---|---|
| Subject | `C=JP, O=Japanese Government, OU=The Ministry of Justice, CN=ZairyuCard CA` |
| Issuer | same as subject, self-signed CA |
| Serial | `93` |
| Valid from | 2024-05-08 13:52:03 GMT |
| Valid until | 2034-08-08 13:52:03 GMT |
| Public key | RSA 2048 |
| Signature algorithm | `sha256WithRSAEncryption` |
| Key usage | Certificate Sign, CRL Sign |
| Basic constraints | CA:TRUE, pathlen:0 |
| SHA-256 fingerprint | `BF:85:44:66:ED:9A:BF:61:F5:59:C3:9B:F8:79:05:46:F8:AC:DA:B9:9B:51:FD:23:30:56:36:69:CE:4A:71:B2` |

Use for first-generation signature validation only, unless the original spec says otherwise.

### Second-generation / specified-card common public-key certificate ZIP

Uploaded ZIP:

```text
001462221.zip
公開鍵証明書（有効期間2026年4月20日～2039年7月20日　※第二世代・特定在留カード等共通）
```

Extracted certificate:

```text
ec_cacert_20260420.crt
```

Certificate metadata:

| Field | Value |
|---|---|
| Subject | `C=JP, O=Japanese Government, OU=The Ministry of Justice, CN=ZairyuCard CA2` |
| Issuer | same as subject, self-signed CA |
| Serial | `01` |
| Valid from | 2026-04-20 04:33:17 GMT |
| Valid until | 2039-07-20 04:33:17 GMT |
| Public key | EC 384-bit |
| Curve | `secp384r1` / NIST P-384 |
| Signature algorithm | `ecdsa-with-SHA256` |
| Key usage | Certificate Sign, CRL Sign |
| Basic constraints | CA:TRUE, pathlen:0 |
| SHA-256 fingerprint | `11:E6:AD:8B:8E:64:F0:CD:B1:D8:BA:9E:36:89:92:6C:80:E8:47:9A:2F:09:86:16:F6:74:A2:35:82:BE:C1:3B` |

Use this as the trust anchor for normal second-generation card (`05`/`06`) signature validation.

### RSA delivery key ZIP — not included in this repository

The Immigration Services Agency also publishes an RSA delivery key archive,
`001462222.zip` (RSA配送鍵（※特定在留カード等のみ）), containing `keys_smrsapub_001.bin`:
an RSA public key, 2048 bit, exponent 65537 (`0x10001`), SHA-256 file digest
`98bf7014e478241f7943fc1a76c38b6c7bda4da9a927d106ae9ab8a1ad684d0a`.

**Neither the archive nor the extracted key is distributed with this project.** The key
belongs to the specified-card (`07`/`08`) flow, which is out of scope: it is never a trust
anchor and is never used for normal second-generation residence cards (`05`/`06`). The
identifier and digest are kept here so the omission is verifiable and deliberate rather
than an oversight.

The specified-card spec uses `SET SESSION KEY` and RSA-OAEP. That path is blocked by policy in this project unless intentionally implemented later.

## Signature verification notes for RC2

Source reference: `001460711.pdf`, pp.13 and 15, sections 3.3.4.10 and 3.4.3.1.

DF3/EF01 contains:

```text
DC = check code / signature value, max 96 bytes, ASN.1 format
DD = public key certificate, max 602 bytes, actual 598 or 599 bytes, X.509 v3, ECDSA NIST P-384 SHA256
```

The signed target is:

```text
printed entries || face image || name image
```

Default privacy mode should skip full signature verification because the face image is part of the signed target. Set:

```text
signature_verified = null
signature_verification_note = "Skipped because default policy does not read face image data required by the signature target."
```

Full verification can be implemented later with an explicit local-only opt-in that transiently reads face-image bytes for cryptographic verification, never stores/displays/exports them, and clears them immediately.

## Suggested manifest.json

```json
{
  "moj_trust_anchors": {
    "first_generation": {
      "path": "resources/moj/trust-anchors/first-generation/zairyucard_ca_20240508_20340808.crt",
      "sha256_fingerprint": "BF:85:44:66:ED:9A:BF:61:F5:59:C3:9B:F8:79:05:46:F8:AC:DA:B9:9B:51:FD:23:30:56:36:69:CE:4A:71:B2",
      "subject_cn": "ZairyuCard CA",
      "valid_from": "2024-05-08T13:52:03Z",
      "valid_until": "2034-08-08T13:52:03Z"
    },
    "second_generation": {
      "path": "resources/moj/trust-anchors/second-generation/zairyucard_ca2_20260420_20390720.crt",
      "sha256_fingerprint": "11:E6:AD:8B:8E:64:F0:CD:B1:D8:BA:9E:36:89:92:6C:80:E8:47:9A:2F:09:86:16:F6:74:A2:35:82:BE:C1:3B",
      "subject_cn": "ZairyuCard CA2",
      "valid_from": "2026-04-20T04:33:17Z",
      "valid_until": "2039-07-20T04:33:17Z"
    }
  },
  "specified_card_material": {
    "enabled": false,
    "rsa_delivery_key_path": null,
    "note": "Specified-card material is not distributed with this project and is never used for card type 05/06."
  }
}
```
