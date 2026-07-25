from __future__ import annotations

from types import SimpleNamespace

from reader.config import get_debug_trace_config, get_rc2_config, load_local_env
from reader.protocols.second_generation_card import read_second_generation_card


def test_rc2_config_defaults_are_safe(monkeypatch) -> None:
    load_local_env.cache_clear()
    monkeypatch.setenv("RC_LOAD_LOCAL_ENV", "false")
    for name in [
        "RC2_ENABLED",
        "RC2_READ_NAME_IMAGE",
        "RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME",
        "RC2_ENABLE_FULL_SIGNATURE_VALIDATION",
        "VERIFICATION_TRUST_PROFILE",
        "RC2_STORE_RAW_APDU",
        "RC2_STORE_RAW_TLV",
        "RC_READ_SCOPE",
    ]:
        monkeypatch.delenv(name, raising=False)

    config = get_rc2_config()

    assert config.enabled is True
    assert config.read_scope == "business"
    assert config.read_name_image is True
    assert config.allow_transient_face_read_for_name is False
    # On by default: staff need a signature status, and the face image the signed target
    # requires is only ever held transiently in memory for the verification itself.
    assert config.enable_full_signature_validation is True
    assert config.verification_trust_profile == "production"
    assert config.store_raw_apdu is False
    assert config.store_raw_tlv is False
    load_local_env.cache_clear()


def test_debug_trace_config_defaults_are_safe(monkeypatch) -> None:
    load_local_env.cache_clear()
    monkeypatch.setenv("RC_LOAD_LOCAL_ENV", "false")
    for name in [
        "DEBUG_TRACE_ENABLED",
        "DEBUG_TRACE_INCLUDE_APDU_HEADERS",
        "DEBUG_TRACE_INCLUDE_STATUS_WORDS",
        "DEBUG_TRACE_INCLUDE_RESPONSE_LENGTHS",
        "DEBUG_TRACE_INCLUDE_TLV_TAGS",
        "DEBUG_TRACE_INCLUDE_FIELD_PRESENCE",
        "DEBUG_TRACE_INCLUDE_SANITIZED_VALUES",
        "DEBUG_TRACE_INCLUDE_PERSONAL_VALUES",
        "DEBUG_TRACE_INCLUDE_RAW_APDU",
        "DEBUG_TRACE_INCLUDE_RAW_TLV",
        "DEBUG_TRACE_INCLUDE_IMAGE_BYTES",
        "DEBUG_TRACE_WRITE_TO_FILE",
        "DEBUG_TRACE_UNSAFE_LOCAL_MODE",
    ]:
        monkeypatch.delenv(name, raising=False)

    config = get_debug_trace_config()

    assert config.enabled is True
    assert config.include_apdu_headers is True
    assert config.include_status_words is True
    assert config.include_response_lengths is True
    assert config.include_tlv_tags is True
    assert config.include_field_presence is True
    assert config.include_sanitized_values is True
    assert config.write_to_file is False
    load_local_env.cache_clear()


def test_no_configuration_switch_can_enable_raw_or_personal_capture(monkeypatch) -> None:
    """Raw APDU/TLV, image bytes and personal values must not be reachable by any setting.

    These once existed as `DEBUG_TRACE_INCLUDE_RAW_APDU` and friends behind a
    `DEBUG_TRACE_UNSAFE_LOCAL_MODE` gate. "Do not store raw IC chip dumps" is a product
    rule, so the switch that could turn it off is gone rather than defaulted off. Setting
    every one of the old variables must now change nothing.
    """
    load_local_env.cache_clear()
    monkeypatch.setenv("RC_LOAD_LOCAL_ENV", "false")
    removed = [
        "DEBUG_TRACE_UNSAFE_LOCAL_MODE",
        "DEBUG_TRACE_INCLUDE_RAW_APDU",
        "DEBUG_TRACE_INCLUDE_RAW_TLV",
        "DEBUG_TRACE_INCLUDE_IMAGE_BYTES",
        "DEBUG_TRACE_INCLUDE_PERSONAL_VALUES",
    ]
    for name in removed:
        monkeypatch.setenv(name, "true")

    config = get_debug_trace_config()

    for field in ("include_raw_apdu", "include_raw_tlv", "include_image_bytes", "include_personal_values"):
        assert not hasattr(config, field), f"{field} must not exist on DebugTraceConfig"
    load_local_env.cache_clear()


def test_local_env_file_can_enable_rc2_name_ocr(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("RC_LOAD_LOCAL_ENV", raising=False)
    monkeypatch.delenv("RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME", raising=False)
    load_local_env.cache_clear()
    env_path = tmp_path / ".env"
    env_path.write_text("RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME=true\n", encoding="utf-8")

    load_local_env(env_path)
    config = get_rc2_config()

    assert config.allow_transient_face_read_for_name is True
    load_local_env.cache_clear()


def test_rc2_can_be_disabled_by_config(monkeypatch) -> None:
    monkeypatch.setenv("RC2_ENABLED", "false")

    result = read_second_generation_card(
        SimpleNamespace(transmit=lambda command: (_ for _ in ()).throw(AssertionError("no APDUs"))),
        SimpleNamespace(
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is False
    assert result["stage"] == "second_generation_disabled_by_config"


def test_official_test_profile_requires_its_explicit_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("RC_LOAD_LOCAL_ENV", "false")
    monkeypatch.setenv("VERIFICATION_TRUST_PROFILE", "official_test")
    assert get_rc2_config().verification_trust_profile == "official_test"

    monkeypatch.setenv("VERIFICATION_TRUST_PROFILE", "combined")
    assert get_rc2_config().verification_trust_profile == "production"
