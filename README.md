# zairyu-card-reader

**[日本語版 README →](README.ja.md)**

A standalone Windows tool that reads a Japanese residence card (在留カード) locally, on one
PC, using a USB NFC reader. Staff review exactly 17 fields on screen.

Everything happens on the machine in front of you. There is no server, no account, no
cloud, and no network traffic of any kind while a card is being read.

> **This project is independently developed and is not affiliated with, endorsed by,
> approved by, or certified by the Immigration Services Agency of Japan or the Ministry of
> Justice.**

---

## What it does

- Detects PC/SC card readers connected to the PC.
- Detects whether a card is on the reader.
- Reads the structured fields stored in the card's IC chip, after you enter the card number
  printed on the front of the card.
- Reads the name and address images with a local OCR engine, when the card generation
  stores them as images.
- Verifies the card's digital signature against offline, packaged Immigration Services
  Agency certificates.
- Displays 17 reviewed fields for a human to check.

## What it does not do

- **No cloud, no telemetry, no analytics, no automatic updates, no remote submission.**
- **No database.** Nothing is stored except the selected reader index.
- **No face photographs, no card images, no raw IC/APDU/TLV data** are stored, displayed,
  logged, copied, or written to disk.
- **No My Number and no JPKI data** are read or accessed.
- **No bulk scanning**, no staff accounts, no reporting.
- **No LAN, tunnel, reverse-proxy, or public hosting.** The server refuses to bind to
  anything but loopback.

## Field testing

> The maintainer has field-tested this application with more than 60 newer-generation and
> about 10 older-generation genuine Japanese residence cards, using a Sony FeliCa RC-S300
> reader on Windows 10, Windows 11, and Windows Server 2016. Structured IC-chip fields and
> signature verification worked correctly during those tests. Results may still differ
> depending on card generation, card condition, NFC reader, reader driver, operating system,
> and OCR environment.

The automated test suite uses synthetic data only. Field testing is useful evidence, but it
does not guarantee reader compatibility, driver behaviour, or OCR quality on your hardware.

## OCR is imperfect, and every OCR field must be reviewed

Where a card stores the name or the address as an image rather than as text, the value is
produced by local OCR. **Always check those fields against the card in front of you before
using the result.** Known problems include:

- spaces inserted at incorrect positions in names;
- long names being partially cut off;
- omitted or incorrectly recognised name characters;
- incorrect address segmentation;
- an incorrect final address line after the prefecture and municipality;
- place names containing complex kanji being misrecognised;
- omitted or incorrectly recognised address characters.

This project makes no claim of perfect OCR accuracy.

The application has **no field for typing a name or an address**. The only thing you type is
the card number. When OCR produces nothing, the field reads `読み取れませんでした` /
"Could not be read"; check the physical card when recording the information elsewhere.

See [docs/ocr.md](docs/ocr.md).

## Signature verification, and what it does not tell you

> Signature verification confirms the cryptographic relationship between the data read from
> the IC chip and the supported trust material. It does not by itself confirm that the card
> remains currently valid or has not subsequently been invalidated.

Verification is entirely offline against certificates packaged with the application, each
checked against a recorded SHA-256 fingerprint before use. The `production` profile is the
default. An official test-card certificate is isolated behind
`VERIFICATION_TRUST_PROFILE=official_test`, which displays a persistent warning and can only
ever report an official-test result — never production authenticity.

See [docs/signature-verification.md](docs/signature-verification.md) and
[docs/official-certificates.md](docs/official-certificates.md).

## Unsupported scope

Unless separately reviewed, this application does **not** support:

- specified residence cards (特定在留カード) with My Number functionality;
- My Number application data;
- JPKI;
- RSA delivery keys for specified cards — this material is not distributed with the project
  at all;
- complete residence-status (在留資格) display mapping; staff must confirm the shown status
  against the physical card;
- remote or network reader operation.

Card types `07` and `08` are refused by policy without attempting My Number or JPKI access.

## Requirements

| Item | Requirement |
|---|---|
| Operating system | Windows 10 or 11 (64-bit). Windows Server 2016 with Desktop Experience is supported through Chromium app mode. |
| Reader | A PC/SC contactless reader with **ISO/IEC 14443 Type B** support. A contact-only or FeliCa/Type-A-only reader will not work. |
| Driver | The reader manufacturer's PC/SC driver, plus the Windows Smart Card service running. |
| Display shell | Microsoft Edge WebView2 Runtime, or an installed Google Chrome / Microsoft Edge / Chromium. |
| Python (source only) | 3.11 or later. Not needed for the released package. |

## Install and run

**Staff:** use the released Windows package. Double-click `zairyu-reader.exe`. Nothing else
is required.

**From source:**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tools\fetch_ocr_assets.py
python app.py
```

Then open `http://127.0.0.1:8787`.

`tools\fetch_ocr_assets.py` stages the local OCR model, which is not tracked in Git because
of its size. It downloads the pinned upstream revision and verifies every artifact against
the committed `resources/ocr/ppocrv6/manifest.json` before installing anything. Run it once.

**An internet connection is needed only to install dependencies and stage the OCR model.
Reading cards needs no internet connection at all.**

> **Never expose this server through a LAN, a tunnel, a reverse proxy, or a public host.**
> The local API returns reviewed card data and has no user authentication. `--host` accepts
> `127.0.0.1`, `localhost` and `::1` only; anything else is refused.

Full details: [docs/installation.md](docs/installation.md) ·
[日本語](docs/installation.ja.md)

## Building the Windows package

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The output is `dist\zairyu-reader\zairyu-reader.exe`, a one-folder distribution that runs on
a Windows PC with no Python installed. The build verifies the OCR model and the health
contract, runs the test suite, and refuses to package a script payload.

Full details: [docs/building.md](docs/building.md) · [日本語](docs/building.ja.md)

## Using it

1. Connect the reader and start the application.
2. Select your reader and save the choice.
3. Place the residence card flat on the reader.
4. Type the card number printed on the front of the card.
5. Select **読み取り開始 / Start reading**.
6. **Review all 17 fields against the card**, especially the name and the address.

## Privacy and security

- [PRIVACY.md](PRIVACY.md) — what is read, what is never read, and what leaves the machine.
- [docs/privacy-and-security.md](docs/privacy-and-security.md) — the technical boundary.
- [SECURITY.md](SECURITY.md) — how to report a vulnerability privately.

**When opening a public issue, never post genuine card photographs, screenshots of real
card data, real names, addresses, birth dates, or card numbers, APDU/TLV/IC dumps, card
certificates or signatures, or logs containing any of these.** Use synthetic values, as the
tests do. Describing the shape of the data is enough.

## Legal and consent

Read a card only when the holder has consented, or when you are otherwise authorised to
verify it. Handling residence-card data engages Japan's Act on the Protection of Personal
Information and, in most workplaces, your own organisation's rules. This tool does not
determine whether you are permitted to read a given card; that responsibility is yours.

## Licence and notices

Copyright 2026 Eringo.io.

This project's own source, tests, tooling and documentation are licensed under the
**Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

The licence does **not** cover third-party material distributed with the project:
government-published certificates remain subject to their publisher's terms, and each
dependency and the OCR model carry their own licences. The complete list — component,
source, version policy, licence, notice obligation, and whether it is bundled — is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Note that `pyscard` is LGPL-2.1-or-later; the other dependencies are permissive.

## Documentation

| Topic | English | 日本語 |
|---|---|---|
| Overview | [README.md](README.md) | [README.ja.md](README.ja.md) |
| Installation | [docs/installation.md](docs/installation.md) | [docs/installation.ja.md](docs/installation.ja.md) |
| Building the package | [docs/building.md](docs/building.md) | [docs/building.ja.md](docs/building.ja.md) |
| Making a release | [docs/releasing.md](docs/releasing.md) · [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) | — |
| Privacy summary | [PRIVACY.md](PRIVACY.md) | (in [README.ja.md](README.ja.md)) |
| Privacy and security detail | [docs/privacy-and-security.md](docs/privacy-and-security.md) | — |
| Reporting a vulnerability | [SECURITY.md](SECURITY.md) | — |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) | — |
| OCR | [docs/ocr.md](docs/ocr.md) | — |
| Signature verification | [docs/signature-verification.md](docs/signature-verification.md) | — |
| Official certificates | [docs/official-certificates.md](docs/official-certificates.md) | — |
| Troubleshooting | [docs/troubleshooting.md](docs/troubleshooting.md) | — |
| Architecture | [docs/architecture.md](docs/architecture.md) | — |
| Local API contract | [docs/api-contract.md](docs/api-contract.md) | — |
| Decision log | [docs/decision-log.md](docs/decision-log.md) | — |

## Non-affiliation

> This project is independently developed and is not affiliated with, endorsed by, approved
> by, or certified by the Immigration Services Agency of Japan or the Ministry of Justice.
