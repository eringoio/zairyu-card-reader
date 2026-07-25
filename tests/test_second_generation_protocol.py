from __future__ import annotations

from types import SimpleNamespace

import pytest

import reader.protocols.second_generation_card as second_generation
from reader.crypto import rc2
from reader.diagnostics import DiagnosticTrace
from reader.ocr.engine import OcrResult


def _disable_transient_image_read(monkeypatch) -> None:
    """
    Turn off both reasons DF1/EF03 would be read.

    Signature validation needs the face image, and name OCR needs the name image; they
    share one file, so a test that must not touch EF03 has to clear both switches.
    """
    monkeypatch.setenv("RC2_ENABLE_FULL_SIGNATURE_VALIDATION", "false")
    monkeypatch.setenv("RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME", "false")


class _AuthConnection:
    def __init__(self, verify_status=(0x90, 0x00), auth_status=(0x90, 0x00)) -> None:
        self.verify_status = verify_status
        self.auth_status = auth_status
        self.commands: list[list[int]] = []

    def transmit(self, command):
        command = list(command)
        self.commands.append(command)
        if command == second_generation.GET_CHALLENGE:
            return list(bytes.fromhex("92 1C E2 77 32 3D A0 57")), 0x90, 0x00
        if command[:5] == [0x00, 0x82, 0x00, 0x00, 0x28]:
            return [0x22] * 40, *self.auth_status
        if command[:8] == [0x08, 0x20, 0x00, 0x86, 0x13, 0x86, 0x11, 0x01]:
            return [], *self.verify_status
        raise AssertionError(f"Unexpected APDU: {command}")


def _patch_crypto(monkeypatch) -> None:
    monkeypatch.setattr(second_generation, "token_bytes", lambda length: bytes([length]) * length)
    monkeypatch.setattr(
        second_generation.rc2,
        "derive_base_keys",
        lambda card_number: SimpleNamespace(kenc=b"k" * 16, kmac=b"m" * 16),
    )
    monkeypatch.setattr(second_generation.rc2, "build_e_ifd", lambda kenc, rnd_ifd, rnd_icc, k_ifd: b"e" * 32)
    monkeypatch.setattr(second_generation.rc2, "build_m_ifd", lambda kmac, e_ifd: b"a" * 8)
    monkeypatch.setattr(second_generation.rc2, "verify_m_icc", lambda kmac, e_icc, m_icc: True)
    monkeypatch.setattr(
        second_generation.rc2,
        "decrypt_e_icc",
        lambda kenc, e_icc, rnd_icc, rnd_ifd, k_ifd: rc2.Rc2MutualAuthResult(
            rnd_icc=rnd_icc,
            rnd_ifd=rnd_ifd,
            k_icc=b"i" * 16,
            ksenc=b"s" * 16,
        ),
    )
    monkeypatch.setattr(second_generation.rc2, "encrypt_verify_payload", lambda ksenc, card_number: b"v" * 16)


def test_second_generation_auth_uses_rc2_apdu_sequence(monkeypatch) -> None:
    _patch_crypto(monkeypatch)
    connection = _AuthConnection()

    session = second_generation.authenticate_second_generation_card(connection, "AB12345678CD")

    assert session.ksenc == b"s" * 16
    assert connection.commands[0] == [0x00, 0x84, 0x00, 0x00, 0x08]
    assert connection.commands[1] == [0x00, 0x82, 0x00, 0x00, 0x28, *([ord("e")] * 32), *([ord("a")] * 8), 0x00]
    assert connection.commands[2] == [0x08, 0x20, 0x00, 0x86, 0x13, 0x86, 0x11, 0x01, *([ord("v")] * 16)]


def test_second_generation_auth_maps_mutual_auth_6300(monkeypatch) -> None:
    _patch_crypto(monkeypatch)
    connection = _AuthConnection(auth_status=(0x63, 0x00))

    result = second_generation.read_second_generation_card(
        connection,
        SimpleNamespace(
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is False
    assert result["stage"] == "second_generation_auth_failed"


def test_second_generation_auth_maps_verify_6300_as_wrong_number(monkeypatch) -> None:
    _patch_crypto(monkeypatch)
    connection = _AuthConnection(verify_status=(0x63, 0x00))

    result = second_generation.read_second_generation_card(
        connection,
        SimpleNamespace(
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is False
    assert result["stage"] == "second_generation_verify_failed_wrong_card_number"
    assert result["message"] == "The residence-card number did not match this card."


def test_plain_read_binary_command_shape() -> None:
    assert second_generation.build_plain_read_binary_command(0x82, length=0) == [
        0x00,
        0xB0,
        0x82,
        0x00,
        0x00,
        0x00,
        0x00,
    ]


def test_sm_read_binary_command_shape() -> None:
    assert second_generation.build_sm_read_binary_command(0x84, length=0) == [
        0x08,
        0xB0,
        0x84,
        0x00,
        0x00,
        0x00,
        0x04,
        0x96,
        0x02,
        0x00,
        0x00,
        0x00,
        0x00,
    ]


def test_second_generation_success_response_omits_raw_and_face_fields(monkeypatch) -> None:
    monkeypatch.delenv("RC2_ENABLED", raising=False)
    _disable_transient_image_read(monkeypatch)
    monkeypatch.setattr(
        second_generation,
        "authenticate_second_generation_card",
        lambda connection, card_number: second_generation.SecondGenerationSession(ksenc=b"s" * 16),
    )
    monkeypatch.setattr(second_generation, "read_default_business_files", lambda connection, session, card_type_code: {})
    monkeypatch.setattr(
        second_generation,
        "parse_rc2_business_fields",
        lambda card_type_code, files, **kwargs: {
            "birth_date": "2000-01-01",
            "signature_verified": None,
        },
    )

    result = second_generation.read_second_generation_card(
        SimpleNamespace(),
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is True
    assert result["stage"] == "second_generation_read_completed"
    assert result["data"]["read_at"]
    text = str(result)
    assert "face_image" not in text
    assert "raw_tlv" not in text
    assert "raw_apdu" not in text
    assert "certificate_bytes" not in text


def test_second_generation_full_signature_validation_reads_ef03_transiently(monkeypatch) -> None:
    """The signed target includes the face image, so DF1/EF03 must be read and then dropped."""
    monkeypatch.setenv("RC2_ENABLE_FULL_SIGNATURE_VALIDATION", "true")
    monkeypatch.setattr(
        second_generation,
        "authenticate_second_generation_card",
        lambda connection, card_number: second_generation.SecondGenerationSession(ksenc=b"s" * 16),
    )
    monkeypatch.setattr(second_generation, "read_default_business_files", lambda connection, session, card_type_code: {})
    monkeypatch.setattr(second_generation, "_read_address_ocr_fields", lambda *args: {})
    monkeypatch.setattr(second_generation, "_decode_mmr_tiff_to_png", lambda image: b"png")
    monkeypatch.setattr(second_generation, "read_name_image", lambda png, **kwargs: {"name_ocr_candidate": "SAMPLE NAME"})

    seen: dict[str, object] = {}

    def capture(card_type_code, files, **kwargs):
        seen.update(kwargs)
        return {"signature_verified": True, "signature_verification_status": "verified"}

    monkeypatch.setattr(second_generation, "parse_rc2_business_fields", capture)
    monkeypatch.setattr(
        second_generation,
        "read_rc2_file",
        lambda connection, session, name, spec, trace=None: bytes.fromhex("D0 02 01 02 D1 02 03 04"),
    )

    result = second_generation.read_second_generation_card(
        SimpleNamespace(),
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert seen["face_image"] == b"\x03\x04"
    assert seen["name_image"] == b"\x01\x02"
    assert seen["full_validation_enabled"] is True
    assert result["data"]["rc2_full_signature_validation_config"] == "enabled"
    assert result["data"]["name_ocr_candidate"] == "SAMPLE NAME"
    # Neither image may appear anywhere in the result the caller receives.
    text = str(result)
    assert "face_image" not in text
    assert "\\x03\\x04" not in text


def test_transient_image_wipe_zeroes_the_buffer() -> None:
    buffer = bytearray(b"face image bytes")

    second_generation.wipe(buffer)

    assert bytes(buffer) == bytes(len(buffer))


def test_rc2_policy_can_block_name_ef03_but_still_allows_address_ef04(monkeypatch) -> None:
    _disable_transient_image_read(monkeypatch)
    reads: list[str] = []
    monkeypatch.setattr(
        second_generation,
        "authenticate_second_generation_card",
        lambda connection, card_number: second_generation.SecondGenerationSession(ksenc=b"s" * 16),
    )
    monkeypatch.setattr(second_generation, "read_default_business_files", lambda connection, session, card_type_code: {})
    monkeypatch.setattr(second_generation, "parse_rc2_business_fields", lambda card_type_code, files, **kwargs: {})

    def fake_read_rc2_file(connection, session, name, spec, trace=None):
        reads.append(name)
        if name == "DF1/EF04":
            return bytes.fromhex("DF D1 00")
        raise AssertionError(f"Unexpected image file read: {name}")

    monkeypatch.setattr(second_generation, "read_rc2_file", fake_read_rc2_file)

    result = second_generation.read_second_generation_card(
        SimpleNamespace(),
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is True
    assert reads == ["DF1/EF04"]
    assert result["data"]["name_ocr_status"] == "blocked_by_privacy_policy"
    assert result["data"]["address_ocr_status"] == "failed"


def test_address_ocr_text_is_normalized_before_splitting(monkeypatch) -> None:
    monkeypatch.setattr(second_generation, "_decode_mmr_tiff_to_png", lambda image: b"png")
    monkeypatch.setattr(
        second_generation,
        "get_ocr_engine",
        lambda: SimpleNamespace(
            recognize_address=lambda png: OcrResult(
                text="東京都 新宿区\r\n西新宿 2-8-1\tサンプル",
                engine="onnxruntime_cpu",
                model="synthetic",
            )
        ),
    )
    monkeypatch.setattr(
        second_generation,
        "read_rc2_file",
        lambda connection, session, name, spec, trace=None: bytes.fromhex("DF D1 01 00"),
    )

    fields = second_generation._read_address_ocr_fields(
        SimpleNamespace(),
        second_generation.SecondGenerationSession(ksenc=b"s" * 16),
        "05",
        None,
    )

    assert fields["address_full"] == "東京都新宿区西新宿2-8-1サンプル"
    assert fields["address_prefecture"] == "東京都"
    assert fields["address_municipality"] == "新宿区"


def test_authorized_test_all_returns_safe_file_metadata(monkeypatch) -> None:
    monkeypatch.setenv("RC_READ_SCOPE", "authorized_test_all")
    _disable_transient_image_read(monkeypatch)
    monkeypatch.setattr(
        second_generation,
        "authenticate_second_generation_card",
        lambda connection, card_number: second_generation.SecondGenerationSession(ksenc=b"s" * 16),
    )
    monkeypatch.setattr(second_generation, "read_default_business_files", lambda connection, session, card_type_code: {})
    monkeypatch.setattr(second_generation, "parse_rc2_business_fields", lambda card_type_code, files, **kwargs: {})
    monkeypatch.setattr(second_generation, "_read_address_ocr_fields", lambda connection, session, card_type_code, trace: {})

    def fake_read_file(connection, session, name, spec, trace=None):
        if name == "DF1/EF03":
            return bytes.fromhex("D0 02 01 02 D1 02 03 04")
        return bytes.fromhex("C5 00")

    monkeypatch.setattr(second_generation, "read_rc2_file", fake_read_file)

    result = second_generation.read_second_generation_card(
        SimpleNamespace(),
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
    )

    assert result["success"] is True
    assert result["data"]["authorized_test_read_scope"] == "authorized_test_all"
    assert {item["file_name"] for item in result["data"]["authorized_test_files"]} == set(second_generation.RC2_FILE_MAP["05"])
    assert result["data"]["authorized_test_files"][2]["tlv_tags"] == [
        {"tag": "D0", "length": 2},
        {"tag": "D1", "length": 2},
    ]
    text = str(result)
    assert "01 02" not in text
    assert "face_image" not in text


def test_rc2_fake_card_success_exercises_sm_decrypt_and_plain_tlv(monkeypatch) -> None:
    _patch_crypto(monkeypatch)
    printed_tlv = bytes.fromhex(
        "C5 08 32 30 33 31 30 31 30 31"
        "C6 08 32 30 30 30 30 31 30 32"
        "C7 01 31"
        "C8 02 58 58"
    )
    df2_ef01 = bytes.fromhex("D5 01 31 D6 08 32 30 32 37 30 34 30 31 D7 01 30")
    df2_ef02 = bytes.fromhex("D8 01 30")
    df2_ef03 = bytes.fromhex("D9 01 31 DE 04 4E 4F 54 45")
    df3_ef01 = bytes.fromhex("DC 01 01 DD 01 01")
    encrypted_printed = b"encrypted-printed"

    monkeypatch.setattr(
        second_generation.rc2,
        "decrypt_sm_response_payload",
        lambda ksenc, payload: printed_tlv if payload == encrypted_printed else pytest.fail("unexpected encrypted payload"),
    )

    class FakeRc2Card:
        def __init__(self) -> None:
            self.selected_df = ""
            self.commands: list[list[int]] = []

        def transmit(self, command):
            command = list(command)
            self.commands.append(command)
            if command == second_generation.GET_CHALLENGE:
                return list(bytes.fromhex("92 1C E2 77 32 3D A0 57")), 0x90, 0x00
            if command[:5] == [0x00, 0x82, 0x00, 0x00, 0x28]:
                return [0x22] * 40, 0x90, 0x00
            if command[:8] == [0x08, 0x20, 0x00, 0x86, 0x13, 0x86, 0x11, 0x01]:
                return [], 0x90, 0x00
            if command[:4] == [0x00, 0xA4, 0x04, 0x0C]:
                aid = bytes(command[5 : 5 + command[4]])
                self.selected_df = {value: key for key, value in second_generation.DF_AIDS.items()}[aid]
                return [], 0x90, 0x00
            if command[:2] == [0x08, 0xB0]:
                return list(bytes([0x86, len(encrypted_printed) + 1, 0x01]) + encrypted_printed), 0x90, 0x00
            if command[:2] == [0x00, 0xB0]:
                key = (self.selected_df, command[2])
                payload = {
                    ("DF2", 0x81): df2_ef01,
                    ("DF2", 0x82): df2_ef02,
                    ("DF2", 0x83): df2_ef03,
                    ("DF3", 0x82): df3_ef01,
                }[key]
                return list(payload), 0x90, 0x00
            raise AssertionError(f"Unexpected APDU: {command}")

    trace = DiagnosticTrace(enabled=True)
    result = second_generation.read_second_generation_card(
        FakeRc2Card(),
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            generation="second_generation",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
        trace,
    )

    assert result["success"] is True
    assert result["stage"] == "second_generation_read_completed"
    assert result["data"]["nationality_label"] == "Unmapped nationality/region code: XX"
    stages = [step["stage"] for step in trace.to_safe_dict()["steps"]]
    assert "rc2_mutual_authenticate_completed" in stages
    assert "rc2_read_df1_ef02_printed_entries" in stages
    assert "rc2_parse_df2" in stages
    assert any(step.get("tlv_tags", [{}])[0].get("tag") == "86" for step in trace.to_safe_dict()["steps"] if step.get("tlv_tags"))


def test_rc2_trace_failure_redacts_payloads(monkeypatch) -> None:
    _patch_crypto(monkeypatch)
    connection = _AuthConnection(auth_status=(0x69, 0x88))
    trace = DiagnosticTrace(enabled=True)

    result = second_generation.read_second_generation_card(
        connection,
        SimpleNamespace(
            card_type_code="05",
            card_type_label="第2世代在留カード",
            generation="second_generation",
            to_dict=lambda: {"card_type_code": "05", "generation": "second_generation"},
        ),
        "AB12345678CD",
        trace,
    )

    assert result["success"] is False
    assert result["failure_classification"] == "rc2_auth_failed"
    trace_text = str(trace.to_safe_dict())
    assert "92 1C E2 77" not in trace_text
    assert "raw_apdu" not in trace_text
    assert "raw_tlv" not in trace_text
    assert "face_image" not in trace_text


def test_rc2_read_binary_retries_full_read_after_extended_length_failure() -> None:
    class FallbackCard:
        def __init__(self) -> None:
            self.commands: list[list[int]] = []

        def transmit(self, command):
            command = list(command)
            self.commands.append(command)
            if command[-2:] == [0x00, 0x49]:
                return [], 0x6C, 0x00
            return [0xC5, 0x00], 0x90, 0x00

    card = FallbackCard()
    trace = DiagnosticTrace(enabled=True)

    data = second_generation.read_binary_plain(card, 0x81, length=73, trace=trace, file_name="DF2/EF01")

    assert data == bytes([0xC5, 0x00])
    assert card.commands[0] == [0x00, 0xB0, 0x81, 0x00, 0x00, 0x00, 0x49]
    assert card.commands[1] == [0x00, 0xB0, 0x81, 0x00, 0x00, 0x00, 0x00]
    assert any(step["stage"].endswith("_full_read_fallback") for step in trace.to_safe_dict()["steps"])
