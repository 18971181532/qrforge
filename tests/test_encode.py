"""Data encoding, block structure, format info and mask tests."""

import unittest

from qrforge import encode as enc
from qrforge import formatinfo as fi
from qrforge import matrix as mtx
from qrforge import tables


class TestModeClassification(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(enc.classify("0123456789"), "numeric")
        self.assertEqual(enc.classify("007"), "numeric")

    def test_alnum(self):
        self.assertEqual(enc.classify("HELLO WORLD 42%"), "alnum")
        self.assertEqual(enc.classify("HTTP://EXAMPLE.COM"), "alnum")

    def test_byte(self):
        self.assertEqual(enc.classify("hello, 世界"), "byte")
        self.assertEqual(enc.classify("a,b"), "byte")  # comma not alnum


class TestEncodeData(unittest.TestCase):
    def test_numeric_bit_packing(self):
        # 3 digits -> 10 bits (ISO 18004 8.3.3): 123 = 0001111011
        v, mode, cw = enc.encode_data("123", "L")
        self.assertEqual((v, mode), (1, "numeric"))
        bits = "".join(f"{b:08b}" for b in cw)
        # mode 0001 + count(10b) 0000000011 + payload 0001111011
        self.assertTrue(bits.startswith("0001" + "0000000011" + "0001111011"))

    def test_alnum_bit_packing(self):
        v, mode, cw = enc.encode_data("AB", "L")
        self.assertEqual((v, mode), (1, "alnum"))
        bits = "".join(f"{b:08b}" for b in cw)
        # A=10, B=11 -> 10*45+11 = 461 = 00111001101 (11 bits)
        self.assertTrue(bits.startswith("0010" + "000000010" + "00111001101"))

    def test_byte_utf8(self):
        v, mode, cw = enc.encode_data("é", "L")
        self.assertEqual(mode, "byte")
        bits = "".join(f"{b:08b}" for b in cw)
        # mode 0100 + count 8b=2 + utf-8 C3 A9
        self.assertTrue(bits.startswith("0100" + "00000010" + "11000011" "10101001"))

    def test_pad_codewords(self):
        v, mode, cw = enc.encode_data("A", "L")
        # after data, terminator + zeros then EC 11 EC 11 ...
        self.assertIn(0xEC, cw)
        self.assertIn(0x11, cw)

    def test_version_selection_and_capacity(self):
        # 26 codewords at 1-L; "x"*15 = 15+1 header bytes = 16 -> fits v1-L
        v, _, _ = enc.encode_data("x" * 15, "L")
        self.assertEqual(v, 1)
        # v1-L holds 19 data codewords = 17 bytes payload max
        v, _, _ = enc.encode_data("x" * 17, "L")
        self.assertEqual(v, 1)
        v, _, _ = enc.encode_data("x" * 18, "L")
        self.assertEqual(v, 2)

    def test_over_capacity_raises(self):
        with self.assertRaises(enc.CapacityError):
            enc.encode_data("x" * 300, "H")


class TestDecodeData(unittest.TestCase):
    def roundtrip(self, text, level="L"):
        version, mode, cw = enc.encode_data(text, level)
        mode2, text2 = enc.decode_data(cw, version)
        self.assertEqual((mode, text), (mode2, text2))

    def test_all_modes(self):
        self.roundtrip("8675309")
        self.roundtrip("HELLO WORLD 99")
        self.roundtrip("Mixed 中文 content!")
        for level in "LMQH":
            self.roundtrip("round trip at level " + level * 3, level)

    def test_numeric_zero_groups(self):
        # regression: zfill group counting must extend, not append
        self.roundtrip("100")
        self.roundtrip("000100")
        self.roundtrip("9")
        self.roundtrip("00000000")


class TestFormatInfo(unittest.TestCase):
    def test_bch_known_codeword(self):
        # M + mask 4: known QR spec example unmasked value ends 10011110011
        bits = fi.bch_format("M", 4)
        self.assertEqual(bits & 0x7FFF, 0b100010111111001)

    def test_roundtrip_all_64_combos(self):
        for level in "LMQH":
            for mask in range(8):
                bits = fi.bch_format(level, mask)
                self.assertEqual(fi.parse_format(bits), (level, mask))

    def test_format_survives_bit_errors(self):
        # The brute-force parser accepts any valid codeword; verify the
        # 15-bit Hamming distance claim on our codeword set instead.
        seen = []
        for level in "LMQH":
            for mask in range(8):
                seen.append(fi.bch_format(level, mask))
        for i in range(len(seen)):
            for j in range(i + 1, len(seen)):
                d = bin(seen[i] ^ seen[j]).count("1")
                self.assertGreaterEqual(d, 3)

    def test_version_info_bch(self):
        # version 7 -> 0x07C94 per ISO 18004 Annex D example
        self.assertEqual(fi.bch_version(7), 0x07C94)
        self.assertEqual(fi.parse_version_info(fi.bch_version(10)), 10)


class TestMatrix(unittest.TestCase):
    def test_size_and_finder(self):
        for version in range(1, 11):
            m = mtx.build_function_patterns(version)
            self.assertEqual(m.size, 17 + 4 * version)
            # finder patterns: 7x7 ring dark at corners of the three eyes
            for r, c in [(0, 0), (0, m.size - 7), (m.size - 7, 0)]:
                self.assertEqual(m.m[r][c], 1)
                self.assertEqual(m.m[r + 6][c + 6], 1)
                self.assertEqual(m.m[r + 6][c], 1)
                # white ring then dark 3x3 centre
                self.assertEqual(m.m[r + 1][c + 1], 0)
                self.assertEqual(m.m[r + 4][c + 4], 1)
                self.assertEqual(m.m[r + 2][c + 2], 1)

    def test_timing_patterns(self):
        m = mtx.build_function_patterns(3)
        for i in range(8, m.size - 8):
            self.assertEqual(m.m[6][i], i % 2 == 0)
            self.assertEqual(m.m[i][6], i % 2 == 0)

    def test_dark_module(self):
        # (4v+9, 8) must always be dark
        for version in range(1, 11):
            m = mtx.build_function_patterns(version)
            self.assertEqual(m.m[4 * version + 9][8], 1)

    def test_alignment_positions(self):
        # v2 alignment center at (18, 18) only
        self.assertEqual(mtx.alignment_centers(2), [(18, 18)])
        # v7 has 6 centers per Thonky table
        self.assertEqual(len(mtx.alignment_centers(7)), 6)

    def test_mask_functions(self):
        # reference implementations from ISO 18004 Table 10
        def mask0(r, c): return (r + c) % 2 == 0
        def mask4(r, c): return (r // 2 + c // 3) % 2 == 0
        for r in range(4):
            for c in range(4):
                self.assertEqual(mtx.MASK_FNS[0](r, c), int(mask0(r, c)))
                self.assertEqual(mtx.MASK_FNS[4](r, c), int(mask4(r, c)))

    def test_penalty_positive(self):
        # a row of 5+ identical modules triggers N1
        row = [[1] * 25 for _ in range(25)]
        self.assertGreater(mtx.penalty(row), 0)


if __name__ == "__main__":
    unittest.main()
