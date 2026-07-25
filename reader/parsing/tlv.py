from __future__ import annotations

from dataclasses import dataclass


class TlvParseError(ValueError):
    pass


@dataclass(frozen=True)
class TlvObject:
    tag: bytes
    value: bytes

    @property
    def tag_hex(self) -> str:
        return self.tag.hex().upper()

    @property
    def tag_int(self) -> int:
        return int.from_bytes(self.tag, "big")


def _format_tag(tag: bytes | int) -> str:
    if isinstance(tag, bytes):
        return tag.hex().upper()
    return f"{tag:X}"


def _read_tag(data: bytes, index: int) -> tuple[bytes, int]:
    if index >= len(data):
        raise TlvParseError("Missing TLV tag.")

    first = data[index]
    index += 1
    if first & 0x1F == 0x1F:
        if index >= len(data):
            raise TlvParseError(f"Missing extended TLV tag byte after {first:02X}.")
        # The RC2 public spec defines tags as 1-2 bytes and includes DFD1.
        # Treat one additional byte as the complete high-tag-number form.
        return bytes([first, data[index]]), index + 1
    return bytes([first]), index


def _read_length(data: bytes, index: int, tag: bytes) -> tuple[int, int]:
    if index >= len(data):
        raise TlvParseError(f"Missing TLV length for tag {_format_tag(tag)}.")

    length_byte = data[index]
    index += 1
    if not length_byte & 0x80:
        return length_byte, index

    length_size = length_byte & 0x7F
    if length_size == 0 or length_size > 3 or index + length_size > len(data):
        raise TlvParseError(f"Invalid TLV length encoding for tag {_format_tag(tag)}.")
    return int.from_bytes(data[index : index + length_size], "big"), index + length_size


def parse_tlv_objects(data: bytes) -> list[TlvObject]:
    objects: list[TlvObject] = []
    index = 0
    while index < len(data):
        if data[index] == 0x00:
            if any(byte != 0x00 for byte in data[index:]):
                index += 1
                continue
            break

        tag, index = _read_tag(data, index)
        length, index = _read_length(data, index, tag)
        value = data[index : index + length]
        if len(value) != length:
            raise TlvParseError(f"Invalid TLV value length for tag {_format_tag(tag)}.")
        index += length
        objects.append(TlvObject(tag=tag, value=value))
    return objects


def parse_tlvs(data: bytes) -> dict[int, bytes]:
    return {tlv.tag_int: tlv.value for tlv in parse_tlv_objects(data)}


def parse_tlvs_by_hex(data: bytes) -> dict[str, bytes]:
    return {tlv.tag_hex: tlv.value for tlv in parse_tlv_objects(data)}


def parse_first_tlv(data: bytes) -> tuple[int, bytes]:
    objects = parse_tlv_objects(data)
    if not objects:
        raise TlvParseError("Short TLV response.")
    first = objects[0]
    return first.tag_int, first.value


def parse_fixed_tlv(data: list[int], expected_tag: int) -> bytes:
    if len(data) < 2:
        raise TlvParseError(f"Short TLV response for tag {expected_tag:02X}.")
    tag, value = parse_first_tlv(bytes(data))
    if tag != expected_tag:
        raise TlvParseError(f"Unexpected TLV tag. expected={expected_tag:02X} actual={tag:02X}")
    return value
