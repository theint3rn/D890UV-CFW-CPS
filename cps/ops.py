"""Radio operations shared by the CLI and the GUI."""
import time

from . import codeplug as C, link, validate as V, diff as D


def import_any(path, digital_as="DMR", model=None):
    """.rdt (AnyTone CPS), .csv (CHIRP / cfw), raw D890UV image / writes.bin, or a cfw codeplug (.d8cp/.json/.yaml).
    model: convert the result to this radio model (default: the source's model; D890UV for D878UV / CHIRP sources)."""
    cp, rep = _import_any(path, digital_as)
    if model and model != cp.model:
        from . import stock
        stock.convert_model(cp, model)
        rep = rep + ["converted to the %s" % model]
    return cp, rep


def _import_any(path, digital_as="DMR"):
    p = path.lower()
    if p.endswith(".rdt"):
        head = open(path, "rb").read(16)
        if head[9:15] in (b"D890UV", b"D168UV"):          # stock D890UV (V1323) / D168UV (V1292) CPS file: lossless reader
            from . import rdt
            return rdt.load(path), ["stock %s CPS file (%s)" % (head[9:15].decode(), head[:5].decode("latin1"))]
        from . import import_rdt
        return import_rdt.import_rdt(path, digital_as)
    if p.endswith(".lst"):
        from . import stock
        cp = stock.from_stock(stock.read_csv_set(path))
        return cp, ["stock CPS CSV set: %d channels, %d zones, %d scan lists, %d talkgroups, %d stock tables"
                    % (len(cp.channels), len(cp.zones), len(cp.scanlists), len(cp.contacts), len(cp.stock))]
    if p.endswith(".csv"):
        from . import import_csv
        cp, line = import_csv.import_csv(path)
        return cp, [line]
    if p.endswith((".bin", ".pages", ".img")):
        from . import import_nand
        return import_nand.import_nand(path)
    return C.load(path), ["cfw codeplug"]


def read_radio(port, log=print, timeout=5.0, progress=None):
    """Returns (Codeplug or None, raw bytes, info)."""
    def fn(r):
        inf = r.info()
        log("radio holds %s" % ("a valid codeplug, %d bytes, generation %d, %d channels"
                                % (inf["len"], inf["generation"], inf["cp_channels"]) if inf["valid"]
                                else "no cfw codeplug (NAND / built-in channels, %d)" % inf["channels"]))
        raw = r.read_codeplug(progress)
        r.end()
        inf["model"] = r.ident.get("model", "D890UV")
        return raw, inf
    raw, inf = link.with_radio(port, fn, log, timeout=timeout)
    return (C.decode(raw) if raw else None), raw, inf


def write_radio(port, cp, log=print, allow_hardware=False, confirm=None, verify=True, timeout=5.0, progress=None):
    """Validate, show the diff against what the radio holds, write, END, read back and compare.
    confirm(diff_lines) -> bool is asked before anything is written (None = always yes)."""
    issues = V.validate(cp)
    errs = V.errors(issues)
    if errs:
        raise C.CodeplugError("codeplug has %d error(s):\n  %s" % (len(errs), "\n  ".join(map(str, errs[:20]))))

    def fn(r):
        if r.ident.get("model", "D890UV") != cp.model:
            r.end()
            raise link.LinkError("the radio is a %s, this codeplug is for the %s (convert it first: File > Radio model / "
                                 "cfw_cps.py export --model)" % (r.ident.get("model"), cp.model))
        if r.ident["write_protected"]:
            r.end()
            raise link.LinkError("radio firmware is a write-protected (HW=1) build; nothing written")
        inf = r.info()
        old = None
        if inf["valid"]:
            try:
                old = C.decode(r.read_codeplug())
            except C.CodeplugError:
                old = None
        import dataclasses
        new = C.Codeplug(**{f.name: getattr(cp, f.name) for f in dataclasses.fields(C.Codeplug)
                            if f.name not in ("generation", "created")})
        new.generation = (old.generation if old else inf["generation"]) + 1
        new.created = int(time.time())
        data = C.encode(new)
        if len(data) > inf["size"]:
            r.end()
            raise C.CodeplugError("codeplug is %d bytes, this radio's codeplug region holds %d (update the cfw)" % (len(data), inf["size"]))
        lines = D.diff(old, new)
        log("diff against the radio (%s):" % D.summary(old, new))
        for l in lines:
            log("  " + l)
        if confirm is not None and not confirm(lines):
            r.end()
            log("cancelled, nothing written")
            return None
        log("writing %d bytes ..." % len(data))
        r.write_codeplug(data, progress)
        ok = r.end()
        if not ok:
            raise link.LinkError("radio says the written codeplug is invalid (END -> NAK)")
        return data, new

    res = link.with_radio(port, fn, log, allow_hardware=allow_hardware, writing=True, timeout=timeout)
    if res is None:
        return None
    data, new = res
    if verify:
        _, back, inf = read_radio(port, log=lambda s: None, timeout=timeout)
        if back != data:
            raise link.LinkError("read-back differs from what was written (%d vs %d bytes)" % (len(back), len(data)))
        log("verified: read back %d bytes, identical (CRC %08X)" % (len(back), inf["crc"]))
    cp.generation, cp.created = new.generation, new.created
    return data
