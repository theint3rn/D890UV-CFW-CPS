"""CSV import/export.

* CHIRP CSV (FM): Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,...
* cfw channel CSV (qdmr-like, every mode): see CFW_COLUMNS; `cfw_cps export x.csv` writes this format.
"""
import csv
import io

from . import codeplug as C

CFW_COLUMNS = ["name", "rx_mhz", "tx_mhz", "mode", "bw", "power", "rx_tone", "tx_tone", "cc", "slot", "tg", "contact",
               "nac", "wacn", "sysid", "ran", "dgid", "ur", "rpt1", "rpt2", "trunk", "scanlist", "zone"]


class CsvError(ValueError):
    pass


def _mhz(s):
    s = (s or "").strip()
    return int(round(float(s) * 1e6)) if s else 0


def _int(s, default=0):
    s = (s or "").strip()
    if not s:
        return default
    return int(s, 0)


def sniff(text):
    head = text.lstrip("﻿").splitlines()[0].lower() if text.strip() else ""
    if "location" in head and "frequency" in head and "duplex" in head:
        return "chirp"
    if "rx_mhz" in head and "mode" in head:
        return "cfw"
    raise CsvError("unknown CSV format (want CHIRP or cfw columns)")


def read_chirp(text):
    chans = []
    for i, r in enumerate(csv.DictReader(io.StringIO(text.lstrip("﻿")))):
        mode = (r.get("Mode") or "FM").strip()
        if mode not in ("FM", "NFM"):
            continue                                   # AM / DV / WFM rows are skipped
        rx = _mhz(r.get("Frequency"))
        dup, off = (r.get("Duplex") or "").strip(), _mhz(r.get("Offset"))
        tx = {"+": rx + off, "-": rx - off, "split": off, "off": 0}.get(dup, rx)
        c = C.Channel(name=(r.get("Name") or "CH%d" % (i + 1)).strip()[:16], rx_hz=rx, tx_hz=tx, mode="FM",
                      wide=mode == "FM")
        tone = (r.get("Tone") or "").strip()
        rt, ct = (r.get("rToneFreq") or "88.5").strip(), (r.get("cToneFreq") or "88.5").strip()
        pol = (r.get("DtcsPolarity") or "NN").strip().upper() + "NN"
        code = "%03d" % int(r.get("DtcsCode") or 23)
        if tone == "Tone":
            c.tx_tone = rt
        elif tone == "TSQL":
            c.tx_tone = c.rx_tone = ct
        elif tone == "DTCS":
            c.tx_tone = "D%s%s" % (code, "I" if pol[0] == "R" else "N")
            c.rx_tone = "D%s%s" % (code, "I" if pol[1] == "R" else "N")
        elif tone == "Cross":
            cm = (r.get("CrossMode") or "Tone->Tone").strip()
            a, _, b = cm.partition("->")
            c.tx_tone = rt if a == "Tone" else ("D%sN" % code if a == "DTCS" else None)
            c.rx_tone = ct if b == "Tone" else ("D%sN" % code if b == "DTCS" else None)
        if (r.get("Skip") or "").strip() == "S":
            c.scan_skip = True
        chans.append(C.normalize_channel(c))
    return chans


def read_cfw(text, cp=None):
    """Returns (channels, zone_name -> [channel indices relative to the returned list])."""
    chans, zones = [], {}
    for i, r in enumerate(csv.DictReader(io.StringIO(text.lstrip("﻿")))):
        try:
            mode = (r.get("mode") or "FM").strip().upper()
            mode = {"P25P1": "P25", "D-STAR": "DSTAR", "C4FM": "YSF"}.get(mode, mode)
            if mode not in C.MODES:
                raise CsvError("mode %r" % mode)
            c = C.Channel(name=(r.get("name") or "").strip()[:16], rx_hz=_mhz(r.get("rx_mhz")), mode=mode)
            c.tx_hz = _mhz(r.get("tx_mhz")) if (r.get("tx_mhz") or "").strip() else c.rx_hz
            c.wide = (r.get("bw") or "").strip() in ("25", "25k", "wide")
            c.power = (r.get("power") or "high").strip().lower() or "high"
            c.rx_tone = (r.get("rx_tone") or "").strip() or None
            c.tx_tone = (r.get("tx_tone") or "").strip() or None
            c.cc = _int(r.get("cc"), 1)
            c.slot = _int(r.get("slot"), 1)
            c.tg = _int(r.get("tg"), 0)
            ct = (r.get("contact") or "").strip()
            c.contact = int(ct) - 1 if ct else None
            c.nac = _int(r.get("nac"), 0x293)
            c.wacn = _int(r.get("wacn"), 0)
            c.sysid = _int(r.get("sysid"), 0)
            c.ran = _int(r.get("ran"), 0)
            c.dgid = _int(r.get("dgid"), 0)
            c.ur, c.rpt1, c.rpt2 = [(r.get(k) or "").strip().upper()[:8] for k in ("ur", "rpt1", "rpt2")]
            c.trunk = (r.get("trunk") or "").strip().lower() in ("1", "y", "yes", "true")
            sl = (r.get("scanlist") or "").strip()
            c.scanlist = int(sl) - 1 if sl else None
        except (ValueError, CsvError) as e:
            raise CsvError("row %d: %s" % (i + 2, e))
        for z in (r.get("zone") or "").split("|"):
            if z.strip():
                zones.setdefault(z.strip(), []).append(len(chans))
        chans.append(C.normalize_channel(c))
    return chans, zones


def import_csv(path, cp=None):
    """Returns a new Codeplug (or appends to `cp`) and a report line."""
    text = open(path, encoding="utf-8-sig", newline="").read()
    kind = sniff(text)
    if cp is None:
        cp = C.new_codeplug()
        cp.channels = []
    base = len(cp.channels)
    if kind == "chirp":
        chans, zones = read_chirp(text), {}
    else:
        chans, zones = read_cfw(text)
    cp.channels.extend(chans)
    for name, mem in zones.items():
        z = next((z for z in cp.zones if z.name == name), None)
        if z is None:
            z = C.Zone(name[:16], [])
            cp.zones.append(z)
        z.channels.extend(base + m for m in mem)
    return cp, "%s CSV: %d channels, %d zones" % (kind, len(chans), len(zones))


def export_csv(cp):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(CFW_COLUMNS)
    inzone = {}
    for z in cp.zones:
        for m in z.channels:
            inzone.setdefault(m, []).append(z.name)
    for i, c in enumerate(cp.channels):
        d = c.mode in ("DMR", "P25", "P25P2", "NXDN")
        w.writerow([c.name, "%.5f" % (c.rx_hz / 1e6), "%.5f" % (c.tx_hz / 1e6) if c.tx_hz else "0", c.mode,
                    ("25" if c.wide else "12.5") if c.mode == "FM" else "", c.power, c.rx_tone or "", c.tx_tone or "",
                    c.cc if c.mode == "DMR" else "", c.slot if c.mode in ("DMR", "P25P2") else "",
                    c.tg if d else "", c.contact + 1 if (d and c.contact is not None) else "",
                    "0x%X" % c.nac if c.mode in ("P25", "P25P2") else "",
                    "0x%X" % c.wacn if c.mode in ("P25", "P25P2") and c.wacn else "",
                    "0x%X" % c.sysid if c.mode in ("P25", "P25P2") and c.sysid else "",
                    c.ran if c.mode == "NXDN" else "", c.dgid if c.mode == "YSF" else "",
                    c.ur if c.mode == "DSTAR" else "", c.rpt1 if c.mode == "DSTAR" else "",
                    c.rpt2 if c.mode == "DSTAR" else "", "1" if c.trunk else "",
                    c.scanlist + 1 if c.scanlist is not None else "", "|".join(inzone.get(i, []))])
    return out.getvalue()
