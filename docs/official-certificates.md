# Official certificates

The application verifies a card's digital signature against certificates published by the
Immigration Services Agency of Japan. Those certificates are packaged with the application
so verification works entirely offline.

> This project is independently developed and is not affiliated with, endorsed by, approved
> by, or certified by the Immigration Services Agency of Japan or the Ministry of Justice.

## Official sources

| Generation | Official page |
|---|---|
| First generation (types `1`/`2`) | <https://www.moj.go.jp/isa/applications/disclosure/120424_01.html> |
| Second generation (types `05`/`06`) and specified cards | <https://www.moj.go.jp/isa/publications/resources/120424_01_00003.html> |

No other source is used. Nothing is fetched at runtime.

## Terms of use

Both pages carry the same statement:

> 著作権は、日本国著作権法及び国際条約により保護されています。ただし、ソフトウェア開発者等が、
> 本公開仕様に基づいてソフトウェア製品を開発し、市場に流通させることを妨げるものではありません。

In substance: copyright in the published specifications is asserted and protected, **but
that does not prevent software developers from building software products based on those
public specifications and distributing them.** The Agency also disclaims liability for any
problems arising from use of the information.

Two consequences shape what this repository contains:

- **The specification documents are cited, not redistributed.** The statement permits
  building software from the specifications; it does not grant permission to republish the
  documents themselves. `docs/specs/moj/` therefore cites them by document number, version,
  page and section, and `source_materials.md` records the SHA-256 of each revision used, so
  you can obtain them from the Agency and confirm you are reading the same one.
- **The certificates are included**, because they are the functional material the permitted
  software needs. Offline verification is impossible without them, and they are public keys
  published for exactly this purpose. This is a considered reading of the terms, not an
  explicit grant; see "Redistribution" below.

## What is packaged

Six certificates live under `resources/moj/trust-anchors/`, described by `manifest.json`:

| Profile | Generation | Local file | Official archive | Historical direct file | Valid until |
|---|---|---|---|---|---|
| `production` | first | `zairyucard_ca_20150606_20250906.crt` | `001460774.zip` | `930001756.crt` | 2025-09-05 |
| `production` | first | `zairyucard_ca_20180407_20280707.crt` | `001460775.zip` | `930001757.crt` | 2028-07-06 |
| `production` | first | `zairyucard_ca_20210527_20310827.crt` | `001460776.zip` | `001353372.crt` | 2031-08-27 |
| `production` | first | `zairyucard_ca_20240508_20340808.crt` | `001460777.zip` | `001421582.crt` | 2034-08-08 |
| `production` | second | `zairyucard_ca2_20260420_20390720.crt` | `001462221.zip` | — | 2039-07-20 |
| `official_test` | second | `zairyucard_ca2_test_20260319_20390619.crt` | `001460788.zip` | — | 2039-06-19 |

All four first-generation production CAs are packaged, not only the newest, because a card
issued years ago is signed by the CA that was current at the time.

### Certificate file digests (SHA-256, hex)

| Local file | SHA-256 |
|---|---|
| `zairyucard_ca_20150606_20250906.crt` | `97f37c5967af5f3cd84e6ed694b09539abb7f8e7e76b6f7496a060008982983d` |
| `zairyucard_ca_20180407_20280707.crt` | `ff02323cea7b8c3dfc0dc2de79d46e78514af587368523086b188e9690aec861` |
| `zairyucard_ca_20210527_20310827.crt` | `6f50161aa80f7ff7c630505faf472906f7b101d5083e327a6182c82cd7985e67` |
| `zairyucard_ca_20240508_20340808.crt` | `bf854466ed9abf61f559c39bf8790546f8acdab99b51fd2330563669ce4a71b2` |
| `zairyucard_ca2_20260420_20390720.crt` | `11e6ad8b8e64f0cdb1d8ba9e3689926c80e8479a2f098616f674a23582bec13b` |
| `zairyucard_ca2_test_20260319_20390619.crt` | `1846b815d31f04fe93d57450a6d8a8c351eac3d8c444a2375d95734df7dd1057` |

The same values appear in `manifest.json` in colon-separated uppercase form, which is what
the application compares against at load time.

### Source-file digests (SHA-256, hex)

| Official file | SHA-256 |
|---|---|
| `001460774.zip` | `5cde542204153e33b866c95a83a311939ada320e3e0534f039cd2c8663731e89` |
| `001460775.zip` | `7651df34bb28288e7cad6fd5ad1c4ffa9588455fbd523c77a2478650be17f6bd` |
| `001460776.zip` | `2d6cc2e9aac1ce086007843c9f6da3e3f17949a1cd0ba2c3df2813ff593ea2e5` |
| `001460777.zip` | `4306634f38c52ef8433ec6ec3ba287706949b15735b40552234a2051c40e3977` |
| `001462221.zip` | `fed0160250a0e95377a55868431397b47ebf97ba77d0dd33aeadc4484a230f15` |
| `001460788.zip` | `900436c0eae20770f4b23b7f8b78ee88e0bdd93a7077db0c87eca3400181d000` |
| `930001756.crt` | `97f37c5967af5f3cd84e6ed694b09539abb7f8e7e76b6f7496a060008982983d` |
| `930001757.crt` | `ff02323cea7b8c3dfc0dc2de79d46e78514af587368523086b188e9690aec861` |
| `001353372.crt` | `6f50161aa80f7ff7c630505faf472906f7b101d5083e327a6182c82cd7985e67` |
| `001421582.crt` | `bf854466ed9abf61f559c39bf8790546f8acdab99b51fd2330563669ce4a71b2` |

The four historical `.crt` digests are identical to the corresponding runtime certificates,
because they are the same bytes. That is the point of keeping both.

Per-certificate subject, issuer, serial number, validity window, public-key algorithm,
signature algorithm, retrieval date, verification status, official source page, and purpose
are recorded in `resources/moj/trust-anchors/manifest.json`, and summarised in
[specs/moj/source_materials.md](specs/moj/source_materials.md).

## Redistribution

The certificates are redistributed here on the reading of the Agency's terms set out above:
the terms expressly permit developing and distributing software built on the public
specifications, and offline signature verification is impossible without the corresponding
public keys. They are public-key certificates published so that software can verify cards —
not confidential material, and not a specification document.

That is a considered interpretation rather than an explicit written grant. Anyone
redistributing this project in a jurisdiction or context where that matters should form
their own view. The specification PDFs, where the copyright assertion is unambiguous, are
**not** redistributed.

Nothing here implies that the Immigration Services Agency or the Ministry of Justice has
reviewed, approved, or endorsed this project.

## What is not packaged

**Specified-card RSA delivery keys.** The Immigration Services Agency also publishes RSA
delivery key material for specified residence cards (`07`/`08`). **Neither the archive nor
the key is distributed with this project.** Specified cards are out of scope; the key is
never a trust anchor and is never used for normal `05`/`06` cards.

The identifier and digest of that material are recorded in `source_materials.md` so the
omission is verifiable rather than looking like an oversight.

**The specification PDFs.** The Immigration Services Agency's residence-card specification
documents are cited by document number, version, page, and section throughout
`docs/specs/moj/`, but are not redistributed here. `source_materials.md` records the SHA-256
of each revision this implementation was written against, so you can obtain the documents
and confirm you are reading the same one.

## How a certificate is trusted

Nothing is trusted because of where it sits on disk.

1. **Fingerprint check.** Before an anchor is used, its bytes are hashed and compared with
   the SHA-256 recorded in `manifest.json`. A mismatch refuses the anchor with a
   `fingerprint_mismatch` status. It is never used as a fallback.
2. **Metadata completeness.** An anchor entry missing any of its 15 required metadata fields
   is refused.
3. **Profile and generation filtering.** Anchors are selected by profile **and** card
   generation. A first-generation anchor is never offered for a second-generation card, and
   a test anchor is never in the production set.
4. **Issuer selection.** Candidates are narrowed by issuer name and, where present, by
   Authority Key Identifier matched against each anchor's Subject Key Identifier.
5. **Real cryptographic verification.** The card certificate's signature is verified against
   each candidate anchor's public key — RSA PKCS#1 v1.5 or ECDSA, as the certificate
   specifies.
6. **Exactly one match.** A trust path is reported as `matched` only when exactly one anchor
   verifies. Zero matches or several are distinct, reported statuses — not a silent pass.

Certificate validity dates are evaluated and reported **separately** from the cryptographic
result, so "the signature is mathematically correct but the certificate has expired" is
distinguishable from "the signature does not verify".

## The two profiles

The profiles are non-overlapping by construction, not by convention.

**`production`** is the default and requires no configuration.

**`official_test`** is selected only by setting `VERIFICATION_TRUST_PROFILE=official_test`
in a local `.env` file or environment variable. In that mode:

- the staff screen shows a persistent warning;
- a successful verification reports `verified_official_test`, never
  `verified_production`;
- the result can never be presented as production-card authenticity.

This exists so an official sample card can be used to check the verification path end to
end without any possibility of the result being mistaken for a real one.

## Supply-chain verification

`docs/external/moj/certs/` holds the official archives and the historical direct-download
certificates as obtained from the Immigration Services Agency. They are not used at runtime;
the application loads only from `resources/moj/trust-anchors/`.

They are kept because `tests/test_trust_store.py` uses them to assert that each packaged
certificate is byte-for-byte identical both to the official archive and to the historical
direct download. That is a real check against a substituted certificate, and it is why those
files are in the repository rather than only their checksums.

## When a certificate expires

The 2015 first-generation CA expired in September 2025. An expired anchor is not removed:
cards signed under it still exist, and the honest result for such a card is "the signature
verifies cryptographically, and the certificate that signed it has expired" — which the
application reports as a distinct status rather than as a failure or a pass.

When the Immigration Services Agency publishes a new CA, adding it means: obtaining the
official archive, recording its SHA-256 in `manifest.json`, placing the certificate under
the matching profile and generation directory, and adding the provenance row to
`source_materials.md`. The fingerprint check then enforces it automatically.

## Related

- [signature-verification.md](signature-verification.md) — what the signature covers and
  what verification does and does not prove.
- [specs/moj/certificate_trust_store.md](specs/moj/certificate_trust_store.md) — the derived
  specification detail.
- [specs/moj/source_materials.md](specs/moj/source_materials.md) — the full provenance
  register with checksums.
