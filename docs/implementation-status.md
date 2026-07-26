# Implementation Status

- Local reader selection, presence check, real/mock scan, OCR/address processing, and signature status are implemented.
- Scan results are shown only in page memory for review and disappear when the page closes.
- The local config migration retains only `reader_id`; it intentionally does not claim forensic deletion of previous values.
- The Windows build remains the supported release path. Field testing has covered Windows
  10, Windows 11, and Windows Server 2016 with a Sony FeliCa RC-S300 and authorised cards;
  repeat the relevant smoke checks for each release artifact.
