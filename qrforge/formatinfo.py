"""Format and version information BCH codes.

Format info: 15 bits = 2 EC-level bits + 3 mask bits + 10 BCH bits,
XORed with 0b101010000010010.  Version info (v7+): 18 bits, BCH(18,6).
"""

from . import tables

FORMAT_MASK = 0b101010000010010


def bch_format(level, mask_id):
    """15-bit format information for (level, mask)."""
    data = (tables.EC_BITS[level] << 3) | mask_id
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return ((data << 10) | (rem & 0x3FF)) ^ FORMAT_MASK


def parse_format(bits15):
    """Decode format bits; return (level, mask) or raise ValueError.

    `bits15` is read most-significant bit first, as placed on the symbol.
    """
    raw = bits15 ^ FORMAT_MASK
    # try all 32 valid codewords (brute force beats BCH decoding for 15 bits)
    for level in ("L", "M", "Q", "H"):
        for mask_id in range(8):
            if bch_format(level, mask_id) == bits15:
                return level, mask_id
    raise ValueError("unreadable format information")


def bch_version(version):
    """18-bit version information (versions 7..40)."""
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return (version << 12) | (rem & 0xFFF)


def parse_version_info(bits18):
    for v in range(7, 41):
        if bch_version(v) == bits18:
            return v
    raise ValueError("unreadable version information")
