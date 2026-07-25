# Production and official-test trust profiles

The previous runtime store held only one second-generation CA2. This change replaces it
with a versioned offline manifest: four published first-generation production CAs, the
normal second-generation CA2, and a distinct official-test CA2 extracted from `001460788.zip`.
The source register records all archive identifiers, runtime filenames, fingerprints, and
the successful byte-for-byte comparison of each first-generation ZIP with its historical
direct-certificate counterpart.

`VERIFICATION_TRUST_PROFILE=production` is the default. `official_test` is explicitly local
configuration, exposes the active profile only through safe diagnostics, and triggers a
persistent test-mode UI warning. A successful test-chain result is `verified_official_test`;
it deliberately leaves `production_authenticity_verified` false.

Selection is generation and profile scoped, narrows by issuer and AKI/SKI where available,
then validates the card-certificate signature. It needs exactly one path. Certificate time
and root time remain separate. The available normal-card specification does not document
historical root-expiration semantics, so an elapsed root date is reported as
`historical_evaluation_required`, not used to invent a rejection rule.

No real production card or official sample card was tested. Automated verification uses
synthetic certificates; public anchor checks only validate packaged public material.
