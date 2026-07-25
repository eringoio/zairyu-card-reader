from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from reader.config import DebugTraceConfig, get_debug_trace_config
from reader.runtime_paths import user_data_root


@dataclass
class DiagnosticStep:
    stage: str
    operation: str = ""
    detail: str = ""
    command_label: str = ""
    cla: str = ""
    ins: str = ""
    p1: str = ""
    p2: str = ""
    sw: str = ""
    response_length: int | None = None
    file_name: str = ""
    expected_length: int | None = None
    tlv_tags: list[dict[str, Any]] = field(default_factory=list)
    field_presence: dict[str, bool] = field(default_factory=dict)
    duration_ms: int | None = None
    success: bool | None = None


class DiagnosticTrace:
    def __init__(self, enabled: bool | None = None, config: DebugTraceConfig | None = None) -> None:
        self.config = config or get_debug_trace_config()
        self.enabled = self.config.enabled if enabled is None else enabled
        self.steps: list[DiagnosticStep] = []
        self.reader_name = ""
        self.card_generation = ""
        self.card_type_code = ""
        self.failure_classification = ""

    def add_step(self, stage: str, operation: str = "", detail: str = "", success: bool | None = None) -> None:
        if self.enabled:
            self.steps.append(DiagnosticStep(stage=stage, operation=operation, detail=detail, success=success))

    def add_apdu_result(
        self,
        stage: str,
        operation: str,
        command: list[int],
        sw1: int,
        sw2: int,
        response_length: int,
        command_label: str = "",
        file_name: str = "",
        expected_length: int | None = None,
        tlv_tags: list[dict[str, Any]] | None = None,
        success: bool | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if not self.enabled:
            return
        step = DiagnosticStep(stage=stage, operation=operation, command_label=command_label)
        if self.config.include_apdu_headers and len(command) >= 4:
            step.cla = f"{command[0]:02X}"
            step.ins = f"{command[1]:02X}"
            step.p1 = f"{command[2]:02X}"
            step.p2 = f"{command[3]:02X}"
        if self.config.include_status_words:
            step.sw = f"{sw1:02X} {sw2:02X}"
        if self.config.include_response_lengths:
            step.response_length = response_length
        if self.config.include_tlv_tags and tlv_tags is not None:
            step.tlv_tags = tlv_tags
        step.file_name = file_name
        step.expected_length = expected_length
        step.duration_ms = duration_ms
        step.success = (sw1, sw2) == (0x90, 0x00) if success is None else success
        self.steps.append(step)

    def add_tlv_summary(self, stage: str, tlv_tags: list[dict[str, Any]], file_name: str = "") -> None:
        if self.enabled and self.config.include_tlv_tags:
            self.steps.append(DiagnosticStep(stage=stage, operation="TLV parse", file_name=file_name, tlv_tags=tlv_tags, success=True))

    def add_field_presence(self, stage: str, fields: dict[str, Any]) -> None:
        if self.enabled and self.config.include_field_presence:
            self.steps.append(DiagnosticStep(stage=stage, operation="field presence", field_presence={k: bool(v) for k, v in sorted(fields.items())}, success=True))

    def to_safe_dict(self) -> dict[str, Any]:
        def clean(step: DiagnosticStep) -> dict[str, Any]:
            data = asdict(step)
            return {key: value for key, value in data.items() if value not in ("", None, [], {})}

        return {
            "enabled": self.enabled,
            "privacy_mode": "safe",
            "steps": [clean(step) for step in self.steps],
        }

    def write_file_if_enabled(self, result: dict[str, Any]) -> str | None:
        if not (self.enabled and self.config.write_to_file):
            return None
        trace_dir = resolve_trace_dir(self.config.trace_dir)
        trace_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        card_type = self.card_type_code or str(result.get("data", {}).get("card_type_code", "unknown"))
        path = trace_dir / f"zairyu_trace_{stamp}_cardtype{card_type}.json"
        payload = {
            "app": "zairyu-local-reader",
            "timestamp": datetime.now().replace(microsecond=0).isoformat(),
            "python": platform.python_version(),
            "os": platform.platform(),
            "reader_name": self.reader_name,
            "card_generation": self.card_generation,
            "card_type_code": self.card_type_code,
            "failure_classification": result.get("failure_classification", self.failure_classification),
            "debug_trace": self.to_safe_dict(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


class timed_step:
    def __init__(self) -> None:
        self.started = perf_counter()

    def ms(self) -> int:
        return int((perf_counter() - self.started) * 1000)


def tlv_tag_summary(tag: int, value: bytes) -> list[dict[str, Any]]:
    return [{"tag": f"{tag:02X}", "length": len(value), "present": bool(value)}]


def resolve_trace_dir(configured: str) -> Path:
    """Resolve the trace directory, keeping a relative value out of the install directory.

    A double-clicked packaged executable inherits an unpredictable working directory —
    often Program Files, sometimes the user's Desktop. A relative `debug_traces` would
    follow it there. Anything not given as an absolute path goes under the per-user
    writable root instead, matching the read-only/writable split in `runtime_paths`.
    """
    path = Path(configured)
    return path if path.is_absolute() else user_data_root() / path
