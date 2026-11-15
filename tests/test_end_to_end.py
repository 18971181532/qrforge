"""End-to-end, damage self-healing, PNG and integration tests."""

import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from qrforge import qrforge as core
from qrforge import png


class TestEndToEnd(unittest.TestCase):
    def roundtrip(self, text, level):
        r = core.encode(text, level=level)
        d = core.decode(r["matrix"])
        self.assertEqual(d["text"], text)
        self.assertEqual(d["level"], level)
        self.assertEqual(d["version"], r["version"])
        self.assertEqual(d["mask"], r["mask"])
        return r, d

    def test_roundtrip_all_modes(self):
        self.roundtrip("0123456789", "L")          # numeric
        self.roundtrip("HELLO WORLD 1234", "M")    # alnum
        self.roundtrip("https://example.com/qrforge?x=1", "Q")  # byte
        self.roundtrip("中文二维码测试", "H")

    def test_roundtrip_all_versions(self):
        # one sample per (version, level) combination v1..v10 x L/M/Q/H
        caps = {1: (17, 14, 11, 7), 2: (32, 26, 20, 14), 3: (53, 42, 32, 24),
                4: (78, 62, 46, 34), 5: (106, 84, 60, 44), 6: (134, 106, 74, 58),
                7: (154, 122, 86, 64), 8: (192, 152, 108, 84),
                9: (230, 180, 130, 98), 10: (271, 213, 151, 119)}
        for version in range(1, 11):
            for li, level in enumerate("LMQH"):
                # byte-mode capacity: cap codewords - ~2.5 header bytes
                text = "x" * (caps[version][li] - 3)
                r, d = self.roundtrip(text, level)
                self.assertEqual(r["version"], version)

    def test_mask_selection_minimizes_penalty(self):
        from qrforge import matrix as mtx
        r = core.encode("mask selection check", "M")
        # recompute all 8 penalties and confirm the chosen one is minimal
        base = core._build_base("mask selection check", "M")
        core._place(base[0], core._interleave(base[2], base[3]))
        scores = [mtx.penalty(mtx.apply_mask(base[0].m, i, base[1]))
                  for i in range(8)]
        self.assertEqual(r["mask"], scores.index(min(scores)))


class TestDamageSelfHealing(unittest.TestCase):
    def test_heal_within_capacity(self):
        # v1: one block; 4 module flips -> at most 4 byte errors, t >= 5
        for seed in range(10):
            r = core.encode("heal me", "M")
            damaged, _ = core.damage(r["matrix"], 4, seed=seed)
            d = core.decode(damaged)
            self.assertEqual(d["text"], "heal me")
            self.assertGreater(d["corrected_bytes"], 0)

    def test_heal_exact_t_single_block_versions(self):
        # v1 has a single RS block at every level: flipping exactly
        # t = ec//2 modules can corrupt at most t bytes -> always healable.
        from qrforge import tables
        for level in "LMQH":
            text = "s" * 7  # fits v1 at every EC level
            r = core.encode(text, level=level)
            self.assertEqual(r["version"], 1)
            self.assertEqual(len(r["blocks"]), 1)  # single RS block
            _, ec_len = tables.block_layout(r["version"], level)
            for seed in range(3):
                damaged, _ = core.damage(r["matrix"], ec_len // 2,
                                         seed=seed * 31 + len(level))
                d = core.decode(damaged)
                self.assertEqual(d["text"], text,
                                 f"v1-{level} seed {seed} failed")

    def test_reject_beyond_capacity(self):
        # saturate: far more flips than any level can heal must raise
        r = core.encode("reject me", "H")
        damaged, _ = core.damage(r["matrix"], 60, seed=5)
        with self.assertRaises(core.QRForgeError):
            core.decode(damaged)

    def test_flips_are_data_modules_only(self):
        r = core.encode("flip targets", "M")
        _, flips = core.damage(r["matrix"], 30, seed=9)
        from qrforge import matrix as mtx
        used = mtx.build_function_patterns(r["version"]).used
        for r_, c_ in flips:
            self.assertFalse(used[r_][c_])


class TestPng(unittest.TestCase):
    def test_png_signature_and_dims(self):
        r = core.encode("png test", "M")
        data = png.qr_png(r["matrix"], scale=6, border=4)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        w, h = png.png_dimensions(data)
        n = r["size"]
        self.assertEqual((w, h), ((n + 8) * 6, (n + 8) * 6))

    def test_png_chunk_integrity(self):
        data = png.qr_png(core.encode("chunks", "L")["matrix"], scale=2)
        pos = 8
        idat = b""
        ihdr_seen = False
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            body = data[pos + 8:pos + 8 + length]
            crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(ctype + body) & 0xFFFFFFFF)
            if ctype == b"IHDR":
                ihdr = body
                ihdr_seen = True
            if ctype == b"IDAT":
                idat += body
            pos += 12 + length
        self.assertTrue(ihdr_seen)
        # IHDR: 8-bit depth, color type 2 (truecolor), then defaults
        self.assertEqual(ihdr[8:13], b"\x08\x02\x00\x00\x00")
        raw = zlib.decompress(idat)
        # each scanline starts with filter byte 0
        self.assertEqual(raw[0], 0)
        side = struct.unpack(">I", ihdr[0:4])[0]
        # truecolor: filter byte + 3 bytes per pixel, side scanlines
        self.assertEqual(len(raw), side * (3 * side + 1))


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "qrforge.cli", *args],
            capture_output=True, text=True, encoding="utf-8")

    def test_encode_decode_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "qr.txt")
            enc = self.run_cli("encode", "cli round trip 42")
            self.assertEqual(enc.returncode, 0)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(enc.stdout)
            dec = self.run_cli("decode", path)
            self.assertEqual(dec.returncode, 0)
            self.assertIn("cli round trip 42", dec.stdout)

    def test_png_output(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "qr.png")
            out = self.run_cli("png", "png cli", "-o", path, "-s", "4")
            self.assertEqual(out.returncode, 0)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")

    def test_json_output(self):
        out = self.run_cli("encode", "json mode", "--json")
        self.assertEqual(out.returncode, 0)
        payload = json.loads(out.stdout)
        self.assertIn("rows", payload)
        self.assertEqual(len(payload["rows"]), payload["size"])

    def test_info_lists_all_versions(self):
        out = self.run_cli("info")
        self.assertEqual(out.returncode, 0)
        for v in range(1, 11):
            for lvl in "LMQH":
                self.assertIn(f"{v}-{lvl}", out.stdout)

    def test_selfcheck(self):
        out = self.run_cli("decode", "--selfcheck", "中文自检")
        self.assertEqual(out.returncode, 0)
        self.assertIn("中文自检", out.stdout)


class TestHelpers(unittest.TestCase):
    def test_to_ascii(self):
        r = core.encode("ascii", "L")
        lines = core.to_ascii(r["matrix"]).splitlines()
        self.assertEqual(len(lines), r["size"])
        self.assertTrue(set(lines[0]) <= {"#", "."})

    def test_to_json_rows(self):
        r = core.encode("serialize", "M")
        j = core.to_json(r)
        self.assertEqual(len(j["rows"]), r["size"])
        for row in j["rows"]:
            self.assertEqual(len(row), r["size"])
            self.assertTrue(set(row) <= {"0", "1"})

    def test_mask_eval_helper(self):
        m = core.mask_eval("helper masks", "M")
        self.assertEqual(len(m["masks"]), 8)
        self.assertIn(m["best"], range(8))

    def test_rs_pipeline_helper(self):
        p = core.rs_pipeline("helper rs", "M")
        self.assertGreater(len(p["interleaved"]), 0)
        self.assertEqual(p["t"], p["ec_len"] // 2)

    def test_bench_helper(self):
        b = core.bench([("L", "bench"), ("M", "bench")])
        self.assertEqual(len(b["rows"]), 2)
        self.assertTrue(all(row["ok"] for row in b["rows"]))


if __name__ == "__main__":
    unittest.main()
