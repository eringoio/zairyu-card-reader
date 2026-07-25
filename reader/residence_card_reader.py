from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from io import BytesIO
from secrets import token_bytes
from typing import Any

from reader.card_type import CardTypeInfo, build_card_type_info
from reader.diagnostics import DiagnosticTrace
from reader.ocr import OcrError, get_ocr_engine, parse_front_ocr_text, recognize_front_card_text
from reader.ocr.address_ocr import build_address_ocr_result
from reader.ocr.engine import OcrResult
from reader.ocr.name_ocr import build_name_ocr_result
from reader.ocr.preprocessing import segment_front_card_text_lines
from reader.parsing.tlv import (
    TlvParseError,
    parse_first_tlv,
    parse_fixed_tlv,
    parse_tlvs,
)
from reader.pcsc import RESIDENCE_CARD_STANDARD
from reader.policy import POLICY_STATUS_FIELDS
from reader.protocols.second_generation_card import read_second_generation_card
from reader.protocols.specified_residence_card import read_specified_residence_card

# Legacy fixed-length reads kept for reference. The active read path now uses
# read_short_tlv_file() so it can handle both single-character card type codes
# (e.g. "C1 01 31") and two-character codes (e.g. "C1 02 30 35").
READ_COMMON_DATA = [0x00, 0xB0, 0x8B, 0x00, 0x06]
READ_CARD_TYPE = [0x00, 0xB0, 0x8A, 0x00, 0x03]
COMMON_DATA_SFI_P1 = 0x8B
CARD_TYPE_SFI_P1 = 0x8A
GET_CHALLENGE = [0x00, 0x84, 0x00, 0x00, 0x08]
DF2_AID = [
    0xD3,
    0x92,
    0xF0,
    0x00,
    0x4F,
    0x03,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
]
DF1_AID = [
    0xD3,
    0x92,
    0xF0,
    0x00,
    0x4F,
    0x02,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
]
DF3_AID = [
    0xD3,
    0x92,
    0xF0,
    0x00,
    0x4F,
    0x04,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
]
DF2_FILES = {
    "address": {"sfi": 0x81, "length": 342},
    "comprehensive_permission": {"sfi": 0x82, "length": 122},
    "individual_permission": {"sfi": 0x83, "length": 122},
    "update_status": {"sfi": 0x84, "length": 3},
}
FRONT_IMAGE_SFI = 0x85
FACE_IMAGE_SFI = 0x86
FIRST_GENERATION_SIGNATURE_SFI = 0x82
FIRST_GENERATION_SIGNATURE_FILE_LENGTH = 1464


class ResidenceCardReadError(Exception):
    pass


def signature_metadata_for_card_type(card_type_code: str) -> dict[str, object]:
    """Fallback only when a first-generation verification attempt could not start."""
    if card_type_code not in {"1", "2"}:
        return {}
    return {
        "signature_verified": None,
        "signature_verification_status": "verification_error",
        "signature_verification_note": "First-generation signature verification did not run.",
        "implementation_status": "implemented_unverified_on_real_hardware",
    }


@dataclass(frozen=True)
class AccessControlSession:
    session_encryption_key: bytes
    session_mac_key: bytes


def _hex(data: list[int] | bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _load_readers():
    try:
        from smartcard.System import readers
    except Exception as exc:
        raise ResidenceCardReadError(f"PC/SC unavailable: {exc}") from exc
    return readers


def _connect(reader_id: int):
    try:
        from smartcard.scard import SCARD_PROTOCOL_T1
    except Exception as exc:
        raise ResidenceCardReadError(f"PC/SC protocol constants unavailable: {exc}") from exc

    try:
        detected = _load_readers()()
    except Exception as exc:
        raise ResidenceCardReadError(f"Failed to list PC/SC readers: {exc}") from exc

    if reader_id >= len(detected):
        raise ResidenceCardReadError("Invalid reader ID.")

    try:
        connection = detected[reader_id].createConnection()
        connection.connect(protocol=SCARD_PROTOCOL_T1)
    except Exception as exc:
        raise ResidenceCardReadError(f"Failed to connect to residence card over T=1: {exc}") from exc

    return str(detected[reader_id]), connection


def _transmit(connection, command: list[int]) -> list[int]:
    data, sw1, sw2 = connection.transmit(command)
    if (sw1, sw2) != (0x90, 0x00):
        raise ResidenceCardReadError(
            f"APDU failed. command={_hex(command)} status={sw1:02X} {sw2:02X} response={_hex(data)}"
        )
    return list(data)


def _transmit_status_ok(connection, command: list[int]) -> list[int]:
    data, sw1, sw2 = connection.transmit(command)
    if (sw1, sw2) != (0x90, 0x00):
        raise ResidenceCardReadError(
            f"APDU failed. command={_hex(command)} status={sw1:02X} {sw2:02X} response={_hex(data)}"
        )
    return list(data)


def _read_binary_raw(connection, sfi_p1: int, offset: int, le: int) -> tuple[list[int], int, int]:
    data, sw1, sw2 = connection.transmit([0x00, 0xB0, sfi_p1, offset & 0xFF, le])
    return list(data), sw1, sw2


def read_short_tlv_file(connection, sfi_p1: int) -> list[int]:
    """
    Read a short public TLV EF by first reading the tag/length header,
    then reading exactly the full TLV object.
    Supports short-form and long-form BER length encoding.

    This replaces hardcoded fixed-length reads (e.g. Le=03) that truncated
    two-character card type codes such as "C1 02 30 35".
    """
    header, sw1, sw2 = _read_binary_raw(connection, sfi_p1, 0, 2)
    if (sw1, sw2) != (0x90, 0x00):
        raise ResidenceCardReadError(
            f"READ BINARY header failed. p1={sfi_p1:02X} status={sw1:02X} {sw2:02X}"
        )
    if len(header) < 2:
        raise ResidenceCardReadError(
            f"Malformed TLV header from EF p1={sfi_p1:02X}: {_hex(header)}"
        )

    length_byte = header[1]
    if length_byte & 0x80:
        length_size = length_byte & 0x7F
        if length_size == 0:
            raise ResidenceCardReadError(
                f"Indefinite-length TLV is not supported for EF p1={sfi_p1:02X}."
            )
        prefix, sw1, sw2 = _read_binary_raw(connection, sfi_p1, 0, 2 + length_size)
        if (sw1, sw2) != (0x90, 0x00):
            raise ResidenceCardReadError(
                f"READ BINARY long-form length failed. p1={sfi_p1:02X} status={sw1:02X} {sw2:02X}"
            )
        if len(prefix) < 2 + length_size:
            raise ResidenceCardReadError(
                f"Truncated long-form TLV length from EF p1={sfi_p1:02X}: {_hex(prefix)}"
            )
        value_length = int.from_bytes(bytes(prefix[2 : 2 + length_size]), "big")
        total_length = 2 + length_size + value_length
    else:
        total_length = 2 + length_byte

    if total_length <= 0 or total_length > 256:
        raise ResidenceCardReadError(
            f"Unreasonable TLV length {total_length} for EF p1={sfi_p1:02X}."
        )

    le = 0 if total_length == 256 else total_length
    full, sw1, sw2 = _read_binary_raw(connection, sfi_p1, 0, le)
    if (sw1, sw2) != (0x90, 0x00):
        raise ResidenceCardReadError(
            f"READ BINARY full object failed. p1={sfi_p1:02X} status={sw1:02X} {sw2:02X}"
        )
    if len(full) < total_length:
        raise ResidenceCardReadError(
            f"Truncated TLV object from EF p1={sfi_p1:02X}: expected {total_length}, got {len(full)}."
        )
    return full[:total_length]


def _tdes_key(key: bytes) -> bytes:
    if len(key) != 16:
        raise ResidenceCardReadError(f"3DES key must be 16 bytes, got {len(key)}.")
    return key + key[:8]


def _tdes_encrypt(key: bytes, data: bytes) -> bytes:
    from Crypto.Cipher import DES3

    return DES3.new(_tdes_key(key), DES3.MODE_CBC, iv=b"\x00" * 8).encrypt(data)


def _tdes_decrypt(key: bytes, data: bytes) -> bytes:
    from Crypto.Cipher import DES3

    return DES3.new(_tdes_key(key), DES3.MODE_CBC, iv=b"\x00" * 8).decrypt(data)


def _pad_80(data: bytes) -> bytes:
    padded = data + b"\x80"
    while len(padded) % 8:
        padded += b"\x00"
    return padded


def _unpad_80(data: bytes) -> bytes:
    index = len(data) - 1
    while index >= 0 and data[index] == 0x00:
        index -= 1
    if index < 0 or data[index] != 0x80:
        raise ResidenceCardReadError("Invalid ISO 7816 padding.")
    return data[:index]


def _retail_mac(key: bytes, data: bytes) -> bytes:
    from Crypto.Cipher import DES

    if len(key) != 16:
        raise ResidenceCardReadError(f"Retail MAC key must be 16 bytes, got {len(key)}.")
    padded = _pad_80(data)
    k1 = key[:8]
    k2 = key[8:]
    # Single-DES calls here implement the ISO 9797-1 Algorithm 3 "retail MAC" that the
    # first-generation residence-card specification requires for secure messaging; the
    # construction as a whole is two-key Triple DES, and the card accepts nothing else.
    # These primitives protect a session with a card the operator is physically holding,
    # keyed from the number printed on that card. They are never used for authenticity
    # verification, which is SHA-256 with RSA-2048 or ECDSA P-384.
    last_block = DES.new(k1, DES.MODE_CBC, iv=b"\x00" * 8).encrypt(padded)[-8:]  # noqa: S304
    return DES.new(k1, DES.MODE_ECB).encrypt(DES.new(k2, DES.MODE_ECB).decrypt(last_block))  # noqa: S304


def _derive_access_keys(card_number: str) -> tuple[bytes, bytes]:
    normalized = card_number.strip().upper().encode("ascii")
    if len(normalized) != 12:
        raise ResidenceCardReadError("Residence card number must be 12 ASCII characters.")
    # Specification-mandated access-key derivation; see the retail-MAC note above.
    key = sha1(normalized).digest()[:16]  # noqa: S324
    return key, key


def _derive_session_keys(k_ifd: bytes, k_icc: bytes) -> AccessControlSession:
    seed = bytes(left ^ right for left, right in zip(k_ifd, k_icc, strict=True))
    # Specification-mandated session-key derivation; see the retail-MAC note above.
    enc = sha1(seed + bytes.fromhex("00000001")).digest()[:16]  # noqa: S324
    mac = sha1(seed + bytes.fromhex("00000002")).digest()[:16]  # noqa: S324
    return AccessControlSession(session_encryption_key=enc, session_mac_key=mac)


def start_access_control(connection, card_number: str) -> AccessControlSession:
    kenc, kmac = _derive_access_keys(card_number)
    rnd_icc = bytes(_transmit_status_ok(connection, GET_CHALLENGE))
    if len(rnd_icc) != 8:
        raise ResidenceCardReadError(f"GET CHALLENGE returned {len(rnd_icc)} bytes, expected 8.")

    rnd_ifd = token_bytes(8)
    k_ifd = token_bytes(16)
    e_ifd = _tdes_encrypt(kenc, rnd_ifd + rnd_icc + k_ifd)
    m_ifd = _retail_mac(kmac, e_ifd)
    response = bytes(_transmit_status_ok(connection, [0x00, 0x82, 0x00, 0x00, 0x28, *e_ifd, *m_ifd, 0x00]))
    if len(response) != 40:
        raise ResidenceCardReadError(f"Mutual Authenticate returned {len(response)} bytes, expected 40.")

    e_icc = response[:32]
    m_icc = response[32:]
    expected_mac = _retail_mac(kmac, e_icc)
    if m_icc != expected_mac:
        raise ResidenceCardReadError("Card authentication MAC verification failed.")

    decrypted = _tdes_decrypt(kenc, e_icc)
    if decrypted[:8] != rnd_icc or decrypted[8:16] != rnd_ifd:
        raise ResidenceCardReadError("Card authentication random challenge verification failed.")

    session = _derive_session_keys(k_ifd, decrypted[16:])
    padded_number = _pad_80(card_number.strip().upper().encode("ascii"))
    encrypted_number = _tdes_encrypt(session.session_encryption_key, padded_number)
    _transmit_status_ok(connection, [0x08, 0x20, 0x00, 0x86, 0x13, 0x86, 0x11, 0x01, *encrypted_number])
    return session


def _parse_fixed_tlv(data: list[int], expected_tag: int) -> bytes:
    try:
        return parse_fixed_tlv(data, expected_tag)
    except TlvParseError as exc:
        raise ResidenceCardReadError(str(exc)) from exc


def _parse_tlvs(data: bytes) -> dict[int, bytes]:
    try:
        return parse_tlvs(data)
    except TlvParseError as exc:
        raise ResidenceCardReadError(str(exc)) from exc


def _parse_first_tlv(data: bytes) -> tuple[int, bytes]:
    try:
        return parse_first_tlv(data)
    except TlvParseError as exc:
        raise ResidenceCardReadError(str(exc)) from exc


def _describe_tlvs(tlvs: dict[int, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "tag": f"{tag:02X}",
            "length": len(value),
            "present": bool(value),
        }
        for tag, value in sorted(tlvs.items())
    ]


def _mark_decoded_text_presence(
    structure: list[dict[str, Any]],
    field_presence: dict[str, bool],
) -> None:
    tag_to_field = {
        "D2": "address_write_date",
        "D3": "municipality_code",
        "D4": "address",
        "D5": "comprehensive_permission",
        "D6": "individual_permission",
        "D7": "residence_update_status",
    }
    for file_info in structure:
        for tag in file_info.get("tags", []):
            field = tag_to_field.get(tag["tag"])
            if field is not None:
                tag["decoded_text_present"] = field_presence.get(field, False)


def _decode_jis_x0201_ascii(value: bytes) -> str:
    return value.decode("ascii", errors="replace").strip("\x00")


def _decode_jis_x0213(value: bytes) -> str:
    stripped = value.rstrip(b"\x00")
    for encoding in ("shift_jisx0213", "cp932"):
        try:
            return stripped.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return stripped.decode("shift_jisx0213", errors="replace").strip()


def _select_df(connection, aid: list[int]) -> None:
    _transmit_status_ok(connection, [0x00, 0xA4, 0x04, 0x0C, len(aid), *aid])


def _read_binary(connection, p1: int, p2: int, length: int) -> list[int]:
    le = 0 if length == 256 else length
    return _transmit_status_ok(connection, [0x00, 0xB0, p1, p2, le])


def _read_binary_sm_all(connection, session: AccessControlSession, sfi_p1: int) -> bytes:
    data, sw1, sw2 = connection.transmit(
        [0x08, 0xB0, sfi_p1, 0x00, 0x00, 0x00, 0x04, 0x96, 0x02, 0x00, 0x00, 0x00, 0x00]
    )
    if (sw1, sw2) != (0x90, 0x00):
        raise ResidenceCardReadError(
            f"SM READ BINARY failed. p1={sfi_p1:02X} status={sw1:02X} {sw2:02X} response={_hex(data)}"
        )
    tag, value = _parse_first_tlv(bytes(data))
    if tag != 0x86:
        raise ResidenceCardReadError(f"Unexpected SM response tag. expected=86 actual={tag:02X}")
    if not value or value[0] != 0x01:
        raise ResidenceCardReadError("Unexpected SM encrypted data object format.")
    decrypted = _tdes_decrypt(session.session_encryption_key, value[1:])
    return _unpad_80(decrypted)


def _read_plain_ef(connection, sfi_p1: int, total_length: int) -> bytes:
    chunks: list[int] = []
    offset = 0
    while offset < total_length:
        chunk_length = min(256, total_length - offset)
        if offset == 0:
            p1 = sfi_p1
            p2 = 0x00
        else:
            p1 = (offset >> 8) & 0x7F
            p2 = offset & 0xFF
        chunks.extend(_read_binary(connection, p1, p2, chunk_length))
        offset += chunk_length
    return bytes(chunks)


def read_front_image_bytes(connection, session: AccessControlSession) -> bytes:
    _select_df(connection, DF1_AID)
    decrypted = _read_binary_sm_all(connection, session, FRONT_IMAGE_SFI)
    tag, value = _parse_first_tlv(decrypted)
    if tag != 0xD0:
        raise ResidenceCardReadError(f"Unexpected front image tag. expected=D0 actual={tag:02X}")
    return value


def read_face_image_bytes(connection, session: AccessControlSession) -> bytearray:
    """Read the D1 value only for transient signature verification; never return it outward."""
    _select_df(connection, DF1_AID)
    decrypted = bytearray(_read_binary_sm_all(connection, session, FACE_IMAGE_SFI))
    try:
        tag, value = _parse_first_tlv(bytes(decrypted))
        if tag != 0xD1:
            raise ResidenceCardReadError(f"Unexpected face image tag. expected=D1 actual={tag:02X}")
        return bytearray(value)
    finally:
        for index in range(len(decrypted)):
            decrypted[index] = 0


def read_first_generation_signature_file(connection) -> bytearray:
    """Read DF3/EF01 after card-number authentication, keeping bytes internal."""
    _select_df(connection, DF3_AID)
    return bytearray(
        _read_plain_ef(connection, FIRST_GENERATION_SIGNATURE_SFI, FIRST_GENERATION_SIGNATURE_FILE_LENGTH)
    )


def _first_generation_signature_error(card_type_code: str) -> dict[str, object]:
    return {
        "card_generation": "first_generation",
        "card_type_code": card_type_code,
        "trust_profile": "production",
        "signature_verified": None,
        "signature_verification_status": "verification_error",
        "signature_verification_note": "signature.verification_error",
        "implementation_status": "implemented_unverified_on_real_hardware",
    }


def verify_first_generation_card_signature(
    connection,
    session: AccessControlSession,
    *,
    front_image_value: bytes,
    card_type_code: str,
) -> dict[str, object]:
    """Isolate cryptographic failure from the normal first-generation business read."""
    face_image: bytearray | None = None
    signature_file: bytearray | None = None
    front_for_verification: bytearray | None = None
    try:
        from reader.signature.first_generation import verify_first_generation_signature_file

        # Controlled mutable copies are overwritten after the crypto operation. CPython
        # cannot guarantee erasure of every immutable/interpreter copy; see security docs.
        front_for_verification = bytearray(front_image_value)
        face_image = read_face_image_bytes(connection, session)
        signature_file = read_first_generation_signature_file(connection)
        return verify_first_generation_signature_file(
            signature_file=signature_file,
            front_image_value=front_for_verification,
            face_image_value=face_image,
            card_type_code=card_type_code,
        )
    except Exception:
        # Authenticity is supplementary to the authorized business-field read.  Keep a
        # safe, honest status even for an unexpected crypto/parser/runtime failure.
        return _first_generation_signature_error(card_type_code)
    finally:
        # Do not let face/image/signature buffers escape the reader process.
        try:
            from reader.signature.first_generation import wipe

            wipe(front_for_verification)
            wipe(face_image)
            wipe(signature_file)
        except ModuleNotFoundError:
            pass


def read_front_image_info(connection, session: AccessControlSession) -> dict[str, Any]:
    value = read_front_image_bytes(connection, session)

    return {
        "file": "DF1/EF01 front-side card image",
        "tag": "D0",
        "length": len(value),
        "format_hint": "MMR-compressed TIFF per public specification",
        "read_status": "read_in_memory_not_saved",
    }


def decode_front_image_to_png(front_image: bytes) -> tuple[bytes, dict[str, Any]]:
    try:
        from PIL import Image
    except Exception as exc:
        raise ResidenceCardReadError(f"Pillow is unavailable for front image decoding: {exc}") from exc

    try:
        with Image.open(BytesIO(front_image)) as image:
            decoded = image.convert("RGB")
            output = BytesIO()
            decoded.save(output, format="PNG")
            return output.getvalue(), {
                "width": decoded.width,
                "height": decoded.height,
                "source_format": image.format or "unknown",
                "preview_format": "PNG",
            }
    except Exception as exc:
        raise ResidenceCardReadError(f"Failed to decode front image as TIFF/MMR: {exc}") from exc


def _front_image_generation_guard(card_info: CardTypeInfo) -> dict[str, Any] | None:
    """
    Return a clean not-implemented response when protected front-image reading
    is requested for a card generation whose secure-messaging protocol is not
    implemented yet. Returns None for the current generation so the existing
    access-control flow proceeds unchanged.

    This prevents applying the old/current-card mutual-authentication flow to a
    second-generation or specified card, which produces a confusing 63 00 APDU
    failure instead of a clear message.
    """
    if card_info.generation == "current":
        return None
    return {
        "success": False,
        "stage": "front_image_blocked_by_default_privacy_policy",
        "message": (
            "Front image reading is blocked by the default privacy policy for this card generation. "
            f"Detected card_type_code={card_info.card_type_code}, "
            f"generation={card_info.generation}. The old/current-card "
            "access-control protocol was not attempted."
        ),
        "data": {
            **card_info.to_dict(),
            "card_type": card_info.card_type_label,
            "scan_method": "blocked_by_default_privacy_policy",
        },
    }


def read_front_image_preview(reader_id: int, card_number: str) -> dict[str, Any]:
    return {
        "success": False,
        "stage": "front_image_preview_blocked_by_privacy_policy",
        "message": "Front-side image preview is blocked by the privacy policy. The image is processed only in memory for local OCR and is never returned.",
    }


def _safe_front_ocr_fields(parsed: dict[str, str]) -> dict[str, str]:
    """Prevent raw OCR text from escaping a front-image OCR operation."""
    return {key: value for key, value in parsed.items() if key != "front_ocr_text"}


def _old_card_name_ocr_fields(parsed: dict[str, str], *, engine: str, model: str, confidence: float | None) -> dict[str, Any]:
    """Map an old-card front-image name candidate into the staff-review contract."""
    result = build_name_ocr_result(str(parsed.get("name", "")))
    result["name_ocr_engine"] = engine
    result["name_ocr_model"] = model
    if confidence is not None:
        result["name_ocr_engine_confidence"] = str(confidence)
    result["name_ocr_source"] = "first_generation_front_image_ppocrv6"
    result["name_ocr_status"] = "completed_local_onnx_ocr"
    result.setdefault("name_ocr_note", "Name candidate was read from the protected old-card front image; verify before export.")
    return result


def _old_card_front_review_fields(parsed: dict[str, str], *, engine: str, model: str, confidence: float | None) -> dict[str, Any]:
    """Translate parsed old-card labels into the reviewed staff/copy-field contract."""
    address = str(parsed.get("address", ""))
    address_review = build_address_ocr_result(
        OcrResult(text=address, engine=engine, model=model, confidence=confidence)
    ) if address else {
        "address_full_candidate": "",
        "address_ocr_confidence": "",
        "address_ocr_confidence_category": "low",
        "address_ocr_review_required": True,
        "address_ocr_review_reasons": ["not_found"],
        "address_ocr_suggested_candidate": "",
    }
    fields: dict[str, Any] = {
        **_old_card_name_ocr_fields(parsed, engine=engine, model=model, confidence=confidence),
        **address_review,
        "birth_date": parsed.get("birth_date", ""),
        "sex_code": parsed.get("sex", ""),
        "nationality_label": parsed.get("nationality", ""),
        "residence_status_label": parsed.get("residence_status", ""),
        "period_of_stay_label": parsed.get("period_of_stay", ""),
        "residence_expiry_date": parsed.get("residence_expiry_date", ""),
        "card_expiry_date": parsed.get("card_expiry_date", ""),
        "address_full": address_review.get("address_full_candidate", address),
        "work_restriction_label": parsed.get("work_restriction", ""),
        "address_ocr_status": "completed_local_onnx_ocr" if address else "not_found_in_front_ocr",
    }
    return fields


def read_front_image_ocr(reader_id: int, card_number: str) -> dict[str, Any]:
    try:
        _, connection = _connect(reader_id)
        card_info = _read_card_type_info(connection)
        guard = _front_image_generation_guard(card_info)
        if guard is not None:
            return guard
        session = start_access_control(connection, card_number)
        front_image = read_front_image_bytes(connection, session)
        png, metadata = decode_front_image_to_png(front_image)
        ocr = recognize_front_card_text(get_ocr_engine(), png)
        if ocr.engine == "unavailable":
            return {
                "success": False,
                "stage": "front_image_ocr_model_unavailable",
                "message": (ocr.warnings or ["Local ONNX OCR is unavailable."])[0],
            }
        parsed = _safe_front_ocr_fields(parse_front_ocr_text(ocr.text))
        parsed.update(_old_card_front_review_fields(parsed, engine=ocr.engine, model=ocr.model, confidence=ocr.confidence))
    except (ResidenceCardReadError, OcrError) as exc:
        return {
            "success": False,
            "stage": "front_image_ocr_failed",
            "message": str(exc),
        }

    return {
        "success": True,
        "stage": "front_image_ocr",
        "message": "Front-side card image OCR completed locally. Review OCR candidates before export.",
        "data": parsed,
        "metadata": {
            **metadata,
            "source_length": len(front_image),
            "ocr_engine": ocr.engine,
            "ocr_model": ocr.model,
            "ocr_confidence": ocr.confidence,
        },
    }


def read_back_side_fields(connection, is_residence_card: bool = True) -> dict[str, str]:
    _select_df(connection, DF2_AID)
    fields: dict[str, str] = {}
    structure: list[dict[str, Any]] = []

    address_spec = DF2_FILES["address"]
    address_tlvs = _parse_tlvs(
        _read_plain_ef(connection, address_spec["sfi"], address_spec["length"])
    )
    structure.append(
        {
            "file": "DF2/EF01 address",
            "sfi": f"{address_spec['sfi']:02X}",
            "expected_length": address_spec["length"],
            "tags": _describe_tlvs(address_tlvs),
        }
    )
    fields["address_write_date"] = _decode_jis_x0201_ascii(address_tlvs.get(0xD2, b""))
    fields["municipality_code"] = _decode_jis_x0201_ascii(address_tlvs.get(0xD3, b""))
    fields["address"] = _decode_jis_x0213(address_tlvs.get(0xD4, b""))
    field_presence = {
        "address_write_date": bool(fields["address_write_date"]),
        "municipality_code": bool(fields["municipality_code"]),
        "address": bool(fields["address"]),
    }

    if is_residence_card:
        comprehensive_spec = DF2_FILES["comprehensive_permission"]
        individual_spec = DF2_FILES["individual_permission"]
        update_spec = DF2_FILES["update_status"]
        comprehensive_tlvs = _parse_tlvs(
            _read_plain_ef(connection, comprehensive_spec["sfi"], comprehensive_spec["length"])
        )
        individual_tlvs = _parse_tlvs(
            _read_plain_ef(connection, individual_spec["sfi"], individual_spec["length"])
        )
        update_tlvs = _parse_tlvs(_read_plain_ef(connection, update_spec["sfi"], update_spec["length"]))
        structure.extend(
            [
                {
                    "file": "DF2/EF02 comprehensive permission",
                    "sfi": f"{comprehensive_spec['sfi']:02X}",
                    "expected_length": comprehensive_spec["length"],
                    "tags": _describe_tlvs(comprehensive_tlvs),
                },
                {
                    "file": "DF2/EF03 individual permission",
                    "sfi": f"{individual_spec['sfi']:02X}",
                    "expected_length": individual_spec["length"],
                    "tags": _describe_tlvs(individual_tlvs),
                },
                {
                    "file": "DF2/EF04 update status",
                    "sfi": f"{update_spec['sfi']:02X}",
                    "expected_length": update_spec["length"],
                    "tags": _describe_tlvs(update_tlvs),
                },
            ]
        )

        comprehensive = _decode_jis_x0213(comprehensive_tlvs.get(0xD5, b""))
        individual = _decode_jis_x0213(individual_tlvs.get(0xD6, b""))
        field_presence["comprehensive_permission"] = bool(comprehensive)
        field_presence["individual_permission"] = bool(individual)
        fields["part_time_permission"] = " / ".join(
            value for value in [comprehensive, individual] if value
        )
        update_status = _decode_jis_x0201_ascii(update_tlvs.get(0xD7, b""))
        field_presence["residence_update_status"] = bool(update_status)
        fields["residence_update_status"] = {
            "0": "無し",
            "1": "申請中",
        }.get(update_status, update_status)

    _mark_decoded_text_presence(structure, field_presence)
    fields["_structure"] = structure
    return fields


def _blank_real_result(card_number: str) -> dict[str, str]:
    result = {
        "read_at": datetime.now().replace(microsecond=0).isoformat(),
        "card_number": card_number.strip().upper(),
        "name": "",
        "birth_date": "",
        "sex": "",
        "nationality": "",
        "address": "",
        "residence_status": "",
        "period_of_stay": "",
        "residence_expiry_date": "",
        "card_expiry_date": "",
        "work_restriction": "",
        "part_time_permission": "",
        "scan_method": "real_partial",
        "address_write_date": "",
        "municipality_code": "",
        "residence_update_status": "",
        "front_side_extraction": "",
        "front_image_status": "",
        "face_photo_status": "",
        "local_diagnostic_summary": "",
        "front_image_read_status": "",
        "front_image_length": "",
        "front_image_format_hint": "",
        "front_ocr_status": "",
        "front_ocr_language": "",
        "front_ocr_text": "",
        "front_ocr_parse_note": "",
    }
    result.update(POLICY_STATUS_FIELDS)
    return result


def _field_text_score(value: str) -> int:
    return len(
        [
            character
            for character in value
            if character.isalnum() or "\u3040" <= character <= "\u9fff"
        ]
    )


def _should_apply_front_ocr_field(field: str, existing: str, candidate: str) -> bool:
    if field == "front_ocr_text":
        return True
    if not existing:
        return True
    if field == "address":
        return _field_text_score(candidate) > _field_text_score(existing)
    return False


def _build_local_diagnostic_summary(data: dict[str, str]) -> str:
    lines = [
        "Local readable chip summary",
        "Do not paste real personal data into chats or tickets. Redact first.",
        "",
        f"scan_method: {data.get('scan_method', '')}",
        f"chip_version: {data.get('chip_version', '')}",
        f"card_type: {data.get('card_type', '')}",
        f"residence_update_status: {data.get('residence_update_status', '')}",
        "",
        "Structured text read from chip:",
    ]
    structured_fields = [
        "address_write_date",
        "municipality_code",
        "address",
        "part_time_permission",
    ]
    for field in structured_fields:
        value = data.get(field, "")
        lines.append(f"- {field}: {value if value else '<empty/not present>'}")

    lines.extend(
        [
            "",
            "Front-side printed fields:",
            "- name/birth_date/sex/nationality/status/expiry/work_restriction: image-based on this card generation",
            f"- front_side_extraction: {data.get('front_side_extraction', '')}",
            f"- front_image_status: {data.get('front_image_status', '')}",
            f"- front_ocr_status: {data.get('front_ocr_status', '')}",
            f"- face_photo_status: {data.get('face_photo_status', '')}",
            "",
            f"read_note: {data.get('read_note', '')}",
        ]
    )
    return "\n".join(lines)


def _build_structure_summary(structure: list[dict[str, Any]]) -> str:
    lines = [
        "Local file/tag structure summary",
        "This lists file names, tags, lengths, and presence only. It omits raw bytes and personal values.",
        "",
        "Public files:",
        "- MF/EF01 common data: tag C0, chip version",
        "- MF/EF02 card type: tag C1, card type",
        "",
        "Authenticated structured files:",
    ]
    for file_info in structure:
        lines.append(
            f"- {file_info['file']} (SFI {file_info['sfi']}, expected {file_info['expected_length']} bytes)"
        )
        tags = file_info.get("tags", [])
        if not tags:
            lines.append("  - no TLV tags parsed")
        for tag in tags:
            status = "present" if tag["present"] else "empty"
            decoded_status = tag.get("decoded_text_present")
            if decoded_status is True:
                status += ", decoded text non-empty"
            elif decoded_status is False:
                status += ", decoded text blank after trimming padding"
            lines.append(f"  - tag {tag['tag']}: length {tag['length']} ({status})")
    lines.extend(
        [
            "",
            "Image-based protected files not read in this prototype:",
            "- DF1/EF01 front-side card image: requires secure-messaging image read and OCR",
            "- DF1/EF02 face photo: requires secure-messaging image read; not stored/read by policy",
        ]
    )
    return "\n".join(lines)


def read_public_residence_card_files(reader_id: int) -> dict[str, Any]:
    reader_name, connection = _connect(reader_id)
    card_info = _read_card_type_info(connection)

    return {
        "reader": reader_name,
        "chip_version": card_info.chip_version,
        "card_type_code": card_info.card_type_code,
        "card_type": card_info.card_type_label,
        "card_type_label": card_info.card_type_label,
        "card_generation": card_info.generation,
        "required_standard": RESIDENCE_CARD_STANDARD,
        "apdu_reads": ["MF/EF01 common data", "MF/EF02 card type"],
    }


def _read_card_type_info(connection) -> CardTypeInfo:
    common_raw = read_short_tlv_file(connection, COMMON_DATA_SFI_P1)
    card_type_raw = read_short_tlv_file(connection, CARD_TYPE_SFI_P1)
    try:
        return build_card_type_info(common_raw, card_type_raw)
    except TlvParseError as exc:
        raise ResidenceCardReadError(str(exc)) from exc


def _public_files_from_card_info(reader_name: str, card_info: CardTypeInfo) -> dict[str, str | list[str]]:
    return {
        "reader": reader_name,
        "chip_version": card_info.chip_version,
        "card_type_code": card_info.card_type_code,
        "card_type": card_info.card_type_label,
        "card_type_label": card_info.card_type_label,
        "card_generation": card_info.generation,
        "required_standard": RESIDENCE_CARD_STANDARD,
        "apdu_reads": ["MF/EF01 common data", "MF/EF02 card type"],
    }


def _unsupported_card_type(card_info: CardTypeInfo) -> dict[str, Any]:
    return {
        "success": False,
        "stage": "unsupported_card_type",
        "message": (
            "Unsupported residence-card type. Only current residence-card generation reading "
            "is enabled in this prototype."
        ),
        "data": {
            **card_info.to_dict(),
            **POLICY_STATUS_FIELDS,
            "card_type": card_info.card_type_label,
            "scan_method": "not_supported",
        },
    }


def read_residence_card(reader_id: int, card_number: str, diagnostic: bool = False) -> dict[str, Any]:
    trace = DiagnosticTrace(enabled=True) if diagnostic else None
    try:
        reader_name, connection = _connect(reader_id)
        if trace is not None:
            trace.reader_name = reader_name
            trace.add_step("pcsc_reader_listed", "reader selected", reader_name, success=True)
            trace.add_step("pcsc_card_connected", "connect", success=True)
        card_info = _read_card_type_info(connection)
        if trace is not None:
            trace.card_generation = card_info.generation
            trace.card_type_code = card_info.card_type_code
            trace.add_step("public_common_data_read", "READ BINARY", success=True)
            trace.add_step("public_card_type_read", "READ BINARY", success=True)
            trace.add_step(f"card_type_classified_{card_info.generation}", "classify", success=True)
        if card_info.generation == "second_generation":
            result = read_second_generation_card(connection, card_info, card_number, trace)
            if trace is not None:
                trace.add_step("rc2_privacy_policy_image_decision", "policy", "face/image files blocked by default privacy policy", success=True)
                if result.get("success"):
                    trace.add_step("rc2_read_completed", "complete", success=True)
                result["debug_trace"] = trace.to_safe_dict()
                trace_path = trace.write_file_if_enabled(result)
                if trace_path:
                    result["debug_trace_file"] = trace_path
            return result
        if card_info.generation == "specified":
            result = read_specified_residence_card(card_info)
            if trace is not None:
                trace.add_step("specified_card_blocked_by_policy", "policy", "no My Number AID, JPKI AID, SET SESSION KEY, or RSA delivery key attempted", success=True)
                result["failure_classification"] = "specified_card_blocked_by_policy"
                result["debug_trace"] = trace.to_safe_dict()
                trace_path = trace.write_file_if_enabled(result)
                if trace_path:
                    result["debug_trace_file"] = trace_path
            return result
        if card_info.generation == "unknown":
            result = _unsupported_card_type(card_info)
            result["failure_classification"] = "unsupported_card_type"
            if trace is not None:
                result["debug_trace"] = trace.to_safe_dict()
            return result

        public_files = _public_files_from_card_info(reader_name, card_info)
        if trace is not None:
            trace.add_step("current_get_challenge_started", "GET CHALLENGE")
        session = start_access_control(connection, card_number)
        if trace is not None:
            trace.add_step("current_verify_completed", "VERIFY", success=True)
        back_side_fields = read_back_side_fields(
            connection,
            is_residence_card=card_info.card_type_code == "1",
        )
        file_structure = back_side_fields.pop("_structure", [])
        front_image = read_front_image_bytes(connection, session)
        front_image_info = {
            "file": "DF1/EF01 front-side card image",
            "tag": "D0",
            "length": len(front_image),
            "format_hint": "MMR-compressed TIFF per public specification",
            "read_status": "read_in_memory_not_saved",
        }
        front_png, front_png_metadata = decode_front_image_to_png(front_image)
        front_ocr_row_count = len(segment_front_card_text_lines(front_png))
        front_ocr = recognize_front_card_text(get_ocr_engine(), front_png)
        if front_ocr.engine != "unavailable":
            front_ocr_fields = _safe_front_ocr_fields(parse_front_ocr_text(front_ocr.text))
            front_ocr_fields.update(
                _old_card_front_review_fields(
                    front_ocr_fields,
                    engine=front_ocr.engine,
                    model=front_ocr.model,
                    confidence=front_ocr.confidence,
                )
            )
            front_ocr_status = "completed_local_onnx_ocr"
            front_ocr_message = "Front-side image OCR completed locally; verify candidates before export."
        else:
            front_ocr_fields = {}
            front_ocr_status = (
                "failed_runtime_unavailable"
                if "runtime" in " ".join(front_ocr.warnings).lower()
                else "failed_model_unavailable"
            )
            front_ocr_message = (front_ocr.warnings or ["Local ONNX OCR is unavailable."])[0]
        # The first-generation official signature covers the front-image D0 value and
        # face-image D1 value.  This intentionally happens after business/OCR extraction
        # and is isolated below so a failed authenticity check never fails the read.
        signature_metadata = verify_first_generation_card_signature(
            connection,
            session,
            front_image_value=front_image,
            card_type_code=card_info.card_type_code,
        )
    except ResidenceCardReadError as exc:
        result = {
            "success": False,
            "stage": "access_control_failed",
            "message": str(exc),
            "failure_classification": "current_auth_failed",
        }
        if trace is not None:
            trace.failure_classification = "current_auth_failed"
            trace.add_step("read_failed", "exception", exc.__class__.__name__, success=False)
            result["debug_trace"] = trace.to_safe_dict()
        return result

    data = _blank_real_result(card_number)
    data.update(back_side_fields)
    for field, value in front_ocr_fields.items():
        if _should_apply_front_ocr_field(field, data.get(field, ""), value):
            data[field] = value
    data.update(
        {
            "chip_version": public_files["chip_version"],
            "card_type_code": public_files["card_type_code"],
            "card_type": public_files["card_type"],
            "card_type_label": public_files["card_type"],
            "read_note": (
                "Residence-card-number access control succeeded. Back-side structured text fields "
                "were read when present. Front-side name, status, expiry, and similar printed fields "
                "were read from the protected card-face image using local ONNX OCR when available. "
                "Review OCR candidates before export."
            ),
            "front_side_extraction": "local_ocr_candidate" if front_ocr_fields else "ocr_unavailable",
            "front_image_status": "read_in_memory_not_saved",
            "front_image_read_status": front_image_info["read_status"],
            "front_image_length": str(front_image_info["length"]),
            "front_image_format_hint": front_image_info["format_hint"],
            "front_ocr_status": front_ocr_status,
            "front_ocr_engine": front_ocr.engine,
            "front_ocr_model": front_ocr.model,
            "front_ocr_confidence": str(front_ocr.confidence or ""),
            "front_ocr_row_count": str(front_ocr_row_count),
            "front_image_width": str(front_png_metadata.get("width", "")),
            "front_image_height": str(front_png_metadata.get("height", "")),
            "front_ocr_parse_note": front_ocr_fields.get(
                "front_ocr_parse_note",
                front_ocr_message,
            ),
        }
    )
    data.update(POLICY_STATUS_FIELDS)
    data.update(signature_metadata)
    data["local_diagnostic_summary"] = _build_local_diagnostic_summary(data)
    data["local_structure_summary"] = _build_structure_summary(file_structure)

    result = {
        "success": True,
        "stage": "access_control_verified",
        "message": (
            "Residence-card-number access control succeeded. Back-side structured fields were read "
            "where present; front-side fields were read from the protected image with local OCR "
            "when available."
        ),
        "data": data,
        "metadata": {
            **public_files,
            "file_structure": file_structure,
            "front_image_info": {**front_image_info, **front_png_metadata},
            "front_ocr": {
                "engine": front_ocr.engine,
                "model": front_ocr.model,
                "confidence": front_ocr.confidence,
                "status": front_ocr_status,
                "row_count": front_ocr_row_count,
            },
        },
    }
    if trace is not None:
        trace.add_step("current_read_completed", "complete", success=True)
        result["debug_trace"] = trace.to_safe_dict()
        trace_path = trace.write_file_if_enabled(result)
        if trace_path:
            result["debug_trace_file"] = trace_path
    return result
