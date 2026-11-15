"""Galois field and Reed-Solomon unit tests — python -m unittest discover tests."""

import random
import unittest

from qrforge import galois as gf
from qrforge import rscodec as rs


class TestGalois(unittest.TestCase):
    def test_mul_inverses(self):
        for a in range(1, 256):
            self.assertEqual(gf.mul(a, gf.div(1, a)), 1)

    def test_field_axioms(self):
        self.assertEqual(gf.mul(3, 5), gf.mul(5, 3))
        self.assertEqual(gf.mul(gf.mul(2, 7), 11), gf.mul(2, gf.mul(7, 11)))
        # addition is XOR, multiplication distributes over it
        self.assertEqual(gf.mul(2, 3 ^ 5), gf.mul(2, 3) ^ gf.mul(2, 5))
        self.assertEqual(gf.add(7, 7), 0)  # char 2

    def test_known_values(self):
        # alpha = 2: EXP[8] = 256 XOR 0x11D = 0x1D
        self.assertEqual(gf.EXP[8], 0x1D)
        self.assertEqual(gf.mul(16, 16), 0x1D)
        self.assertEqual(gf.mul(1, 123), 123)
        self.assertEqual(gf.mul(0, 123), 0)

    def test_log_tables(self):
        self.assertEqual(len(set(gf.LOG[1:256])), 255)
        for i in range(255):
            self.assertEqual(gf.LOG[gf.EXP[i]], i)

    def test_generator_roots(self):
        # g(x) has roots alpha^0..alpha^(ec-1), highest-degree-first layout
        for ec in (7, 10, 13, 16, 22, 28):
            g = gf.generator(ec)
            self.assertEqual(len(g), ec + 1)
            self.assertEqual(g[0], 1)
            for k in range(ec):
                self.assertEqual(gf.poly_eval(g, gf.EXP[k]), 0)

    def test_gen7_matches_thonky(self):
        # ec7 generator coefficients match Thonky's decimal table
        g = gf.generator(7)
        want = [1, 127, 122, 154, 164, 11, 68, 117]
        self.assertEqual(g, want)

    def test_rs_remainder_clean_syndromes(self):
        data = [12, 34, 56, 78]
        ec = gf.reed_solomon(data, 16)
        cw = data + ec
        for k in range(16):
            s = 0
            x = gf.EXP[k]
            for b in cw:
                s = gf.mul(s, x) ^ b
            self.assertEqual(s, 0)


class TestRSCodec(unittest.TestCase):
    def test_single_byte_error(self):
        data = [12, 34, 56, 78, 90]
        ec = rs.encode_block(data, 6)
        cw = data + ec
        cw[2] ^= 0xFF
        fixed, pos = rs.decode_block(cw, 6)
        self.assertEqual(fixed, data + ec)
        self.assertEqual(pos, [2])

    def test_full_capacity_t(self):
        # ec16 -> t=8; fix 8 scattered errors
        data = list(range(28))
        ec = rs.encode_block(data, 16)
        cw = data + ec
        for i in range(8):
            cw[i * 4] ^= 0xA5
        fixed, pos = rs.decode_block(cw, 16)
        self.assertEqual(fixed, data + ec)
        self.assertEqual(pos, sorted(i * 4 for i in range(8)))

    def test_over_capacity_raises(self):
        data = [1] * 26
        ec = rs.encode_block(data, 16)
        cw = data + ec
        for i in range(9):  # t+1 = 9 errors, beyond capacity
            cw[i] ^= 0x5A
        with self.assertRaises(rs.ReedSolomonError):
            rs.decode_block(cw, 16)

    def test_random_errors_stress(self):
        rng = random.Random(42)
        for _ in range(30):
            ec_len = rng.choice([7, 10, 13, 16, 22, 26, 28])
            t = ec_len // 2
            data = [rng.randrange(256) for _ in range(rng.randrange(1, 30))]
            ec = rs.encode_block(data, ec_len)
            cw = data + ec
            errors = rng.sample(range(len(cw)), t)
            for e in errors:
                cw[e] ^= rng.randrange(1, 256)
            fixed, pos = rs.decode_block(cw, ec_len)
            self.assertEqual(fixed, data + ec)
            self.assertEqual(pos, sorted(errors))

    def test_no_error_fast_path(self):
        data = [9, 8, 7]
        ec = rs.encode_block(data, 7)
        fixed, pos = rs.decode_block(data + ec, 7)
        self.assertEqual(fixed, data + ec)
        self.assertEqual(pos, [])


if __name__ == "__main__":
    unittest.main()
