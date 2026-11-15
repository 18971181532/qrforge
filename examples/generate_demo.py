"""QRForge API tour: encode, decode, damage self-healing, mask evaluation.

Run:  python examples/generate_demo.py
"""

from qrforge import qrforge as core


def main():
    r = core.encode("Hello, QRForge!", level="M")
    print(f"version {r['version']}-{r['level']}  mask {r['mask']}  "
          f"size {r['size']}x{r['size']}  mode {r['mode']}")

    print("\nASCII rendering (top-left 10 rows):")
    for line in core.to_ascii(r["matrix"]).splitlines()[:10]:
        print(" ", line)

    d = core.decode(r["matrix"])
    print(f"\ndecoded: {d['text']!r}  corrected {d['corrected_bytes']} bytes")

    # mask evaluation detail
    detail = core.mask_eval("Hello, QRForge!", "M")
    print("\nmask penalties (lower is better):")
    for m in detail["masks"]:
        star = " <-- chosen" if m["id"] == detail["best"] else ""
        print(f"  mask {m['id']}: N1={m['n1']:4d} N2={m['n2']:4d} "
              f"N3={m['n3']:4d} N4={m['n4']:4d}  total={m['score']}{star}")

    # export a PNG
    from qrforge import png
    data = png.qr_png(r["matrix"], scale=8)
    out = "demo.png"
    with open(out, "wb") as fh:
        fh.write(data)
    print(f"\nwrote {out} ({len(data)} bytes, "
          f"{png.png_dimensions(data)[0]}x{png.png_dimensions(data)[1]})")


if __name__ == "__main__":
    main()
