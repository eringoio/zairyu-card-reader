from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from secrets import token_bytes
from typing import Any

from reader.card_type import CardTypeInfo
from reader.config import get_rc2_config
from reader.crypto import rc2
from reader.diagnostics import DiagnosticTrace, timed_step, tlv_tag_summary
from reader.ocr import OcrError, OcrResult, get_ocr_engine, read_address_image
from reader.ocr.name_ocr import read_name_image
from reader.parsing.second_generation_fields import parse_rc2_business_fields
from reader.parsing.tlv import TlvParseError, parse_first_tlv, parse_tlvs_by_hex
from reader.policy import POLICY_STATUS_FIELDS

GET_CHALLENGE = [0x00, 0x84, 0x00, 0x00, 0x08]
DF_AIDS = {
    "DF1": bytes.fromhex("D3 92 F0 00 4F 02 00 00 00 00 00 00 00 00 00 00"),
    "DF2": bytes.fromhex("D3 92 F0 00 4F 03 00 00 00 00 00 00 00 00 00 00"),
    "DF3": bytes.fromhex("D3 92 F0 00 4F 04 00 00 00 00 00 00 00 00 00 00"),
}
RC2_FILE_MAP = {
    "05": {
        "DF1/EF01": {"df": "DF1", "p1": 0x81, "length": 14, "sm": True},
        "DF1/EF02": {"df": "DF1", "p1": 0x83, "length": 73, "sm": True},
        "DF1/EF03": {"df": "DF1", "p1": 0x84, "length": 5508, "sm": True},
        "DF1/EF04": {"df": "DF1", "p1": 0x86, "length": 2505, "sm": True},
        "DF2/EF01": {"df": "DF2", "p1": 0x81, "length": 22, "sm": False},
        "DF2/EF02": {"df": "DF2", "p1": 0x82, "length": 3, "sm": False},
        "DF2/EF03": {"df": "DF2", "p1": 0x83, "length": 207, "sm": False},
        "DF3/EF01": {"df": "DF3", "p1": 0x82, "length": 704, "sm": False},
    },
    "06": {
        "DF1/EF01": {"df": "DF1", "p1": 0x81, "length": 14, "sm": True},
        "DF1/EF02": {"df": "DF1", "p1": 0x83, "length": 46, "sm": True},
        "DF1/EF03": {"df": "DF1", "p1": 0x84, "length": 5508, "sm": True},
        "DF1/EF04": {"df": "DF1", "p1": 0x86, "length": 2505, "sm": True},
        "DF2/EF01": {"df": "DF2", "p1": 0x83, "length": 207, "sm": False},
        "DF3/EF01": {"df": "DF3", "p1": 0x82, "length": 704, "sm": False},
    },
}


class SecondGenerationProtocolError(Exception):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def wipe(buffer: bytearray | None) -> None:
    """
    Overwrite a transient image buffer.

    Defined here rather than imported from `reader.signature.rc_signature` so the protocol
    keeps working when `cryptography` is absent; that module degrades on import.
    """
    if buffer:
        for index in range(len(buffer)):
            buffer[index] = 0


@dataclass(frozen=True)
class SecondGenerationSession:
    ksenc: bytes


def _transmit(connection: Any, command: list[int]) -> tuple[bytes, int, int]:
    data, sw1, sw2 = connection.transmit(command)
    return bytes(data), sw1, sw2


def _transmit_traced(
    connection: Any,
    command: list[int],
    trace: DiagnosticTrace | None,
    stage: str,
    operation: str,
    command_label: str = "",
    file_name: str = "",
    expected_length: int | None = None,
) -> tuple[bytes, int, int]:
    timer = timed_step()
    data, sw1, sw2 = _transmit(connection, command)
    trace_tags = None
    if data:
        try:
            tag, value = parse_first_tlv(data)
            trace_tags = tlv_tag_summary(tag, value)
        except TlvParseError:
            trace_tags = []
    if trace is not None:
        trace.add_apdu_result(
            stage=stage,
            operation=operation,
            command=command,
            sw1=sw1,
            sw2=sw2,
            response_length=len(data),
            command_label=command_label,
            file_name=file_name,
            expected_length=expected_length,
            tlv_tags=trace_tags,
            duration_ms=timer.ms(),
        )
    return data, sw1, sw2


def authenticate_second_generation_card(
    connection: Any,
    card_number: str,
    trace: DiagnosticTrace | None = None,
) -> SecondGenerationSession:
    keys = rc2.derive_base_keys(card_number)

    if trace is not None:
        trace.add_step("rc2_get_challenge_started", "GET CHALLENGE")
    rnd_icc, sw1, sw2 = _transmit_traced(
        connection,
        GET_CHALLENGE,
        trace,
        "rc2_get_challenge_completed",
        "GET CHALLENGE",
        "RC2 GET CHALLENGE",
        expected_length=8,
    )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            f"Second-generation GET CHALLENGE failed with status {sw1:02X} {sw2:02X}.",
        )
    if len(rnd_icc) != 8:
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            f"Second-generation GET CHALLENGE returned {len(rnd_icc)} bytes, expected 8.",
        )

    rnd_ifd = token_bytes(8)
    k_ifd = token_bytes(16)
    e_ifd = rc2.build_e_ifd(keys.kenc, rnd_ifd, rnd_icc, k_ifd)
    m_ifd = rc2.build_m_ifd(keys.kmac, e_ifd)
    if trace is not None:
        trace.add_step("rc2_mutual_authenticate_started", "MUTUAL AUTHENTICATE")
    auth_response, sw1, sw2 = _transmit_traced(
        connection,
        rc2.build_mutual_authenticate_command(e_ifd, m_ifd),
        trace,
        "rc2_mutual_authenticate_completed",
        "MUTUAL AUTHENTICATE",
        "RC2 MUTUAL AUTHENTICATE",
        expected_length=40,
    )
    if (sw1, sw2) == (0x63, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            "Second-generation AES/CMAC mutual authentication failed. Re-check card state and retry.",
        )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            f"Second-generation mutual authentication failed with status {sw1:02X} {sw2:02X}.",
        )
    if len(auth_response) != 40:
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            f"Second-generation mutual authentication returned {len(auth_response)} bytes, expected 40.",
        )

    e_icc = auth_response[:32]
    m_icc = auth_response[32:]
    try:
        if not rc2.verify_m_icc(keys.kmac, e_icc, m_icc):
            raise SecondGenerationProtocolError(
                "second_generation_auth_failed",
                "Second-generation card MAC verification failed.",
            )
        if trace is not None:
            trace.add_step("rc2_card_mac_verified", "MAC verify", success=True)
        auth = rc2.decrypt_e_icc(keys.kenc, e_icc, rnd_icc, rnd_ifd, k_ifd)
        if trace is not None:
            trace.add_step("rc2_session_key_derived", "derive session key", success=True)
        verify_command = rc2.build_verify_command(rc2.encrypt_verify_payload(auth.ksenc, card_number))
    except rc2.Rc2CryptoError as exc:
        raise SecondGenerationProtocolError("second_generation_auth_failed", str(exc)) from exc

    if trace is not None:
        trace.add_step("rc2_verify_started", "VERIFY")
    verify_response, sw1, sw2 = _transmit_traced(
        connection,
        verify_command,
        trace,
        "rc2_verify_completed",
        "VERIFY",
        "RC2 encrypted VERIFY",
    )
    if (sw1, sw2) == (0x63, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_verify_failed_wrong_card_number",
            "The residence-card number did not match this card.",
        )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_auth_failed",
            f"Second-generation VERIFY failed with status {sw1:02X} {sw2:02X}.",
        )

    return SecondGenerationSession(ksenc=auth.ksenc)


def build_select_df_command(df_name: str) -> list[int]:
    aid = DF_AIDS[df_name]
    return [0x00, 0xA4, 0x04, 0x0C, len(aid), *aid]


def build_plain_read_binary_command(p1: int, p2: int = 0x00, length: int = 0) -> list[int]:
    return [0x00, 0xB0, p1, p2, 0x00, (length >> 8) & 0xFF, length & 0xFF]


def build_sm_read_binary_command(p1: int, p2: int = 0x00, length: int = 0) -> list[int]:
    return [0x08, 0xB0, p1, p2, 0x00, 0x00, 0x04, 0x96, 0x02, (length >> 8) & 0xFF, length & 0xFF, 0x00, 0x00]


def select_df(connection: Any, df_name: str, trace: DiagnosticTrace | None = None) -> None:
    stage = f"rc2_select_{df_name.lower()}"
    _, sw1, sw2 = _transmit_traced(
        connection,
        build_select_df_command(df_name),
        trace,
        stage,
        "SELECT DF",
        f"SELECT {df_name}",
        file_name=df_name,
    )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_sm_read_failed",
            f"SELECT {df_name} failed with status {sw1:02X} {sw2:02X}.",
        )


def read_binary_plain(
    connection: Any,
    p1: int,
    length: int = 0,
    trace: DiagnosticTrace | None = None,
    file_name: str = "",
    stage: str = "rc2_read_plain",
) -> bytes:
    command = build_plain_read_binary_command(p1, length=length)
    data, sw1, sw2 = _transmit_traced(
        connection,
        command,
        trace,
        stage,
        "READ BINARY",
        f"READ BINARY {file_name}".strip(),
        file_name=file_name,
        expected_length=length,
    )
    if (sw1, sw2) != (0x90, 0x00) and length:
        fallback = build_plain_read_binary_command(p1, length=0)
        data, sw1, sw2 = _transmit_traced(
            connection,
            fallback,
            trace,
            f"{stage}_full_read_fallback",
            "READ BINARY fallback",
            f"READ BINARY full {file_name}".strip(),
            file_name=file_name,
        )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_sm_read_failed",
            f"Plain READ BINARY failed. p1={p1:02X} status={sw1:02X} {sw2:02X}.",
        )
    return data


def read_binary_sm(
    connection: Any,
    session: SecondGenerationSession,
    p1: int,
    length: int = 0,
    trace: DiagnosticTrace | None = None,
    file_name: str = "",
    stage: str = "rc2_read_sm",
) -> bytes:
    data, sw1, sw2 = _transmit_traced(
        connection,
        build_sm_read_binary_command(p1, length=length),
        trace,
        stage,
        "SM READ BINARY",
        f"SM READ BINARY {file_name}".strip(),
        file_name=file_name,
        expected_length=length,
    )
    if (sw1, sw2) != (0x90, 0x00) and length:
        data, sw1, sw2 = _transmit_traced(
            connection,
            build_sm_read_binary_command(p1, length=0),
            trace,
            f"{stage}_full_read_fallback",
            "SM READ BINARY fallback",
            f"SM READ BINARY full {file_name}".strip(),
            file_name=file_name,
        )
    if (sw1, sw2) != (0x90, 0x00):
        raise SecondGenerationProtocolError(
            "second_generation_sm_read_failed",
            f"SM READ BINARY failed. p1={p1:02X} status={sw1:02X} {sw2:02X}.",
        )
    try:
        tag, value = parse_first_tlv(data)
    except TlvParseError as exc:
        raise SecondGenerationProtocolError("second_generation_tlv_parse_failed", str(exc)) from exc
    if tag != 0x86 or not value or value[0] != 0x01:
        raise SecondGenerationProtocolError(
            "second_generation_sm_read_failed",
            "Unexpected SM READ BINARY response object.",
        )
    try:
        return rc2.decrypt_sm_response_payload(session.ksenc, value[1:])
    except rc2.Rc2CryptoError as exc:
        raise SecondGenerationProtocolError("second_generation_sm_read_failed", str(exc)) from exc


def read_rc2_file(
    connection: Any,
    session: SecondGenerationSession,
    name: str,
    spec: dict[str, Any],
    trace: DiagnosticTrace | None = None,
) -> bytes:
    select_df(connection, str(spec["df"]), trace)
    stage = {
        "DF1/EF02": "rc2_read_df1_ef02_printed_entries",
        "DF2/EF01": "rc2_read_df2_ef01",
        "DF2/EF02": "rc2_read_df2_ef02",
        "DF2/EF03": "rc2_read_df2_ef03",
        "DF3/EF01": "rc2_read_df3_ef01",
    }.get(name, "rc2_read_file")
    if spec["sm"]:
        return read_binary_sm(connection, session, int(spec["p1"]), int(spec["length"]), trace, name, stage)
    return read_binary_plain(connection, int(spec["p1"]), int(spec["length"]), trace, name, stage)


def read_default_business_files(
    connection: Any,
    session: SecondGenerationSession,
    card_type_code: str,
    trace: DiagnosticTrace | None = None,
) -> dict[str, bytes]:
    file_map = RC2_FILE_MAP[card_type_code]
    if card_type_code == "05":
        names = ["DF1/EF02", "DF2/EF01", "DF2/EF02", "DF2/EF03", "DF3/EF01"]
    else:
        names = ["DF1/EF02", "DF2/EF01", "DF3/EF01"]
    return {name: read_rc2_file(connection, session, name, file_map[name], trace) for name in names}


def normalize_address_ocr_text(text: str) -> str:
    # Compatibility helper. The field pipeline keeps separate lines until it can analyse
    # their scripts and address components, rather than deleting every space.
    from reader.ocr.normalization import join_address_lines, normalize_address_text

    return join_address_lines(normalize_address_text(text))


def _safe_file_metadata(name: str, data: bytes) -> dict[str, Any]:
    item: dict[str, Any] = {"file_name": name, "length": len(data), "tlv_tags": []}
    try:
        tags = parse_tlvs_by_hex(data)
    except TlvParseError as exc:
        item["parse_status"] = "failed"
        item["parse_note"] = str(exc)[:160]
        return item
    item["parse_status"] = "parsed"
    item["tlv_tags"] = [{"tag": tag, "length": len(value)} for tag, value in tags.items()]
    return item


def read_authorized_test_file_metadata(
    connection: Any,
    session: SecondGenerationSession,
    card_type_code: str,
    trace: DiagnosticTrace | None = None,
) -> list[dict[str, Any]]:
    metadata = []
    for name, spec in RC2_FILE_MAP[card_type_code].items():
        data = read_rc2_file(connection, session, name, spec, trace)
        metadata.append(_safe_file_metadata(name, data))
    return metadata


def _decode_mmr_tiff_to_png(image: bytes) -> bytes:
    try:
        from PIL import Image
    except Exception as exc:
        raise OcrError(f"Pillow is unavailable for image decoding: {exc}") from exc

    try:
        with Image.open(BytesIO(image)) as source:
            output = BytesIO()
            source.save(output, format="PNG")
            return output.getvalue()
    except Exception as exc:
        raise OcrError(f"Image decode failed: {exc}") from exc


def _ocr_status(result: OcrResult) -> str:
    if result.engine in {"ppocrv6", "onnxruntime_cpu"}:
        return "completed_local_onnx_ocr"
    warning = " ".join(result.warnings).lower()
    if "runtime" in warning:
        return "failed_runtime_unavailable"
    return "failed_model_unavailable"


def _read_address_ocr_fields(
    connection: Any,
    session: SecondGenerationSession,
    card_type_code: str,
    trace: DiagnosticTrace | None,
) -> dict[str, Any]:
    try:
        data = read_rc2_file(connection, session, "DF1/EF04", RC2_FILE_MAP[card_type_code]["DF1/EF04"], trace)
        tlvs = parse_tlvs_by_hex(data)
        image = tlvs.get("DFD1", b"")
        if trace is not None:
            trace.add_tlv_summary("rc2_parse_df1_ef04_address_image", tlv_tag_summary(0xDFD1, image), "DF1/EF04")
        if not image:
            return {
                "address_ocr_status": "failed",
                "address_source": "rc2_dfd1_address_image_ocr_failed",
                "address_ocr_note": "DF1/EF04 did not contain a DFD1 address image object.",
            }
        png = _decode_mmr_tiff_to_png(image)
        candidate, ocr_result = read_address_image(png, engine=get_ocr_engine())
        if ocr_result.engine == "unavailable":
            return {
                "address_ocr_status": _ocr_status(ocr_result),
                "address_source": "rc2_dfd1_address_image_ocr_unavailable",
                "address_ocr_note": (ocr_result.warnings or ["Local OCR is unavailable."])[0],
            }
        split = {
            "address_full": str(candidate["address_full_candidate"]),
            "address_prefecture": str(candidate["address_prefecture"]),
            "address_municipality": str(candidate["address_municipality"]),
            "address_other": str(candidate["address_other"]),
        }
        status = _ocr_status(ocr_result)
        return {
            "address_full": split["address_full"],
            "address_prefecture": split["address_prefecture"],
            "address_municipality": split["address_municipality"],
            "address_other": split["address_other"],
            "address": split["address_full"],
            "address_source": "rc2_dfd1_address_image_local_onnx_ocr",
            "address_ocr_status": status,
            "address_ocr_confidence": candidate.get("address_ocr_confidence", ""),
            "address_ocr_confidence_category": candidate.get("address_ocr_confidence_category", "low"),
            "address_ocr_review_required": candidate.get("address_ocr_review_required", True),
            "address_ocr_review_reasons": candidate.get("address_ocr_review_reasons", []),
            "address_ocr_suggested_candidate": candidate.get("address_ocr_suggested_candidate", ""),
            "address_ocr_note": (ocr_result.warnings or ["Address image OCR completed locally; verify before export."])[0],
        }
    except Exception:
        return {
            "address_ocr_status": "failed",
            "address_source": "rc2_dfd1_address_image_ocr_failed",
            "address_ocr_note": "Address image OCR failed locally; chip fields were still read.",
        }


def _transient_images_are_needed(config: Any) -> bool:
    """
    DF1/EF03 carries the name image (`D0`) and the face image (`D1`) in one file.

    Reading it is justified when the signature must be verified (the face image is part of
    the signed target) or when the operator has explicitly opted into name OCR. In both
    cases the face image is transient and never leaves this module.
    """
    if config.enable_full_signature_validation:
        return True
    return bool(config.read_name_image and config.allow_transient_face_read_for_name)


def _read_transient_card_images(
    connection: Any,
    session: SecondGenerationSession,
    card_type_code: str,
    trace: DiagnosticTrace | None,
) -> tuple[bytearray, bytearray]:
    """Return `(name_image, face_image)` as mutable buffers so the caller can wipe them."""
    data = read_rc2_file(connection, session, "DF1/EF03", RC2_FILE_MAP[card_type_code]["DF1/EF03"], trace)
    try:
        tlvs = parse_tlvs_by_hex(data)
        return bytearray(tlvs.get("D0", b"")), bytearray(tlvs.get("D1", b""))
    finally:
        del data


def _name_ocr_fields(name_image: bytearray) -> dict[str, Any]:
    config = get_rc2_config()
    if not config.read_name_image:
        return {
            "name_ocr_status": "not_attempted_disabled_by_config",
            "name_ocr_candidate": "",
            "name_ocr_note": "Name image OCR is disabled by local configuration.",
        }
    if not name_image:
        return {
            "name_ocr_status": "failed",
            "name_ocr_candidate": "",
            "name_ocr_source": "rc2_d0_name_image_ocr_failed",
            "name_ocr_note": "DF1/EF03 did not contain a D0 name image object.",
        }
    png = b""
    try:
        png = _decode_mmr_tiff_to_png(bytes(name_image))
        result = read_name_image(png, engine=get_ocr_engine())
        if result.get("name_ocr_engine") == "unavailable":
            return {
                "name_ocr_status": "failed_runtime_unavailable" if "runtime" in str(result.get("name_ocr_availability_warning", "")).lower() else "failed_model_unavailable",
                "name_ocr_candidate": "",
                "name_ocr_source": "rc2_d0_name_image_ocr_unavailable",
                "name_ocr_note": "Local ONNX OCR is unavailable; chip fields were still read.",
            }
        result.setdefault("name_ocr_note", "Name image OCR completed locally. The D1 face image is not returned.")
        result["name_ocr_source"] = "rc2_d0_name_image_local_onnx_ocr"
        result["name_ocr_status"] = "completed_local_onnx_ocr"
        return result
    except Exception:
        return {
            "name_ocr_status": "failed",
            "name_ocr_candidate": "",
            "name_ocr_source": "rc2_d0_name_image_ocr_failed",
            "name_ocr_note": "Name image OCR failed locally; chip fields were still read.",
        }
    finally:
        del png


def _name_ocr_blocked_fields(trace: DiagnosticTrace | None) -> dict[str, Any]:
    if trace is not None:
        trace.add_step(
            "rc2_name_ocr_blocked_by_policy",
            "policy",
            "DF1/EF03 holds the D0 name image and D1 face image together.",
            success=True,
        )
    return {
        "name_ocr_status": "blocked_by_privacy_policy",
        "name_ocr_candidate": "",
        "name_ocr_note": "Name image is stored together with the face image. The full EF read is blocked by the current privacy configuration.",
    }


def _failure_classification(stage: str) -> str:
    return {
        "second_generation_auth_failed": "rc2_auth_failed",
        "second_generation_verify_failed_wrong_card_number": "rc2_wrong_card_number",
        "second_generation_sm_read_failed": "rc2_sm_read_failed",
        "second_generation_tlv_parse_failed": "rc2_tlv_parse_failed",
    }.get(stage, "rc2_sm_read_failed")


def read_second_generation_card(
    connection: Any,
    card_info: CardTypeInfo,
    card_number: str,
    trace: DiagnosticTrace | None = None,
) -> dict[str, Any]:
    config = get_rc2_config()
    if trace is not None:
        trace.card_generation = card_info.generation
        trace.card_type_code = card_info.card_type_code
        trace.add_step("rc2_protocol_selected", "dispatch", success=True)
    if not config.enabled:
        return {
            "success": False,
            "stage": "second_generation_disabled_by_config",
            "message": "Second-generation direct reading is disabled by local configuration.",
            "data": {
                **card_info.to_dict(),
                **POLICY_STATUS_FIELDS,
                "card_type": card_info.card_type_label,
                "scan_method": "disabled_by_config",
            },
        }

    name_image = bytearray()
    face_image = bytearray()
    try:
        if trace is None:
            session = authenticate_second_generation_card(connection, card_number)
        else:
            session = authenticate_second_generation_card(connection, card_number, trace)
        if trace is None:
            files = read_default_business_files(connection, session, card_info.card_type_code)
        else:
            files = read_default_business_files(connection, session, card_info.card_type_code, trace)

        images_needed = _transient_images_are_needed(config)
        if images_needed:
            name_image, face_image = _read_transient_card_images(
                connection, session, card_info.card_type_code, trace
            )
            if trace is not None:
                trace.add_step(
                    "rc2_transient_images_read",
                    "READ BINARY",
                    "DF1/EF03 read in memory for signature verification and name OCR only",
                    success=True,
                )

        if trace is not None:
            trace.add_step("rc2_parse_df1_ef02_printed_entries", "TLV parse", success=True)
            trace.add_step("rc2_parse_df2", "TLV parse", success=True)
            trace.add_step("rc2_signature_metadata_parsed", "metadata parse", success=True)
        fields = parse_rc2_business_fields(
            card_info.card_type_code,
            files,
            face_image=bytes(face_image) if face_image else None,
            name_image=bytes(name_image) if name_image else None,
            full_validation_enabled=config.enable_full_signature_validation,
            trust_profile=config.verification_trust_profile,
        )
        if config.read_scope == "authorized_test_all":
            fields["authorized_test_read_scope"] = "authorized_test_all"
            fields["authorized_test_files"] = read_authorized_test_file_metadata(connection, session, card_info.card_type_code, trace)
        fields.update(_read_address_ocr_fields(connection, session, card_info.card_type_code, trace))
        fields.update(_name_ocr_fields(name_image) if images_needed else _name_ocr_blocked_fields(trace))
        if trace is not None:
            trace.add_field_presence("rc2_fields_parsed", fields)
    except SecondGenerationProtocolError as exc:
        classification = _failure_classification(exc.stage)
        if trace is not None:
            trace.failure_classification = classification
        return {
            "success": False,
            "stage": exc.stage,
            "message": exc.message,
            "failure_classification": classification,
            "data": {
                **card_info.to_dict(),
                **POLICY_STATUS_FIELDS,
                "card_type": card_info.card_type_label,
                "scan_method": "second_generation_direct",
            },
        }
    except TlvParseError as exc:
        if trace is not None:
            trace.failure_classification = "rc2_tlv_parse_failed"
        return {
            "success": False,
            "stage": "second_generation_tlv_parse_failed",
            "message": str(exc),
            "failure_classification": "rc2_tlv_parse_failed",
            "data": {
                **card_info.to_dict(),
                **POLICY_STATUS_FIELDS,
                "card_type": card_info.card_type_label,
                "scan_method": "second_generation_direct",
            },
        }
    finally:
        # The face image existed only to satisfy the signature target. Overwrite both
        # buffers before any caller sees the result dict.
        wipe(name_image)
        wipe(face_image)
        del name_image, face_image

    return {
        "success": True,
        "stage": "second_generation_read_completed",
        "message": "Second-generation residence card detected. Reading with AES/CMAC protocol.",
        "data": {
            **card_info.to_dict(),
            **POLICY_STATUS_FIELDS,
            **fields,
            "read_at": datetime.now().replace(microsecond=0).isoformat(),
            "card_number": card_number.strip().upper(),
            "card_type": card_info.card_type_label,
            "card_type_label": card_info.card_type_label,
            "scan_method": "second_generation_direct",
            "name_image_status": fields.get("name_ocr_status", ""),
            "address_image_status": fields.get("address_ocr_status", ""),
            "read_note": "Second-generation AES/CMAC authentication and card-number VERIFY succeeded. Structured fields were read directly. Address OCR was attempted from DF1/EF04. The name and face images were read transiently in memory for name OCR and signature verification, then discarded.",
            "rc2_read_name_image_config": (
                "transient_image_read_enabled" if images_needed else "blocked_by_privacy_policy"
            ),
            "rc2_full_signature_validation_config": (
                "enabled" if config.enable_full_signature_validation else "disabled_by_config"
            ),
            "verification_trust_profile": config.verification_trust_profile,
        },
    }
