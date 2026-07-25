# Privacy and policy rules

Generated: 2026-07-07

These rules apply to `zairyu-card-reader`, especially the second-generation implementation.

## Hard rules

Do not:

1. Read, display, store, export, log, or cache face-photo data by default.
2. Access My Number.
3. Access JPKI.
4. Access signature certificates or user certificates belonging to My Number/JPKI functions.
5. Store raw IC dumps.
6. Store raw protected TLV bytes.
7. Store raw APDU logs containing personal data.
8. Send any card data to external/cloud services.
9. Use external OCR services.
10. Brute-force AIDs, EF IDs, SFI values, authentication parameters, or keys.
11. Use the specified-card RSA delivery key for normal second-generation cards.

## Default RC2 reading mode

Recommended configuration:

```text
RC2_ENABLED=true
RC2_READ_PRINTED_ENTRIES=true
RC2_READ_NAME_IMAGE=false
RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME=false
RC2_ENABLE_FULL_SIGNATURE_VALIDATION=false
RC2_STORE_RAW_APDU=false
RC2_STORE_RAW_TLV=false
```

Default allowed reads:

| Data | Default |
|---|---|
| Public common/card type | Allowed |
| DF1/EF02 printed entries | Allowed after auth + SM |
| DF2 business fields | Allowed after auth |
| DF3/EF01 signature/certificate | Allowed after auth, but do not store raw bytes |
| D0 name image | Disabled by default; may be transient OCR-only |
| D1 face image | Not displayed/stored/exported; avoid reading by default |
| DFD1 address image | Disabled by default; may be transient OCR-only |

## Face image policy problem

The second-generation spec stores:

```text
DF1/EF03 = D0 name image + D1 face image
```

The official read example reads the whole EF. If the app needs the name image (`D0`), it may have to receive face-image data (`D1`) in the same EF response. Handle this carefully:

- default should not read DF1/EF03;
- if enabled, read transiently in memory only;
- immediately discard `D1`;
- never decode/display/store/export `D1`;
- do not include raw image bytes in API responses;
- do not include raw image bytes in copied text;
- do not log decrypted EF data.

## Signature verification policy

The RC2 signature covers:

```text
printed entries || face image || name image
```

Full cryptographic verification requires the face image. Therefore, in default privacy mode:

```text
signature_verified = null
signature_verification_note = "Skipped because default policy does not read face image data required by the signature target."
```

Optional local-only full verification can be added behind:

```text
RC2_ENABLE_FULL_SIGNATURE_VALIDATION=true
```

If enabled:

- transiently read face image only for cryptographic verification;
- never display/store/export it;
- zero/discard buffers as soon as possible;
- do not return raw target bytes from any API.

## Output rules

These rules were originally written for a CSV export that no longer exists. They now govern
the fixed Japanese tab-separated text staff copy, which is the only output this application
produces. The allowlist and denylist below are unchanged and are enforced by
`reader/policy.py` and the allowlist in `reader/local_api.py`.

Output may include reviewed business fields only, for example:

```text
card_number
card_type_code
card_type_label
birth_date
sex_code
sex_label
nationality_region_code
residence_status_code
period_of_stay_raw
period_of_stay_label
permission_type_code
permission_date
work_restriction_code
residence_expiry_date
card_expiry_date
comprehensive_permission_code
comprehensive_permission_expiry_date
individual_permission_code
renewal_application_status
signature_verified
signature_verification_note
```

Output must never include:

```text
face_photo
face_image
image_bytes
raw_ic
raw_tlv
raw_apdu
jpki
my_number
certificate_bytes
signature_bytes
front_image_data_url
```

## API sanitizer

Before returning an API response or building copy text, recursively reject keys containing these substrings:

```text
face_photo
face_image
photo_bytes
image_bytes
raw_ic
raw_tlv
raw_apdu
apdu_log
my_number
individual_number
jpki
signature_certificate
user_certificate
certificate_bytes
private_key
```

`public_key_certificate_status`, `signature_verified`, and `signature_verification_note` are allowed, but raw certificate bytes are not.
