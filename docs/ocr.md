# Local OCR

## Known limitations — read this first

Some residence-card generations store the holder's **name** and **address** as images
rather than as text. Those two fields are therefore produced by OCR, and OCR gets things
wrong. **Every OCR-derived field must be checked against the card in front of you before it
is copied.**

Known problems:

- spaces inserted at incorrect positions in names;
- long names being partially cut off;
- omitted or incorrectly recognised name characters;
- incorrect address segmentation;
- omitted or incorrectly recognised address characters.

既知の問題:

- 氏名の途中に誤った位置でスペースが入る;
- 長い氏名の一部が欠ける;
- 氏名の文字が抜ける、または誤認識される;
- 住所の区切りが誤る;
- 住所の文字が抜ける、または誤認識される。

**This project makes no claim of perfect OCR accuracy.** The remaining fields — card number,
dates, status, permissions — come from structured chip data, not from OCR, and are not
subject to these problems.

The application has no field for typing a name or an address. When OCR produces nothing the
field reads `読み取れませんでした` / "Could not be read"; consult the physical card when
recording the information elsewhere.

## The recognizer

The bundled recognizer is PaddlePaddle `PP-OCRv6_medium_rec` running locally
through ONNX Runtime CPU. It is the only bundled PaddleOCR model. Its source is
`PaddlePaddle/PP-OCRv6_medium_rec_onnx` at revision
`4ca479517810450af7bcff5bac0e6c4616987d51`; the reviewed `inference.onnx` SHA-256 is
`9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba`.

Assets live under `resources/ocr/ppocrv6/` and consist of `model.onnx`, `inference.yml`,
`dictionary.txt`, and `manifest.json`. The dictionary is generated directly, in order,
from `PostProcess.character_dict` in the matching metadata. No runtime path downloads,
updates, or repairs a model.

## The model is not tracked in Git

`model.onnx` is 76 MB. Tracking it would dominate the repository and, because Git history
is permanent, every future model update would add another 76 MB for the life of the
project. So `model.onnx`, `inference.yml` and `dictionary.txt` are gitignored and staged
locally instead.

`manifest.json` **is** tracked. It carries the reviewed SHA-256 of each artifact and is
what makes an untracked model safe: the staging tool treats it as authority, not as output.
If a download does not reproduce the committed checksums, the tool names the artifact that
differs and installs nothing.

This affects contributors and release builds, not staff. The released `.exe` bundles the
verified model; a staff PC never fetches anything.

## Maintainer setup and release verification

Stage the reviewed, pinned artifacts once per checkout, and again before a package build:

```powershell
powershell -ExecutionPolicy Bypass -File tools\fetch_ocr_assets.ps1
```

For non-Windows CI, `tools/fetch_ocr_assets.py` provides the same atomic staging operation:

```bash
python tools/fetch_ocr_assets.py
```

Staging is atomic: the new set is assembled in a temporary directory, verified, and only
then swapped into place, with the previous set restored if any step fails.

Verify staged assets and the ONNX input/output contract with:

```cmd
.venv\Scripts\python.exe tools\verify_ocr_assets.py
```

The verifier checks all manifest hashes, metadata/dictionary order, the fixed BGR
`[1, 3, 48, W]` recognition input, and CTC output class mapping. `build_windows.ps1`
fails before packaging when this check fails. The package includes the assets and ONNX
Runtime native libraries, resolved relative to the bundled resources rather than a
developer path.

## Recognition

PP-OCRv6 uses BGR preprocessing, aspect-preserving resize to height 48, normalization to
`[-1, 1]`, and zero right-padding. CTC blank handling and class mapping are verified from
the staged metadata and inspected ONNX session; raw images and raw OCR output never leave
the in-memory OCR boundary.

## There is no second OCR engine

PP-OCRv6 is the only recognizer. When it is missing, fails integrity or session
initialization, or cannot read an image, the result is reported as **OCR unavailable** and
structured IC-chip reading continues normally. Nothing else is attempted.

That is deliberate, not a missing feature. An earlier revision fell back to
`Windows.Media.Ocr` through a bundled PowerShell helper. Doing so meant writing the
preprocessed card image to `%TEMP%` as a real file, then running
`powershell.exe -ExecutionPolicy Bypass` from a packaged desktop application. The temporary
file was removed in a `finally` block, but a `finally` block does not survive a crash, a
forced termination, or the launcher's immediate process exit — so a residence-card image
could be left on disk. Both behaviours contradicted the project's own rules ("do not add
PowerShell/Windows Runtime OCR dependencies"; "any required image processing stays in
memory and images are not output"), so the fallback was removed rather than documented.

Structured IC-chip fields are unaffected either way, so an unreadable image never costs a
failed read.

## What staff see when a field was not read

The application has **no field for typing a name or an address**. The only editable input
is the visible card number; everything else is read-only and reviewed. So "the
recognizer produced nothing" and "the recognizer produced something worth checking" call
for different actions and are shown differently:

| State | Field value | Notice |
|---|---|---|
| Nothing was read (`*_ocr_status` starts with `failed`) | `読み取れませんでした` / `Could not be read` | "This app has no field for typing a name — read it from the card when recording information elsewhere." |
| Read, but review it | the candidate | "The name is OCR-derived. Please review it." |
| Read, low confidence | the candidate | The review notice, plus the reason and the suggested alternative |

Staff read the value from the card in front of them when recording information elsewhere.
Nothing is typed into this application.

All OCR is local: no image, text, model output, telemetry, or model request is sent to a
cloud service, and no card image is written to disk at any point. If verification fails,
rerun the fetch command; do not copy an unverified model into the package.
