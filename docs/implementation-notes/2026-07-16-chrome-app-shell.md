# 2026-07-16 — Chrome app-mode shell

## Goal

Provide an application-style local window on Windows Server 2016, where the existing WebView2 shell can render the page while failing to run its JavaScript.

## Implementation

- Added `--chrome-app` and `--webview` launcher modes while preserving `--browser`, `--no-browser`, `--headless`, `--host`, and `--port`.
- The default shell prefers Chromium app mode on detected Windows Server 2016. Other desktop Windows versions try the existing Edge WebView2 shell, then fall back to Chromium app mode if WebView2 startup raises an error.
- Browser discovery is Python-only and prefers Chrome, Edge, then Chromium. `ZAIRYU_BROWSER_PATH` is accepted only when it identifies a file.
- Chromium receives a loopback `--app` URL, the dedicated `%LOCALAPPDATA%\ZairyuReader\BrowserProfile`, and flags disabling first-run setup, extensions, sync, and background networking. It receives no remote-debugging switch or card data.
- The launcher continues to identify a reusable server through `/api/health`, stops only an owned Uvicorn server, and monitors only the exact Chromium bootstrap process it created.

## Lifecycle limitation

Chromium can delegate a new app window to a running process for the same local profile and immediately exit the bootstrap process. The launcher does not inspect or kill that other process. It leaves an owned server running for a bounded 15-second grace period in that case, but cannot detect when the delegated app window later closes. Operators should close existing Zairyu Reader app windows before relaunching when automatic server shutdown matters.

## Verification

`python3 -m py_compile launch_reader.py tests/test_launcher.py`, `node --check static/local.js`, and `python3 launch_reader.py --help` completed in this workspace. `python3 -m pytest tests/test_launcher.py -q` could not run because this environment does not have pytest installed. No Windows build, actual Chrome app window, WebView2 fallback, Windows Server 2016 test, physical reader, or authorized card test was run here.
