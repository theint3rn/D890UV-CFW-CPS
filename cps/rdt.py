"""Stock D890UV CPS file (.rdt, version V1323, model "D890UV") and stock D168UV CPS file (V1292, model "D168UV"):
lossless reader / writer.

The stock CPS serialises its tables field by field (little endian, NUL-terminated strings with a maximum length). The
layout below was decoded by comparing a real codeplug saved by the stock CPS (V1323) with the same codeplug in the
D878UV format (V1270, cps/import_rdt.py) and with the stock CSV export of both (docs/STOCK_CPS_MAP.md):

  header      0x00-0x80 fixed (u32 at 5 = file length - 14) | cstr(16) power-on line 1 | cstr(8) password | 11 B | cstr(16) line 2 | 94 B
  channels    u16 count, {u16 slot (VFO A/B = 4000/4001), 46 B (V1270 layout), cstr(16) name, 50 B}
  radio IDs   u8 count, {u8 idx, u24 ID, cstr(16) name}
  zones       u8 count, {u8 idx, u8 n, (n+2) u16 slots (members, A, B), cstr(16) name}, then 3 B per zone
  scan lists  u8 count, {u8 idx, cstr(16) name, 14 B, u8 n, n x (u8, u16 slot)}
  talkgroups  u8, u16 count, 3 B, {u24 ID, u16 idx (1-based), u8 type, six 7-bit packed strings}
  user DB     u8, u24 count, 3 B, the same records (RadioID users)
  SMS         3 B, u8 count, {u8 idx, cstr(200)}
  FM          u8 count, {u8 idx, u8 flag, u16 freq (10 kHz), cstr(16) name}
  RX groups   u8 count, {u8 idx, cstr(16) name, u8 n, n x u16 talkgroup index}
  tail        everything after (alert tones, APRS, roaming, GPS roaming, AM, encryption codes, NXDN, hot keys, ...):
              kept byte for byte. Decoded inside it: the NXSetting block (nx_row / nx_patch; it sits a fixed
              distance before the end of the file, apart from the TxAliasName cstr).

D168UV (V1292) differs from this layout in (LAYOUT below): header C 90 B; channel tail 35 B; one extra byte after each
zone name (not 3 B per zone after the list); scan list header 11 B; talkgroups and user DB carry a byte length instead
of a count (u8, u16 length, u8 / u8, u24 length, u8; length counts from the byte after the length field); FM records
have no name and end with the VFO record (idx 100); no NXSetting.

load() gives a cfw Codeplug (cps/stock.from_stock of the decoded tables) that remembers the parsed file; save() writes
the remembered file back with the decoded sections rebuilt from the Codeplug, so open + save is byte-identical and
edits of channels / zones / scan lists / talkgroups / contacts / SMS / FM / RX groups / radio IDs / power-on texts / OptionalSetting
(mapped fields) / NXSetting are written. Edits of tail tables (APRS, roaming, ...) are NOT written to an .rdt (use the stock CSV set) - save() says so.
"""
import copy
import os
import struct

from . import codeplug as C, stock as ST

_SCHEMA_DIR = os.path.dirname(ST._schema_path())
_MAP = os.path.join(_SCHEMA_DIR, "rdt_map.json")
# Template ("new file") for writing an .rdt that was not opened from one (new codeplug, CSV import, model change, new
# channels): a codeplug saved by the stock CPS right after File > New. It is not shipped with cfw_cps; the user points
# to their own (see template_path / README "Stock .rdt files").
TEMPLATE_FILES = {"D890UV": "new_v1323.rdt", "D168UV": "new_v1292.rdt"}
TEMPLATE_ENV = "CFW_CPS_RDT_TEMPLATE_%s"            # one file per model, e.g. CFW_CPS_RDT_TEMPLATE_D890UV=/path/new.rdt
TEMPLATE_DIR_ENV = "CFW_CPS_RDT_DIR"                # a folder holding new_v1323.rdt / new_v1292.rdt
TEMPLATE_USER_DIR = os.path.join(os.path.expanduser("~"), ".config", "cfw_cps")
_TEMPLATE = {}                                       # model -> path chosen in this run (set_template)
# power-on texts of the stock new file the rdt_map experiments were made on (channel offsets depend on their length)
REF_TEXTS = {"D890UV": ("WELCOME", "", "ANYTONE"), "D168UV": ("", "", "")}
# base-file header layout (new file, V1323): A = 0x00-0x80, line 1 at 0x81 (8 B), password 0x89 (1 B), B = 0x8A-0x94,
# line 2 at 0x95 (8 B), C = 0x9D-0xFA. Experiment offsets are converted to (segment, offset in segment).

LAYOUT = {
    "D890UV": {"version": "V1323", "map": _MAP, "C": 94, "chan_tail": 50, "zone_extra": ("after", 3),
               "scan_hdr": 14, "tg_pre": 6, "user_pre": 7, "counted": True, "fm_name": True,
               "segs": ((0, 0x81), (0x8A, 0x95), (0x9D, 0xFB))},
    "D168UV": {"version": "V1292",
               "map": os.path.join(_SCHEMA_DIR, "rdt_map_d168.json"), "C": 90, "chan_tail": 35, "zone_extra": ("inline", 1),
               "scan_hdr": 11, "tg_pre": 4, "user_pre": 5, "counted": False, "fm_name": False,
               # experiment reference: empty power-on texts -> line 1 at 0x81, password 0x82, B 0x83-0x8D, line 2 0x8E
               "segs": ((0, 0x81), (0x83, 0x8E), (0x8F, 0xE9)),
               # a second Optional Setting block sits in the tail a fixed distance before the end of the file (the same
               # 23 360 B in the 24 713-byte reference and in a real codeplug): offsets >= end_from are addressed from the end
               "end_from": 0x400},
}


def _opt_fields(model="D890UV"):
    """OptionalSetting column -> (segment, offset) for one-byte header fields found by the experiments"""
    import json
    L = LAYOUT[model]
    mm = json.load(open(L["map"])) if os.path.exists(L["map"]) else {}
    m, ref = mm.get("OptionalSetting", {}), mm.get("_ref_len", {}).get("OptionalSetting")
    out = {}
    for col, offs in m.items():
        if len(offs) != 1:
            continue
        o = offs[0]
        for seg, (a, b) in zip("ABC", L["segs"]):
            if a <= o < b:
                out[col] = (seg, o - a)
        if L.get("end_from") and ref and L["end_from"] <= o < ref:
            out[col] = ("E", ref - o)               # tail byte, distance from the end of the file
    return out


OPT_FIELDS = _opt_fields()
_OPT = {"D890UV": OPT_FIELDS}


def opt_fields(model):
    if model not in _OPT:
        _OPT[model] = _opt_fields(model)
    return _OPT[model]


def set_template(path, model=None):
    """use this stock CPS file as the .rdt template (model taken from the file); returns the model"""
    m = file_model(open(path, "rb").read(16))
    if m is None or (model and m != model):
        raise RdtError("%s is not a stock %s CPS file" % (path, model or "D890UV / D168UV"))
    _TEMPLATE[m] = os.path.abspath(path)
    return m


def template_path(model="D890UV"):
    """the .rdt template for a model, or None: set_template(), $CFW_CPS_RDT_TEMPLATE_<MODEL>, $CFW_CPS_RDT_DIR/<file>,
    ~/.config/cfw_cps/<file> (file = new_v1323.rdt for the D890UV, new_v1292.rdt for the D168UV)"""
    name = TEMPLATE_FILES[model]
    for p in (_TEMPLATE.get(model), os.environ.get(TEMPLATE_ENV % model),
              os.path.join(os.environ[TEMPLATE_DIR_ENV], name) if os.environ.get(TEMPLATE_DIR_ENV) else None,
              os.path.join(TEMPLATE_USER_DIR, name)):
        if p and os.path.isfile(p):
            return p
    return None


def template_help(model="D890UV"):
    return ("no stock %s .rdt template: cfw_cps does not ship one. In the stock %s CPS do File > New and save the empty "
            "codeplug, then use it with --rdt-template FILE, $%s, $%s/%s or ~/.config/cfw_cps/%s (opening an .rdt and saving "
            "it again needs no template)" % (model, model, TEMPLATE_ENV % model, TEMPLATE_DIR_ENV, TEMPLATE_FILES[model],
                                              TEMPLATE_FILES[model]))


def default_rdt(model="D890UV"):
    p = template_path(model)
    if p is None:
        raise RdtError(template_help(model))
    return p


def _default_file(model):
    """the template: the user's stock new file when given, else the built-in blank file (blank_file)"""
    p = template_path(model)
    return parse(open(p, "rb").read()) if p else blank_file(model)


# ------------------------------------------------------------------ built-in blank file
# A blank .rdt made from the layout above and cfw_cps's own defaults (the schema's stock default values, written at the
# offsets of rdt_map*.json); no bytes are taken from a stock file. Unknown bytes are zero, except format bytes the stock
# CPS checks when it loads a file (found by loading test files into the stock CPS V1.05 / D168 V1.07: it answers
# "Get_FileData_Ver_Error" or "file error." without them). The undecoded tail is zeros of the stock length.
BLANK = {
    # tail: the stock reader needs non-empty strings (cstr lengths keep the following fields in place), record counts
    # and the version trailer; the strings are cfw_cps's own (same lengths): APRS destination / source / path /
    # symbol+comment, a roaming channel and roaming zone, the AM air channel and AM VFO
    "D890UV": {"tail_len": 22881, "hdr": {23: 1}, "tg_pre": {}, "user_pre": {4: 1}, "sms_pre": [1, 0, 0],
               "tail": {126: b"APZCFW", 133: b"N0CALL", 140: b"WIDE1-1,WIDE2-1", 156: b"/[N0CALL", 167: 1,
                        181: b"Roam Chan 01", 194: 1, 198: b"Roam List 1", 210: 1,
                        # AM air: 2 records (scan flag, u32 frequency in 10 Hz = 118.000 MHz, name): channel 1, VFO
                        22360: 2, 22364: 1, 22365: struct.pack("<I", 11800000), 22369: b"AIR 01",
                        22377: 1, 22379: struct.pack("<I", 11800000), 22383: b"VFO", 22876: b"V1323"}},
    # D168 tail: APRS destination (6 chars, no NUL), a flag byte, source, path (two 7-char calls, no NUL between),
    # symbol+comment, a roaming channel and roaming zone, the version trailer
    "D168UV": {"tail_len": 24052, "hdr": {23: 1}, "tg_pre": {}, "user_pre": {}, "sms_pre": [1, 0, 0],
               "tail": {126: b"APZCFW\x01N0CALL", 140: b"WIDE1-1WIDE2-1", 155: b"/[N0CALL", 166: 1,
                        180: b"Roaming Chan 1", 195: 1, 199: b"Roam List 1", 211: 1, 24047: b"V1292"}},
}
HW_VERSION = b"V100"
FM_VFO = {"idx": 100, "flag": 0, "freq": 8750, "name": ""}       # FM radio VFO record (87.50 MHz)                                 # header 19-22, as in the radio's identify reply


def _blank_channel(model):
    """channel record for a channel that never was in an .rdt (no template): zeros + the schema's Custom CTCSS
    default; _ch_record writes every mapped column from the stock row"""
    x = bytearray(48)
    ch = dict(zip(ST.schema_of(model)["tables"]["Channel"]["columns"], ST.schema_of(model)["tables"]["Channel"]["defaults"]))
    try:
        struct.pack_into("<H", x, 26, int(round(float(ch.get("Custom CTCSS", "0")) * 10)))
    except ValueError:
        pass
    x[34] = 0xFF                                     # no scan list
    return {"fixed": bytes(x), "name": "", "tail": bytes(LAYOUT[model]["chan_tail"])}


def blank_file(model="D890UV"):
    """parsed-file structure of an empty codeplug (one contact: the stock CPS refuses a file without one)"""
    L, B = LAYOUT[model], BLANK[model]
    a = bytearray(0x81)
    a[0:5] = L["version"].encode()
    a[9:15] = model.encode()
    a[19:23] = HW_VERSION
    for k, v in B["hdr"].items():
        a[k] = v
    segs = {"A": a, "B": bytearray(L["segs"][1][1] - L["segs"][1][0]), "C": bytearray(L["C"]),
            "E": bytearray(B["tail_len"])}
    for k, v in B["tail"].items():
        if isinstance(v, int):
            segs["E"][k] = v
        else:
            segs["E"][k:k + len(v)] = v
    sch = ST.schema_of(model)["tables"]["OptionalSetting"]
    opt = dict(zip(sch["columns"], sch["defaults"]))
    for k, (seg, o) in opt_fields(model).items():
        try:
            v = int(opt.get(k, ""))
        except ValueError:
            continue
        if 0 <= v <= 255:
            if seg == "E":
                segs["E"][len(segs["E"]) - o] = v
            else:
                segs[seg][o] = v
    tg_pre, user_pre = bytearray(L["tg_pre"]), bytearray(L["user_pre"])
    for k, v in B["tg_pre"].items():
        tg_pre[k] = v
    for k, v in B["user_pre"].items():
        user_pre[k] = v
    f = {"version": L["version"], "model": model, "A": bytes(segs["A"]), "line1": "", "password": "", "B": bytes(segs["B"]),
         "line2": "", "C": bytes(segs["C"]), "channels": [], "ids": [], "zones": [], "scans": [], "tg_pre": bytes(tg_pre),
         "tgs": [_default_contact()], "user_pre": bytes(user_pre), "users": [], "sms_pre": bytes(B["sms_pre"]), "sms": [], "fm": [],
         "rxgroups": [], "tail": bytes(segs["E"])}
    if not L["fm_name"]:
        f["fm_vfo"] = dict(FM_VFO)           # D168: the stock CPS refuses a file without the FM VFO record
    return f


def _default_contact():
    return {"id": 1, "idx": 1, "type": 0x10, "strs": ["Contact 1", "", "", "", "", ""], "raw": b""}


def blank_rdt(model="D890UV"):
    """bytes of the built-in blank .rdt"""
    return serialise(blank_file(model))


def _nx_fields():
    """NXSetting layout in the tail (from the experiments). The block sits a fixed distance before the end of the file,
    except for the variable-length alias cstr (TxAliasName): fields after it are addressed from the end of the file,
    fields before it from the start of the alias. -> (alias end-offset, {col: ("pre", bytes before alias, size) |
    ("post", bytes from file end, 1)}) or None"""
    import json
    if not os.path.exists(_MAP):
        return None
    m = json.load(open(_MAP))
    nx, ref = m.get("NXSetting", {}), m.get("_ref_len", {}).get("NXSetting")
    if len(nx.get("TxAliasEn", [])) != 1 or not ref:
        return None
    alias = nx["TxAliasEn"][0] + 1           # the alias cstr follows TxAliasEn (its own experiment changes the length)
    pre = sorted((offs[0], c) for c, offs in nx.items() if len(offs) == 1 and offs[0] < alias)
    out = {}
    for i, (o, c) in enumerate(pre):
        nxt = pre[i + 1][0] if i + 1 < len(pre) else alias
        out[c] = ("pre", alias - o, nxt - o)
    for c, offs in nx.items():
        if len(offs) == 1 and offs[0] > alias:
            out[c] = ("post", ref - offs[0], 1)
    return ref - alias, out


NX = _nx_fields()
NX_ALIAS_MAX = 16


def _nx_find(tail):
    """-> (start of the alias in tail, alias length) or None when the NX block is not where the layout says.
    The alias NUL is always NX[0] bytes before the end; the alias is the run of printable bytes before it (the byte
    before the alias is TxAliasEn, 0/1)."""
    if not NX or len(tail) < NX[0] + 16:
        return None
    nul = len(tail) - NX[0]
    if tail[nul] != 0:
        return None
    a = nul
    while a > nul - NX_ALIAS_MAX and 0x20 <= tail[a - 1] < 0x7F:
        a -= 1
    if tail[a - 1] not in (0, 1):
        return None
    return a, nul - a


def nx_row(tail):
    """NXSetting row decoded from the file tail, or None"""
    loc = _nx_find(tail)
    if loc is None:
        return None
    a, L = loc
    cols = ST.TABLES["NXSetting"]["columns"]
    row = list(ST.default_rows("NXSetting")[0])
    names = {c.strip(): c for c in cols}
    for c, (kind, d, size) in NX[1].items():
        p = a - d if kind == "pre" else len(tail) - d
        v = int.from_bytes(tail[p:p + size], "little")
        if names.get(c.strip()) in cols:
            row[cols.index(names[c.strip()])] = str(v)
    row[cols.index("TxAliasName")] = tail[a:a + L].decode("latin1")
    return row


def nx_patch(tail, row):
    """tail with the NXSetting row written into it (None if the block cannot be located)"""
    loc = _nx_find(tail)
    if loc is None:
        return None
    a, L = loc
    cols = ST.TABLES["NXSetting"]["columns"]
    r = {c.strip(): v for c, v in zip(cols, row)}
    alias = r.get("TxAliasName", "").encode("latin1", "replace")[:NX_ALIAS_MAX]
    alias = bytes(ch if 0x20 <= ch < 0x7F else 0x3F for ch in alias)
    t = bytearray(tail[:a]) + alias + bytearray(tail[a + L:])
    a2 = a
    for c, (kind, d, size) in NX[1].items():
        try:
            v = int(r.get(c.strip(), ""))
        except ValueError:
            continue
        if not 0 <= v < (1 << (8 * size)):
            continue
        p = a2 - d if kind == "pre" else len(t) - d
        t[p:p + size] = v.to_bytes(size, "little")
    return bytes(t)


class RdtError(ValueError):
    pass


def _cstr(d, p, mx):
    e = p
    while e < p + mx and e < len(d) and d[e] != 0:
        e += 1
    s = d[p:e].decode("latin1")
    if e < p + mx:
        e += 1
    return s, e


def _wcstr(s, mx):
    b = s.encode("latin1", "replace")[:mx]
    return b + (b"\0" if len(b) < mx else b"")


def _s7(d, p, nstr=6):
    bits = n = 0
    out, cur, q = [], [], p
    while len(out) < nstr:
        while n < 7:
            if q >= len(d):
                raise RdtError("packed string runs past the end")
            bits |= d[q] << n
            n += 8
            q += 1
        c = bits & 0x7F
        bits >>= 7
        n -= 7
        if c == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(chr(c))
    return out, q


def _w7(strs):
    bits = n = 0
    out = bytearray()
    for s in strs:
        for ch in list(s.encode("ascii", "replace")) + [0]:
            bits |= (ch & 0x7F) << n
            n += 7
            while n >= 8:
                out.append(bits & 0xFF)
                bits >>= 8
                n -= 8
    if n:
        out.append(bits & 0xFF)
    return bytes(out)


# ------------------------------------------------------------------ structural parse / serialise (lossless)

def file_model(d):
    m = d[9:15].decode("latin1")
    return m if m in LAYOUT else None


def parse(d):
    model = file_model(d)
    if model is None:
        raise RdtError("not a stock D890UV / D168UV CPS file (model %r)" % d[9:15])
    L = LAYOUT[model]
    f = {"version": d[:5].decode("latin1"), "model": model}
    p = 0x81
    f["A"] = d[:p]
    f["line1"], p = _cstr(d, p, 16)
    f["password"], p = _cstr(d, p, 8)
    f["B"], p = d[p:p + 11], p + 11
    f["line2"], p = _cstr(d, p, 16)
    f["C"], p = d[p:p + L["C"]], p + L["C"]
    n = struct.unpack_from("<H", d, p)[0]
    p += 2
    chans = []
    T = L["chan_tail"]
    for _ in range(n):
        fixed = d[p:p + 48]
        name, q = _cstr(d, p + 48, 16)
        chans.append({"fixed": fixed, "name": name, "tail": d[q:q + T]})
        p = q + T
    f["channels"] = chans
    n = d[p]
    p += 1
    ids = []
    for _ in range(n):
        idx, rid = d[p], d[p + 1] | d[p + 2] << 8 | d[p + 3] << 16
        name, p = _cstr(d, p + 4, 16)
        ids.append({"idx": idx, "id": rid, "name": name})
    f["ids"] = ids
    n = d[p]
    p += 1
    zones = []
    zx_where, zx_len = L["zone_extra"]
    for i in range(n):
        if d[p] != i:
            raise RdtError("zone %d at 0x%X" % (i, p))
        m = d[p + 1]
        slots = list(struct.unpack_from("<%dH" % (m + 2), d, p + 2))
        name, p = _cstr(d, p + 2 + 2 * (m + 2), 16)
        zones.append({"slots": slots[:m], "a": slots[m], "b": slots[m + 1], "name": name})
        if zx_where == "inline":
            zones[-1]["extra"] = d[p:p + zx_len]
            p += zx_len
    if zx_where == "after":
        for z in zones:
            z["extra"] = d[p:p + zx_len]
            p += zx_len
    f["zones"] = zones
    n = d[p]
    p += 1
    scans = []
    H = L["scan_hdr"]
    for i in range(n):
        if d[p] != i:
            raise RdtError("scan list %d at 0x%X" % (i, p))
        name, p = _cstr(d, p + 1, 16)
        hdr = d[p:p + H]
        m = d[p + H]
        p += H + 1
        mem = [(d[p + 3 * k], struct.unpack_from("<H", d, p + 3 * k + 1)[0]) for k in range(m)]
        p += 3 * m
        scans.append({"name": name, "hdr": hdr, "members": mem})
    f["scans"] = scans
    k = L["tg_pre"]
    f["tg_pre"] = d[p:p + k]
    if L["counted"]:
        n = struct.unpack_from("<H", d, p + 1)[0]
        p += k
        f["tgs"], p = _records(d, p, n)
    else:
        end = p + 3 + struct.unpack_from("<H", d, p + 1)[0]
        p += k
        f["tgs"], p = _records(d, p, None, end)
    k = L["user_pre"]
    f["user_pre"] = d[p:p + k]
    if L["counted"]:
        n = d[p + 1] | d[p + 2] << 8 | d[p + 3] << 16
        p += k
        f["users"], p = _records(d, p, n)
    else:
        end = p + 4 + (d[p + 1] | d[p + 2] << 8 | d[p + 3] << 16)
        p += k
        f["users"], p = _records(d, p, None, end)
    f["sms_pre"] = d[p:p + 3]
    n = d[p + 3]
    p += 4
    sms = []
    for i in range(n):
        if d[p] != i:
            raise RdtError("SMS %d at 0x%X" % (i, p))
        t, p = _cstr(d, p + 1, 200)
        sms.append(t)
    f["sms"] = sms
    n = d[p]
    p += 1
    fm = []
    for _ in range(n):
        idx, flag, fr = d[p], d[p + 1], struct.unpack_from("<H", d, p + 2)[0]
        if L["fm_name"]:
            name, p = _cstr(d, p + 4, 16)
        else:
            name, p = "", p + 4
        fm.append({"idx": idx, "flag": flag, "freq": fr, "name": name})
    if not L["fm_name"]:                    # D168: the last record is the FM VFO (idx 100), not a list entry
        f["fm_vfo"] = fm.pop() if fm and fm[-1]["idx"] == 100 else None
    f["fm"] = fm
    n = d[p]
    p += 1
    rg = []
    for i in range(n):
        if d[p] != i:
            raise RdtError("RX group list %d at 0x%X" % (i, p))
        name, p = _cstr(d, p + 1, 16)
        m = d[p]
        rg.append({"name": name, "members": list(struct.unpack_from("<%dH" % m, d, p + 1))})
        p += 1 + 2 * m
    f["rxgroups"] = rg
    f["tail"] = d[p:]
    return f


def _records(d, p, n, end=None):
    """n records (counted, D890) or records up to byte offset end (D168)"""
    out = []
    while (len(out) < n) if end is None else (p < end):
        rid = d[p] | d[p + 1] << 8 | d[p + 2] << 16
        idx, ty = struct.unpack_from("<HB", d, p + 3)
        s, q = _s7(d, p + 6)
        out.append({"id": rid, "idx": idx, "type": ty, "strs": s, "raw": d[p:q]})
        p = q
    return out, p


def _wrecords(recs):
    b = bytearray()
    for r in recs:
        enc = struct.pack("<I", r["id"])[:3] + struct.pack("<HB", r["idx"], r["type"]) + _w7(r["strs"])
        # keep the original bytes when the content did not change (padding bits can differ)
        b += r["raw"] if r.get("raw") and _same_record(r) else enc
    return bytes(b)


def _same_record(r):
    try:
        cid = r["raw"][0] | r["raw"][1] << 8 | r["raw"][2] << 16
        idx, ty = struct.unpack_from("<HB", r["raw"], 3)
        s, _ = _s7(r["raw"], 6)
        return (cid, idx, ty, s) == (r["id"], r["idx"], r["type"], r["strs"])
    except (RdtError, struct.error, IndexError):
        return False


def serialise(f):
    L = LAYOUT[f.get("model", "D890UV")]
    b = bytearray(f["A"])
    b += _wcstr(f["line1"], 16) + _wcstr(f["password"], 8) + f["B"] + _wcstr(f["line2"], 16) + f["C"]
    b += struct.pack("<H", len(f["channels"]))
    for c in f["channels"]:
        b += c["fixed"] + _wcstr(c["name"], 16) + c["tail"]
    b.append(len(f["ids"]))
    for r in f["ids"]:
        b += bytes([r["idx"]]) + struct.pack("<I", r["id"])[:3] + _wcstr(r["name"], 16)
    b.append(len(f["zones"]))
    inline = L["zone_extra"][0] == "inline"
    for i, z in enumerate(f["zones"]):
        b += bytes([i, len(z["slots"])]) + struct.pack("<%dH" % (len(z["slots"]) + 2), *(z["slots"] + [z["a"], z["b"]]))
        b += _wcstr(z["name"], 16)
        if inline:
            b += z["extra"]
    if not inline:
        for z in f["zones"]:
            b += z["extra"]
    b.append(len(f["scans"]))
    for i, s in enumerate(f["scans"]):
        b += bytes([i]) + _wcstr(s["name"], 16) + s["hdr"] + bytes([len(s["members"])])
        for x, slot in s["members"]:
            b += bytes([x]) + struct.pack("<H", slot)
    pre, recs = bytearray(f["tg_pre"]), _wrecords(f["tgs"])
    pre[1:3] = struct.pack("<H", len(f["tgs"]) if L["counted"] else len(pre) - 3 + len(recs))
    if L["counted"]:
        pre[3:5] = struct.pack("<H", len(recs) + 1)      # D890: record bytes + 1 (the stock CPS checks it)
    b += pre + recs
    pre, recs = bytearray(f["user_pre"]), _wrecords(f["users"])
    pre[1:4] = struct.pack("<I", len(f["users"]) if L["counted"] else len(pre) - 4 + len(recs))[:3]
    if L["counted"] and pre[4] | pre[5] << 8 | pre[6] << 16 < len(recs) + 1:
        pre[4:7] = struct.pack("<I", len(recs) + 1)[:3]   # D890: at least record bytes + 1 (smaller: Ver_Error)
    b += pre + recs
    sp = bytearray(f["sms_pre"])
    if sp[0] in (0, 1):
        sp[0] = 0 if f["users"] else 1                # as the stock CPS writes it (1 = empty user database)
    b += sp + bytes([len(f["sms"])])
    for i, t in enumerate(f["sms"]):
        b += bytes([i]) + _wcstr(t, 200)
    fm = list(f["fm"]) + ([f["fm_vfo"]] if f.get("fm_vfo") else [])
    b.append(len(fm))
    for r in fm:
        b += bytes([r["idx"], r["flag"]]) + struct.pack("<H", r["freq"]) + (_wcstr(r["name"], 16) if L["fm_name"] else b"")
    b.append(len(f["rxgroups"]))
    for i, g in enumerate(f["rxgroups"]):
        b += bytes([i]) + _wcstr(g["name"], 16) + bytes([len(g["members"])]) + struct.pack("<%dH" % len(g["members"]), *g["members"])
    b += f["tail"]
    struct.pack_into("<I", b, 5, len(b) - 14)      # header: file length - 14 (the stock CPS refuses a file without it)
    return bytes(b)


# ------------------------------------------------------------------ file <-> stock tables

POWER = ["Low", "Middle", "High", "Turbo"]
TYPES = ["A-Analog", "D-Digital", "A+D TX A", "D+A TX D"]
CALLTYPE = {0x10: "Group Call", 0x00: "Private Call", 0x20: "All Call"}
CALLTYPE_R = {v: k for k, v in CALLTYPE.items()}
BUSY = {False: {0: "Off", 2: "Channel Free"}, True: {0: "Always", 1: "Channel Free", 2: "Different Color Code"}}   # by digital
BUSY_D168 = {False: {0: "Off", 2: "Busy"}, True: BUSY[True]}            # the D168 CPS calls analog busy lock "Busy"
ONOFF = ["Off", "On"]
# channel columns held in single record bytes: column -> (byte (48+ = tail), values)
CH_BYTES = {"Squelch Mode": (33, ["Carrier", "CTCSS/DCS"]), "PTT Prohibit": (15, ONOFF), "Talk Around(Simplex)": (17, ONOFF),
            "Digital Duplex": (42, ONOFF), "AES Digital Encryption": (47, ["Normal Encryption", "Enhanced Encryption"]),
            "2TONE Decode": (48, None), "txcc": (97, None),
            # tail bytes from the stock-CPS import/save/diff map (schema/rdt_map.json, value byte = CSV value)
            "Exclude channel from roaming": (59, None), "DMR MODE": (60, None), "DataACK Disable": (65, None), "R5toneBot": (66, None), "R5ToneEot": (67, None), "Auto Scan": (68, None), "Ana APRS Mute": (69, None), "Send Talker Alias DMR/NX": (70, None), "AnaAprsTxPath": (72, None), "ARC4": (73, None), "ex_emg_kind": (74, None), "Rpga_Mdc": (75, None), "DisturEn": (76, None), "DisturFreq": (77, None), "dmr_crc_ignore": (78, None), "compand": (79, None), "dup_call": (80, None), "tx_int": (81, None), "BtRxState": (82, None), "idle_tx": (83, None), "tx_talkalaes": (84, None), "nxdn_wn": (85, None), "NxdnRpga": (86, None), "nxdnSqCon": (87, None), "NxdnTxBusy": (88, None), "NxDnPttId": (89, None), "EnRan": (90, None), "DeRan": (91, None), "NxdnEncry": (92, None), "NxdnGroupId": (93, None), "NxdnIdNum": (94, None), "NxdnStateNum": (96, None)}
# D168UV: channel columns held in single record bytes (the fixed 48 bytes have the V1270 layout; tail positions from
# schema/rdt_map_d168.json are added by _ch_bytes)
CH_BYTES_D168 = {"Squelch Mode": (33, ["Carrier", "CTCSS/DCS"]), "PTT Prohibit": (15, ONOFF), "Idle TX": (42, ONOFF),
                 "AES Digital Encryption": (47, ["Normal Encryption", "Enhanced Encryption"])}
# D168: byte 17 is "Talk Around(Simplex)" on analog channels and "Work Alone" on digital ones (experiment + a real codeplug)
D168_B17 = {False: "Talk Around(Simplex)", True: "Work Alone"}
_CHB = {"D890UV": CH_BYTES}


def _ch_bytes(model):
    if model not in _CHB:
        out = dict(CH_BYTES_D168)
        out.update(_map_tail_bytes(model))
        _CHB[model] = out
    return _CHB[model]


def _map_tail_bytes(model):
    """Channel columns the experiments found in one tail byte: {column: (48 + tail pos, None)} (value byte = CSV
    number) or (.., ONOFF) for Off/On columns"""
    import json
    L = LAYOUT[model]
    if not os.path.exists(L["map"]):
        return {}
    m = json.load(open(L["map"])).get("Channel", {})
    l1, pw, l2 = REF_TEXTS[model]
    first = 0x81 + len(_wcstr(l1, 16)) + len(_wcstr(pw, 8)) + 11 + len(_wcstr(l2, 16)) + L["C"] + 2
    tail0 = first + 48 + len(_wcstr("Channel 1", 16))       # the experiment's row 1 is "Channel 1"
    ch = ST.schema_of(model)["tables"]["Channel"]
    defaults = dict(zip(ch["columns"], ch["defaults"]))
    alias = dict(zip(ch.get("csv_columns", ch["columns"]), ch["columns"]))      # experiment names = stock CSV names
    out = {}
    for col, offs in m.items():
        col = alias.get(col, col)
        offs = [o for o in offs if o >= tail0]
        if len(offs) == 1 and offs[0] - tail0 < L["chan_tail"]:
            if defaults.get(col, "x").isdigit():
                out[col] = (48 + offs[0] - tail0, None)
            elif defaults.get(col) in ONOFF:
                out[col] = (48 + offs[0] - tail0, ONOFF)
    return out


SCAN_TIMES = {"Look Back Time A[s]": 7, "Look Back Time B[s]": 8, "Dropout Delay Time[s]": 9, "Dwell Time[s]": 10}


def _rb(c, pos):
    return c["fixed"][pos] if pos < 48 else c["tail"][pos - 48]


def _mhz(v10):
    return "%.5f" % (v10 * 10 / 1e6)


def _tone_text(sig, idx, dcs, custom):
    if sig == 1:
        v = C.CTCSS[idx] if idx < len(C.CTCSS) else custom
        return "%d.%d" % (v // 10, v % 10)
    if sig == 2:
        return "D%03o%s" % (dcs & 0x1FF, "I" if dcs & 0x200 else "N")
    return "Off"


def _tone_bytes(text, custom):
    """stock tone text -> (sig, ctcss idx, dcs code); None when not representable (keep the original bytes)"""
    if text == "Off":
        return 0, None, None
    if text.startswith("D"):
        try:
            return 2, None, int(text[1:4], 8) | (0x200 if text.endswith("I") else 0)
        except ValueError:
            return None
    try:
        v = int(round(float(text) * 10))
    except ValueError:
        return None
    if v in C.CTCSS:
        return 1, C.CTCSS.index(v), None
    return None


def tables_from_file(f):
    """parsed file -> {table: rows} for the decoded tables (others: stock defaults)."""
    model = f.get("model", "D890UV")
    ST.use(model)
    chb = _ch_bytes(model)
    busy = BUSY_D168 if model == "D168UV" else BUSY
    t = {}
    slot2ch = {}
    tg_names = [r["strs"][0] for r in f["tgs"]]
    scan_names = [s["name"] for s in f["scans"]]
    rows = []
    for c in f["channels"]:
        x = c["fixed"]
        slot, rx, sh, off = struct.unpack_from("<HIBI", x)
        tx = rx + off if sh == 1 else rx - off if sh == 2 else rx
        d = dict(ST.CH_DEFAULT_D)
        d.update({"No.": str(slot + 1), "Channel Name": c["name"], "Receive Frequency": _mhz(rx), "Transmit Frequency": _mhz(tx),
                  "Channel Type": TYPES[x[11] & 3], "Transmit Power": POWER[x[12] & 3], "Band Width": "25K" if x[13] == 1 else "12.5K",
                  "CTCSS/DCS Decode": _tone_text(x[18], x[19], struct.unpack_from("<H", x, 20)[0], struct.unpack_from("<H", x, 26)[0]),
                  "CTCSS/DCS Encode": _tone_text(x[22], x[23], struct.unpack_from("<H", x, 24)[0], struct.unpack_from("<H", x, 26)[0]),
                  "Custom CTCSS": "%.1f" % (struct.unpack_from("<H", x, 26)[0] / 10),
                  "RX Color Code": str(x[40]), "Slot": str((x[41] & 1) + 1),
                  "Scan List": scan_names[x[34]] if x[34] < len(scan_names) else "None"})
        dig = (x[11] & 3) in (1, 3)
        d["Busy Lock/TX Permit"] = busy[dig].get(x[32], d["Busy Lock/TX Permit"])
        for col, (pos, vals) in chb.items():
            v = _rb(c, pos)
            d[col] = (vals[v] if v < len(vals) else d[col]) if vals else str(v)
        if model == "D168UV" and x[17] < 2:
            d[D168_B17[dig]] = ONOFF[x[17]]
        d["Radio ID"] = f["ids"][x[35]]["name"] if x[35] < len(f["ids"]) else ""
        ci = struct.unpack_from("<H", x, 28)[0]
        if ci < len(f["tgs"]):
            r = f["tgs"][ci]
            d.update({"Contact/Talk Group": r["strs"][0], "Contact/Talk Group Call Type": CALLTYPE.get(r["type"] & 0x30, "Group Call"),
                      "Contact/Talk Group TG/DMR ID": str(r["id"])})
        slot2ch[slot] = (c["name"], d["Receive Frequency"], d["Transmit Frequency"])
        rows.append(d)
    t["Channel"] = [[r.get(k, "") for k in ST.CH_COLS] for r in rows]
    t["RadioIDList"] = [[str(i + 1), str(r["id"]), r["name"]] for i, r in enumerate(f["ids"])]

    def names(slots):
        ch = [slot2ch[s] for s in slots if s in slot2ch]
        return "|".join(c[0] for c in ch), "|".join(c[1] for c in ch), "|".join(c[2] for c in ch)
    zcols = ST.TABLES["DMRZone"]["columns"]
    t["DMRZone"] = []
    for i, z in enumerate(f["zones"]):
        a, b = slot2ch.get(z["a"], ("", "", "")), slot2ch.get(z["b"], ("", "", ""))
        nm, rx, tx = names(z["slots"])
        row = dict(zip(zcols, [""] * len(zcols)))
        row.update({"No.": str(i + 1), "Zone Name": z["name"], "Zone Channel Member": nm, "Zone Channel Member RX Frequency": rx,
                    "Zone Channel Member TX Frequency": tx, "A Channel": a[0], "A Channel RX Frequency": a[1],
                    "A Channel TX Frequency": a[2], "B Channel": b[0], "B Channel RX Frequency": b[1], "B Channel TX Frequency": b[2],
                    "Zone Hide ": str(z["extra"][0])})
        t["DMRZone"].append([row[k] for k in zcols])
    scols = ST.TABLES["ScanList"]["columns"]
    t["ScanList"] = []
    for i, s in enumerate(f["scans"]):
        nm, rx, tx = names([slot for _, slot in s["members"]])
        row = dict(zip(scols, ST.TABLES["ScanList"]["defaults"] or [""] * len(scols)))
        row.update({"No.": str(i + 1), "Scan List Name": s["name"], "Scan Channel Member": nm,
                    "Scan Channel Member RX Frequency": rx, "Scan Channel Member TX Frequency": tx})
        for col, pos in SCAN_TIMES.items():
            row[col] = "%.1f" % (s["hdr"][pos] / 10)
        h = s["hdr"]
        if not any(h[:7]):              # only the all-zero encoding is known (a real codeplug, the stock default)
            row.update({"Scan Mode": "Off", "Priority Channel Select": "Off", "Priority Channel 1": "Off",
                        "Priority Channel 2": "Off", "Revert Channel": "Selected"})
        t["ScanList"].append([row.get(k, "") for k in scols])
    t["DMRTalkGroups"] = [[str(i + 1), str(r["id"]), r["strs"][0], CALLTYPE.get(r["type"] & 0x30, "Group Call"), "None"]
                          for i, r in enumerate(f["tgs"])]
    t["DMRDigitalContactList"] = [[str(i + 1), str(r["id"]), r["strs"][2], r["strs"][0], r["strs"][1], r["strs"][3], r["strs"][4],
                                   r["strs"][5], CALLTYPE.get(r["type"] & 0x30, "Private Call"), "None"] for i, r in enumerate(f["users"])]
    t["PrefabricatedSMS"] = [[str(i + 1), s] for i, s in enumerate(f["sms"])]
    t["FM"] = [[str(r["idx"] + 1), "%d.%03d" % (r["freq"] // 100, (r["freq"] % 100) * 10), "Add" if r["flag"] else "Del", r["name"]]
               [:len(ST.TABLES["FM"]["columns"])] for r in f["fm"]]
    t["DMRReceiveGroupCallList"] = [[str(i + 1), g["name"], "|".join(tg_names[m] for m in g["members"] if m < len(tg_names)),
                                     "|".join(str(f["tgs"][m]["id"]) for m in g["members"] if m < len(f["tgs"]))]
                                    [:len(ST.TABLES["DMRReceiveGroupCallList"]["columns"])] for i, g in enumerate(f["rxgroups"])]
    opt = ST.default_rows("OptionalSetting")
    cols = ST.TABLES["OptionalSetting"]["columns"]
    for k, v in (("Start_Char", f["line1"]), ("Start_Char2", f["line2"]), ("Password_Char", f["password"])):
        opt[0][cols.index(k)] = v
    for k, (seg, o) in opt_fields(model).items():
        if k in cols:
            if seg == "E":
                if o <= len(f["tail"]):
                    opt[0][cols.index(k)] = str(f["tail"][len(f["tail"]) - o])
            else:
                opt[0][cols.index(k)] = str(f[seg][o])
    t["OptionalSetting"] = opt
    if model == "D890UV":
        nx = nx_row(f["tail"])
        if nx is not None:
            t["NXSetting"] = [nx]
    return t


def load(path):
    d = open(path, "rb").read()
    f = parse(d)
    if serialise(f) != d:
        raise RdtError("internal: %s does not re-serialise identically" % path)
    cp = ST.from_stock(tables_from_file(f), f["model"])
    cp._rdt = f
    cp._rdt_stock = copy.deepcopy({t: cp.stock.get(t) for t in tail_tables() + (["NXSetting"] if cp.model == "D890UV" else [])})
    cp._rdt_opt = ST.stock_settings_view(cp, "OptionalSetting")
    for c, rc in zip(cp.channels, f["channels"]):
        c._rdt = rc
    return cp


def _ch_record(c, row, template, tg_index, scan_index, chb=CH_BYTES):
    """cfw channel + its stock row -> V1323 channel record (template = original bytes or the default record)"""
    x = bytearray(template["fixed"])
    slot = int(row["No."]) - 1
    rx = int(round(float(row["Receive Frequency"]) * 1e5))
    tx = int(round(float(row["Transmit Frequency"]) * 1e5))
    sh_old = x[6]
    off_old = struct.unpack_from("<I", x, 7)[0]
    if tx == rx and sh_old == 0:
        sh, off = 0, off_old            # simplex: the stock CPS keeps whatever offset was there (0 or RX)
    elif tx == rx:
        sh, off = 0, rx
    elif tx > rx:
        sh, off = 1, tx - rx
    else:
        sh, off = 2, rx - tx
    struct.pack_into("<HIBI", x, 0, slot, rx, sh, off)
    if row["Channel Type"] in TYPES:
        x[11] = TYPES.index(row["Channel Type"])
    if row["Transmit Power"] in POWER:
        x[12] = POWER.index(row["Transmit Power"])
    x[13] = 1 if row["Band Width"] == "25K" else 0
    custom = struct.unpack_from("<H", x, 26)[0]
    for col, so in (("CTCSS/DCS Decode", 18), ("CTCSS/DCS Encode", 22)):
        cur = _tone_text(x[so], x[so + 1], struct.unpack_from("<H", x, so + 2)[0], custom)
        if cur == row[col]:
            continue
        tb = _tone_bytes(row[col], custom)
        if tb is None:
            continue
        sig, idx, dcs = tb
        x[so] = sig
        if idx is not None:
            x[so + 1] = idx
        if dcs is not None:
            struct.pack_into("<H", x, so + 2, dcs)
    try:
        x[40] = int(row["RX Color Code"]) & 15
        x[41] = (x[41] & ~1) | (1 if row["Slot"] == "2" else 0)
    except ValueError:
        pass
    ci = tg_index.get((row["Contact/Talk Group"], row.get("Contact/Talk Group TG/DMR ID")))
    if ci is not None:
        struct.pack_into("<H", x, 28, ci)
    x[34] = scan_index.get(row["Scan List"], 0xFF)
    tail = bytearray(template["tail"])
    dig = (x[11] & 3) in (1, 3)
    inv = {v: k for k, v in (BUSY_D168 if len(template["tail"]) == LAYOUT["D168UV"]["chan_tail"] else BUSY)[dig].items()}
    if row["Busy Lock/TX Permit"] in inv:
        x[32] = inv[row["Busy Lock/TX Permit"]]
    if len(template["tail"]) == LAYOUT["D168UV"]["chan_tail"] and row.get(D168_B17[dig], "") in ONOFF:
        x[17] = ONOFF.index(row[D168_B17[dig]])
    for col, (pos, vals) in chb.items():
        v = row.get(col, "")
        if vals:
            if v not in vals:
                continue
            v = vals.index(v)
        else:
            try:
                v = int(v)
            except ValueError:
                continue
        if pos < 48:
            x[pos] = v & 0xFF
        else:
            tail[pos - 48] = v & 0xFF
    return {"fixed": bytes(x), "name": row["Channel Name"], "tail": bytes(tail)}


def build_file(cp, template=None):
    """cfw Codeplug -> parsed-file structure (template = the file it was loaded from, else the stock default file)"""
    model = cp.model
    base = template or getattr(cp, "_rdt", None)
    if base is None or base.get("model", "D890UV") != model:
        base = _default_file(model)           # new / imported / converted to another model: start from the template
    f = copy.copy(base)
    t = ST.to_stock(cp)
    opt = dict(zip(ST.TABLES["OptionalSetting"]["columns"], t["OptionalSetting"][0]))
    f["line1"], f["line2"], f["password"] = opt["Start_Char"], opt["Start_Char2"], opt["Password_Char"]
    segs = {k: bytearray(f[k]) for k in "ABC"}
    segs["E"] = bytearray(f["tail"])
    # write only settings that differ from what the template file holds (as loaded, or the stock defaults): for a few
    # fields the stock CSV default is not the byte in the stock new file, and unchanged bytes must stay as they are
    ref = getattr(cp, "_rdt_opt", None) if base is getattr(cp, "_rdt", None) else None
    ref = ref or dict(zip(ST.TABLES["OptionalSetting"]["columns"], ST.TABLES["OptionalSetting"]["defaults"]))
    for k, (seg, o) in opt_fields(model).items():
        if opt.get(k) == ref.get(k):
            continue
        try:
            v = int(opt.get(k, ""))
        except ValueError:
            continue
        if 0 <= v <= 255:
            if seg == "E":
                if o <= len(segs["E"]):
                    segs["E"][len(segs["E"]) - o] = v
            else:
                segs[seg][o] = v
    for k in "ABC":
        f[k] = bytes(segs[k])
    f["tail"] = bytes(segs["E"])
    if t.get("NXSetting"):
        nt = nx_patch(f["tail"], t["NXSetting"][0])
        if nt is not None:
            f["tail"] = nt
    # talkgroups / contacts (keep the 7-bit packed extra strings of existing records)
    old_tg = {(r["strs"][0], r["id"]): r for r in base["tgs"]}
    tgs = []
    for i, row in enumerate(t["DMRTalkGroups"]):
        rid, name, ct = int(row[1] or 0), row[2], row[3]
        r = dict(old_tg.get((name, rid)) or {"strs": [name, "", "", "", "", ""], "raw": b""})
        r.update({"id": rid, "idx": i + 1, "type": (r.get("type", 0) & ~0x30) | CALLTYPE_R.get(ct, 0x10)})
        r["strs"] = [name] + list(r["strs"][1:])
        tgs.append(r)
    f["tgs"] = tgs or [_default_contact()]            # the stock CPS refuses a file with no contact
    tg_index = {(r["strs"][0], str(r["id"])): i for i, r in enumerate(tgs)}
    if not ST.has_col("Channel", "Contact/Talk Group TG/DMR ID"):         # D168: contacts by name
        for i, r in enumerate(tgs):
            tg_index.setdefault((r["strs"][0], None), i)
    scan_index = {row[1]: i for i, row in enumerate(t["ScanList"])}
    # record for channels that never were in an .rdt: the template's channel 1, else the built-in blank record (all
    # mapped columns are rewritten from the stock row)
    dflt = base["channels"][0] if base["channels"] else None
    if any(getattr(c, "_rdt", None) is None for c in cp.channels):
        tf = _default_file(model) if template_path(model) else None
        dflt = tf["channels"][0] if tf and tf["channels"] else _blank_channel(model)
    chans = []
    chb = _ch_bytes(model)
    for c, row in zip(cp.channels, t["Channel"]):
        r = dict(zip(ST.CH_COLS, row))
        tpl = getattr(c, "_rdt", None)
        if tpl is None or (dflt is not None and len(tpl["tail"]) != len(dflt["tail"])):
            tpl = dflt
        chans.append(_ch_record(c, r, tpl, tg_index, scan_index, chb))
    chans.sort(key=lambda rc: struct.unpack_from("<H", rc["fixed"])[0])     # the stock CPS keeps records in number order
    f["channels"] = chans
    key2slot = {}
    for rc in chans:
        slot, rx, sh, off = struct.unpack_from("<HIBI", rc["fixed"])
        tx = rx + off if sh == 1 else rx - off if sh == 2 else rx
        key2slot.setdefault((rc["name"], _mhz(rx), _mhz(tx)), slot)

    name2slot = {}
    for k, v in key2slot.items():
        name2slot.setdefault(k[0], v)

    def slots(names, rxs, txs):
        sp = lambda s: s.split("|") if s else []          # noqa: E731
        if rxs is None:                                   # D168: members by name only
            return [name2slot[n] for n in sp(names) if n in name2slot]
        return [key2slot[k] for k in zip(sp(names), sp(rxs), sp(txs)) if k in key2slot]
    zc = ST.TABLES["DMRZone"]["columns"]
    zones = []
    for i, row in enumerate(t["DMRZone"]):
        r = dict(zip(zc, row))
        old = base["zones"][i] if i < len(base["zones"]) else {"extra": b"\0" * LAYOUT[model]["zone_extra"][1], "a": 0, "b": 0}
        a = slots(r["A Channel"], r.get("A Channel RX Frequency"), r.get("A Channel TX Frequency"))
        bb = slots(r["B Channel"], r.get("B Channel RX Frequency"), r.get("B Channel TX Frequency"))
        extra = bytearray(old["extra"])
        try:
            extra[0] = int(r["Zone Hide "] or 0) & 0xFF
        except (ValueError, KeyError):
            pass
        zones.append({"slots": slots(r["Zone Channel Member"], r.get("Zone Channel Member RX Frequency"), r.get("Zone Channel Member TX Frequency")),
                      "a": a[0] if a else old["a"], "b": bb[0] if bb else old["b"], "name": r["Zone Name"], "extra": bytes(extra)})
    f["zones"] = zones
    sc = ST.TABLES["ScanList"]["columns"]
    scans = []
    for i, row in enumerate(t["ScanList"]):
        r = dict(zip(sc, row))
        old = base["scans"][i] if i < len(base["scans"]) else {"hdr": (b"\0" * 7 + bytes([5, 5, 1, 1, 0, 0, 0]))[:LAYOUT[model]["scan_hdr"]],
                                                               "members": []}
        xs = {s: x for x, s in old["members"]}
        mem = slots(r["Scan Channel Member"], r.get("Scan Channel Member RX Frequency"), r.get("Scan Channel Member TX Frequency"))
        hdr = bytearray(old["hdr"])
        for col, pos in SCAN_TIMES.items():
            try:
                hdr[pos] = int(round(float(r[col]) * 10)) & 0xFF
            except ValueError:
                pass
        scans.append({"name": r["Scan List Name"], "hdr": bytes(hdr), "members": [(xs.get(s, 0), s) for s in mem]})
    f["scans"] = scans
    f["ids"] = [{"idx": i, "id": int(row[1] or 0), "name": row[2]} for i, row in enumerate(t["RadioIDList"])]
    f["sms"] = [row[1] for row in t["PrefabricatedSMS"]]
    f["fm"] = [{"idx": int(row[0]) - 1, "flag": 1 if row[2] == "Add" else 0, "freq": int(round(float(row[1]) * 100)),
                "name": row[3] if len(row) > 3 else ""} for row in t["FM"]]
    names = [r["strs"][0] for r in tgs]
    f["rxgroups"] = []
    for row in t["DMRReceiveGroupCallList"]:
        nm = row[2].split("|") if row[2] else []
        if len(row) > 3:
            ids = row[3].split("|") if row[3] else []
            mem = [tg_index[(n, i)] for n, i in zip(nm, ids) if (n, i) in tg_index]
        else:                                             # D168: contacts by name
            first = {}
            for i, r in enumerate(tgs):
                first.setdefault(r["strs"][0], i)
            mem = [first[n] for n in nm if n in first]
        f["rxgroups"].append({"name": row[1], "members": mem})
    old_u = {(r["id"], r["strs"][0]): r for r in base["users"]}
    users = []
    for i, row in enumerate(t["DMRDigitalContactList"]):
        rid = int(row[1] or 0)
        r = dict(old_u.get((rid, row[3])) or {"raw": b"", "type": 0})
        r.update({"id": rid, "idx": (i + 1) & 0xFFFF, "strs": [row[3], row[4], row[2], row[5], row[6], row[7]],
                  "type": (r.get("type", 0) & ~0x30) | CALLTYPE_R.get(row[8], 0)})
        users.append(r)
    f["users"] = users
    return f


def unsaved_tail_edits(cp):
    """stock tables edited in cfw that an .rdt save cannot carry (they live in the undecoded tail)"""
    ST.use(cp.model)
    snap = getattr(cp, "_rdt_stock", None)
    out = []
    opt = ST.stock_settings_view(cp, "OptionalSetting")
    ref = getattr(cp, "_rdt_opt", None) or dict(zip(ST.TABLES["OptionalSetting"]["columns"], ST.TABLES["OptionalSetting"]["defaults"]))
    lost = [k for k, v in opt.items() if v != ref.get(k) and k not in opt_fields(cp.model)
            and k not in ("Start_Char", "Start_Char2", "Password_Char")]
    if lost:
        out.append("OptionalSetting (%s)" % ", ".join(lost[:8]) + (" ..." if len(lost) > 8 else ""))
    tabs = tail_tables()
    tpl = getattr(cp, "_rdt", None)
    if cp.model == "D890UV" and _nx_find((tpl or _default_file(cp.model))["tail"]) is None:
        tabs = tabs + ["NXSetting"]             # NX block not found in this file: its edits cannot be written
    for t in tabs:
        cur = cp.stock.get(t)
        ref = snap.get(t) if snap is not None else None
        if snap is None:
            if cur is not None and cur != ST.default_rows(t):
                out.append(t)
        elif cur != ref:
            out.append(t)
    return out


def save(cp, path):
    """write a stock D890UV / D168UV .rdt (the codeplug's model); returns the list of stock tables whose edits could not be written (see module doc)"""
    f = build_file(cp)
    open(path, "wb").write(serialise(f))
    return unsaved_tail_edits(cp)


def tail_tables():
    """stock tables that live in the undecoded tail: edits to them are not written into an .rdt"""
    return [t for t in ST.ORDER if t not in ("Channel", "RadioIDList", "DMRZone", "ScanList", "DMRTalkGroups",
                                              "DMRDigitalContactList", "PrefabricatedSMS", "FM", "DMRReceiveGroupCallList",
                                              "OptionalSetting", "NXSetting")]
