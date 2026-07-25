# 2026-07-17 — PP-OCRv6 medium recognizer

The prior PP-OCRv5 profile/staging design was replaced with one pinned, official
`PP-OCRv6_medium_rec` ONNX artifact. Its metadata is bundled alongside the model and the
dictionary is mechanically generated from the matching `PostProcess.character_dict` list.
The engine validates all asset hashes and its ONNX contract before inference, preprocesses
BGR crops at 48px high, and decodes CTC output with metadata-derived class count.

`tools/fetch_ocr_assets.ps1` performs atomic Windows staging; the equivalent Python helper
supports non-Windows CI. The application has no download code. When the primary engine
fails, it attempts a real local Windows.Media.Ocr recognition call on supported Windows
systems and otherwise reports OCR unavailable without blocking chip data.

For first-generation cards (`1`/`2`), the protected image is a complete front-card TIFF,
not an RC2 field crop. The reader now extracts text-row fragments across the whole card in
memory, excludes photograph-sized regions by shape, merges same-row fragments, and passes
the resulting rows to PP-OCRv6. Parsed labels are mapped to the reviewed name, date, sex,
nationality, status, address, expiry, and work-restriction fields. Real-card acceptance is
still required because no personal card images are retained as fixtures.
