from __future__ import annotations

from reader.parsing.tlv import parse_first_tlv, parse_tlv_objects, parse_tlvs, parse_tlvs_by_hex


def test_parse_one_byte_tag_short_length() -> None:
    parsed = parse_tlvs_by_hex(bytes.fromhex("C1 02 30 35"))

    assert parsed == {"C1": b"05"}


def test_parse_d0_two_byte_long_length() -> None:
    value = b"\xA0" * 2500
    parsed = parse_tlvs(bytes.fromhex("D0 82 09 C4") + value)

    assert parsed[0xD0] == value


def test_parse_d1_two_byte_long_length() -> None:
    value = b"\xA1" * 3000
    parsed = parse_tlvs_by_hex(bytes.fromhex("D1 82 0B B8") + value)

    assert parsed["D1"] == value


def test_parse_dfd1_as_single_two_byte_tag() -> None:
    value = b"\xA2" * 2500
    objects = parse_tlv_objects(bytes.fromhex("DF D1 82 09 C4") + value)

    assert len(objects) == 1
    assert objects[0].tag == bytes.fromhex("DF D1")
    assert objects[0].tag_hex == "DFD1"
    assert objects[0].tag_int == 0xDFD1
    assert objects[0].value == value


def test_parse_dc_one_byte_length() -> None:
    value = b"\xA3" * 96
    parsed = parse_tlvs_by_hex(bytes.fromhex("DC 60") + value)

    assert parsed["DC"] == value


def test_parse_dd_two_byte_long_length_with_padding() -> None:
    value = b"\xA4" * 598
    parsed = parse_tlvs_by_hex(bytes.fromhex("DD 82 02 56") + value + b"\x00" * 4)

    assert parsed["DD"] == value


def test_parse_first_tlv_preserves_two_byte_tag_as_int() -> None:
    tag, value = parse_first_tlv(bytes.fromhex("DF D1 81 80") + (b"\xA5" * 128))

    assert tag == 0xDFD1
    assert value == b"\xA5" * 128
