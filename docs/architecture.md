# Architecture

Browser UI → local FastAPI (`127.0.0.1:8787`) → PC/SC → residence-card protocol modules. The browser never accesses the reader directly.

`reader/local_config.py` stores only the selected reader ID and app version. `reader/local_api.py` provides local status, reader configuration, manual scan, and copy-text endpoints. `reader/text_export.py` derives Japanese staff labels on the backend and emits the fixed 17-line tab-separated format. Batch data and last copied text live only in page memory.

Card-type detection, old-card/RC2 reading, OCR candidate extraction, address normalization, signature verification, PC/SC, mock reads, diagnostics for development tests, and privacy sanitization remain isolated in their existing modules.
