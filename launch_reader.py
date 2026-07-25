"""Desktop launcher for the local-only residence-card reader.

The FastAPI application continues to own all UI APIs.  This module only starts or
reuses that loopback server and hosts the existing page in WebView2 or installed
Chromium app mode. Keeping lifecycle decisions in small functions makes them
testable without a Windows desktop, WebView2, a reader, or a card.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
STARTUP_TIMEOUT_SECONDS = 30.0
SHUTDOWN_TIMEOUT_SECONDS = 0.2
APP_ID = "zairyu-reader"
CHROME_BOOTSTRAP_GRACE_SECONDS = 15.0


@dataclass(frozen=True)
class ChromiumBrowser:
    """An installed Chromium-family browser suitable for the local app shell."""

    name: str
    path: Path


class ExistingServer(Enum):
    NOT_RUNNING = "not_running"
    READER = "reader"
    OTHER = "other"


@dataclass
class ServerSession:
    """A server and whether this launcher is responsible for stopping it."""

    server: Any | None = None
    thread: threading.Thread | None = None
    owned: bool = False

    def stop(self, timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """Request a graceful shutdown only for a server started by this process."""
        if not self.owned or self.server is None:
            return
        self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def check_dependencies() -> list[str]:
    missing: list[str] = []
    for module, package in [("fastapi", "fastapi"), ("uvicorn", "uvicorn[standard]")]:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def port_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((host, port)) == 0


def server_url(host: str, port: int) -> str:
    """Return a URL for the supported IPv4/hostname launcher inputs."""
    return f"http://{host}:{port}"


def read_health(url: str, timeout: float = 1.0) -> dict[str, Any] | None:
    """Read the public health document without exposing network errors to staff."""
    try:
        # `url` is built by `server_url()` from a host that `main()` has already rejected
        # unless it is 127.0.0.1, localhost or ::1, so the scheme is always plain http on
        # loopback. This is the only outbound request the application ever makes.
        with urllib.request.urlopen(f"{url}/api/health", timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def is_reader_health(payload: dict[str, Any] | None) -> bool:
    return bool(payload and payload.get("success") is True and payload.get("app") == APP_ID)


def inspect_existing_server(
    host: str,
    port: int,
    *,
    port_checker: Callable[[str, int], bool] = port_is_open,
    health_reader: Callable[[str], dict[str, Any] | None] = read_health,
) -> ExistingServer:
    """Classify the requested port, never trusting TCP reachability alone."""
    if not port_checker(host, port):
        return ExistingServer.NOT_RUNNING
    return ExistingServer.READER if is_reader_health(health_reader(server_url(host, port))) else ExistingServer.OTHER


def wait_for_reader_health(
    host: str,
    port: int,
    *,
    timeout: float = STARTUP_TIMEOUT_SECONDS,
    poll_interval: float = 0.2,
    health_reader: Callable[[str], dict[str, Any] | None] = read_health,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = clock() + timeout
    url = server_url(host, port)
    while clock() < deadline:
        if is_reader_health(health_reader(url)):
            return True
        sleeper(poll_interval)
    return is_reader_health(health_reader(url))


def create_uvicorn_server(host: str, port: int) -> Any:
    """Create, but do not run, the embedded Uvicorn server."""
    import uvicorn

    import app as app_module

    # The packaged app is windowed (``console=False``), so ``sys.stderr`` is not
    # available. Uvicorn's default logging configuration probes that stream while
    # constructing its formatter and otherwise aborts before the server starts.
    config = uvicorn.Config(
        app_module.app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    return uvicorn.Server(config)


def start_owned_server(
    host: str,
    port: int,
    *,
    server_factory: Callable[[str, int], Any] = create_uvicorn_server,
    readiness_waiter: Callable[[str, int], bool] = wait_for_reader_health,
) -> ServerSession | None:
    """Start one server in a background thread and wait for its identified health API."""
    server = server_factory(host, port)
    # Normal shutdown joins this thread. Making it a daemon is the final fallback
    # if a broken server implementation ignores should_exit, so the desktop
    # process cannot remain hung after its only window has closed.
    thread = threading.Thread(target=server.run, name="zairyu-reader-server", daemon=True)
    session = ServerSession(server=server, thread=thread, owned=True)
    thread.start()
    if readiness_waiter(host, port):
        return session
    session.stop()
    return None


def is_windows_server_2016(
    *,
    system: str = sys.platform,
    win_version: Callable[[], tuple[str, str, str, str]] = platform.win32_ver,
) -> bool:
    """Return whether this is Windows Server 2016 (build 14393)."""
    if system != "win32":
        return False
    release, version, _csd, product_type = win_version()
    return release == "2016" or version.startswith("10.0.14393") or product_type == "Server 2016"


def display_mode(
    args: argparse.Namespace,
    *,
    server_2016: bool | None = None,
) -> str:
    """Select an explicit shell mode, keeping server/browser compatibility modes."""
    if getattr(args, "browser", False):
        return "browser"
    if getattr(args, "no_browser", False) or getattr(args, "headless", False):
        return "server"
    if getattr(args, "chrome_app", False):
        return "chrome-app"
    if getattr(args, "webview", False):
        return "webview"
    return "chrome-app" if (is_windows_server_2016() if server_2016 is None else server_2016) else "webview"


def is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def non_loopback_error_message(host: str) -> str:
    return (
        f"指定されたアドレス {host} は利用できません。\n"
        "在留カードリーダーはこのPC内（127.0.0.1）でのみ動作します。\n\n"
        f"The address {host} cannot be used.\n"
        "The residence card reader runs on this PC only (127.0.0.1). Network, LAN and "
        "public hosting are not supported, because the local API returns reviewed card "
        "data and has no user authentication."
    )


def show_error(message: str, title: str = "在留カードリーダー / Residence Card Reader") -> None:
    """Show a traceback-free staff message, including from a windowed executable."""
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except (AttributeError, OSError):
            pass
    print(f"{title}\n{message}", file=sys.stderr)


def webview_error_message() -> str:
    return (
        "Microsoft Edge WebView2 Runtime が必要なため、デスクトップ画面を開けませんでした。\n"
        "WebView2 Runtime をインストールしてから、もう一度お試しください。\n\n"
        "Microsoft Edge WebView2 Runtime is required to open the desktop window.\n"
        "Install it and try again. As a fallback, start zairyu-reader.exe --chrome-app or --browser."
    )


def chrome_app_error_message() -> str:
    return (
        "Chrome、Microsoft Edge、または Chromium が見つからないため、アプリ形式の画面を開けませんでした。\n"
        "対応するブラウザをインストールするか、zairyu-reader.exe --browser を使用してください。\n\n"
        "Chrome, Microsoft Edge, or Chromium was not found, so the application-style window could not be opened.\n"
        "Install a compatible browser or use zairyu-reader.exe --browser as the last fallback."
    )


def browser_profile_path(environ: dict[str, str] | None = None) -> Path:
    """Return the local-only Chromium profile used by the application shell."""
    env = os.environ if environ is None else environ
    local_app_data = env.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "ZairyuReader" / "BrowserProfile"


def discover_chromium_browser(
    *,
    environ: dict[str, str] | None = None,
    is_file: Callable[[Path], bool] | None = None,
) -> ChromiumBrowser | None:
    """Find a configured or installed Chromium browser without using PowerShell."""
    env = os.environ if environ is None else environ
    exists = is_file or Path.is_file

    configured = env.get("ZAIRYU_BROWSER_PATH")
    if configured:
        path = Path(configured).expanduser()
        if path.suffix.lower() == ".exe" and exists(path):
            return ChromiumBrowser("Configured browser", path)

    program_files = env.get("ProgramFiles")
    program_files_x86 = env.get("ProgramFiles(x86)")
    local_app_data = env.get("LOCALAPPDATA")
    candidates: list[tuple[str, Path]] = []

    def add(name: str, root: str | None, *parts: str) -> None:
        if root:
            candidates.append((name, Path(root).joinpath(*parts)))

    # Keep this order aligned with the staff-facing compatibility policy.
    add("Google Chrome", program_files, "Google", "Chrome", "Application", "chrome.exe")
    add("Google Chrome", program_files_x86, "Google", "Chrome", "Application", "chrome.exe")
    add("Google Chrome", local_app_data, "Google", "Chrome", "Application", "chrome.exe")
    add("Microsoft Edge", program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe")
    add("Microsoft Edge", program_files, "Microsoft", "Edge", "Application", "msedge.exe")
    add("Chromium", program_files, "Chromium", "Application", "chrome.exe")
    add("Chromium", program_files_x86, "Chromium", "Application", "chrome.exe")
    add("Chromium", local_app_data, "Chromium", "Application", "chrome.exe")

    for name, path in candidates:
        if exists(path):
            return ChromiumBrowser(name, path)
    return None


def is_local_url(url: str) -> bool:
    """Accept only loopback HTTP URLs for the Chromium application shell."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def chrome_app_arguments(browser: ChromiumBrowser, url: str, profile: Path) -> list[str]:
    """Build privacy-preserving app-mode arguments with no remote debugging."""
    if not is_local_url(url):
        raise ValueError("Chrome app mode supports loopback URLs only")
    return [
        str(browser.path),
        f"--app={url}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
    ]


def launch_chrome_app(
    browser: ChromiumBrowser,
    url: str,
    profile: Path,
    *,
    process_factory: Callable[[list[str]], Any] = subprocess.Popen,
) -> Any:
    """Start exactly one Chromium bootstrap process for the local application URL."""
    profile.mkdir(parents=True, exist_ok=True)
    return process_factory(chrome_app_arguments(browser, url, profile))


def wait_for_chrome_app(
    process: Any,
    *,
    bootstrap_grace: float = CHROME_BOOTSTRAP_GRACE_SECONDS,
    poll_interval: float = 0.2,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Wait for the owned browser process, with a grace period for Chrome delegation.

    Chromium can hand a new app window to an already-running process for the same
    profile and let this bootstrap process exit immediately.  We cannot inspect or
    terminate that unrelated process, so keep an owned server alive briefly rather
    than stopping it at once.
    """
    started = clock()
    while process.poll() is None:
        sleeper(poll_interval)
    if clock() - started < poll_interval:
        deadline = clock() + bootstrap_grace
        while clock() < deadline:
            sleeper(poll_interval)


def open_native_window(url: str, on_closed: Callable[[], None]) -> None:
    """Open the staff UI without a browser chrome or JavaScript bridge."""
    import webview

    # These are supported pywebview 5+ settings and are set before start(). The
    # page only talks to the existing FastAPI API; no js_api object is provided.
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    window = webview.create_window(
        "在留カードリーダー",
        url,
        width=1100,
        height=820,
        min_size=(880, 620),
        resizable=True,
        frameless=False,
        background_color="#f5f7fa",
        text_select=True,
    )
    window.events.closed += on_closed
    # Do not allow pywebview to choose the obsolete MSHTML fallback.
    webview.start(gui="edgechromium", debug=False)


def wait_for_server(session: ServerSession) -> None:
    """Keep explicit server-only/browser fallback modes alive until Ctrl+C."""
    try:
        while session.thread is not None and session.thread.is_alive():
            session.thread.join(0.5)
    except KeyboardInterrupt:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local residence-card reader.")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Loopback bind address. Only 127.0.0.1, localhost and ::1 are accepted; anything else is refused.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port. Default: 8787.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--browser", action="store_true", help="Open the local UI in the default browser.")
    mode.add_argument("--no-browser", action="store_true", help="Start the local server without a user interface.")
    mode.add_argument("--headless", action="store_true", help="Compatibility alias for --no-browser (server only).")
    mode.add_argument("--chrome-app", action="store_true", help="Open the local UI in Chrome/Edge app mode.")
    mode.add_argument("--webview", action="store_true", help="Force the Microsoft Edge WebView2 desktop window.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mode = display_mode(args)
    url = server_url(args.host, args.port)

    if not is_frozen() and str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    missing = check_dependencies()
    if missing:
        show_error(
            "必要なライブラリがインストールされていません。\n"
            "Required libraries are not installed.\n\n"
            f"不足 / Missing: {', '.join(missing)}\n"
            "pip install -r requirements.txt"
        )
        return 1

    # Every mode, without exception. A warning is worthless here: the packaged build is
    # windowed, so nobody sees stderr, and `--no-browser --host 0.0.0.0` would otherwise
    # publish an unauthenticated card-reading API to the whole network.
    if not is_loopback(args.host):
        show_error(non_loopback_error_message(args.host))
        return 1

    existing = inspect_existing_server(args.host, args.port)
    if existing is ExistingServer.OTHER:
        show_error(
            f"ポート {args.port} は別のプログラムが使用しています。在留カードリーダーは開きません。\n"
            f"Port {args.port} is used by a different application. The residence-card reader was not opened."
        )
        return 1

    session: ServerSession
    if existing is ExistingServer.READER:
        session = ServerSession(owned=False)
    else:
        session = start_owned_server(args.host, args.port)
        if session is None:
            show_error(
                "ローカルサーバーを開始できませんでした。\n"
                "The local server did not become ready. Check that port " + str(args.port) + " is available."
            )
            return 1

    if mode == "server":
        print(f"Local server ready: {url}")
        wait_for_server(session)
        session.stop()
        return 0

    if mode == "browser":
        try:
            if not webbrowser.open(url):
                raise RuntimeError("default browser could not be opened")
            wait_for_server(session)
            return 0
        except Exception:
            show_error("ブラウザを開けませんでした。\nCould not open the default browser.")
            return 1
        finally:
            session.stop()

    if mode == "chrome-app":
        browser = discover_chromium_browser()
        if browser is None:
            show_error(chrome_app_error_message())
            session.stop()
            return 1
        browser_process = None
        try:
            browser_process = launch_chrome_app(browser, url, browser_profile_path())
            wait_for_chrome_app(browser_process)
            return 0
        except Exception:
            show_error(chrome_app_error_message())
            return 1
        finally:
            if browser_process is not None:
                try:
                    if browser_process.poll() is None:
                        browser_process.terminate()
                except Exception:
                    pass
            session.stop()

    try:
        open_native_window(url, session.stop)
        return 0
    except Exception:
        if args.webview:
            # A forced WebView2 request must fail clearly rather than changing modes.
            show_error(webview_error_message())
            return 1

        # Default desktop mode tries WebView2 first on supported desktop Windows.
        # If its renderer cannot initialize, use a local Chromium app window before
        # suggesting the regular browser fallback.
        browser = discover_chromium_browser()
        if browser is None:
            show_error(webview_error_message() + "\n\n" + chrome_app_error_message())
            return 1
        try:
            browser_process = launch_chrome_app(browser, url, browser_profile_path())
            wait_for_chrome_app(browser_process)
            return 0
        except Exception:
            show_error(chrome_app_error_message())
            return 1
    finally:
        session.stop()


if __name__ == "__main__":
    status = main()
    # Explicitly force-exit the process immediately after main finishes,
    # ensuring no background threads keep the console or executable hanging.
    os._exit(status)
