# Contributing

[日本語版 →](CONTRIBUTING.ja.md)

Thank you for contributing. This project reads sensitive personal information, so every change
must preserve the following rules:

- Keep card reading, OCR, and signature verification local. Do not add cloud services,
  telemetry, analytics, exports, clipboard functions, remote submission, or runtime downloads.
- Do not commit real card data, card images, names, addresses, card numbers, personal paths,
  private keys, or organisation-specific identifiers. Use synthetic data everywhere.
- Do not read My Number, JPKI, or specified residence-card data.
- Keep the service loopback-only; do not add LAN hosting, tunnels, reverse proxies, or CORS.
- Do not save raw chip data, images, face photographs, OCR data, card certificates, or
  signatures to files, logs, or UI responses.
- Treat OCR as a reviewed aid, not an authoritative source.
- Do not make official test material pass as production verification.

Before proposing a change, run the relevant tests and update both English and Japanese
documentation. Discuss any change to these rules before implementing it. See
[Privacy](PRIVACY.md) and [Security](SECURITY.md) for the user-facing policy.
