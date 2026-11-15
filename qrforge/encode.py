"""Data encoding for QR codes: numeric, alphanumeric and byte modes.

`encode_data` picks the densest mode for the whole text, the smallest
version (1-10) that fits at the chosen EC level, then emits the bit
stream: mode indicator + character count + payload + terminator +
byte alignment + alternating 0xEC/0x11 pad codewords.
"""

from . import tables

ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

MODE_BITS = {"numeric": 1, "alnum": 2, "byte": 4}


class CapacityError(ValueError):
    """Input text is too long for the supported version range."""


class BitBuffer:
    def __init__(self):
        self.bits = []

    def put(self, value, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((value >> i) & 1)

    def bytes(self):
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            byte = 0
            for j in range(8):
                bit = self.bits[i + j] if i + j < len(self.bits) else 0
                byte = (byte << 1) | bit
            out.append(byte)
        return bytes(out)


def classify(text):
    """Densest single mode able to represent the whole text."""
    if not text:
        return "byte"
    if all(c.isdigit() and c.isascii() for c in text):
        return "numeric"
    if all(c in ALNUM for c in text):
        return "alnum"
    return "byte"


def _count_bits(mode, version):
    if version <= 9:
        return {"numeric": 10, "alnum": 9, "byte": 8}[mode]
    return {"numeric": 12, "alnum": 11, "byte": 16}[mode]


def _payload_bits(mode, data):
    """Mode payload bits, excluding mode and count indicators."""
    bits = []
    if mode == "numeric":
        i = 0
        while i < len(data):
            chunk = data[i:i + 3]
            width = {3: 10, 2: 7, 1: 4}[len(chunk)]
            for b in range(width - 1, -1, -1):
                bits.append((int(chunk) >> b) & 1)
            i += 3
    elif mode == "alnum":
        s = data.upper()
        i = 0
        while i < len(s):
            chunk = s[i:i + 2]
            if len(chunk) == 2:
                v = ALNUM.index(chunk[0]) * 45 + ALNUM.index(chunk[1])
                width = 11
            else:
                v = ALNUM.index(chunk[0])
                width = 6
            for b in range(width - 1, -1, -1):
                bits.append((v >> b) & 1)
            i += 2
    else:
        for byte in data.encode("utf-8"):
            for b in range(7, -1, -1):
                bits.append((byte >> b) & 1)
    return bits


def _stream_bits(text, mode, version):
    """Full bit stream for `text` in `mode` at `version`, no padding."""
    if mode == "byte":
        count = len(text.encode("utf-8"))
    else:
        count = len(text)
    return (4 + _count_bits(mode, version) +
            len(_payload_bits(mode, text)))


def _bits_available(version, level):
    return 8 * tables.total_data_codewords(version, level)


def choose_version(text, level):
    """Smallest version in 1..10 whose data codewords fit the stream."""
    mode = classify(text)
    for version in range(1, tables.MAX_VERSION + 1):
        if _stream_bits(text, mode, version) <= \
                _bits_available(version, level):
            return version, mode
    raise CapacityError(
        "text does not fit in versions 1-%d at level %s"
        % (tables.MAX_VERSION, level))


def encode_data(text, level):
    """Return (version, mode, data codewords) ready for RS encoding."""
    version, mode = choose_version(text, level)
    available = _bits_available(version, level)

    buf = BitBuffer()
    buf.put(MODE_BITS[mode], 4)
    if mode == "byte":
        raw = text.encode("utf-8")
        buf.put(len(raw), _count_bits(mode, version))
        for b in raw:
            buf.put(b, 8)
    else:
        buf.put(len(text), _count_bits(mode, version))
        for bit in _payload_bits(mode, text):
            buf.bits.append(bit)

    # terminator: up to four zero bits
    for _ in range(min(4, available - len(buf.bits))):
        buf.bits.append(0)
    # byte alignment
    while len(buf.bits) % 8:
        buf.bits.append(0)
    # pad codewords
    pads = (available - len(buf.bits)) // 8
    for i in range(pads):
        buf.put(0xEC if i % 2 == 0 else 0x11, 8)
    return version, mode, buf.bytes()


def decode_data(codewords, version):
    """Parse data codewords back into (mode, text)."""
    bits = []
    for b in codewords:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)

    def take(pos, n):
        v = 0
        for i in range(pos, pos + n):
            v = (v << 1) | bits[i]
        return v, pos + n

    if len(bits) < 10:
        raise ValueError("no data")
    mode_val, pos = take(0, 4)
    modes = {1: "numeric", 2: "alnum", 4: "byte"}
    if mode_val not in modes:
        raise ValueError("unsupported mode indicator %d" % mode_val)
    mode = modes[mode_val]
    if mode == "byte":
        count, pos = take(pos, _count_bits(mode, version))
        raw = bytearray()
        for _ in range(count):
            v, pos = take(pos, 8)
            raw.append(v)
        return mode, raw.decode("utf-8", errors="replace")
    if mode == "numeric":
        count, pos = take(pos, _count_bits(mode, version))
        chars = []
        while len(chars) < count:
            remaining = count - len(chars)
            if remaining >= 3:
                width, ndigits = 10, 3
            elif remaining == 2:
                width, ndigits = 7, 2
            else:
                width, ndigits = 4, 1
            v, pos = take(pos, width)
            chars.extend(str(v).zfill(ndigits))
        return mode, "".join(chars)
    count, pos = take(pos, _count_bits(mode, version))
    chars = []
    while len(chars) < count:
        remaining = count - len(chars)
        if remaining >= 2:
            v, pos = take(pos, 11)
            chars.append(ALNUM[v // 45])
            chars.append(ALNUM[v % 45])
        else:
            v, pos = take(pos, 6)
            chars.append(ALNUM[v])
    return mode, "".join(chars)
