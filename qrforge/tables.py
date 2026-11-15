"""RS block structure tables for QR versions 1-10 (ISO/IEC 18004).

Each entry (total_data_cw, ec_per_block, g1_blocks, g1_data, g2_blocks,
g2_data) comes straight from the standard's error correction table.
"""

EC_LEVELS = ("L", "M", "Q", "H")
EC_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}

# version, level -> (total data cw, ec per block, g1 blocks, g1 data,
#                    g2 blocks, g2 data)
BLOCKS = {
    (1, "L"): (19, 7, 1, 19, 0, 0),
    (1, "M"): (16, 10, 1, 16, 0, 0),
    (1, "Q"): (13, 13, 1, 13, 0, 0),
    (1, "H"): (9, 17, 1, 9, 0, 0),
    (2, "L"): (34, 10, 1, 34, 0, 0),
    (2, "M"): (28, 16, 1, 28, 0, 0),
    (2, "Q"): (22, 22, 1, 22, 0, 0),
    (2, "H"): (16, 28, 1, 16, 0, 0),
    (3, "L"): (55, 15, 1, 55, 0, 0),
    (3, "M"): (44, 26, 1, 44, 0, 0),
    (3, "Q"): (34, 18, 2, 17, 0, 0),
    (3, "H"): (26, 22, 2, 13, 0, 0),
    (4, "L"): (80, 20, 1, 80, 0, 0),
    (4, "M"): (64, 18, 2, 32, 0, 0),
    (4, "Q"): (48, 26, 2, 24, 0, 0),
    (4, "H"): (36, 16, 4, 9, 0, 0),
    (5, "L"): (108, 26, 1, 108, 0, 0),
    (5, "M"): (86, 24, 2, 43, 0, 0),
    (5, "Q"): (62, 18, 2, 15, 2, 16),
    (5, "H"): (46, 22, 2, 11, 2, 12),
    (6, "L"): (136, 18, 2, 68, 0, 0),
    (6, "M"): (108, 16, 4, 27, 0, 0),
    (6, "Q"): (76, 24, 4, 19, 0, 0),
    (6, "H"): (60, 28, 4, 15, 0, 0),
    (7, "L"): (156, 20, 2, 78, 0, 0),
    (7, "M"): (124, 18, 4, 31, 0, 0),
    (7, "Q"): (88, 18, 2, 14, 4, 15),
    (7, "H"): (66, 26, 4, 13, 1, 14),
    (8, "L"): (194, 24, 2, 97, 0, 0),
    (8, "M"): (154, 22, 2, 38, 2, 39),
    (8, "Q"): (110, 22, 4, 18, 2, 19),
    (8, "H"): (86, 26, 4, 14, 2, 15),
    (9, "L"): (232, 30, 2, 116, 0, 0),
    (9, "M"): (182, 22, 3, 36, 2, 37),
    (9, "Q"): (132, 20, 4, 16, 4, 17),
    (9, "H"): (100, 24, 4, 12, 4, 13),
    (10, "L"): (274, 18, 2, 68, 2, 69),
    (10, "M"): (216, 26, 4, 43, 1, 44),
    (10, "Q"): (154, 24, 6, 19, 2, 20),
    (10, "H"): (122, 28, 6, 15, 2, 16),
}

# version -> (module size, alignment pattern centers)
VERSION_INFO = {
    v: (17 + 4 * v, _centers)
    for v, _centers in [
        (1, []), (2, [6, 18]), (3, [6, 22]), (4, [6, 26]), (5, [6, 30]),
        (6, [6, 34]), (7, [6, 22, 38]), (8, [6, 24, 42]), (9, [6, 26, 46]),
        (10, [6, 28, 50]),
    ]
}

MAX_VERSION = 10


def size(version):
    """Matrix size (modules per side) for a version."""
    return VERSION_INFO[version][0]


def centers(version):
    """Alignment pattern center coordinates."""
    return VERSION_INFO[version][1]


def block_layout(version, level):
    """Return (blocks, ec_len) where blocks is a list of data lengths."""
    total, ec_len, g1n, g1d, g2n, g2d = BLOCKS[(version, level)]
    blocks = [g1d] * g1n + [g2d] * g2n
    return blocks, ec_len


def total_data_codewords(version, level):
    return BLOCKS[(version, level)][0]
