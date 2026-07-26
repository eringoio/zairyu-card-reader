# 2026-07-21 — Fix Certificate Signature Verification

## Goal

Resolve card public key certificate verification failures occurring on genuine first-generation and second-generation Japanese residence cards by supporting BER/CER ASN.1 decoding and zero-padding normalization, while retaining strict trust store and fingerprint validations.

## Context

Physical cards may encode certificates in BER/CER ASN.1 formats or pad them to fixed widths (e.g. 1200 bytes inside the `DB` tag for first-generation cards). Strictly calling `cryptography`'s `load_der_x509_certificate` on raw certificate bytes read from the card fails when trailing zero-padding or non-DER encodings are present.

Additionally, newer versions of `cryptography` (which use a strict Rust-backed ASN.1 parser) reject certificates with `ExtraData` in `TbsCertificate::signature_alg` if the parameters field of an ECDSA signature algorithm identifier is encoded as `NULL` (`05 00`) rather than being completely absent/omitted (as required by strict DER rules under RFC 5480).

## Assumptions

- Card certificates are valid ASN.1 X.509 certificate structures.
- Extra trailing bytes can only consist of zero padding (`0x00`). Any non-zero trailing byte indicates a malformed or tampered payload.
- Cryptography `Certificate` objects in newer versions (like `49.0.0`) are Rust-backed instances and do not permit custom attribute assignment.

## Decisions

- Created a shared certificate loader helper: `reader/signature/certificate_encoding.py`.
- First attempt to load with strict DER parser (`x509.load_der_x509_certificate`).
- If that fails, decode using `pyasn1.codec.ber.decoder.decode` with the `rfc2459.Certificate` schema to locate the certificate end.
- Assert that any trailing bytes are exactly `0x00` and reject if non-zero trailing bytes are present.
- Added signature algorithm normalization: For any ECDSA signature algorithm identifier (OIDs starting with `1.2.840.10045.4` in both `tbsCertificate.signature` and `signatureAlgorithm`), unset/remove the `parameters` field if it was encoded as `NULL`, bringing it in line with strict DER Omit rules.
- Re-encode the decoded and normalized ASN.1 tree to DER format to obtain canonical DER representation.
- Use a global ID-based mapping registry `_metadata_registry` to link diagnostic metadata to parsed certificates instead of setting custom properties on final Rust classes.
- Replaced direct calls to `x509.load_der_x509_certificate` on CA/trust anchor certificates in `rc_signature.py` and `trust_store.py` with `load_card_x509_certificate` to ensure the trust anchors are normalized as well.
- Updated `zairyu-reader.spec` with PyInstaller hidden imports for `pyasn1` and `pyasn1_modules` submodules.
- Modified tests to cover all 10 new criteria, and padded the synthetic first-generation card DB certificate to test zero-padding robustness.
- Added detailed log outputs to `sys.stderr` when certificate loading fails, and allowed diagnostic fields to be returned through the local API and printed to the terminal console during manual scans.

## Files changed

- `reader/signature/certificate_encoding.py` (New file)
- `reader/signature/result.py`
- `reader/signature/rc_signature.py`
- `reader/signature/trust_store.py`
- `reader/local_api.py`
- `requirements.txt`
- `zairyu-reader.spec`
- `tests/test_certificate_encoding.py` (New file)
- `tests/test_first_generation_signature.py`
- Historical text-export fixtures (later removed with the clipboard/export workflow)

## Checks run

```bash
.venv_linux/bin/python -m pytest
```

## Checks skipped

- Physical card reader validation (requires physical hardware).

## Results

All 281 tests passed successfully in the `.venv_linux` environment, confirming that the new helper successfully parses strict DER, padded DER, BER/CER with indefinite length, BER/CER with padding, while rejecting non-zero trailing bytes and truncated/empty inputs.

## Risks / follow-up

- Physical-card verification has been simulated in tests but requires verified physical-card dry-run testing.

## Suggested next step

Perform manual verification using an authorized card reader and genuine physical cards.
