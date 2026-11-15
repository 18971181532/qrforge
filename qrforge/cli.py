"""qrforge command-line interface.

Subcommands:
  encode   encode text, print the module matrix as ASCII or JSON
  decode   decode an ASCII matrix from a file (or --self round-trip)
  png      render a QR code to a PNG file
  info     show version/capacity/block tables
  serve    start the local web workbench
"""

import argparse
import json
import sys

from . import qrforge as core
from . import tables, encode as enc, png as pngmod


def _cmd_encode(args):
    result = core.encode(args.text, level=args.level)
    if args.json:
        payload = core.to_json(result)
        if args.png and args.png != "-":
            payload["png"] = args.png
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(core.to_ascii(result["matrix"]))
        print(f"// version {result['version']}-{result['level']} "
              f"mode {result['mode']} mask {result['mask']} "
              f"size {result['size']}x{result['size']}", file=sys.stderr)
    if args.png and args.png != "-":
        data = pngmod.qr_png(result["matrix"], scale=args.scale)
        with open(args.png, "wb") as fh:
            fh.write(data)
        if not args.json:
            print(f"// wrote {args.png}", file=sys.stderr)


def _cmd_decode(args):
    if args.selfcheck:
        result = core.encode(args.selfcheck, level=args.level)
        decoded = core.decode(result["matrix"])
        if args.json:
            print(json.dumps(decoded, ensure_ascii=False))
        else:
            print(decoded["text"])
            print(f"// corrected {decoded['corrected_bytes']} bytes, "
                  f"mask {decoded['mask']}", file=sys.stderr)
        return 0 if decoded["text"] == args.selfcheck else 1
    with open(args.file, encoding="utf-8") as fh:
        lines = [ln.rstrip() for ln in fh if ln.strip()]
    # accept '#', '1', 'X' style markers for dark modules
    m = []
    for ln in lines:
        row = [ch not in ". 0" for ch in ln]
        m.append(row)
    height = len(m)
    width = max(len(r) for r in m)
    if any(len(r) != width for r in m):
        print("error: ragged matrix", file=sys.stderr)
        return 2
    decoded = core.decode(m)
    if args.json:
        print(json.dumps(decoded, ensure_ascii=False))
    else:
        print(decoded["text"])
        print(f"// corrected {decoded['corrected_bytes']} bytes, "
              f"mask {decoded['mask']}, level {decoded['level']}",
              file=sys.stderr)
    return 0


def _cmd_png(args):
    result = core.encode(args.text, level=args.level)
    data = pngmod.qr_png(result["matrix"], scale=args.scale,
                         border=args.border)
    with open(args.out, "wb") as fh:
        fh.write(data)
    if args.json:
        print(json.dumps({"out": args.out, "bytes": len(data),
                          "version": result["version"],
                          "level": result["level"],
                          "size": pngmod.png_dimensions(data)}))
    else:
        w, h = pngmod.png_dimensions(data)
        print(f"wrote {args.out}: {w}x{h}, "
              f"version {result['version']}-{result['level']}")
    return 0


def _cmd_info(args):
    if args.json:
        info = {}
        for (v, lv), row in tables.BLOCKS.items():
            info[f"{v}-{lv}"] = row
        print(json.dumps(info))
        return 0
    print(f"{'key':>6} {'data':>5} {'ec':>3} {'g1':>3}x{'d1':>3} "
          f"{'g2':>3}x{'d2':>3}")
    for (v, lv), row in sorted(tables.BLOCKS.items()):
        total, ec, g1n, g1d, g2n, g2d = row
        print(f"{str(v) + '-' + lv:>6} {total:>5} {ec:>3} "
              f"{g1n:>3}x{g1d:<3} {g2n:>3}x{g2d:<3}")


def _cmd_serve(args):
    from . import server
    server.serve(host=args.host, port=args.port, open_browser=not args.no_open)
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="qrforge",
        description="QR code encoder/decoder built from scratch "
                    "(GF(256) Reed-Solomon, versions 1-10).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("encode", help="encode text to a module matrix")
    pe.add_argument("text")
    pe.add_argument("-l", "--level", choices=("L", "M", "Q", "H"),
                    default="M")
    pe.add_argument("--json", action="store_true")
    pe.add_argument("--png", help="also render to a PNG file")

    pd = sub.add_parser("decode", help="decode an ASCII matrix file")
    pd.add_argument("file", nargs="?")
    pd.add_argument("--selfcheck", metavar="TEXT",
                    help="round-trip check TEXT instead of reading a file")
    pd.add_argument("-l", "--level", choices=("L", "M", "Q", "H"),
                    default="M")
    pd.add_argument("--json", action="store_true")

    pp = sub.add_parser("png", help="render text to a PNG file")
    pp.add_argument("text")
    pp.add_argument("-o", "--out", default="qr.png")
    pp.add_argument("-l", "--level", choices=("L", "M", "Q", "H"),
                    default="M")
    pp.add_argument("-s", "--scale", type=int, default=8)
    pp.add_argument("-b", "--border", type=int, default=4)
    pp.add_argument("--json", action="store_true")

    pi = sub.add_parser("info", help="show version/block tables")
    pi.add_argument("--json", action="store_true")

    ps = sub.add_parser("serve", help="start the local web workbench")
    ps.add_argument("-p", "--port", type=int, default=8860)
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--no-open", action="store_true")

    for parser, fn in ((pe, _cmd_encode), (pd, _cmd_decode),
                       (pp, _cmd_png), (pi, _cmd_info), (ps, _cmd_serve)):
        parser.set_defaults(fn=fn)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.fn(args) or 0
    except core.QRForgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except enc.CapacityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
