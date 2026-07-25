from __future__ import annotations

from types import SimpleNamespace

import pytest

import reader.residence_card_reader as residence_card_reader_module
from reader.card_type import build_card_type_info
from reader.ocr import parse_front_ocr_text, repair_mojibake
from reader.parsing.code_maps import CARD_TYPE_LABELS
from reader.residence_card_reader import (
    ResidenceCardReadError,
    _blank_real_result,
    _decode_jis_x0213,
    _derive_access_keys,
    _derive_session_keys,
    _pad_80,
    _parse_first_tlv,
    _parse_fixed_tlv,
    _parse_tlvs,
    _retail_mac,
    _should_apply_front_ocr_field,
    _tdes_encrypt,
    decode_front_image_to_png,
    signature_metadata_for_card_type,
)

COMMON_DATA_TLV = [0xC0, 0x04, 0x30, 0x30, 0x30, 0x31]


class FakeCardConnection:
    """Minimal PC/SC connection stub that answers READ BINARY for the public
    common-data and card-type EFs and records every APDU it receives."""

    def __init__(self, card_type_tlv, common_tlv=None) -> None:
        self.card_type_tlv = list(card_type_tlv)
        self.common_tlv = list(common_tlv if common_tlv is not None else COMMON_DATA_TLV)
        self.commands: list[list[int]] = []

    def transmit(self, command):
        command = list(command)
        self.commands.append(command)
        ins, p1, p2, le = command[1], command[2], command[3], command[4]
        if ins == 0xB0:  # READ BINARY
            if p1 == residence_card_reader_module.CARD_TYPE_SFI_P1:
                tlv = self.card_type_tlv
            elif p1 == residence_card_reader_module.COMMON_DATA_SFI_P1:
                tlv = self.common_tlv
            else:
                return [], 0x6A, 0x82
            end = len(tlv) if le == 0 else p2 + le
            return list(tlv[p2:end]), 0x90, 0x00
        raise AssertionError(f"Unexpected APDU: {command}")

    def sent_mutual_auth(self) -> bool:
        return any(command[:2] == [0x00, 0x82] for command in self.commands)


def test_parse_common_data_tlv() -> None:
    value = _parse_fixed_tlv([0xC0, 0x04, 0x30, 0x30, 0x30, 0x31], 0xC0)

    assert value == b"0001"


def test_parse_card_type_label() -> None:
    assert CARD_TYPE_LABELS["1"] == "在留カード"


@pytest.mark.parametrize("card_type", ["1", "2"])
def test_first_generation_fallback_is_not_claimed_as_unsupported(card_type: str) -> None:
    assert signature_metadata_for_card_type(card_type) == {
        "signature_verified": None,
        "signature_verification_status": "verification_error",
        "signature_verification_note": "First-generation signature verification did not run.",
        "implementation_status": "implemented_unverified_on_real_hardware",
    }


def test_rc2_card_types_keep_their_own_signature_result_path() -> None:
    assert signature_metadata_for_card_type("05") == {}


def test_first_generation_business_fields_are_returned_when_signature_fails(monkeypatch) -> None:
    connection = object()
    card_info = build_card_type_info(COMMON_DATA_TLV, [0xC1, 0x01, 0x31])
    monkeypatch.setattr(residence_card_reader_module, "_connect", lambda reader_id: ("Sample Reader", connection))
    monkeypatch.setattr(residence_card_reader_module, "_read_card_type_info", lambda conn: card_info)
    monkeypatch.setattr(residence_card_reader_module, "start_access_control", lambda conn, number: object())
    monkeypatch.setattr(residence_card_reader_module, "read_back_side_fields", lambda *args, **kwargs: {"address": "Synthetic address", "_structure": []})
    monkeypatch.setattr(residence_card_reader_module, "read_front_image_bytes", lambda *args: b"synthetic-front")
    monkeypatch.setattr(residence_card_reader_module, "decode_front_image_to_png", lambda image: (b"png", {}))
    monkeypatch.setattr(
        residence_card_reader_module,
        "get_ocr_engine",
        lambda: SimpleNamespace(recognize_address=lambda png: SimpleNamespace(engine="onnxruntime_cpu", model="synthetic", confidence=1.0, text="")),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "verify_first_generation_card_signature",
        lambda *args, **kwargs: {"signature_verified": False, "signature_verification_status": "signature_mismatch"},
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is True
    assert result["data"]["address"] == "Synthetic address"
    assert result["data"]["signature_verification_status"] == "signature_mismatch"


def test_first_generation_front_ocr_populates_the_reviewed_name_candidate(monkeypatch) -> None:
    connection = object()
    card_info = build_card_type_info(COMMON_DATA_TLV, [0xC1, 0x01, 0x31])
    monkeypatch.setattr(residence_card_reader_module, "_connect", lambda reader_id: ("Sample Reader", connection))
    monkeypatch.setattr(residence_card_reader_module, "_read_card_type_info", lambda conn: card_info)
    monkeypatch.setattr(residence_card_reader_module, "start_access_control", lambda conn, number: object())
    monkeypatch.setattr(residence_card_reader_module, "read_back_side_fields", lambda *args, **kwargs: {"_structure": []})
    monkeypatch.setattr(residence_card_reader_module, "read_front_image_bytes", lambda *args: b"synthetic-front")
    monkeypatch.setattr(residence_card_reader_module, "decode_front_image_to_png", lambda image: (b"png", {}))
    monkeypatch.setattr(
        residence_card_reader_module,
        "recognize_front_card_text",
        lambda engine, image: SimpleNamespace(
            engine="ppocrv6", model="synthetic", confidence=0.99,
            text="NAME: YAMADA TARO\n2000-01-02 M", warnings=[],
        ),
    )
    monkeypatch.setattr(residence_card_reader_module, "get_ocr_engine", lambda: object())
    monkeypatch.setattr(residence_card_reader_module, "verify_first_generation_card_signature", lambda *args, **kwargs: {})

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is True
    assert result["data"]["name_ocr_candidate"] == "YAMADA TARO"
    assert result["data"]["name_ocr_status"] == "completed_local_onnx_ocr"



@pytest.mark.parametrize("card_type_tlv, expected_code", [([0xC1, 0x02, 0x30, 0x35], "05"), ([0xC1, 0x02, 0x30, 0x36], "06")])
def test_read_residence_card_dispatches_second_generation_before_access_control(monkeypatch, card_type_tlv, expected_code) -> None:
    connection = FakeCardConnection(card_type_tlv)
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )
    calls = []

    def fake_second_generation_card(dispatched_connection, card_info, card_number, trace=None):
        calls.append((dispatched_connection, card_info.card_type_code, card_number))
        return {
            "success": True,
            "stage": "second_generation_auth_verified",
            "data": card_info.to_dict(),
        }

    monkeypatch.setattr(
        residence_card_reader_module,
        "read_second_generation_card",
        fake_second_generation_card,
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is True
    assert result["stage"] == "second_generation_auth_verified"
    assert result["data"]["card_type_code"] == expected_code
    assert calls == [(connection, expected_code, "AB12345678CD")]
    assert not connection.sent_mutual_auth()


def test_read_residence_card_dispatches_specified_card_before_access_control(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x37])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is False
    assert result["stage"] == "specified_card_blocked_by_policy"
    assert result["data"]["card_type_code"] == "07"
    assert result["data"]["my_number_status"] == "not_accessed_by_policy"
    assert not connection.sent_mutual_auth()


def test_read_residence_card_blocks_specified_special_permanent_resident_card(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x38])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is False
    assert result["stage"] == "specified_card_blocked_by_policy"
    assert result["data"]["card_type_code"] == "08"
    assert result["data"]["scan_method"] == "blocked_by_policy"
    assert not connection.sent_mutual_auth()


def test_diagnostic_trace_proves_specified_card_policy_block(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x37])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD", diagnostic=True)

    assert result["success"] is False
    assert result["failure_classification"] == "specified_card_blocked_by_policy"
    trace_text = str(result["debug_trace"])
    assert "specified_card_blocked_by_policy" in trace_text
    assert "no My Number AID" in trace_text
    assert "JPKI AID" in trace_text
    assert "SET SESSION KEY" in trace_text
    assert "RSA delivery key" in trace_text
    assert not connection.sent_mutual_auth()


def test_read_residence_card_rejects_unknown_card_type_before_access_control(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x39, 0x39])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )

    result = residence_card_reader_module.read_residence_card(0, "AB12345678CD")

    assert result["success"] is False
    assert result["stage"] == "unsupported_card_type"
    assert result["data"]["card_type_code"] == "99"
    assert result["data"]["raw_ic_storage_status"] == "disabled_by_policy"
    assert not connection.sent_mutual_auth()


def test_read_short_tlv_file_reads_single_char_card_type() -> None:
    connection = FakeCardConnection([0xC1, 0x01, 0x31])

    raw = residence_card_reader_module.read_short_tlv_file(
        connection, residence_card_reader_module.CARD_TYPE_SFI_P1
    )

    assert raw == [0xC1, 0x01, 0x31]
    info = build_card_type_info(COMMON_DATA_TLV, raw)
    assert info.card_type_code == "1"
    assert info.generation == "current"


def test_read_short_tlv_file_reads_two_char_card_type_without_truncation() -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x35])

    raw = residence_card_reader_module.read_short_tlv_file(
        connection, residence_card_reader_module.CARD_TYPE_SFI_P1
    )

    # The helper must read the 2-byte header first, then the full object.
    assert connection.commands[0][4] == 0x02
    assert raw == [0xC1, 0x02, 0x30, 0x35]
    info = build_card_type_info(COMMON_DATA_TLV, raw)
    assert info.card_type_code == "05"
    assert info.generation == "second_generation"


def test_read_short_tlv_file_reads_specified_card_type() -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x37])

    raw = residence_card_reader_module.read_short_tlv_file(
        connection, residence_card_reader_module.CARD_TYPE_SFI_P1
    )

    info = build_card_type_info(COMMON_DATA_TLV, raw)
    assert info.card_type_code == "07"
    assert info.generation == "specified"


def test_front_image_ocr_blocks_second_generation_without_access_control(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x35])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )

    result = residence_card_reader_module.read_front_image_ocr(0, "AB12345678CD")

    assert result["success"] is False
    assert result["stage"] == "front_image_blocked_by_default_privacy_policy"
    assert result["data"]["card_type_code"] == "05"
    assert result["data"]["generation"] == "second_generation"
    assert result["data"]["scan_method"] == "blocked_by_default_privacy_policy"
    assert "image_data_url" not in result
    assert not connection.sent_mutual_auth()


def test_front_image_preview_is_blocked_without_reading_any_card_data(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x02, 0x30, 0x36])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )
    monkeypatch.setattr(
        residence_card_reader_module,
        "start_access_control",
        lambda connection, card_number: pytest.fail("access control must not run"),
    )

    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: pytest.fail("card connection must not run"),
    )

    result = residence_card_reader_module.read_front_image_preview(0, "AB12345678CD")

    assert result["success"] is False
    assert result["stage"] == "front_image_preview_blocked_by_privacy_policy"
    assert not connection.sent_mutual_auth()


def test_front_image_ocr_current_card_still_attempts_access_control(monkeypatch) -> None:
    connection = FakeCardConnection([0xC1, 0x01, 0x31])
    monkeypatch.setattr(
        residence_card_reader_module,
        "_connect",
        lambda reader_id: ("Sample Reader", connection),
    )

    calls: list[str] = []

    def fake_access_control(connection, card_number):
        calls.append(card_number)
        raise ResidenceCardReadError("SENTINEL current-card flow reached")

    monkeypatch.setattr(residence_card_reader_module, "start_access_control", fake_access_control)

    result = residence_card_reader_module.read_front_image_ocr(0, "AB12345678CD")

    assert calls == ["AB12345678CD"]
    assert result["success"] is False
    assert result["stage"] == "front_image_ocr_failed"
    assert "SENTINEL" in result["message"]


def test_parse_tlv_rejects_wrong_tag() -> None:
    with pytest.raises(ResidenceCardReadError):
        _parse_fixed_tlv([0xC2, 0x01, 0x31], 0xC1)


def test_parse_long_form_tlv() -> None:
    tlvs = _parse_tlvs(bytes([0xD4, 0x82, 0x01, 0x40]) + (b"\x00" * 320))

    assert tlvs[0xD4] == b"\x00" * 320


def test_parse_first_long_form_tlv() -> None:
    tag, value = _parse_first_tlv(bytes([0xD0, 0x82, 0x01, 0x40]) + (b"\xAA" * 320))

    assert tag == 0xD0
    assert value == b"\xAA" * 320


def test_decode_jis_x0213_strips_null_padding() -> None:
    assert _decode_jis_x0213("東京都".encode("shift_jisx0213") + b"\x00\x00") == "東京都"


def test_blank_real_result_does_not_fill_protected_fields() -> None:
    result = _blank_real_result("ab12345678cd")

    assert result["card_number"] == "AB12345678CD"
    assert result["name"] == ""
    assert result["address"] == ""
    assert result["scan_method"] == "real_partial"
    assert result["address_write_date"] == ""
    assert result["front_image_read_status"] == ""


def test_access_key_derivation_matches_spec_example() -> None:
    kenc, kmac = _derive_access_keys("AA12345678BB")

    assert kenc.hex().upper() == "6522B4E171195BB218223A976C040111"
    assert kmac == kenc


def test_mutual_auth_crypto_matches_spec_example() -> None:
    kenc, kmac = _derive_access_keys("AA12345678BB")
    rnd_ifd = bytes.fromhex("1122334455667788")
    rnd_icc = bytes.fromhex("5A6E7E385162B7A3")
    k_ifd = bytes.fromhex("404142434445464748494A4B4C4D4E4F")
    e_ifd = _tdes_encrypt(kenc, rnd_ifd + rnd_icc + k_ifd)
    m_ifd = _retail_mac(kmac, e_ifd)

    assert e_ifd.hex().upper() == (
        "937745C20883A1BAD1E04193722A1592378F81A8F1DC589157AEB0F7544FA1BA"
    )
    assert m_ifd.hex().upper() == "1AD7FB6A3389E017"


def test_session_key_derivation_matches_spec_example() -> None:
    k_ifd = bytes.fromhex("404142434445464748494A4B4C4D4E4F")
    k_icc = bytes.fromhex("19D049490FFF52EEDBFCB930BC810ED0")
    session = _derive_session_keys(k_ifd, k_icc)

    assert session.session_encryption_key.hex().upper() == "CE94938E19E3B97DF96EABCEDC1715CC"


def test_card_number_verify_encryption_matches_spec_example() -> None:
    session_key = bytes.fromhex("CE94938E19E3B97DF96EABCEDC1715CC")
    encrypted = _tdes_encrypt(session_key, _pad_80(b"AA12345678BB"))

    assert encrypted.hex().upper() == "1AA82973DB959A811F9711D728F0EEF6"


def test_decode_front_image_to_png_with_synthetic_tiff() -> None:
    from io import BytesIO

    from PIL import Image

    source = BytesIO()
    Image.new("1", (4, 4), 1).save(source, format="TIFF")

    png, metadata = decode_front_image_to_png(source.getvalue())

    assert png.startswith(b"\x89PNG")
    assert metadata["width"] == 4
    assert metadata["height"] == 4
    assert metadata["preview_format"] == "PNG"


def test_parse_front_ocr_text_extracts_candidate_fields() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000年01月02日 男 M. SAMPLELAND",
                "東京都新宿区西新宿2-8-1",
                "永住者",
                "就労制限なし",
                "2030年04月01日まで有効",
            ]
        )
    )

    assert parsed["name"] == "SAMPLE PERSON"
    assert parsed["birth_date"] == "2000-01-02"
    assert parsed["sex"] == "M"
    assert parsed["nationality"] == "SAMPLELAND"
    assert parsed["address"] == "東京都新宿区西新宿2-8-1"
    assert parsed["residence_status"] == "永住者"
    assert parsed["period_of_stay"] == "無期限"
    assert parsed["residence_expiry_date"] == "該当なし"
    assert parsed["card_expiry_date"] == "2030-04-01"


def test_parse_front_ocr_text_preserves_multiline_address() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000年01月02日 男 M. SAMPLELAND",
                "東京都新宿区サンプル通",
                "サンプルハイツ１０１号",
                "永住者",
                "就労制限なし",
                "2030年04月01日まで有効",
            ]
        )
    )

    assert parsed["address"] == "東京都新宿区サンプル通\nサンプルハイツ１０１号"
    assert parsed["residence_status"] == "永住者"


def test_parse_front_ocr_text_stitches_detached_building_name() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000年01月02日 男 M. SAMPLELAND",
                "東 京 都 新 宿 区 見 本 通 5 丁 目 5 番 地",
                "本 通 1 0 1 号",
                "永 住 者",
                "SAMPLELAND",
                "サ ン プ ル ハ イ ツ )",
                "就 労 制 限 な し",
            ]
        )
    )

    assert parsed["address"] == "東京都新宿区見本通5丁目5番地\nサンプルハイツ見本通101号"


def test_front_ocr_address_can_replace_shorter_chip_address() -> None:
    assert _should_apply_front_ocr_field(
        "address",
        "東京都新宿区見本通5丁目5番地\n本通101号",
        "東京都新宿区見本通5丁目5番地\nサンプルハイツ見本通101号",
    )


def test_parse_front_ocr_text_handles_spaced_japanese_ocr() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000 年 01 月 02 日 男 M.",
                "東 京 都 新 宿 区 西 新 宿 2 丁 目 8 番 地",
                "永 住 者",
                "就 労 制 限 な し",
            ]
        )
    )

    assert parsed["address"] == "東京都新宿区西新宿2丁目8番地"
    assert parsed["residence_status"] == "永住者"
    assert parsed["work_restriction"] == "就労制限なし"


def test_parse_front_ocr_text_handles_split_validity_date() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "SAMPLE PERSON",
                "2000年01月02日 男 M.",
                "VALIDITY OF THIS",
                "2 0 3 1 年 1 0 月 0",
                "2024年10月01日",
                "1 日 ま で 有 効",
            ]
        )
    )

    assert parsed["card_expiry_date"] == "2031-10-01"


def test_parse_front_ocr_text_handles_old_card_labeled_lines() -> None:
    parsed = parse_front_ocr_text(
        "\n".join(
            [
                "在留カード",
                "SAMPLE PERSON",
                "生年月日 1990年4月5日",
                "性別 女",
                "国籍・地域 SAMPLELAND",
                "住居地 東京都新宿区西新宿2丁目8番地",
                "在留資格 定住者",
                "就労制限なし",
                "2029年7月8日まで有効",
            ]
        )
    )

    assert parsed["birth_date"] == "1990-04-05"
    assert parsed["sex"] == "F"
    assert parsed["nationality"] == "SAMPLELAND"
    assert parsed["address"] == "東京都新宿区西新宿2丁目8番地"
    assert parsed["residence_status"] == "定住者"
    assert parsed["card_expiry_date"] == "2029-07-08"


def test_repair_mojibake_fixes_utf8_as_cp1252_text() -> None:
    mojibake = "永住者".encode().decode("latin1")

    assert repair_mojibake(mojibake) == "永住者"
