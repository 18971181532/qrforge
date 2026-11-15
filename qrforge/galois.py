"""Galois field GF(256) arithmetic for Reed-Solomon codes.

QR codes use GF(2^8) with the primitive polynomial
    x^8 + x^4 + x^3 + x^2 + 1   (0x11D)
and generator alpha = 2.  Multiplication is done with logarithm tables
so both mul and div are O(1) table lookups.
"""

PRIM = 0x11D

# exp[i] = alpha^i ; log[i] = log_alpha(i)
EXP = [0] * 512
LOG = [0] * 256


def _build_tables():
    x = 1
    for i in range(255):
        EXP[i] = x
        LOG[x] = i
        # x *= alpha, i.e. shift-left one bit then reduce by the primitive
        x <<= 1
        if x & 0x100:
            x ^= PRIM
    for i in range(255, 512):
        EXP[i] = EXP[i - 255]


_build_tables()


def exp(i):
    return EXP[i % 255]


def log(v):
    if v == 0:
        raise ValueError("log(0) undefined")
    return LOG[v]


def mul(a, b):
    if a == 0 or b == 0:
        return 0
    return EXP[LOG[a] + LOG[b]]


def div(a, b):
    if b == 0:
        raise ZeroDivisionError("GF(256) division by zero")
    if a == 0:
        return 0
    return EXP[(LOG[a] - LOG[b]) % 255]


def add(a, b):
    return a ^ b


def poly_mul(p, q):
    """Multiply two polynomials whose coefficients are GF elements.

    Coefficients are stored highest-degree first.
    """
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        la = LOG[a]
        for j, b in enumerate(q):
            if b:
                out[i + j] ^= EXP[la + LOG[b]]
    return out


def poly_eval(p, x):
    """Evaluate polynomial p (highest degree first) at GF element x."""
    y = p[0]
    for c in p[1:]:
        y = mul(y, x) ^ c
    return y


def generator(ec_len):
    """Reed-Solomon generator polynomial g(x) = prod(x - alpha^i)."""
    g = [1]
    for i in range(ec_len):
        g = poly_mul(g, [1, EXP[i]])
    return g


def reed_solomon(data, ec_len):
    """Compute `ec_len` error correction codewords for `data`."""
    if ec_len == 0:
        return []
    gen = generator(ec_len)
    # remainder of data * x^ec_len divided by gen
    rem = [0] * ec_len
    for b in data:
        factor = b ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            lf = LOG[factor]
            for i, c in enumerate(gen[1:]):
                if c:
                    rem[i] ^= EXP[lf + LOG[c]]
    return rem
