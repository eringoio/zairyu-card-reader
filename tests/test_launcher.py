from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import launch_reader
from app import health


def test_health_keeps_legacy_fields_and_identifies_this_application() -> None:
    payload = health()

    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["app"] == "zairyu-reader"
    assert launch_reader.is_reader_health(payload) is True


def test_existing_reader_server_is_reused_only_after_health_identity_check() -> None:
    result = launch_reader.inspect_existing_server(
        "127.0.0.1",
        8787,
        port_checker=lambda _host, _port: True,
        health_reader=lambda _url: {"success": True, "message": "ok", "app": "zairyu-reader"},
    )

    assert result is launch_reader.ExistingServer.READER


def test_unrelated_service_on_open_port_is_rejected() -> None:
    result = launch_reader.inspect_existing_server(
        "127.0.0.1",
        8787,
        port_checker=lambda _host, _port: True,
        health_reader=lambda _url: {"success": True, "message": "a different app"},
    )

    assert result is launch_reader.ExistingServer.OTHER


def test_health_wait_times_out_without_a_reader_identity() -> None:
    ticks = iter([0.0, 0.0, 0.5, 1.0, 1.0])

    assert not launch_reader.wait_for_reader_health(
        "127.0.0.1",
        8787,
        timeout=1.0,
        poll_interval=0,
        health_reader=lambda _url: None,
        clock=lambda: next(ticks),
        sleeper=lambda _seconds: None,
    )


def test_owned_session_stops_its_server_but_external_session_does_not() -> None:
    class Thread:
        def __init__(self) -> None:
            self.timeout = None

        def join(self, timeout: float) -> None:
            self.timeout = timeout

    owned_server = SimpleNamespace(should_exit=False)
    owned_thread = Thread()
    launch_reader.ServerSession(owned_server, owned_thread, owned=True).stop(timeout=0.1)

    external_server = SimpleNamespace(should_exit=False)
    launch_reader.ServerSession(external_server, Thread(), owned=False).stop()

    assert owned_server.should_exit is True
    assert owned_thread.timeout == 0.1
    assert external_server.should_exit is False


def test_mode_selection_keeps_browser_server_and_headless_compatibility() -> None:
    base = {"browser": False, "no_browser": False, "headless": False, "chrome_app": False, "webview": False}
    assert launch_reader.display_mode(argparse.Namespace(**base), server_2016=False) == "webview"
    assert launch_reader.display_mode(argparse.Namespace(**base), server_2016=True) == "chrome-app"
    assert launch_reader.display_mode(argparse.Namespace(**{**base, "browser": True})) == "browser"
    assert launch_reader.display_mode(argparse.Namespace(**{**base, "no_browser": True})) == "server"
    assert launch_reader.display_mode(argparse.Namespace(**{**base, "headless": True})) == "server"
    assert launch_reader.display_mode(argparse.Namespace(**{**base, "chrome_app": True})) == "chrome-app"
    assert launch_reader.display_mode(argparse.Namespace(**{**base, "webview": True})) == "webview"


def test_browser_mode_uses_the_default_browser_without_starting_a_second_server(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(launch_reader, "check_dependencies", list)
    monkeypatch.setattr(launch_reader, "inspect_existing_server", lambda *_args: launch_reader.ExistingServer.READER)
    monkeypatch.setattr(launch_reader.webbrowser, "open", lambda url: opened.append(url) or True)

    assert launch_reader.main(["--browser"]) == 0
    assert opened == ["http://127.0.0.1:8787"]


def test_forced_webview_failure_is_friendly_and_stops_an_owned_server(monkeypatch) -> None:
    errors: list[str] = []
    server = SimpleNamespace(should_exit=False)
    session = launch_reader.ServerSession(server=server, owned=True)
    monkeypatch.setattr(launch_reader, "check_dependencies", list)
    monkeypatch.setattr(launch_reader, "inspect_existing_server", lambda *_args: launch_reader.ExistingServer.NOT_RUNNING)
    monkeypatch.setattr(launch_reader, "start_owned_server", lambda *_args: session)
    monkeypatch.setattr(launch_reader, "open_native_window", lambda *_args: (_ for _ in ()).throw(RuntimeError("missing WebView2")))
    monkeypatch.setattr(launch_reader, "show_error", lambda message: errors.append(message))

    assert launch_reader.main(["--webview"]) == 1
    assert errors == [launch_reader.webview_error_message()]
    assert server.should_exit is True


def test_native_window_forces_edgechromium_without_a_javascript_bridge(monkeypatch) -> None:
    closed: list[object] = []

    class Signal:
        def __iadd__(self, callback):
            self.callback = callback
            return self

    window = SimpleNamespace(events=SimpleNamespace(closed=Signal()))
    fake_webview = SimpleNamespace(
        settings={},
        create_window=lambda *args, **kwargs: closed.append((args, kwargs)) or window,
        start=lambda **kwargs: closed.append(kwargs),
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    launch_reader.open_native_window("http://127.0.0.1:8787", lambda: None)

    assert closed[0][0] == ("在留カードリーダー", "http://127.0.0.1:8787")
    assert closed[0][1]["frameless"] is False
    assert closed[1] == {"gui": "edgechromium", "debug": False}
    assert fake_webview.settings == {
        "ALLOW_DOWNLOADS": False,
        "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
        "OPEN_DEVTOOLS_IN_DEBUG": False,
    }


def test_embedded_uvicorn_does_not_configure_a_console_formatter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Config:
        def __init__(self, app, **kwargs) -> None:
            captured["app"] = app
            captured["kwargs"] = kwargs

    fake_uvicorn = SimpleNamespace(Config=Config, Server=lambda config: config)
    fake_app = SimpleNamespace(app=object())
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "app", fake_app)

    launch_reader.create_uvicorn_server("127.0.0.1", 8787)

    assert captured["app"] is fake_app.app
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 8787,
        "log_level": "warning",
        "access_log": False,
        "log_config": None,
    }


def test_browser_discovery_prefers_chrome_then_edge_then_chromium(tmp_path) -> None:
    program_files = tmp_path / "Program Files"
    program_files_x86 = tmp_path / "Program Files (x86)"
    local_app_data = tmp_path / "LocalAppData"
    chrome = program_files / "Google" / "Chrome" / "Application" / "chrome.exe"
    edge = program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    chromium = local_app_data / "Chromium" / "Application" / "chrome.exe"
    for executable in (chrome, edge, chromium):
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.touch()

    browser = launch_reader.discover_chromium_browser(
        environ={
            "ProgramFiles": str(program_files),
            "ProgramFiles(x86)": str(program_files_x86),
            "LOCALAPPDATA": str(local_app_data),
        }
    )

    assert browser == launch_reader.ChromiumBrowser("Google Chrome", chrome)


def test_configured_browser_path_is_used_when_it_is_a_file(tmp_path) -> None:
    configured = tmp_path / "custom-browser.exe"
    configured.touch()

    browser = launch_reader.discover_chromium_browser(environ={"ZAIRYU_BROWSER_PATH": str(configured)})

    assert browser == launch_reader.ChromiumBrowser("Configured browser", configured)


def test_missing_configured_browser_is_not_accepted(tmp_path) -> None:
    browser = launch_reader.discover_chromium_browser(
        environ={"ZAIRYU_BROWSER_PATH": str(tmp_path / "missing.exe")}
    )

    assert browser is None


def test_configured_browser_must_be_an_executable_path(tmp_path) -> None:
    configured = tmp_path / "not-a-browser.txt"
    configured.touch()

    browser = launch_reader.discover_chromium_browser(environ={"ZAIRYU_BROWSER_PATH": str(configured)})

    assert browser is None


def test_chrome_app_arguments_use_local_profile_and_no_remote_debugging(tmp_path) -> None:
    browser = launch_reader.ChromiumBrowser("Google Chrome", tmp_path / "chrome.exe")
    profile = tmp_path / "BrowserProfile"

    arguments = launch_reader.chrome_app_arguments(browser, "http://127.0.0.1:8787", profile)

    assert arguments == [
        str(browser.path),
        "--app=http://127.0.0.1:8787",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
    ]
    assert not any("remote-debug" in argument for argument in arguments)


def test_profile_path_uses_local_appdata() -> None:
    assert launch_reader.browser_profile_path({"LOCALAPPDATA": r"C:\\Users\\staff\\AppData\\Local"}) == (
        Path(r"C:\\Users\\staff\\AppData\\Local") / "ZairyuReader" / "BrowserProfile"
    )


def test_windows_server_2016_detection() -> None:
    assert launch_reader.is_windows_server_2016(
        system="win32", win_version=lambda: ("10", "10.0.14393", "", "Server")
    )
    assert not launch_reader.is_windows_server_2016(
        system="win32", win_version=lambda: ("10", "10.0.19045", "", "")
    )
    assert not launch_reader.is_windows_server_2016(
        system="linux", win_version=lambda: ("2016", "10.0.14393", "", "Server")
    )


def test_chrome_app_launch_uses_mock_process_factory(tmp_path) -> None:
    executable = tmp_path / "chrome.exe"
    browser = launch_reader.ChromiumBrowser("Google Chrome", executable)
    received: list[list[str]] = []
    process = object()

    result = launch_reader.launch_chrome_app(
        browser,
        "http://127.0.0.1:8787",
        tmp_path / "profile",
        process_factory=lambda arguments: received.append(arguments) or process,
    )

    assert result is process
    assert received[0][0] == str(executable)
    assert (tmp_path / "profile").is_dir()


def test_owned_server_stops_after_the_exact_browser_process_exits(monkeypatch) -> None:
    class Process:
        def poll(self):
            return 0

    server = SimpleNamespace(should_exit=False)
    session = launch_reader.ServerSession(server=server, owned=True)
    browser = launch_reader.ChromiumBrowser("Google Chrome", Path("chrome.exe"))
    monkeypatch.setattr(launch_reader, "check_dependencies", list)
    monkeypatch.setattr(launch_reader, "inspect_existing_server", lambda *_args: launch_reader.ExistingServer.NOT_RUNNING)
    monkeypatch.setattr(launch_reader, "start_owned_server", lambda *_args: session)
    monkeypatch.setattr(launch_reader, "discover_chromium_browser", lambda: browser)
    monkeypatch.setattr(launch_reader, "launch_chrome_app", lambda *_args: Process())
    monkeypatch.setattr(launch_reader, "wait_for_chrome_app", lambda _process: None)

    assert launch_reader.main(["--chrome-app"]) == 0
    assert server.should_exit is True


def test_existing_server_is_not_stopped_after_chrome_app_exits(monkeypatch) -> None:
    browser = launch_reader.ChromiumBrowser("Google Chrome", Path("chrome.exe"))
    monkeypatch.setattr(launch_reader, "check_dependencies", list)
    monkeypatch.setattr(launch_reader, "inspect_existing_server", lambda *_args: launch_reader.ExistingServer.READER)
    monkeypatch.setattr(launch_reader, "discover_chromium_browser", lambda: browser)
    monkeypatch.setattr(launch_reader, "launch_chrome_app", lambda *_args: SimpleNamespace(poll=lambda: 0))
    monkeypatch.setattr(launch_reader, "wait_for_chrome_app", lambda _process: None)

    assert launch_reader.main(["--chrome-app"]) == 0


def test_default_webview_failure_falls_back_to_chrome_app(monkeypatch) -> None:
    browser = launch_reader.ChromiumBrowser("Google Chrome", Path("chrome.exe"))
    launched: list[launch_reader.ChromiumBrowser] = []
    monkeypatch.setattr(launch_reader, "check_dependencies", list)
    monkeypatch.setattr(launch_reader, "inspect_existing_server", lambda *_args: launch_reader.ExistingServer.READER)
    monkeypatch.setattr(
        launch_reader,
        "open_native_window",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("WebView2 unavailable")),
    )
    monkeypatch.setattr(launch_reader, "discover_chromium_browser", lambda: browser)
    monkeypatch.setattr(
        launch_reader,
        "launch_chrome_app",
        lambda selected, *_args: launched.append(selected) or SimpleNamespace(poll=lambda: 0),
    )
    monkeypatch.setattr(launch_reader, "wait_for_chrome_app", lambda _process: None)

    assert launch_reader.main([]) == 0
    assert launched == [browser]


def test_immediate_chrome_bootstrap_exit_gets_a_bounded_grace_period() -> None:
    sleeps: list[float] = []
    ticks = iter([0.0, 0.0, 0.0, 0.0, 16.0])

    launch_reader.wait_for_chrome_app(
        SimpleNamespace(poll=lambda: 0),
        bootstrap_grace=15.0,
        poll_interval=0.2,
        clock=lambda: next(ticks),
        sleeper=sleeps.append,
    )

    assert sleeps == [0.2]


# ------------------------------------------------------------- loopback enforcement


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_hosts_are_accepted(host: str) -> None:
    assert launch_reader.is_loopback(host) is True


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "::", "192.168.1.10", "10.0.0.5", "example.com", "", "127.0.0.2"],
)
def test_non_loopback_hosts_are_not_loopback(host: str) -> None:
    assert launch_reader.is_loopback(host) is False


@pytest.mark.parametrize(
    "argv",
    [
        ["--host", "0.0.0.0", "--no-browser"],
        ["--host", "0.0.0.0", "--headless"],
        ["--host", "0.0.0.0", "--browser"],
        ["--host", "0.0.0.0", "--chrome-app"],
        ["--host", "0.0.0.0", "--webview"],
        ["--host", "192.168.1.10"],
        ["--host", "::"],
    ],
)
def test_a_non_loopback_host_is_a_hard_failure_in_every_mode(monkeypatch, argv: list[str]) -> None:
    """A warning is not enough: the packaged build is windowed, so nobody reads stderr.

    `--no-browser --host 0.0.0.0` would otherwise publish an unauthenticated card-reading
    API to the whole network.
    """
    shown: list[str] = []
    monkeypatch.setattr(launch_reader, "show_error", lambda message, *args, **kwargs: shown.append(message))
    monkeypatch.setattr(launch_reader, "check_dependencies", list)

    def must_not_start(*args, **kwargs):
        raise AssertionError("no server may be started for a non-loopback host")

    monkeypatch.setattr(launch_reader, "inspect_existing_server", must_not_start)
    monkeypatch.setattr(launch_reader, "start_owned_server", must_not_start)

    assert launch_reader.main(argv) == 1
    assert shown and "127.0.0.1" in shown[0]


def test_the_loopback_default_needs_no_flag() -> None:
    arguments = launch_reader.build_parser().parse_args([])
    assert arguments.host == "127.0.0.1"
    assert launch_reader.is_loopback(arguments.host) is True
