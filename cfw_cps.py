#!/usr/bin/env python3
"""cfw_cps: codeplug programming software for the D890UV and D168UV custom firmware (cfw).

  cfw_cps.py read PORT -o radio.d8cp            read the radio (.d8cp binary, .json, .yaml)
  cfw_cps.py write PORT FILE [--yes]            validate, show diff, write, verify (codeplug only)
  cfw_cps.py new -o OUT [--model D168UV]        new codeplug for a radio model (D890UV default, D168UV)
  cfw_cps.py import SRC -o OUT [--model M]      .rdt (stock D890UV / D168UV / D878UV CPS), stock CSV set (.LST),
                                                CHIRP/cfw .csv, D890UV image -> cfw codeplug (--model: convert)
  cfw_cps.py export FILE -o OUT [--model M]     convert (.d8cp / .json / .yaml / .csv / .LST stock CSV set / .rdt / .html)
  cfw_cps.py validate FILE                      errors + warnings, exit 1 on errors
  cfw_cps.py diff A B                           what would change
  cfw_cps.py info PORT                          identify + info block
  cfw_cps.py show FILE                          summary
  cfw_cps.py gui [FILE] [--model M]             Tkinter editor (radio model of a new codeplug; File > Radio Model)
An .rdt that was not opened from one is written on the built-in blank file, or on --rdt-template FILE (README).
PORT: tcp:localhost:3470 (emulator) or /dev/ttyUSB0 (cable; writes need --allow-hardware + the owner's OK).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cps import codeplug as C, validate as V, diff as D, ops, link  # noqa: E402


def _save(cp, out):
    if out.lower().endswith((".html", ".txt")):
        from cps import report
        open(out, "w").write(report.html(cp) if out.lower().endswith(".html") else report.text(cp))
    elif out.lower().endswith(".csv"):
        from cps import import_csv
        open(out, "w").write(import_csv.export_csv(cp))
    else:
        C.save(cp, out)
    print("wrote %s" % out)


def show(cp):
    s = cp.settings
    print("radio model: %s" % cp.model)
    print("settings: callsign %s, DMR ID %d, step %d Hz, radio name %r" % (s.callsign, s.dmr_id, s.step_hz, s.radio_name))
    from collections import Counter
    print("channels: %d (%s)" % (len(cp.channels), ", ".join("%s %d" % kv for kv in Counter(c.mode for c in cp.channels).items())))
    print("zones %d, scan lists %d, contacts %d, TG lists %d, trunk systems %d; %d bytes encoded" % (
        len(cp.zones), len(cp.scanlists), len(cp.contacts), len(cp.tglists), len(cp.trunksys), len(C.encode(cp))))
    for i, c in enumerate(cp.channels[:12]):
        print("  %4d %-16s %10.5f %10.5f %-5s" % (i + 1, c.name, c.rx_hz / 1e6, c.tx_hz / 1e6, c.mode))
    if len(cp.channels) > 12:
        print("  ...")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("read"); a.add_argument("port"); a.add_argument("-o", "--out", required=True)
    a = sub.add_parser("write"); a.add_argument("port"); a.add_argument("file")
    a.add_argument("--yes", action="store_true", help="do not ask after showing the diff")
    a.add_argument("--allow-hardware", action="store_true", help="allow writing over a real serial port (owner OK only)")
    a.add_argument("--no-verify", action="store_true")
    models = list(C.MODELS)
    a = sub.add_parser("new"); a.add_argument("-o", "--out", required=True); a.add_argument("--model", default="D890UV", choices=models)
    a = sub.add_parser("import"); a.add_argument("src"); a.add_argument("-o", "--out", required=True)
    a.add_argument("--digital-as", default="DMR", choices=C.MODES[1:], help="mode for digital .rdt channels")
    a.add_argument("--model", choices=models, help="radio model of the result (default: the source's)")
    a = sub.add_parser("export"); a.add_argument("file"); a.add_argument("-o", "--out", required=True)
    a.add_argument("--model", choices=models, help="convert to this radio model")
    a = sub.add_parser("validate"); a.add_argument("file"); a.add_argument("-q", "--quiet", action="store_true")
    a = sub.add_parser("diff"); a.add_argument("a"); a.add_argument("b")
    a = sub.add_parser("info"); a.add_argument("port")
    a = sub.add_parser("show"); a.add_argument("file")
    a = sub.add_parser("gui"); a.add_argument("file", nargs="?")
    a.add_argument("--model", default="D890UV", choices=models, help="radio model of a new codeplug")
    a.add_argument("--port", default="tcp:localhost:3470")
    for p in sub.choices.values():
        p.add_argument("--timeout", type=float, default=5.0)
        p.add_argument("--rdt-template", action="append", default=[], metavar="FILE",
                       help="stock CPS new file (File > New, saved) used to write .rdt files; once per model")
    args = ap.parse_args(argv)
    if args.rdt_template:
        from cps import rdt
        for t in args.rdt_template:
            rdt.set_template(t)

    try:
        if args.cmd == "read":
            cp, raw, inf = ops.read_radio(args.port, timeout=args.timeout)
            if cp is None:
                print("radio holds no cfw codeplug; nothing saved")
                return 2
            if args.out.lower().endswith(".d8cp"):
                open(args.out, "wb").write(raw)          # exact bytes from the radio
                print("wrote %s (%d bytes, raw)" % (args.out, len(raw)))
            else:
                _save(cp, args.out)
        elif args.cmd == "write":
            cp = C.load(args.file)

            def confirm(lines):
                if args.yes:
                    return True
                return input("write this to the radio? [y/N] ").strip().lower() == "y"
            r = ops.write_radio(args.port, cp, allow_hardware=args.allow_hardware, confirm=confirm,
                                verify=not args.no_verify, timeout=args.timeout)
            return 0 if r is not None else 1
        elif args.cmd == "new":
            _save(C.new_codeplug(args.model), args.out)
        elif args.cmd == "import":
            cp, rep = ops.import_any(args.src, args.digital_as, args.model)
            for l in rep:
                print(l)
            iss = V.validate(cp)
            for i in iss[:30]:
                print(i)
            _save(cp, args.out)
            return 1 if V.errors(iss) else 0
        elif args.cmd == "export":
            cp = C.load(args.file)
            if args.model and args.model != cp.model:
                from cps import stock
                stock.convert_model(cp, args.model)
                print("converted to the %s" % args.model)
            _save(cp, args.out)
        elif args.cmd == "validate":
            iss = V.validate(C.load(args.file))
            for i in iss:
                if not args.quiet or i.level == "error":
                    print(i)
            e = len(V.errors(iss))
            print("%d error(s), %d warning(s)" % (e, len(iss) - e))
            return 1 if e else 0
        elif args.cmd == "diff":
            a, b = C.load(args.a), C.load(args.b)
            print(D.summary(a, b))
            for l in D.diff(a, b):
                print(l)
        elif args.cmd == "info":
            def fn(r):
                inf = r.info()
                r.end()
                return inf
            inf = link.with_radio(args.port, fn, timeout=args.timeout)
            for k, v in inf.items():
                print("%-16s %s" % (k, hex(v) if k in ("base", "size", "crc") else v))
        elif args.cmd == "show":
            show(C.load(args.file))
        elif args.cmd == "gui":
            from cps import gui
            gui.run(args.file, args.port, model=args.model)
    except (C.CodeplugError, link.LinkError, OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
