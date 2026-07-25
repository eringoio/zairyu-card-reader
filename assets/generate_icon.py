"""Generate the original Windows application icon without downloading any asset.

The icon deliberately uses only an abstract card outline and NFC arcs. It is not a
government emblem and does not resemble a real residence card.
"""

from __future__ import annotations

import struct
from pathlib import Path

OUT = Path(__file__).with_name("zairyu-reader.ico")


def pixel(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    scale = size / 64
    x64, y64 = x / scale, y / scale
    color = (8, 119, 101, 255)
    # White rounded card outline.
    in_outer = 12 <= x64 <= 48 and 17 <= y64 <= 45
    in_inner = 15 <= x64 <= 45 and 20 <= y64 <= 42
    if in_outer and not in_inner:
        color = (255, 255, 255, 255)
    # Small NFC arcs at the card's upper right.
    for radius in (7, 11):
        distance = ((x64 - 42) ** 2 + (y64 - 23) ** 2) ** 0.5
        if abs(distance - radius) <= 1.5 and x64 >= 40 and y64 <= 25:
            color = (255, 255, 255, 255)
    if 20 <= x64 <= 34 and 27 <= y64 <= 29:
        color = (255, 255, 255, 255)
    return color


def bmp_image(size: int) -> bytes:
    # ICO stores a DIB with XOR then AND bitmap. Pixels are BGRA and bottom-up.
    rows = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = pixel(x, y, size)
            rows.extend((b, g, r, a))
    and_mask = bytes(((size + 31) // 32 * 4) * size)
    header = struct.pack("<IIIHHIIIIII", 40, size, size * 2, 1, 32, 0, len(rows), 0, 0, 0, 0)
    return header + rows + and_mask


def main() -> None:
    images = [(32, bmp_image(32)), (48, bmp_image(48)), (64, bmp_image(64))]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    data = bytearray()
    for size, image in images:
        entries.extend(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), offset))
        data.extend(image)
        offset += len(image)
    OUT.write_bytes(header + entries + data)


if __name__ == "__main__":
    main()
