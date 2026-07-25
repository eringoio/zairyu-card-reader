# Contributing

Thank you for looking at this project. It reads personal data off government identity
documents, so the rules below are not style preferences — they are the reason the tool is
safe to run at all. A change that breaks one of them will not be merged, however good the
rest of it is.

## The invariants

These hold for every change. If you believe one of them should change, open an issue and
argue the case before writing code; do not change it as a side effect of another feature.

### Privacy

- **No cloud, no telemetry, no analytics, no remote submission, no automatic updates.** The
  application makes no outbound network request at runtime, ever. The only network call in
  the codebase is the launcher polling its own loopback health endpoint.
- **Never store raw IC chip dumps**, and never expose raw APDU, TLV, or IC responses
  through the UI, an API, a log, the clipboard, a file, or a diagnostic.
- **Never store or expose face photographs or card images.** The first-generation signature
  path reads the face image transiently because it is part of the signed target; those
  bytes never leave the verification function.
- **Never read or store My Number or JPKI material.**
- **Never expose raw OCR text, card certificates, card signatures, or signed targets.**
- **Specified residence cards (`07`/`08`), My Number application data, JPKI, and RSA
  delivery keys are out of scope.** RSA delivery key material is not distributed with this
  project and is never used for normal `05`/`06` cards.
- Treat copied text and any manually exported file as sensitive.

There must be no configuration switch that turns any of the above off. A privacy rule with
an off switch is a default, not a rule.

### Network boundary

- The server binds to loopback only. A non-loopback `--host` is a **hard failure in every
  mode**, not a warning.
- Loopback alone is not the boundary. Keep the `Host` allowlist, the per-process request
  token on `/api/local/*`, the `Origin`/`Sec-Fetch-Site` provenance checks on
  state-changing requests, the request-size bound, and the absence of CORS headers. See
  [docs/privacy-and-security.md](docs/privacy-and-security.md) for why each exists.
- Never log the request token, place it on a command line, or return it from an API.
- No LAN hosting, tunnels, reverse proxies, public deployment, or remote reader operation.

### OCR

- Local ONNX Runtime CPU inference only. There is **no second engine and no fallback**.
- No runtime model downloads. No PowerShell or Windows Runtime OCR dependency. No PyTorch.
- Nothing under `reader/ocr/` may import `subprocess` or `tempfile`, and **no card image
  may reach the filesystem**. A test enforces this by inspecting the import graph.
- A staged model must have a reviewed manifest and a SHA-256 check.
- Every OCR-derived field requires staff review. Do not claim OCR accuracy the tool does
  not have — see the known limitations in [README.md](README.md).

### Certificates and trust

- Trust profiles are explicit and non-overlapping. `production` is the default;
  `official_test` requires `VERIFICATION_TRUST_PROFILE=official_test` and must stay visibly
  labelled as test-only.
- **Never let official test material produce a production authenticity result.**
- Validate every packaged trust-anchor fingerprint before use.
- Signature verification confirms a cryptographic relationship. It does **not** confirm that
  a card is currently valid or has not been invalidated. Do not describe it as though it
  does.

### Data in the repository

- Use synthetic data everywhere: tests, examples, documentation, screenshots, and fixtures.
  Never commit real card data, real names, real addresses, or real card numbers.
- No personal machine paths, internal URLs, or organisation-specific identifiers.

### Product scope

- The staff workflow is: read a card, review exactly 17 fields, copy fixed Japanese
  tab-separated text. The copy contract is the output — do not change it without a
  demonstrated regression and updated fixtures.
- The only editable input in the UI is the visible card number. Names and addresses are
  read-only; a value that could not be read is corrected in the destination system after
  pasting, not in this application.
- School-management integration, device pairing, job polling, remote submission, waiting
  mode, and CSV export are out of scope. They were removed deliberately.

## Working on the code

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python tools\fetch_ocr_assets.py   # once: stages and SHA-256-verifies the OCR model
pytest
```

The OCR model is not tracked in Git — see [docs/ocr.md](docs/ocr.md). The staging tool
verifies every artifact against the tracked `resources/ocr/ppocrv6/manifest.json` before
installing it.

Run the application from source with `python app.py` (server only) or
`python launch_reader.py` (desktop shell). Open `http://127.0.0.1:8787`.

### Style

- Inspect before modifying; prefer small, verifiable steps.
- Keep reader detection separate from residence-card parsing, and mock data separate from
  real card reading.
- Keep mock mode working.
- Handle failures gracefully and visibly. A failure staff cannot see is worse than one they
  can.
- Do not refactor adjacent code unless the change requires it.
- Update the documentation when behaviour changes — especially
  [docs/privacy-and-security.md](docs/privacy-and-security.md), [docs/api-contract.md](docs/api-contract.md), and
  [docs/ocr.md](docs/ocr.md).
- Record durable architecture decisions in [docs/decision-log.md](docs/decision-log.md).
- Be explicit in pull requests about which checks you ran and which you skipped. Do not
  report success for a check you did not run.

## Testing

`pytest` must pass before a pull request. Tests use synthetic data only and must not
require a physical reader, a card, a network connection, or a smart-card service.

Hardware behaviour cannot be covered by the suite. If your change touches PC/SC, the
protocol modules, or signature verification, say so in the pull request and describe what
you were able to verify and what you were not. See
[docs/testing-matrix.md](docs/testing-matrix.md).

## Opening an issue

**Never post genuine card photographs, screenshots of real card data, real names,
addresses, birth dates, or card numbers, APDU/TLV/IC dumps, card certificates or
signatures, or logs containing any of these.** Use synthetic values, exactly as the tests
do — `SAMPLE NAME`, `SAMPLELAND`, `AB12345678AJ`. Describing the shape of the data is
almost always enough to diagnose a problem.

Screenshots are welcome only when the content is clearly synthetic and you have checked
every visible field. Sample-data mode exists partly for this: tick the sample-data option,
read once, and screenshot that.

Useful, non-sensitive details for a bug report: reader model, Windows version, Python
version, the exact error message, whether reader detection worked, whether card detection
worked, and whether another known-good reader application can read the same card.

## Reporting a security issue

Please do not open a public issue for a vulnerability that would expose card data. See
[SECURITY.md](SECURITY.md).

## Documentation

English and Japanese must communicate the same material facts. If you change behaviour
covered by a bilingual pair — `README.md` / `README.ja.md`,
[docs/installation.md](docs/installation.md) / [docs/installation.ja.md](docs/installation.ja.md),
[docs/building.md](docs/building.md) / [docs/building.ja.md](docs/building.ja.md) — update
both.

The Japanese versions must never omit privacy warnings, OCR limitations, signature-verification
limitations, unsupported scope, model and certificate setup, security reporting, or the
non-affiliation disclaimer. Do not translate the approved statements loosely: the
field-testing statement, the signature-verification wording, and the non-affiliation
disclaimer have fixed wording in both languages.

English-only documents are acceptable for engineering reference, provided every fact a user
needs in order to use the tool safely also appears in `README.ja.md`.
