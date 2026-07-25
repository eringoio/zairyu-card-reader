from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from reader.runtime_paths import env_path, resource_root

BASE_DIR = resource_root()
ENV_PATH = env_path()


@lru_cache(maxsize=1)
def load_local_env(path: Path = ENV_PATH) -> None:
    if os.getenv("RC_LOAD_LOCAL_ENV", "true").strip().lower() in {"0", "false", "no", "off"}:
        return
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool) -> bool:
    load_local_env()
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Rc2Config:
    enabled: bool
    read_scope: str
    read_name_image: bool
    allow_transient_face_read_for_name: bool
    enable_full_signature_validation: bool
    verification_trust_profile: str
    store_raw_apdu: bool
    store_raw_tlv: bool


@dataclass(frozen=True)
class OcrConfig:
    engine: str


def get_ocr_config() -> OcrConfig:
    """Return the deliberately small, local-only OCR configuration surface."""
    load_local_env()
    engine = os.getenv("OCR_ENGINE", "onnx").strip().lower()
    if engine not in {"onnx", "unavailable"}:
        engine = "onnx"
    return OcrConfig(engine=engine)


def get_rc2_config() -> Rc2Config:
    load_local_env()
    profile = os.getenv("VERIFICATION_TRUST_PROFILE", "production").strip().lower()
    if profile not in {"production", "official_test"}:
        profile = "production"
    return Rc2Config(
        enabled=_env_bool("RC2_ENABLED", True),
        read_scope=os.getenv("RC_READ_SCOPE", "business").strip().lower(),
        read_name_image=_env_bool("RC2_READ_NAME_IMAGE", True),
        allow_transient_face_read_for_name=_env_bool("RC2_ALLOW_TRANSIENT_FACE_READ_FOR_NAME", False),
        # The signed target includes the face image, so full validation implies a transient
        # in-memory face read. Staff need the signature status, so this is on by default.
        enable_full_signature_validation=_env_bool("RC2_ENABLE_FULL_SIGNATURE_VALIDATION", True),
        verification_trust_profile=profile,
        store_raw_apdu=_env_bool("RC2_STORE_RAW_APDU", False),
        store_raw_tlv=_env_bool("RC2_STORE_RAW_TLV", False),
    )


@dataclass(frozen=True)
class DebugTraceConfig:
    """What a diagnostic trace may contain.

    Every field here describes *structure*: which APDU header bytes, status words, response
    lengths, TLV tags and field-presence booleans are recorded. There is deliberately no
    switch for raw APDU/TLV bytes, image bytes, or personal values. Earlier revisions
    carried `DEBUG_TRACE_INCLUDE_RAW_APDU`, `..._RAW_TLV`, `..._IMAGE_BYTES` and
    `..._PERSONAL_VALUES` behind a `DEBUG_TRACE_UNSAFE_LOCAL_MODE` gate; nothing ever read
    them, and "do not store raw IC chip dumps" is a product rule, not a default. A switch
    that could turn a privacy rule off does not belong in the configuration surface.
    """

    enabled: bool
    include_apdu_headers: bool
    include_status_words: bool
    include_response_lengths: bool
    include_tlv_tags: bool
    include_field_presence: bool
    include_sanitized_values: bool
    write_to_file: bool
    trace_dir: str


def get_debug_trace_config() -> DebugTraceConfig:
    load_local_env()
    return DebugTraceConfig(
        enabled=_env_bool("DEBUG_TRACE_ENABLED", True),
        include_apdu_headers=_env_bool("DEBUG_TRACE_INCLUDE_APDU_HEADERS", True),
        include_status_words=_env_bool("DEBUG_TRACE_INCLUDE_STATUS_WORDS", True),
        include_response_lengths=_env_bool("DEBUG_TRACE_INCLUDE_RESPONSE_LENGTHS", True),
        include_tlv_tags=_env_bool("DEBUG_TRACE_INCLUDE_TLV_TAGS", True),
        include_field_presence=_env_bool("DEBUG_TRACE_INCLUDE_FIELD_PRESENCE", True),
        include_sanitized_values=_env_bool("DEBUG_TRACE_INCLUDE_SANITIZED_VALUES", True),
        write_to_file=_env_bool("DEBUG_TRACE_WRITE_TO_FILE", False),
        trace_dir=os.getenv("DEBUG_TRACE_DIR", "debug_traces"),
    )
