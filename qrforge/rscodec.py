"""Reed-Solomon error correction over GF(256).

Encoding follows ISO/IEC 18004 (polynomial division by the generator).
Decoding uses the textbook pipeline: syndromes -> Berlekamp-Massey ->
Chien search -> Forney magnitudes.  Polynomials here use the
"coefficient of x^k at index k" (lowest-degree-first) convention.
"""

from . import galois as gf


class ReedSolomonError(ValueError):
    """Raised when a block has more errors than its correction capacity."""


def encode_block(data, ec_len):
    """Return ec codewords for one block of data codewords."""
    return gf.reed_solomon(list(data), ec_len)


def syndromes(cw, ec_len):
    """S_k = R(alpha^k) for k = 0..ec_len-1; zero means no error seen."""
    out = []
    for k in range(ec_len):
        s = 0
        x = gf.EXP[k]
        for b in cw:  # Horner, highest-degree first
            s = gf.mul(s, x) ^ b
        out.append(s)
    return out


def berlekamp_massey(synd):
    """Error locator sigma(x), lowest-degree first (sigma[0] == 1)."""
    n = len(synd)
    sigma = [1]
    b = [1]
    l = 0  # current number of errors
    m = 1  # iterations since last update of b
    bb = 1
    for i in range(n):
        # discrepancy
        delta = synd[i]
        for j in range(1, l + 1):
            delta ^= gf.mul(sigma[j], synd[i - j])
        if delta == 0:
            m += 1
        elif 2 * l <= i:
            prev = list(sigma)
            scale = gf.div(delta, bb)
            shifted = [0] * m + [gf.mul(c, scale) for c in b]
            if len(shifted) > len(sigma):
                sigma = sigma + [0] * (len(shifted) - len(sigma))
            for k, c in enumerate(shifted):
                sigma[k] ^= c
            b = prev
            bb = delta
            l = i + 1 - l
            m = 1
        else:
            scale = gf.div(delta, bb)
            shifted = [0] * m + [gf.mul(c, scale) for c in b]
            if len(shifted) > len(sigma):
                sigma = sigma + [0] * (len(shifted) - len(sigma))
            for k, c in enumerate(shifted):
                sigma[k] ^= c
            m += 1
    return sigma


def chien(sigma, total):
    """Positions i in [0, total) with sigma(alpha^-(total-1-i)) == 0."""
    pos = []
    l = len(sigma) - 1
    if l == 0:
        return pos
    for i in range(total):
        # X^-1 for codeword index i is alpha^-(total-1-i) = alpha^(i+1-total)
        xinv = gf.EXP[((i + 1 - total) * -1) % 255] if True else 1
        xinv = gf.EXP[((total - 1 - i) * -1) % 255]
        # evaluate sigma at xinv
        y = 0
        power = 1
        for c in sigma:
            if c:
                y ^= gf.mul(c, power)
            power = gf.mul(power, xinv)
        if y == 0:
            pos.append(i)
    if len(pos) != l:
        raise ReedSolomonError(
            f"Chien search found {len(pos)} roots, expected {l}")
    return pos


def forney(cw, sigma, synd, pos, ec_len):
    """Flip error magnitudes at `pos` using Forney's algorithm."""
    # omega(x) = (sigma(x) * S(x)) mod x^ec_len, lowest-degree first
    omega = [0] * ec_len
    for i, s in enumerate(synd):
        if s == 0:
            continue
        for j, c in enumerate(sigma):
            if c and i + j < ec_len:
                omega[i + j] ^= gf.mul(s, c)
    total = len(cw)
    for p in pos:
        # X = alpha^(total-1-p) -> error locator root x = X^-1
        e_inv = gf.EXP[((total - 1 - p) * -1) % 255]
        # numerator: omega evaluated at X^-1
        num = 0
        power = 1
        for c in omega:
            if c:
                num ^= gf.mul(c, power)
            power = gf.mul(power, e_inv)
        # denominator: sigma'(X^-1) = sum over odd k of sigma_k * (X^-1)^(k-1)
        den = 0
        power = 1
        for k in range(1, len(sigma)):
            if k % 2 == 1 and sigma[k]:
                den ^= gf.mul(sigma[k], power)
            power = gf.mul(power, e_inv)
        if den == 0:
            raise ReedSolomonError("Forney: zero denominator")
        # e = X * omega(X^-1) / sigma'(X^-1)   (first root alpha^0, f=0)
        x = gf.EXP[(total - 1 - p) % 255]
        mag = gf.mul(x, gf.div(num, den))
        # In GF(2^8), correction is XOR by the magnitude.
        cw[p] ^= mag
    return cw


def decode_block(cw, ec_len):
    """Correct up to ec_len//2 byte errors in one RS block.

    Returns (corrected list, sorted corrected positions).
    Raises ReedSolomonError if uncorrectable.
    """
    cw = list(cw)
    synd = syndromes(cw, ec_len)
    if not any(synd):
        return cw, []
    sigma = berlekamp_massey(synd)
    pos = chien(sigma, len(cw))
    forney(cw, sigma, synd, pos, ec_len)
    if any(syndromes(cw, ec_len)):
        raise ReedSolomonError("correction failed verification")
    return cw, sorted(pos)
