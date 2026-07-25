"""Local OCR engine contract and safe, image-free result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class OcrResult:
    """The only OCR payload allowed to leave an engine.

    Images, model tensors, bounding boxes, and full diagnostic traces intentionally do
    not belong here. Callers derive their reviewed field candidates before returning data.
    """

    text: str = ""
    lines: list[str] = field(default_factory=list)
    confidence: float | None = None
    engine: str = "unavailable"
    model: str = ""
    warnings: list[str] = field(default_factory=list)


class OcrEngine(Protocol):
    def recognize_name(self, image: bytes) -> OcrResult:
        ...

    def recognize_address(self, image: bytes) -> OcrResult:
        ...
