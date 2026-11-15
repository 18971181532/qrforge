"""Minimal PNG encoder using only zlib and struct (no third-party deps)."""

import struct
import zlib


def _chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload +
            struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def png_gray(width, height, rows):
    """Encode 8-bit grayscale rows (each a bytes/bytearray of `width`
    pixels) into a PNG file image."""
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def qr_png(matrix, scale=8, border=4, dark=(0, 0, 0), light=(255, 255, 255)):
    """Render a QR module matrix as a PNG.

    `border` is the quiet zone in modules (ISO requires >= 4).
    Colours are RGB tuples; the image is 24-bit truecolor.
    """
    if scale < 1:
        raise ValueError("scale must be >= 1")
    n = len(matrix)
    side = (n + 2 * border) * scale
    # build one dark row-pixel line and one light row-pixel line per module
    dark_line = bytes(dark) * scale
    light_line = bytes(light) * scale
    quiet = bytes(light) * (border * scale)
    rows = []
    for _ in range(border * scale):
        rows.append(bytes(light) * side)
    for mod_row in matrix:
        line = bytearray(quiet)
        for v in mod_row:
            line += (dark_line if v else light_line)
        line += quiet
        for _ in range(scale):
            rows.append(bytes(line))
    for _ in range(border * scale):
        rows.append(bytes(light) * side)
    raw = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def png_dimensions(data):
    """(width, height) of a PNG byte string."""
    return struct.unpack(">II", data[16:24])
