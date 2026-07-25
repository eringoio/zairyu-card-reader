# 2026-07-17 — Field-specific OCR pipeline

## Change

Address and name OCR now run through a local, field-specific pipeline before their
staff-facing candidate is built. The pipeline keeps every image in memory and generates
grayscale, autocontrast, three-times-upscaled, sharpened, adaptive-threshold, Otsu, and
inverted-Otsu variants. It conservatively removes blank borders, applies a narrow
projection-based deskew where it improves line concentration, and segments multi-line
address fields by horizontal ink projections.

Each line/variant is recognized locally. Raw variant results remain internal; only the
best normalized candidate, confidence category, review-required flag, safe reason codes,
and suggested normalized candidate can reach the staff API. No image, OCR trace, or raw
candidate key is added to the API.

## Text handling

Address normalization applies NFKC and removes spaces only between Japanese address
components or adjoining address numbers. It retains Latin word spacing, punctuation, and
line order long enough to make a field-aware join. For example,
`ｍａｉｓｏｎＩ　Ｎｏ．３７０５号` becomes `maisonI No.3705号` rather than
`maisonINo.3705号`.

Name normalization is separate: it supports Latin names, Katakana, apostrophes, hyphens,
and name-component spaces, without using address correction rules. Confusion indicators
such as mixed scripts, `No.`/`N0.` patterns, and visually ambiguous Latin/numeric
characters trigger review metadata rather than open-ended dictionary substitutions.
Normalization only closes spacing inside a genuine `No.` marker: `N0.` remains visible in
the suggested text and receives a `room_number_confusion` review reason.

For address OCR only, complete known prefecture aliases with a simplified glyph are
canonicalized (for example, `爱知県` to `愛知県`), and `@` between two digits is read as
the zero digit. These are bounded address-context rules, not general Chinese/Japanese
character substitutions.

## Benchmark

`tests/ocr_benchmark_cases.py` defines 12 synthetic-only cases covering Japanese address
components, Katakana/small kana/dakuten, full- and half-width Latin, room numbers,
hyphens, mixed lines, low contrast, broken strokes, compression, and skew.
`tools/generate_synthetic_ocr_benchmark.py` makes degradations using an explicitly chosen
local Japanese-capable font. `tools/benchmark_ocr_pipeline.py` records exact-line
accuracy, CER, address-component preservation, name/address latency, and selected model
profile in JSON. Pass `--profile compact` and `--profile accurate` to create separate,
directly comparable reports.

The checked-in source tree intentionally has no reviewed model, so actual compact and
accurate recognition/latency figures are not claimed. The deterministic normalization
examples improve from 1/2 under the previous unconditional whitespace deletion to 2/2
(`メディアパーク`, `maisonI No.3705号`) under this pipeline. A staged model benchmark
must be recorded before package-performance claims are made.

## Profile recommendation

Use the existing `compact` 48×320 profile for ordinary local review workflows and the
`accurate` 48×640 profile when slower recognition is acceptable for difficult scans. Both
remain local ONNX Runtime profiles and require the reviewed manifest/checksum workflow.
