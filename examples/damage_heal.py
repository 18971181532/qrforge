"""Damage self-healing demo: inject corruption, watch RS recover it.

Run:  python examples/damage_heal.py
"""

from qrforge import qrforge as core
from qrforge import tables


def main():
    text = "Reed-Solomon self-healing"
    r = core.encode(text, level="H")
    lens, ec_len = tables.block_layout(r["version"], r["level"])
    t = ec_len // 2
    print(f"v{r['version']}-H: {len(lens)} block(s), ec={ec_len} -> "
          f"t={t} byte errors per block")

    for flips in range(0, 4 * t + 2, 4):
        damaged, cells = core.damage(r["matrix"], flips, seed=flips)
        try:
            d = core.decode(damaged)
            print(f"{flips:3d} modules flipped -> healed, "
                  f"{d['corrected_bytes']} bytes corrected, "
                  f"text={d['text']!r}")
        except core.QRForgeError as exc:
            print(f"{flips:3d} modules flipped -> rejected: {exc}")
            break


if __name__ == "__main__":
    main()
