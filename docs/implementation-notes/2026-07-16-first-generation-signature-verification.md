# First-generation signature verification

Date: 2026-07-16

## Decision

Implement card types `1` (residence card) and `2` (special permanent resident certificate)
in a dedicated RSA verifier. Do not reuse second-generation ECDSA assumptions.

## Official evidence

The sole format source is the published Immigration Services Agency / Ministry of Justice
document below. It is cited, not redistributed by this repository:

```text
001414093.pdf
在留カード等仕様書（一般公開用） Ver. 1.5, March 2024
SHA-256 e529e43284abc9d4400538125a91084d46c0d3601234a113abe529261b417352
```

| Fact | Official location |
|---|---|
| Both old card types and file capacities | §3.3.1, pp. 8-9 |
| `DF1/EF01`, tag `D0`, front image, 7,000-byte value field | §3.3.4.3, p. 10 |
| `DF1/EF02`, tag `D1`, face image, 3,000-byte value field | §3.3.4.4, p. 10 |
| `DF3/EF01`, tag `DA` 256-byte check code and `DB` X.509 v3 certificate | §3.3.4.9, p. 13 |
| RSA-2048, PKCS#1 v1.5 padding, SHA-256, and the signed-target diagram | §3.4.3.1 / Figure 3-4, p. 14 |
| DF1 SFI `85`/`86`; DF3 SFI `82`; plain versus SM reads | §4.2.5, p. 32; Appendix read sequence, p. 40 |

The current official publication page also lists the four first-generation root CA
certificates. Each bundled DER certificate is from its official archive/direct official
publication and is checksum-validated through the runtime manifest; provenance is recorded
in `docs/specs/moj/source_materials.md`.

## Exact verification rule

```text
target = D0.value + 00-padding to 7000 bytes
       || D1.value + 00-padding to 3000 bytes
hash   = SHA-256(target)
verify = RSA-2048 PKCS#1 v1.5 verification of DA using DB's public key
```

`D0` and `D1` are their TLV values only: tag and length encoding are excluded. No printed
entry, name-image, address-image, or second-generation component is added. Both card types
use the same rule.

The card certificate is parsed as X.509 v3, checked for RSA-2048 public key and digital
signature KeyUsage when present, checked for present-time validity, then required to chain
cryptographically to exactly one `production` `first_generation` anchor. CA2 and
specified-card RSA delivery keys are excluded.

## Privacy and failure handling

`D1` is read only in memory for signature verification, never displayed, returned, logged,
persisted, exported, or included in diagnostics. Controlled mutable face/image/signature and
signed-target buffers are overwritten in `finally` blocks. CPython makes this best effort,
not a guarantee against allocator/interpreter copies.

An unavailable/malformed signature path returns a safe status. It does not abort the
authorized business-field read.

## Validation status

Synthetic fixtures test type `1` and `2`, valid signatures, D0/D1 tampering, missing/wrong
certificate or signature, certificate time/path statuses, malformed lengths and encodings,
and byte-free result dictionaries.

No authorized physical first-generation card was used. The implemented result therefore
retains `implementation_status=implemented_unverified_on_real_hardware` until manual
acceptance in `docs/testing-matrix.md` is completed.
