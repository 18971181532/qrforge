"""End-to-end QR code generation and decoding.

`encode(text, level)` produces the finished module matrix:
data codewords -> RS blocks -> interleaving -> placement -> best mask ->
format info.  `decode(matrix)` reverses the process, using Reed-Solomon
to self-heal damaged blocks, and returns the recovered text plus a
damage report.
"""

import json

from . import tables, encode as enc, rscodec, matrix as mtx, formatinfo

PAD_A, PAD_B = 0xEC, 0x11


class QRForgeError(ValueError):
    pass


# ------------------------------------------------------------ generation

def _make_blocks(data_cw, version, level):
    """Split data codewords into blocks and append RS codewords."""
    lens, ec_len = tables.block_layout(version, level)
    blocks = []
    pos = 0
    for ln in lens:
        blocks.append(list(data_cw[pos:pos + ln]) +
                      rscodec.encode_block(data_cw[pos:pos + ln], ec_len))
        pos += ln
    return blocks, ec_len


def _interleave(blocks, ec_len):
    """Interleave data then ec codewords across blocks (ISO 8.5.4)."""
    out = []
    max_data = max(len(b) - ec_len for b in blocks)
    for i in range(max_data):
        for b in blocks:
            if i < len(b) - ec_len:
                out.append(b[i])
    for i in range(ec_len):
        for b in blocks:
            out.append(b[len(b) - ec_len + i])
    return out


def _place(matrix, codewords):
    """Zig-zag placement of codeword bits, skipping column 6."""
    n = matrix.size
    bit_index = 0
    total_bits = len(codewords) * 8

    def next_bit():
        nonlocal bit_index
        if bit_index < total_bits:
            byte = codewords[bit_index // 8]
            bit = (byte >> (7 - (bit_index % 8))) & 1
            bit_index += 1
            return bit
        return 0  # remaining 0..7 bits: fill with 0 (no remainder at v1-10)

    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        for i in range(n):
            r = (n - 1 - i) if upward else i
            for c in (col, col - 1):
                if not matrix.is_used(r, c):
                    matrix.set(r, c, next_bit())
        col -= 2
        upward = not upward


def _write_format(matrix, level, mask_id):
    bits = formatinfo.bch_format(level, mask_id)
    n = matrix.size
    # around top-left finder
    seq = [(bits >> i) & 1 for i in range(14, -1, -1)]
    positions1 = [
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    ]
    # around the other two finders
    positions2 = [
        (n - 1, 8), (n - 2, 8), (n - 3, 8), (n - 4, 8), (n - 5, 8),
        (n - 6, 8), (n - 7, 8),
        (8, n - 8), (8, n - 7), (8, n - 6), (8, n - 5), (8, n - 4),
        (8, n - 3), (8, n - 2), (8, n - 1),
    ]
    for bit, (r, c) in zip(seq, positions1):
        matrix.set(r, c, bit)
    for bit, (r, c) in zip(seq, positions2):
        matrix.set(r, c, bit)


def encode(text, level="M", mask=None):
    """Generate a QR code.  Returns a dict with the matrix and metadata."""
    if level not in tables.EC_LEVELS:
        raise QRForgeError(f"level must be one of {tables.EC_LEVELS}")
    version, mode, data_cw = enc.encode_data(text, level)
    blocks, ec_len = _make_blocks(data_cw, version, level)
    codewords = _interleave(blocks, ec_len)

    matrix = mtx.build_function_patterns(version)
    function_used = [row[:] for row in matrix.used]
    _place(matrix, codewords)

    best_mask, best_score, best_bits = 0, None, None
    for mask_id in range(8):
        bits = mtx.apply_mask(matrix.m, mask_id, function_used)
        score = mtx.penalty(bits)
        if best_score is None or score < best_score:
            best_mask, best_score, best_bits = mask_id, score, bits

    final_bits = best_bits
    matrix.m = final_bits
    _write_format(matrix, level, best_mask)

    return {
        "text": text,
        "level": level,
        "version": version,
        "mode": mode,
        "mask": best_mask,
        "size": matrix.size,
        "ec_len": ec_len,
        "blocks": [len(b) - ec_len for b in blocks],
        "matrix": matrix.m,
    }


def _build_base(text, level):
    """(matrix, function_used, rs_blocks, ec_len) before data placement."""
    version, _mode, data_cw = enc.encode_data(text, level)
    blocks, ec_len = _make_blocks(data_cw, version, level)
    matrix = mtx.build_function_patterns(version)
    function_used = [row[:] for row in matrix.used]
    return matrix, function_used, blocks, ec_len


def mask_eval(text, level="M"):
    """Per-mask penalty detail for the workbench mask tab."""
    result = encode(text, level)
    matrix, function_used, blocks, ec_len = _build_base(text, level)
    _place(matrix, _interleave(blocks, ec_len))
    masks = []
    for mask_id in range(8):
        bits = mtx.apply_mask(matrix.m, mask_id, function_used)
        total, n1, n2, n3, n4 = mtx.penalty_detail(bits)
        masks.append({"id": mask_id, "score": total,
                      "n1": n1, "n2": n2, "n3": n3, "n4": n4})
    return {
        "masks": masks,
        "best": result["mask"],
        "score": min(m["score"] for m in masks),
        "version": result["version"],
        "level": level,
        "rows": ["".join("1" if v else "0" for v in row)
                 for row in result["matrix"]],
    }


def rs_pipeline(text, level="M"):
    """Codeword-level view: per-block data + EC and interleaved bytes."""
    version, mode, data_cw = enc.encode_data(text, level)
    blocks, ec_len = _make_blocks(data_cw, version, level)
    return {
        "version": version, "level": level, "mode": mode, "ec_len": ec_len,
        "t": ec_len // 2,
        "blocks": [{"data": b[:len(b) - ec_len], "ec": b[len(b) - ec_len:]}
                   for b in blocks],
        "interleaved": _interleave(blocks, ec_len),
        "rows": ["".join("1" if v else "0" for v in row)
                 for row in encode(text, level)["matrix"]],
    }


def bench(samples=None):
    """Small encode/decode timing table for the workbench bench tab."""
    import time
    if samples is None:
        samples = []
        for level in ("L", "M", "Q", "H"):
            for v in range(1, 11):
                cap = {1: (17, 14, 11, 7), 2: (32, 26, 20, 14),
                       3: (53, 42, 32, 24), 4: (78, 62, 46, 34),
                       5: (106, 84, 60, 44), 6: (134, 106, 74, 58),
                       7: (154, 122, 86, 64), 8: (192, 152, 108, 84),
                       9: (230, 180, 130, 98), 10: (271, 213, 151, 119)}
                n = cap[v][("LMQH".index(level))]
                samples.append((level, "x" * (n - 4)))
    rows = []
    enc_total = 0.0
    for level, text in samples:
        t0 = time.perf_counter()
        r = encode(text, level=level)
        t1 = time.perf_counter()
        d = decode(r["matrix"])
        t2 = time.perf_counter()
        enc_ms = round((t1 - t0) * 1000, 2)
        enc_total += enc_ms
        rows.append({"level": level, "text": text,
                     "version": r["version"], "mode": r["mode"],
                     "enc_ms": enc_ms,
                     "dec_ms": round((t2 - t1) * 1000, 2),
                     "ok": d["text"] == text})
    return {"rows": rows,
            "avg_enc": round(enc_total / max(len(rows), 1), 2)}


# ------------------------------------------------------------- decoding

def _read_format_bits(m):
    n = len(m)
    seq1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
            (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    seq2 = [(n - 1, 8), (n - 2, 8), (n - 3, 8), (n - 4, 8), (n - 5, 8),
            (n - 6, 8), (n - 7, 8),
            (8, n - 8), (8, n - 7), (8, n - 6), (8, n - 5), (8, n - 4),
            (8, n - 3), (8, n - 2), (8, n - 1)]
    bits = [m[r][c] for r, c in seq1]
    bits2 = [m[r][c] for r, c in seq2]
    return bits, bits2


def _unmask(m, mask_id, size):
    version = (size - 17) // 4
    used = mtx.build_function_patterns(version).used
    out = [row[:] for row in m]
    for r in range(size):
        for c in range(size):
            if not used[r][c] and mtx.mask_bit(mask_id, r, c):
                out[r][c] = not out[r][c]
    return out


def _extract(m, size, count):
    """Read `count` codewords via the same zig-zag walk as placement."""
    out = []
    byte = 0
    bit_i = 0
    col = size - 1
    upward = True
    remaining = count * 8
    while col > 0 and remaining > 0:
        if col == 6:
            col -= 1
        for i in range(size):
            r = (size - 1 - i) if upward else i
            for c in (col, col - 1):
                if not _function_at(r, c, size) and remaining > 0:
                    byte = (byte << 1) | (1 if m[r][c] else 0)
                    bit_i += 1
                    remaining -= 1
                    if bit_i == 8:
                        out.append(byte)
                        byte = 0
                        bit_i = 0
        col -= 2
        upward = not upward
    return out


_FUNCTION_CACHE = {}


def _function_at(r, c, size):
    """True if (r, c) belongs to a function pattern or reserved area."""
    key = size
    if key not in _FUNCTION_CACHE:
        m = mtx.build_function_patterns(_version_for_size(size))
        _FUNCTION_CACHE[key] = m.used
    return _FUNCTION_CACHE[key][r][c]


def _version_for_size(size):
    return (size - 17) // 4


def _deinterleave(codewords, version, level):
    lens, ec_len = tables.block_layout(version, level)
    n_blocks = len(lens)
    # data part
    data_blocks = [[] for _ in range(n_blocks)]
    idx = 0
    for i in range(max(lens)):
        for b, ln in enumerate(lens):
            if i < ln:
                data_blocks[b].append(codewords[idx])
                idx += 1
    ec_blocks = [[] for _ in range(n_blocks)]
    for i in range(ec_len):
        for b in range(n_blocks):
            ec_blocks[b].append(codewords[idx])
            idx += 1
    return [d + e for d, e in zip(data_blocks, ec_blocks)], lens, ec_len


def decode(m):
    """Decode a module matrix (list of rows of 0/1/bool).

    Returns dict with text, metadata and a damage report.
    """
    size = len(m)
    if (size - 17) % 4 != 0:
        raise QRForgeError(f"invalid matrix size {size}")
    version = (size - 17) // 4
    if not 1 <= version <= tables.MAX_VERSION:
        raise QRForgeError(f"unsupported version {version}")

    b1, b2 = _read_format_bits(m)
    level = mask_id = None
    for seq in (b1, b2):
        try:
            level, mask_id = formatinfo.parse_format(_to_int(seq))
            break
        except ValueError:
            continue
    if level is None:
        raise QRForgeError("format information unreadable on both copies")

    un = _unmask(m, mask_id, size)
    total_cw = sum(tables.block_layout(version, level)[0]) + \
        len(tables.block_layout(version, level)[0]) * \
        tables.block_layout(version, level)[1]
    codewords = _extract(un, size, total_cw)
    blocks, lens, ec_len = _deinterleave(codewords, version, level)

    corrected = 0
    failed_blocks = 0
    data_cw = []
    for block, ln in zip(blocks, lens):
        try:
            fixed, positions = rscodec.decode_block(block, ec_len)
            corrected += len(positions)
            data_cw.extend(fixed[:ln])
        except rscodec.ReedSolomonError:
            failed_blocks += 1
            data_cw.extend(block[:ln])

    if failed_blocks:
        raise QRForgeError(
            "%d of %d blocks unrecoverable (damage exceeds EC capacity)"
            % (failed_blocks, len(blocks)))
    mode, text = enc.decode_data(bytes(data_cw), version)
    return {
        "text": text,
        "mode": mode,
        "level": level,
        "version": version,
        "mask": mask_id,
        "corrected_bytes": corrected,
        "failed_blocks": failed_blocks,
        "ok": failed_blocks == 0,
    }


def _to_int(bits):
    v = 0
    for b in bits:
        v = (v << 1) | (1 if b else 0)
    return v


def damage(m, cells, seed=0):
    """Flip `cells` random data modules (for self-heal demos)."""
    import random
    rng = random.Random(seed)
    size = len(m)
    used = mtx.build_function_patterns(_version_for_size(size)).used
    candidates = [(r, c) for r in range(size) for c in range(size)
                  if not used[r][c]]
    out = [row[:] for row in m]
    flips = rng.sample(candidates, min(cells, len(candidates)))
    for r, c in flips:
        out[r][c] = not out[r][c]
    return out, flips


def to_ascii(m, dark="#", light="."):
    return "\n".join("".join(dark if v else light for v in row) for row in m)


def to_json(result):
    """Serialize an encode() result, matrix as strings of 0/1 rows."""
    out = {k: v for k, v in result.items() if k != "matrix"}
    out["rows"] = ["".join("1" if v else "0" for v in row)
                   for row in result["matrix"]]
    return out
