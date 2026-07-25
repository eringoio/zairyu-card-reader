# Third-Party Notices

Every third-party component this project uses, with its source, version policy, licence,
notice obligation, and whether it is bundled in the released Windows package or installed
separately.

The Apache License 2.0 in [LICENSE](LICENSE) covers this project's own source, tests,
tooling and documentation. It does **not** cover anything listed below.

Licences are stated as published by each project. Verify them against the exact versions in
[requirements.lock.txt](requirements.lock.txt) for a given release.

---

## 1. Machine-learning model and runtime

### PP-OCRv6_medium_rec

| | |
|---|---|
| Component | `PP-OCRv6_medium_rec` recognition model |
| Source | `PaddlePaddle/PP-OCRv6_medium_rec_onnx` (Hugging Face) |
| Version policy | **Pinned by commit**, revision `4ca479517810450af7bcff5bac0e6c4616987d51`. Never a branch or tag. |
| Licence | Apache-2.0 |
| Notice requirement | Retain the Apache-2.0 licence and any NOTICE shipped by PaddlePaddle when redistributing the model bytes |
| Distribution | **Not tracked in this repository.** Staged locally; bundled in the released Windows package |

`model.onnx` SHA-256:
`9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba`

`resources/ocr/ppocrv6/dictionary.txt` is generated reproducibly from
`PostProcess.character_dict` in the matching `inference.yml`. It is derived from the
upstream model metadata, not authored here, and carries the model's licence. Do not
distribute modified or unverified model bytes. See [docs/ocr.md](docs/ocr.md).

### ONNX Runtime

| | |
|---|---|
| Component | ONNX Runtime (CPU execution provider) |
| Source | `onnxruntime` on PyPI, Microsoft |
| Version policy | `>=1.17,<2`, pinned exactly in the lockfile |
| Licence | MIT |
| Notice requirement | Retain the MIT licence text; consult the licence notices bundled in the distribution for the exact version |
| Distribution | Native libraries **bundled** in the released Windows package |

---

## 2. Python runtime dependencies

All installed from PyPI. Version policy: a floor and ceiling in
[requirements.txt](requirements.txt), pinned exactly in
[requirements.lock.txt](requirements.lock.txt). Each is **bundled** into the released
Windows package by PyInstaller.

| Component | Licence | Notice requirement | Used for |
|---|---|---|---|
| FastAPI | MIT | Retain licence text | The local HTTP application |
| Uvicorn (`uvicorn[standard]`) | BSD-3-Clause | Retain licence and copyright notice | The ASGI server |
| pyscard | **LGPL-2.1-or-later** | See below | PC/SC card reader access |
| pycryptodome | BSD-2-Clause / Public Domain (dual) | Retain licence text | AES, CMAC, 3DES for card secure messaging |
| Pillow | MIT-CMU | Retain licence and copyright notice | Image decoding and preprocessing for OCR |
| NumPy | BSD-3-Clause | Retain licence and copyright notice | OCR tensor preparation and CTC decoding |
| PyYAML | MIT | Retain licence text | Reading the pinned OCR model metadata |
| cryptography (PyCA) | Apache-2.0 **or** BSD-3-Clause (dual) | Retain the chosen licence; Apache-2.0 also requires NOTICE propagation | X.509 parsing, RSA/ECDSA signature verification |
| pywebview | BSD-3-Clause | Retain licence and copyright notice | The WebView2 desktop window |
| pyasn1 | BSD-2-Clause | Retain licence text | BER/DER normalisation of card certificates |
| pyasn1-modules | BSD-2-Clause | Retain licence text | RFC 2459 certificate structures |

### pyscard and the LGPL

`pyscard` is **LGPL-2.1-or-later** — the only dependency whose terms differ materially from
the permissive remainder, so it is worth being precise:

- It is used **unmodified**, through its documented public API, and is imported by the
  Python interpreter at runtime. No pyscard source is copied into this project.
- PyInstaller bundles it as a separate, replaceable module in the distribution rather than
  statically linking it into a single binary.
- The LGPL requires that a recipient be able to replace the library with a modified version.
  In a one-folder PyInstaller distribution the pyscard files remain individually present
  under `_internal`, which supports that.
- If you **modify** pyscard itself, the LGPL's terms govern that modification and you must
  make the modified source available.

This is a statement of how the dependency is used, not legal advice. If you redistribute a
build in a context where LGPL compliance is contentious, take your own advice.

---

## 3. Development-only dependencies

Listed in [requirements-dev.txt](requirements-dev.txt). **Not bundled** — the PyInstaller
spec explicitly excludes `pytest`.

| Component | Licence | Used for |
|---|---|---|
| pytest | MIT | The test suite |
| PyInstaller | GPL-2.0-or-later **with a bootloader exception** permitting proprietary and differently-licensed applications to be packaged | Building the Windows package |
| pip-audit | Apache-2.0 | Dependency vulnerability auditing |
| ruff | MIT | Linting |

PyInstaller's exception is what makes it usable here: it permits distributing an application
packaged with PyInstaller under the application's own licence. The bootloader itself remains
under its own terms.

---

## 4. Government-published material

### Immigration Services Agency of Japan — public key certificates

| | |
|---|---|
| Component | Residence-card CA certificates (6 files) |
| Source | <https://www.moj.go.jp/isa/applications/disclosure/120424_01.html> (first generation)<br><https://www.moj.go.jp/isa/publications/resources/120424_01_00003.html> (second generation) |
| Version policy | Fixed files, each verified against a recorded SHA-256 before use |
| Licence | Published by the Immigration Services Agency under the terms on those pages. **Not** covered by this project's Apache-2.0 licence |
| Notice requirement | Do not imply government endorsement. Do not present official-test material as a production result |
| Distribution | **Bundled**, in `resources/moj/trust-anchors/` and the released package |

The pages state that copyright in the published specifications is protected, while expressly
not preventing software developers from building and distributing software based on them.
The full reasoning for what is and is not redistributed, the per-file digests, and the
provenance register are in [docs/official-certificates.md](docs/official-certificates.md).

**Not distributed:** the specification PDFs (cited by document number, version, page and
section instead), and specified-card RSA delivery key material (`001462222.zip`,
`001460789.zip`), which is out of scope entirely.

---

## 5. Original assets and data

These are this project's own work, authored by the maintainer, and are covered by
[LICENSE](LICENSE).

### `resources/moj/trust-anchors/countries/countries_ja.json`

An ISO 3166-1 alpha-3 code to Japanese country/region name mapping (about 250 entries), used
to render a nationality label from a chip code. Authored for this project; it is not derived
from a third-party dataset. The alpha-3 codes are the published international standard's
identifiers; the Japanese names are this project's own compilation.

### `assets/zairyu-reader.ico`

Generated by `assets/generate_icon.py`, original code in this repository. It draws an
abstract card outline and NFC arcs. It is **not** a government emblem and does not resemble
a real residence card.

---

## Verifying this list

```bash
python -m pip install pip-licenses
pip-licenses --from=mixed --with-urls --format=markdown
```

Run it against the exact pinned set for a release and reconcile any difference against this
document. The tabulated licences above were compiled by hand and should be treated as a
starting point for that reconciliation, not as its output.
