# Native desktop shell

## Architecture

The Windows package keeps the current standalone architecture: a pywebview native window using Edge Chromium/WebView2 loads the existing UI from the local FastAPI server at `127.0.0.1:8787`. JavaScript continues to call the existing local HTTP API. No pywebview `js_api` bridge is exposed.

pywebview was selected because it is a thin native window around the working plain-web UI and does not bundle a browser runtime. Electron, Tauri, and a full native rewrite were not selected because they would duplicate or replace the existing UI/backend boundary for no product benefit in this milestone.

## Lifecycle and fallback

The launcher checks `/api/health` and requires `{"app": "zairyu-reader"}` before reusing a listening port. It rejects unrelated services. It tracks whether it created Uvicorn; closing the desktop window requests graceful shutdown only for that owned server and waits briefly for its thread. `--browser` opens the same local URL in the system browser; `--no-browser` and legacy `--headless` are server-only modes.

WebView2 Runtime is required and is not bundled. A native Japanese/English error explains the requirement and documents `--browser` as a fallback. The shell forces `edgechromium`; it does not silently use MSHTML. Downloads are disabled and external links are configured to open in the system browser.

Windows Server 2016 requires Desktop Experience. Server Core cannot display the native UI. WebView2 Runtime, the Windows Smart Card service, a PC/SC reader driver, and possibly Japanese OCR support must be installed. OCR failure must not prevent non-OCR chip fields from being read. Hardware and OCR behavior on Windows Server 2016 requires manual verification.

## Verification

Automated tests cover health identity, existing-instance detection, unrelated-port rejection, readiness timeout, ownership shutdown behavior, display-mode selection, browser selection, mocked pywebview settings, and traceback-free native-shell failure handling. The implementation also adds the build-script JavaScript syntax check and package resource checks.

This workspace ran `python3 -m py_compile app.py launch_reader.py assets/generate_icon.py tests/test_launcher.py`, `python3 launch_reader.py --help`, pure launcher assertions, `node --check static/local.js`, an icon-directory check, and a Python syntax parse of the PyInstaller spec. `pytest` was attempted but the available Linux interpreter has no pytest; the checked-in virtual environment contains a Windows executable that cannot run in this environment.

The windowed PyInstaller executable has no usable `sys.stderr`. The embedded Uvicorn configuration therefore sets `log_config=None`, avoiding its default console formatter, which otherwise fails during startup before the desktop window can open.

This Linux workspace did not open a real pywebview window, run a Windows PyInstaller build, test the WebView2 fallback, run on Windows Server 2016, use a physical NFC reader, or read an authorized residence card. Those remain manual acceptance checks.
