"""QR symbol matrix: structure patterns, masking and penalty evaluation."""

from . import tables

MASK_FNS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def mask_bit(mask_id, r, c):
    """True where the mask inverts the module (ISO/IEC 18004 table)."""
    return MASK_FNS[mask_id](r, c)


class Matrix:
    """A size x size boolean module grid plus a reservation map."""

    def __init__(self, size):
        self.size = size
        self.m = [[False] * size for _ in range(size)]
        self.used = [[False] * size for _ in range(size)]

    def set(self, r, c, v):
        self.m[r][c] = bool(v)
        self.used[r][c] = True

    def get(self, r, c):
        return self.m[r][c]

    def is_used(self, r, c):
        return self.used[r][c]


def _finder(m, r, c):
    """7x7 finder pattern at (r, c) plus its separation ring."""
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < m.size and 0 <= cc < m.size:
                ring = max(abs(dr - 3), abs(dc - 3))
                # dark: centre 3x3 (ring <= 1) and outer border (ring == 3);
                # light: ring 2 and the separation ring (ring >= 4)
                m.set(rr, cc, ring <= 1 or ring == 3)


def _alignment(m, r, c):
    """5x5 alignment pattern centred at (r, c)."""
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            ring = max(abs(dr), abs(dc))
            m.set(r + dr, c + dc, ring != 1)


def _timing(m):
    n = m.size
    for i in range(8, n - 8):
        m.set(6, i, i % 2 == 0)
        m.set(i, 6, i % 2 == 0)


def alignment_centers(version):
    """Alignment centres, skipping the three finder corners."""
    cs = tables.centers(version)
    if not cs:
        return []
    out = []
    for r in cs:
        for c in cs:
            if (r == 6 and c == 6) or (r == 6 and c == cs[-1]) or \
               (r == cs[-1] and c == 6):
                continue
            out.append((r, c))
    return out


def build_function_patterns(version):
    """Matrix with finder, timing, alignment, dark module; format and
    version areas reserved (reserved cells carry False but marked used)."""
    n = tables.size(version)
    m = Matrix(n)
    _finder(m, 0, 0)
    _finder(m, 0, n - 7)
    _finder(m, n - 7, 0)
    _timing(m)
    # reserve format areas (both copies)
    for i in range(9):
        if not m.is_used(8, i):
            m.set(8, i, False)
        if not m.is_used(i, 8):
            m.set(i, 8, False)
    for i in range(8):
        m.set(8, n - 1 - i, False)
        m.set(n - 1 - i, 8, False)
    # reserve version areas (v7+)
    if version >= 7:
        for i in range(6):
            for j in range(3):
                m.set(n - 11 + j, i, False)
                m.set(i, n - 11 + j, False)
    for r, c in alignment_centers(version):
        _alignment(m, r, c)
    # dark module — set last so the format reservation above cannot clear it
    m.set(4 * version + 9, 8, True)
    return m


def apply_mask(bits, mask_id, used):
    """XOR every unreserved data module with the mask function."""
    n = len(bits)
    out = [row[:] for row in bits]
    for r in range(n):
        for c in range(n):
            if not used[r][c] and mask_bit(mask_id, r, c):
                out[r][c] = not out[r][c]
    return out


def penalty_detail(m):
    """(total, n1, n2, n3, n4) penalty components for mask evaluation."""
    n = len(m)
    n1 = n2 = n3 = n4 = 0
    for grid in (m, [list(col) for col in zip(*m)]):
        for row in grid:
            run = 1
            prev = row[0]
            for v in row[1:]:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        n1 += 3 + (run - 5)
                    run = 1
                prev = v
            if run >= 5:
                n1 += 3 + (run - 5)
    for r in range(n - 1):
        for c in range(n - 1):
            v = m[r][c]
            if m[r][c + 1] == v and m[r + 1][c] == v and m[r + 1][c + 1] == v:
                n2 += 3
    finder_pat = (1, 0, 1, 1, 1, 0, 1)
    for m2 in (m, [list(col) for col in zip(*m)]):
        for r in range(n):
            for c in range(n - 10):
                window = tuple(1 if v else 0 for v in m2[r][c:c + 11])
                if window[:4] == (0, 0, 0, 0) and window[4:] == finder_pat:
                    n3 += 40
                if window[7:] == (0, 0, 0, 0) and window[:7] == finder_pat:
                    n3 += 40
    dark = sum(v for row in m for v in row)
    percent = dark * 200 // (n * n)
    prev_multiple = percent // 10 * 10
    n4 = abs(prev_multiple - 50) // 5 * 10
    return n1 + n2 + n3 + n4, n1, n2, n3, n4


def penalty(m):
    """Mask evaluation penalty: N1 runs, N2 blocks, N3 finder-like
    patterns, N4 dark ratio (ISO/IEC 18004 annex)."""
    return penalty_detail(m)[0]
