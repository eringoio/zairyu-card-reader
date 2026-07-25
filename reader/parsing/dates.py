from __future__ import annotations


def date_or_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    parts = stripped.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return stripped
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
