# Signature verification

[日本語版 →](signature-verification.ja.md)

For supported card data, the application can verify a digital signature with packaged
Immigration Services Agency trust anchors. Verification runs entirely on the local PC.

## What the result means

A successful result means that the available signed data and certificate chain verified against
the selected trust profile. It is useful evidence that the displayed supported data has not
been altered after it was signed.

It does **not** prove that a card is current, belongs to the person presenting it, has not
been lost or revoked, or is valid for a particular administrative purpose. Follow the rules of
the procedure you are performing and check the physical card.

## Trust profiles

The production profile is used for ordinary cards. The test profile exists for authorised test
materials and should not be selected for a real-card decision. The application displays which
profile was used.

## Limits

Signature verification is available only for card generations and fields implemented by the
application. A result such as unavailable, incomplete, or failed is not a substitute for
manual review. Do not share card data while seeking support.

The trust anchors are bundled for offline use. Their source and maintenance approach are
described in [Official certificates](official-certificates.md).
