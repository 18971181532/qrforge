"""QRForge — a zero-dependency QR code encoder/decoder built from scratch.

GF(256) Reed-Solomon, BCH format info, mask penalty evaluation, module
matrix decoding with damage self-healing, PNG rendering, CLI and an
animated Canvas workbench.  Pure Python standard library.
"""

__version__ = "0.1.0"

from . import galois, tables, encode, rscodec, matrix, formatinfo, qrforge
from .qrforge import encode as make_qr, decode as read_qr, damage, \
    to_ascii, to_json, QRForgeError

__all__ = ["galois", "tables", "encode", "rscodec", "matrix", "formatinfo",
           "qrforge", "make_qr", "read_qr", "damage", "to_ascii", "to_json",
           "QRForgeError", "__version__"]
