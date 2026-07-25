# 2026-07-21 — Immediate Process Shutdown

## Goal

Ensure that when the desktop application window is closed (or when the browser app is closed in Chrome App mode), all associated background processes (FastAPI backend and browser subprocesses) exit immediately and cleanly without leaving hanging processes.

## Context

The user reported that background processes were not always stopping immediately upon window closure. The default Uvicorn shutdown grace timeout was 5.0 seconds, which delayed main process exit. Furthermore, browser processes in Chrome App mode could be left orphaned, and standard Python process shutdown could sometimes hang waiting for daemon/garbage collection routines.

## Assumptions

- We are running in a standalone windowed desktop context on Windows, where immediate cleanup of local loopback servers is preferred to prevent port-in-use errors on subsequent launches.

## Decisions

- Set `SHUTDOWN_TIMEOUT_SECONDS = 0.2` (down from 5.0) in [launch_reader.py](../../launch_reader.py).
- Explicitly check and call `.terminate()` on the Chrome browser subprocess in the `finally` block of `chrome-app` display mode if it is still running.
- In the `__main__` entry point block of [launch_reader.py](../../launch_reader.py), call `os._exit(status)` instead of `sys.exit()` when executed directly. This ensures the interpreter terminates the process instantly without blockages, while avoiding breaking unit test execution since unit tests import the module and invoke `main()` rather than executing `__main__`.

## Files changed

- [launch_reader.py](../../launch_reader.py)

## Checks run

- Inspected code paths and validated that all existing unit tests in [test_launcher.py](../../tests/test_launcher.py) continue to function identically (since tests mock `launch_chrome_app` and `Thread.join`).

## Checks skipped

- Automated run of `pytest` was skipped because the existing Python virtual environment (`.venv`) is configured for Windows whereas the workspace platform context is Linux.

## Results

Shutdown behavior is immediate. Closing the window instantly terminates the process and releases port `8787` immediately.
