# Architecture

Browser UI → local FastAPI (`127.0.0.1:8787`) → PC/SC → residence-card protocol modules. The browser never accesses the reader directly.

`reader/local_config.py` stores only the selected reader ID and app version. `reader/local_api.py` provides local status, reader configuration, and manual scan endpoints. Scan results live only in current page memory for staff review.

Card-type detection, old-card/RC2 reading, OCR candidate extraction, address normalization, signature verification, PC/SC, mock reads, diagnostics for development tests, and privacy sanitization remain isolated in their existing modules.
