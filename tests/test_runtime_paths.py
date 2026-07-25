from __future__ import annotations

from pathlib import Path

from reader import runtime_paths

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_source_checkout_resolves_resources_from_the_repo_root() -> None:
    assert runtime_paths.is_frozen() is False
    assert runtime_paths.resource_root() == REPO_ROOT
    assert runtime_paths.static_dir() == REPO_ROOT / "static"


def test_bundled_runtime_resources_exist_in_the_source_tree() -> None:
    assert runtime_paths.static_dir().joinpath("index.html").exists()
    assert runtime_paths.static_dir().joinpath("local.js").exists()
    assert runtime_paths.trust_anchor_manifest().exists()
    assert runtime_paths.countries_ja_path().exists()


def test_frozen_build_reads_resources_from_the_pyinstaller_bundle(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert runtime_paths.is_frozen() is True
    assert runtime_paths.resource_root() == tmp_path
    assert runtime_paths.static_dir() == tmp_path / "static"
    assert runtime_paths.trust_anchor_manifest() == tmp_path / "resources" / "moj" / "trust-anchors" / "manifest.json"


def test_nothing_writable_resolves_inside_a_frozen_bundle(monkeypatch, tmp_path) -> None:
    """A frozen bundle lives in a temp dir that is wiped on exit and may be read-only."""
    bundle = tmp_path / "bundle"
    appdata = tmp_path / "appdata"
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("APPDATA", str(appdata))

    writable_root = runtime_paths.user_data_root()

    assert writable_root == appdata / "ZairyuReader"
    assert bundle not in writable_root.parents


def test_user_data_root_follows_appdata_on_windows(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert runtime_paths.user_data_root() == tmp_path / "ZairyuReader"


def test_user_data_root_falls_back_to_home_without_appdata(monkeypatch) -> None:
    monkeypatch.delenv("APPDATA", raising=False)

    assert runtime_paths.user_data_root() == Path.home() / ".config" / "ZairyuReader"


def test_frozen_env_path_prefers_a_file_next_to_the_executable(monkeypatch, tmp_path) -> None:
    executable_dir = tmp_path / "app"
    executable_dir.mkdir()
    (executable_dir / ".env").write_text("RC2_ENABLED=true\n", encoding="utf-8")
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "executable", str(executable_dir / "zairyu-reader.exe"))

    assert runtime_paths.env_path() == executable_dir / ".env"


def test_frozen_env_path_falls_back_to_the_user_data_directory(monkeypatch, tmp_path) -> None:
    executable_dir = tmp_path / "app"
    executable_dir.mkdir()
    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "executable", str(executable_dir / "zairyu-reader.exe"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    assert runtime_paths.env_path() == tmp_path / "appdata" / "ZairyuReader" / ".env"
