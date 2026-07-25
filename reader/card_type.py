from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reader.parsing.code_maps import CARD_TYPE_LABELS
from reader.parsing.tlv import parse_fixed_tlv
from reader.pcsc import RESIDENCE_CARD_STANDARD

READ_COMMON_DATA = [0x00, 0xB0, 0x8B, 0x00, 0x06]
READ_CARD_TYPE = [0x00, 0xB0, 0x8A, 0x00, 0x03]
COMMON_DATA_SFI_P1 = 0x8B
CARD_TYPE_SFI_P1 = 0x8A
CURRENT_CARD_TYPES = {"1", "2"}
SECOND_GENERATION_CARD_TYPES = {"05", "06"}
SPECIFIED_CARD_TYPES = {"07", "08"}


@dataclass(frozen=True)
class CardTypeInfo:
    chip_version: str
    card_type_code: str
    card_type_label: str
    generation: str
    required_standard: str = RESIDENCE_CARD_STANDARD

    def to_dict(self) -> dict[str, str]:
        return {
            "chip_version": self.chip_version,
            "card_type_code": self.card_type_code,
            "card_type_label": self.card_type_label,
            "generation": self.generation,
            "required_standard": self.required_standard,
        }


def decode_ascii(value: bytes) -> str:
    return value.decode("ascii", errors="replace").strip("\x00")


def classify_card_type(card_type_code: str) -> str:
    if card_type_code in CURRENT_CARD_TYPES:
        return "current"
    if card_type_code in SECOND_GENERATION_CARD_TYPES:
        return "second_generation"
    if card_type_code in SPECIFIED_CARD_TYPES:
        return "specified"
    return "unknown"


def build_card_type_info(common_raw: list[int], card_type_raw: list[int]) -> CardTypeInfo:
    version = decode_ascii(parse_fixed_tlv(common_raw, 0xC0))
    card_type_code = decode_ascii(parse_fixed_tlv(card_type_raw, 0xC1))
    return CardTypeInfo(
        chip_version=version,
        card_type_code=card_type_code,
        card_type_label=CARD_TYPE_LABELS.get(card_type_code, f"Unknown ({card_type_code})"),
        generation=classify_card_type(card_type_code),
    )


def _read_short_tlv(connection: Any, sfi_p1: int, label: str) -> list[int]:
    """Length-aware read of a short public TLV EF.

    Reads the 2-byte tag/length header first, then reads exactly the full TLV
    object so that both single-character card type codes (``C1 01 31``) and
    two-character codes (``C1 02 30 35``) are read without truncation.
    """
    header, sw1, sw2 = connection.transmit([0x00, 0xB0, sfi_p1, 0x00, 0x02])
    if (sw1, sw2) != (0x90, 0x00):
        raise RuntimeError(f"Failed to read {label} header: {sw1:02X} {sw2:02X}")
    header = list(header)
    if len(header) < 2:
        raise RuntimeError(f"Malformed {label} TLV header.")

    length_byte = header[1]
    if length_byte & 0x80:
        length_size = length_byte & 0x7F
        prefix, sw1, sw2 = connection.transmit([0x00, 0xB0, sfi_p1, 0x00, 2 + length_size])
        if (sw1, sw2) != (0x90, 0x00) or len(list(prefix)) < 2 + length_size:
            raise RuntimeError(f"Failed to read {label} long-form length: {sw1:02X} {sw2:02X}")
        prefix = list(prefix)
        total_length = 2 + length_size + int.from_bytes(bytes(prefix[2 : 2 + length_size]), "big")
    else:
        total_length = 2 + length_byte

    le = 0 if total_length == 256 else total_length
    full, sw1, sw2 = connection.transmit([0x00, 0xB0, sfi_p1, 0x00, le])
    if (sw1, sw2) != (0x90, 0x00):
        raise RuntimeError(f"Failed to read {label}: {sw1:02X} {sw2:02X}")
    full = list(full)
    if len(full) < total_length:
        raise RuntimeError(f"Truncated {label} TLV object.")
    return full[:total_length]


def detect_card_type(connection: Any) -> CardTypeInfo:
    common_raw = _read_short_tlv(connection, COMMON_DATA_SFI_P1, "common data")
    card_type_raw = _read_short_tlv(connection, CARD_TYPE_SFI_P1, "card type")
    return build_card_type_info(common_raw, card_type_raw)
