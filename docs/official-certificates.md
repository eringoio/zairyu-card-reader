# Official certificates

[日本語版 →](official-certificates.ja.md)

The application packages the public trust anchors needed for its offline signature-verification
feature. They are public certificates, not private keys, and are stored in
`resources/moj/trust-anchors/`.

## Source and verification

The project records the certificate source, expected filenames, and SHA-256 fingerprints in
the runtime trust manifest. The build and test checks verify that the bundled anchors match
that manifest. The application does not download certificates while it reads a card.

The certificates originate from material published by Japan's Immigration Services Agency.
They are included only for the verification feature and remain subject to the publisher's
terms. They are not an endorsement of this independently developed project.

## Updates and expiry

Trust anchors can expire or be replaced. A future release may update them only after checking
the official source and reviewing the relevant verification tests. Do not replace the files in
an installed release manually; use an updated release instead.

For the meaning and limitations of a verification result, see
[Signature verification](signature-verification.md).
