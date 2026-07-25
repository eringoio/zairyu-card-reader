# Signature Verification

What the application checks, what it does not check, and why the face image is involved.

## What verification does and does not prove

> **Signature verification confirms the cryptographic relationship between the data read
> from the IC chip and the supported trust material. It does not by itself confirm that the
> card remains currently valid or has not subsequently been invalidated.**

> **署名検証は、ICチップから読み取ったデータと、対応する信頼情報との間の暗号学的な整合性を
> 確認するものです。それ自体は、そのカードが現在も有効であること、またはその後に失効して
> いないことを確認するものではありません。**

In plain terms, a `verified_production` result means: *the data on this chip was signed by a
key whose certificate chains to a certificate the Immigration Services Agency published, and
the data has not been altered since.*

It does **not** mean:

- that the card is still valid today;
- that the card has not been reported lost, surrendered, or revoked;
- that the holder's residence status is still current;
- that the person presenting the card is its holder;
- that the Immigration Services Agency has certified this application or its result.

There is no revocation check. The application is offline by design and performs no OCSP or
CRL lookup, because doing so would mean contacting a remote service every time a card is
read. Expiry dates printed on the card and stored in the chip are shown for a human to
check.

A verified signature is strong evidence that a card is genuine and unaltered. It is not a
substitute for the checks your organisation is required to perform.

## Trust profiles and current result categories

The package works offline. Its default `VERIFICATION_TRUST_PROFILE=production` permits only
the published production anchors for the card generation. The explicit
`VERIFICATION_TRUST_PROFILE=official_test` profile permits only the official sample-card CA
from `001460788.zip`; it shows a persistent `公的テストカード用モード` warning and cannot
set `production_authenticity_verified`.

Safe results include `trust_profile`, `selected_anchor_id`, separate certificate-chain,
certificate-validity, and anchor-validity statuses, and one of:

| Final signature status | Meaning |
|---|---|
| `verified_production` | Valid production path and final signature; production authenticity is true. |
| `verified_official_test` | Valid official-test path and final signature; never a production result. |
| `untrusted_certificate` / `ambiguous_trust_path` | No unique profile-authorized chain. |
| `certificate_expired` / `certificate_not_yet_valid` | Current card-certificate time check failed. |
| `anchor_fingerprint_mismatch` | Packaged anchor integrity check failed before use. |
| `missing_signature`, `missing_certificate`, `missing_signed_component` | Required verification input is absent. |

Anchor selection uses card generation, active profile, issuer/subject, AKI/SKI when present,
and cryptographic issuer-signature verification. It never picks the newest first-generation
anchor merely by date. A root date that has elapsed is reported separately as
`historical_evaluation_required`: the stored official normal-card material does not define
a retrospective root-expiration rule, so the application does not invent one.

## First-generation signed target (card types `1` / `2`)

The first-generation verifier is implemented in `reader/signature/first_generation.py` and
uses only the old-generation public specification: `001414093.pdf` (Ver. 1.5), sections
3.3.1 (file layout, pp. 8-9), 3.3.4.3-3.3.4.4 (D0/D1, p. 10), 3.3.4.9
(DA/DB, p. 13), 3.4.3.1 / Figure 3-4 (target and RSA verification, p. 14), and
4.2.5 / the read sequence (DF selectors and READ BINARY, pp. 32, 40). The specification is
not redistributed here; `docs/specs/moj/source_materials.md` records the SHA-256 of the
revision this implementation was written against so you can verify your own copy.

| File | Tag | Purpose |
|---|---|---|
| `DF1/EF01` | `D0` | Front-of-card image value, maximum 7,000 bytes |
| `DF1/EF02` | `D1` | Face-image value, maximum 3,000 bytes |
| `DF3/EF01` | `DA` | 256-byte RSA check code/signature |
| `DF3/EF01` | `DB` | X.509 v3 card certificate (maximum 1,200 bytes) |

The exact target is:

```txt
pad_right(D0.value, 7000, 0x00) || pad_right(D1.value, 3000, 0x00)
```

`D0`/`D1` tag and length bytes are excluded. The specification requires trailing NUL
padding within each value area before concatenation. Both card type `1` and card type `2`
use this target; no name-image or printed-entry component is included. `DA` is exactly a
2048-bit RSA signature and is verified as `RSA PKCS#1 v1.5 + SHA-256`; it is not ASN.1
ECDSA encoding. The card certificate must be an RSA-2048 X.509 certificate, chain directly
and uniquely to one checksum-validated `first_generation` production CA in the manifest,
and be currently valid. CA validity is reported separately as described above.

`official_test` has no first-generation anchor; first-generation verification always uses
the isolated `production` first-generation trust set. It never uses CA2.

The implementation result includes
`implementation_status=implemented_unverified_on_real_hardware`. This remains true until
an authorized physical first-generation card is exercised under the manual cases below.

## Second-generation signed target

A second-generation residence card stores a signature and a public-key certificate in `DF3/EF01`:

| Tag | Meaning | Format |
|---|---|---|
| `DC` | Check code / signature value | 96 bytes, raw `r‖s` for P-384 (DER is also accepted) |
| `DD` | Public-key certificate | DER X.509 v3, ECDSA NIST P-384, SHA-256 |

The signature covers exactly:

```txt
printed entries || face image || name image
```

- **printed entries** — the concatenated TLV *values* of `DF1/EF02`, with tag and length bytes stripped. 53 bytes on a residence card. A special permanent resident certificate carries 34 bytes, NUL-padded to 53.
- **face image** — the `D1` value inside `DF1/EF03`.
- **name image** — the `D0` value inside `DF1/EF03`.

Algorithm: `SHA256withECDSA` on `secp384r1` / NIST P-384.

## Why the face image is read

There is no way to verify this signature without the face image: it is part of the signed bytes. Any implementation claiming full verification without reading `D1` is either not verifying, or verifying something else.

So the app reads it, and the privacy rule is drawn around *what happens next* rather than around the read itself:

- The face image exists only in local memory: the second-generation protocol hands a
  `bytearray` to `reader/signature/rc_signature.py`; the first-generation reader hands a
  controlled `bytearray` to `reader/signature/first_generation.py`.
- It is used only to build the documented signed target and verify it.
- The signed-target buffer and controlled image buffers are overwritten with zeros in a
  `finally` block before the read result is handed to any caller.
- It is **never** displayed, stored, written to disk, logged, or traced.
- The result dict contains no bytes at all — only booleans, statuses, and notes.

CPython cannot guarantee erasure; the allocator may already have copied the bytes elsewhere. Zeroing the buffers we control removes the obvious long-lived copy. This is a mitigation, not a proof.

`face_photo_status` stays `not_read_by_policy` in every exported and transmitted record, because no face photo is ever *retained*.

## Configuration

```txt
RC2_ENABLE_FULL_SIGNATURE_VALIDATION=true    # default
```

On by default: staff need to know whether a card is genuine, and the transient read above is the only way to answer that.

Set it to `false` to skip verification entirely. `DF1/EF03` is then not read at all unless `RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME=true` separately enables name OCR, which reads the same file.

| `RC2_ENABLE_FULL_SIGNATURE_VALIDATION` | `RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME` | `DF1/EF03` read? | Signature | Name OCR |
|---|---|---|---|---|
| `true` (default) | any | yes | verified | available |
| `false` | `true` | yes | skipped by config | available |
| `false` | `false` | no | skipped by config | blocked by policy |

## Verification order

1. Parse generation-specific signature and certificate tags from `DF3/EF01` (`DA`/`DB` for
   first generation; `DC`/`DD` for second generation).
2. Parse the card certificate as DER X.509.
3. Verify the card certificate chains to exactly one generation-appropriate bundled MOJ
   trust anchor (`resources/moj/trust-anchors/`), checking both issuer data and issuer
   signature. The anchor's SHA-256 fingerprint is checked against `manifest.json` on load.
4. Confirm the specified public-key type/size (RSA-2048 for first generation; ECDSA P-384
   for second generation).
5. Rebuild the exact generation-specific signed target.
6. Verify it using the documented generation-specific algorithm.

If step 3 fails, the signature is **not** checked and the card is reported as not verified. A signature that verifies against an untrusted certificate proves nothing.

## Result fields

| Field | Values |
|---|---|
| `signature_present` | `true` / `false` |
| `public_key_certificate_status` | `present` / `not_present` |
| `public_key_certificate_parse_status` | `parsed` / `failed` / `not_attempted_missing_dependency` |
| `certificate_chain_verified` | `true` / `false` / `""` (not evaluated) |
| `certificate_chain_verification_note` | English technical note |
| `signature_verified` | `true` / `false` / `null` (not checked) |
| `signature_verification_status` | `verified_production`, `verified_official_test`, `untrusted_certificate`, `certificate_expired`, `certificate_not_yet_valid`, `signature_mismatch`, `missing_signature`, `missing_certificate`, or `verification_error` |
| `signature_verification_note` | English technical note |

`signature_verified` is rendered as `""` rather than `"None"` when the check did not run. "Not checked" and "not valid" are different outcomes and must never be confused.

## What staff see

`display_signature_status` collapses the status into one line:

| Status | Japanese | English |
|---|---|---|
| `verified` | `署名検証: 確認済み` | `Signature: Verified` |
| `not_verified`, `images_unavailable` | `署名検証: 確認できませんでした` | `Signature: Not verified` |
| `skipped_by_config` | `署名検証: 未確認（設定によりスキップ）` | `Signature: Not checked; skipped by settings` |
| `certificate_unavailable`, `missing_dependency` | `署名検証: 未確認（証明書を確認できません）` | `Signature: Not checked; certificate unavailable` |

## What verification means

**It does mean** the documented generation-specific chip-image components are exactly what
the Ministry of Justice signed when the card was issued, and that the signing certificate
chains to the generation-appropriate bundled MOJ anchor.

**It does not mean:**

- that the card has not been revoked, cancelled, or reported lost — there is no revocation check and no online lookup;
- that the card is still within its validity period — check `card_expiry_date` separately;
- that the person presenting the card is its holder — the app never shows the face image, so no visual comparison is possible, and no biometric matching is performed;
- that the *printed* card surface matches the chip — only chip contents are verified;
- that the chip is not a cloned copy of a genuine chip.

Signature verification answers "is this chip data authentic and unmodified?", not "is this person who they claim to be?".

## Degradation

Every failure path returns a status instead of raising:

| Situation | Status |
|---|---|
| `RC2_ENABLE_FULL_SIGNATURE_VALIDATION=false` | `skipped_by_config` |
| `cryptography` not installed | `missing_dependency` |
| No `DC` or no `DD` on the card | `certificate_unavailable` |
| Certificate does not parse as DER X.509 | `certificate_unavailable` |
| Trust anchor missing or fingerprint mismatch | `certificate_unavailable` |
| Certificate key is not ECDSA P-384 | `certificate_unavailable` |
| Certificate does not chain to the anchor | `not_verified` |
| Face or name image unavailable | `images_unavailable` |
| Signature does not verify over the target | `not_verified` |

A read never fails because verification failed. The business fields are still returned with an honest signature status attached.

## Tests

`tests/test_signature.py` builds a throwaway P-384 CA for the second-generation format.
`tests/test_first_generation_signature.py` builds a throwaway RSA-2048 CA/card certificate
and synthetic D0/D1 values in the first-generation official format. It covers valid type
`1`/`2` signatures, each tampered target component, missing/invalid inputs, untrusted and
time-invalid certificate states, malformed signature encoding/target length, and no
sensitive bytes in results. No real MOJ card material is used.

Real-card verification against any production anchor still requires an authorized physical
card and reader; see `docs/testing-matrix.md`.
