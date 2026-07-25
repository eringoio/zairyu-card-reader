from __future__ import annotations

from reader.card_type import (
    CARD_TYPE_SFI_P1,
    build_card_type_info,
    classify_card_type,
    detect_card_type,
)


class _FakeConnection:
    def __init__(self, card_type_tlv, common_tlv):
        self.card_type_tlv = list(card_type_tlv)
        self.common_tlv = list(common_tlv)

    def transmit(self, command):
        _, ins, p1, p2, le = command
        tlv = self.card_type_tlv if p1 == CARD_TYPE_SFI_P1 else self.common_tlv
        end = len(tlv) if le == 0 else p2 + le
        return list(tlv[p2:end]), 0x90, 0x00


def test_classify_known_card_types() -> None:
    assert classify_card_type("1") == "current"
    assert classify_card_type("05") == "second_generation"
    assert classify_card_type("07") == "specified"
    assert classify_card_type("99") == "unknown"


def test_build_card_type_info_from_public_tlvs() -> None:
    info = build_card_type_info(
        [0xC0, 0x04, 0x30, 0x30, 0x30, 0x31],
        [0xC1, 0x02, 0x30, 0x35],
    )

    assert info.chip_version == "0001"
    assert info.card_type_code == "05"
    assert info.card_type_label == "第2世代在留カード"
    assert info.generation == "second_generation"


def test_detect_card_type_reads_single_char_code() -> None:
    connection = _FakeConnection(
        card_type_tlv=[0xC1, 0x01, 0x31],
        common_tlv=[0xC0, 0x04, 0x30, 0x30, 0x30, 0x31],
    )

    info = detect_card_type(connection)

    assert info.card_type_code == "1"
    assert info.generation == "current"


def test_detect_card_type_reads_two_char_code_without_truncation() -> None:
    connection = _FakeConnection(
        card_type_tlv=[0xC1, 0x02, 0x30, 0x35],
        common_tlv=[0xC0, 0x04, 0x30, 0x30, 0x30, 0x31],
    )

    info = detect_card_type(connection)

    assert info.card_type_code == "05"
    assert info.generation == "second_generation"
