import json

from reader.local_config import LocalConfigStore


def test_legacy_config_migrates_without_remote_values(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"reader_id": 3, "server_url": "https://private", "device_token": "secret", "device_uuid": "uuid", "device_name": "PC"}), encoding="utf-8")
    config = LocalConfigStore(path).load()
    assert config.reader_id == 3
    assert "secret" not in path.read_text(encoding="utf-8")
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {"config_version", "reader_id", "app_version"}


def test_invalid_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"; path.write_text("not json", encoding="utf-8")
    assert LocalConfigStore(path).load().reader_id == 0


def test_no_card_data_can_be_persisted_to_local_settings(tmp_path):
    """Settings hold a reader index and a version. Never a scan, never a card field.

    A card result written to disk would outlive the page that produced it and defeat the
    "batch is cleared when the page closes" guarantee the UI gives staff.
    """
    path = tmp_path / "config.json"
    store = LocalConfigStore(path)
    config = store.load()

    # Attempt to smuggle card material through the config object before saving.
    for attribute, value in [
        ("card_number", "AB12345678AJ"),
        ("name", "SAMPLE NAME"),
        ("birth_date", "2000-01-01"),
        ("address", "東京都新宿区西新宿2-8-1"),
        ("front_ocr_text", "SAMPLE NAME"),
    ]:
        setattr(config, attribute, value)
    store.save(config)

    written = path.read_text(encoding="utf-8")
    assert set(json.loads(written)) == {"config_version", "reader_id", "app_version"}
    for leaked in ("AB12345678AJ", "SAMPLE NAME", "2000-01-01", "新宿"):
        assert leaked not in written, leaked


def test_the_safe_config_view_exposes_no_card_or_remote_fields(tmp_path):
    config = LocalConfigStore(tmp_path / "config.json").load()
    assert set(config.safe_dict()) <= {"config_version", "reader_id", "app_version"}
