"""Stock D890UV CPS (V1.05) data: the 38 tables of its "Export All" CSV set, kept verbatim in the cfw codeplug.

* schema/stock_d890uv.json (tools/make_stock_schema.py): tables, columns (= stock CSV columns, in order), defaults,
  the stock CPS tree, Optional-Settings tabs + labels, .rdt offsets.
* Codeplug.stock = {table: rows}. Record tables (OptionalSetting, NXSetting, APRS, AlertTone) hold one row.
  Tables the cfw models natively (Channel, DMRZone, ScanList, DMRTalkGroups, DMRReceiveGroupCallList) are NOT in
  Codeplug.stock: their rows are rebuilt from cfw channels / zones / scan lists / contacts / TG lists, and every
  stock column cfw does not hold lives in that object's `.stock` dict (only values that differ from the default).
* read_csv_set / write_csv_set read and write the stock "Export All" format (.LST + one .CSV per table) byte for
  byte, so stock CSV -> cfw -> stock CSV is lossless (tests/test_stock.py).
"""
import json
import os
import struct
import sys

from . import codeplug as C


MODELS = ["D890UV", "D168UV"]                                # radio models (stock CPS schema per model)
SCHEMA_FILE = {"D890UV": "stock_d890uv.json", "D168UV": "stock_d168uv.json"}
DEFAULT_MODEL = "D890UV"


def _schema_path(model=DEFAULT_MODEL):
    name = SCHEMA_FILE[model]
    base = getattr(sys, "_MEIPASS", None)                      # PyInstaller bundle
    for root in ([base] if base else []) + [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")]:
        p = os.path.join(root, "schema", name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("schema/" + name)


MAPPED = ["Channel", "DMRZone", "ScanList", "DMRTalkGroups", "DMRReceiveGroupCallList"]
_SCHEMAS = {}


def use(model=None):
    """select the radio model whose stock schema the module-level names (SCHEMA, TABLES, ORDER, ...) describe.
    Tables and columns carry the D890UV ("canonical") names for both models; csv_name / csv_columns hold the D168 ones."""
    global MODEL, SCHEMA, TABLES, ORDER, RECORD, FILE_ONLY, LABELS, CH_COLS, CH_DEFAULT_D, CH_DEFAULT_A, TAB_ID, \
        CHOICES, PAGES
    model = model or DEFAULT_MODEL
    if model not in SCHEMA_FILE:
        raise ValueError("unknown radio model %r (known: %s)" % (model, ", ".join(MODELS)))
    if model not in _SCHEMAS:
        _SCHEMAS[model] = json.load(open(_schema_path(model)))
    MODEL = model
    SCHEMA = _SCHEMAS[model]
    TABLES = SCHEMA["tables"]
    ORDER = SCHEMA["lst_order"]
    RECORD = [t for t, v in TABLES.items() if v["kind"] == "record"]
    FILE_ONLY = [t for t, v in TABLES.items() if v["file_only"]]
    LABELS = SCHEMA["labels"]
    CHOICES = SCHEMA.get("choices", {})        # key -> value list (stored stock CSV value = list index)
    PAGES = SCHEMA.get("pages", {})            # "<table>#<title>" -> {table, title, keys, note}
    # analog channel defaults for the stock columns cfw does not map (digital defaults = the stock "new" channel)
    CH_COLS = TABLES["Channel"]["columns"]
    CH_DEFAULT_D = dict(zip(CH_COLS, TABLES["Channel"]["defaults"]))
    CH_DEFAULT_A = dict(CH_DEFAULT_D, **{"Busy Lock/TX Permit": "Off", "Squelch Mode": "CTCSS/DCS", "Custom CTCSS": "0.0",
                                          "2TONE Decode": "1", "txcc": "1", "Contact/Talk Group Call Type": "Private Call"})
    TAB_ID = {t: i for i, t in enumerate(ORDER)}
    return SCHEMA


def choice_text(key, value):
    """stock CSV value -> its label in the radio's value list (raw value when the key has no list or is out of range)"""
    c = CHOICES.get(key)
    v = str(value).strip()
    if c and v.isdigit() and int(v) < len(c):
        return c[int(v)]
    return v


def choice_value(key, text):
    """label from choice_text (or a raw value) -> stock CSV value"""
    c = CHOICES.get(key)
    t = str(text).strip()
    return str(c.index(t)) if c and t in c else t


def schema_of(model):
    """the stock schema of a model without selecting it"""
    if model not in _SCHEMAS:
        _SCHEMAS[model] = json.load(open(_schema_path(model)))
    return _SCHEMAS[model]


def csv_name(table):
    return TABLES[table].get("csv_name", table)


def has_col(table, col):
    return col in TABLES[table]["columns"]


use(DEFAULT_MODEL)


class StockError(ValueError):
    pass


# ------------------------------------------------------------------ CSV (stock dialect)

def parse_csv(text):
    """stock CSV text -> (rows, trail flags). Quoted fields keep their text exactly; trail = unquoted empty last field."""
    rows, trails = [], []
    for line in text.split("\r\n"):
        if line == "":
            continue
        f, i, trail = [], 0, False
        while True:
            if i < len(line) and line[i] == '"' and rows:
                # data row: a field ends at '",' or at the closing quote of the line; quotes inside a value are not
                # escaped by the stock CPS (contact names like 'R.L. \Ray\" Tual')
                k = line.find('",', i + 1)
                k = (len(line) - 1 if line.endswith('"') and len(line) - 1 > i else len(line)) if k < 0 else k
                f.append(line[i + 1:k])
                i = k + 1
            elif i < len(line) and line[i] == '"':
                j = line.index('"', i + 1)
                k = line.find(",", j)
                k = len(line) if k < 0 else k
                f.append(line[i + 1:j] + line[j + 1:k])      # header: text after a closing quote is appended (APRS)
                i = k
            else:
                j = line.find(",", i)
                j = len(line) if j < 0 else j
                f.append(line[i:j])
                i = j
            if i < len(line) and line[i] == ",":
                i += 1
                if i == len(line):
                    trail = True
                    break
            else:
                break
        rows.append(f)
        trails.append(trail)
    return rows, trails


def format_csv(table, rows):
    t = TABLES[table]
    out = [t["header_raw"]]
    for r in rows:
        out.append('"' + '","'.join(r) + '"' + ("," if t["row_trail"] else ""))
    return "\r\n".join(out) + "\r\n"


def detect_model(names):
    """stock CSV file base names of an "Export All" set -> radio model (D890UV unless a name only another model has)"""
    base = {v.get("csv_name", t) for t, v in schema_of(DEFAULT_MODEL)["tables"].items()}
    for m in MODELS:
        if m == DEFAULT_MODEL:
            continue
        own = {v.get("csv_name", t) for t, v in schema_of(m)["tables"].items()}
        if any(n in own and n not in base for n in names):
            return m
    return DEFAULT_MODEL


def read_csv_set(lst_path, model=None):
    """stock "Export All" set (.LST + CSVs) -> {table: rows}; unknown tables are ignored, missing ones = default.
    The model (D890UV / D168UV) is detected from the file names unless given; it is selected (use())."""
    d = os.path.dirname(lst_path)
    entries = []
    for line in open(lst_path, encoding="latin1"):
        line = line.strip()
        if "," not in line:
            continue
        entries.append(line.split(",", 1)[1].strip('"'))
    use(model or detect_model([n[:-4] for n in entries]))
    by_csv = {csv_name(t): t for t in TABLES}
    res = {}
    for name in entries:
        table = by_csv.get(name[:-4])
        if table is None or not os.path.exists(os.path.join(d, name)):
            continue
        rows, _ = parse_csv(open(os.path.join(d, name), "rb").read().decode("latin1"))
        if rows and rows[0] != TABLES[table].get("csv_columns", TABLES[table]["columns"]):
            raise StockError("%s: columns differ from the stock %s export (other CPS version?)" % (name, SCHEMA["stock_cps"]))
        res[table] = rows[1:]
    return res


def write_csv_set(tables, lst_path):
    d = os.path.dirname(os.path.abspath(lst_path))
    os.makedirs(d, exist_ok=True)
    lines = ["%d" % len(ORDER)]
    for i, t in enumerate(ORDER):
        lines.append('%d,"%s.CSV"' % (TABLES[t]["lst_index"], csv_name(t)))
        open(os.path.join(d, csv_name(t) + ".CSV"), "wb").write(format_csv(t, tables.get(t, default_rows(t))).encode("latin1"))
    open(lst_path, "wb").write(("\r\n".join(lines) + "\r\n").encode("latin1"))


def default_rows(table):
    t = TABLES[table]
    if t["kind"] == "record":
        return [list(t["defaults"])]
    return [list(r) for r in t["default_rows"]]


# ------------------------------------------------------------------ value conversions (stock text <-> cfw)

POWER = {"Low": "low", "Middle": "mid", "High": "high", "Turbo": "turbo"}
POWER_R = {v: k for k, v in POWER.items()}
CALLTYPE = {"Group Call": "group", "Private Call": "private", "All Call": "all"}
CALLTYPE_R = {v: k for k, v in CALLTYPE.items()}


def mhz_to_hz(s):
    return int(round(float(s) * 1e6)) if s.strip() else 0


def hz_to_mhz(hz):
    return "%.5f" % (hz / 1e6)


def tone_from_stock(s):
    s = s.strip()
    if s in ("Off", ""):
        return None
    if s[0] in "Dd":
        return s.upper()
    return s


def tone_to_stock(t):
    return "Off" if not t else t


def _chan_mode(type_text):
    return "FM" if type_text.startswith("A") else "DMR"


def _type_text(mode):
    return "A-Analog" if mode == "FM" else "D-Digital"


# ------------------------------------------------------------------ stock -> cfw

def _member_index(chans_by_key, names, rxs, txs):
    out = []
    for n, rx, tx in zip(names, rxs, txs):
        k = (n, rx, tx)
        if k in chans_by_key:
            out.append(chans_by_key[k])
    return out


def _split(s):
    return [x for x in s.split("|")] if s != "" else []


def from_stock(tables, model=None):
    """{table: rows} (stock CSV set or .rdt) -> cfw Codeplug, lossless (to_stock gives the same rows back).
    model: radio model of the tables (default: the selected one, see use())."""
    if model:
        use(model)
    cp = C.Codeplug(model=MODEL)
    cp.settings.radio_name = C.MODELS[MODEL]["name"]
    # contacts
    tg_rows = tables.get("DMRTalkGroups", default_rows("DMRTalkGroups"))
    cols = TABLES["DMRTalkGroups"]["columns"]
    for r in tg_rows:
        d = dict(zip(cols, r))
        c = C.Contact(name=d["Name"][:16], id=int(d["Radio ID"] or 0), kind=CALLTYPE.get(d["Call Type"], "group"), mode="DMR")
        c._raw = d
        cp.contacts.append(c)
    contact_by = {(c.name, c.id): i for i, c in enumerate(cp.contacts)}
    contact_name = {}
    for i, c in enumerate(cp.contacts):
        contact_name.setdefault(c.name, i)
    # RX group lists
    cols = TABLES["DMRReceiveGroupCallList"]["columns"]
    for r in tables.get("DMRReceiveGroupCallList", []):
        d = dict(zip(cols, r))
        names = _split(d["Contact"])
        if "Contact TG/DMR ID" in d:
            ids = _split(d["Contact TG/DMR ID"])
            mem = [contact_by[(n, int(i))] for n, i in zip(names, ids) if (n, int(i or 0)) in contact_by]
        else:                                           # D168: contacts by name only
            mem = [contact_name[n] for n in names if n in contact_name]
        t = C.TgList(d["Group Name"][:16], mem)
        t._raw = d
        cp.tglists.append(t)
    tgl_by = {t.name: i for i, t in enumerate(cp.tglists)}
    sl_rows = tables.get("ScanList", [])
    sl_names = [dict(zip(TABLES["ScanList"]["columns"], r))["Scan List Name"] for r in sl_rows]
    # channels
    for r in tables.get("Channel", default_rows("Channel")):
        d = dict(zip(CH_COLS, r))
        mode = _chan_mode(d["Channel Type"])
        c = C.Channel(name=d["Channel Name"][:16], rx_hz=mhz_to_hz(d["Receive Frequency"]), tx_hz=mhz_to_hz(d["Transmit Frequency"]),
                      mode=mode, power=POWER.get(d["Transmit Power"], "high"))
        if mode == "FM":
            c.wide = d["Band Width"] == "25K"
            c.rx_tone, c.tx_tone = tone_from_stock(d["CTCSS/DCS Decode"]), tone_from_stock(d["CTCSS/DCS Encode"])
        else:
            c.cc = int(d["RX Color Code"] or 0)
            c.slot = 2 if d["Slot"] == "2" else 1
            if "Contact/Talk Group TG/DMR ID" in d:
                c.tg = int(d["Contact/Talk Group TG/DMR ID"] or 0)
                c.contact = contact_by.get((d["Contact/Talk Group"], c.tg))
            else:                                       # D168: the contact by name gives the TG
                c.contact = contact_name.get(d["Contact/Talk Group"])
                c.tg = cp.contacts[c.contact].id if c.contact is not None else 0
            c.tglist = tgl_by.get(d["Receive Group List"])
        c.scanlist = sl_names.index(d["Scan List"]) if d["Scan List"] in sl_names else None
        c.talkaround = d.get("Talk Around(Simplex)") == "On"
        C.normalize_channel(c)
        c._raw = d
        cp.channels.append(c)
    by_key, by_name = {}, {}
    for i, c in enumerate(cp.channels):
        by_key.setdefault((c.name, hz_to_mhz(c.rx_hz), hz_to_mhz(c.tx_hz)), i)
        by_name.setdefault(c.name, i)
    for table, cls, namecol in (("DMRZone", C.Zone, "Zone Name"), ("ScanList", C.ScanList, "Scan List Name")):
        cols = TABLES[table]["columns"]
        pre = "Zone Channel Member" if table == "DMRZone" else "Scan Channel Member"
        for r in tables.get(table, []):
            d = dict(zip(cols, r))
            if pre + " RX Frequency" in d:
                mem = _member_index(by_key, _split(d[pre]), _split(d[pre + " RX Frequency"]), _split(d[pre + " TX Frequency"]))
            else:                                       # D168: members by channel name only
                mem = [by_name[n] for n in _split(d[pre]) if n in by_name]
            z = cls(d[namecol][:16], mem)
            z._raw = d
            (cp.zones if table == "DMRZone" else cp.scanlists).append(z)
    # radio ID -> cfw DMR ID
    rid = tables.get("RadioIDList", [])
    if rid:
        cp.settings.dmr_id = int(dict(zip(TABLES["RadioIDList"]["columns"], rid[0]))["Radio ID"] or 0)
    cp.stock = {t: [list(x) for x in rows] for t, rows in tables.items() if t not in MAPPED}
    for t in MAPPED:
        for o in getattr(cp, OBJ_ATTR[t]):
            o.stock = _extras(t, o._raw, o, cp)
            del o._raw
    return cp


def _extras(table, d, obj, cp=None):
    """stock columns of one row that differ from what to_stock would generate from obj alone (= lossless overrides)"""
    gen = _row(table, obj, cp, {})
    gen["No."] = str(_index_of(cp, table, obj) + 1)
    ex = {}
    for k, v in d.items():
        if gen.get(k) != v:
            ex[k] = v
    return ex


def _index_of(cp, table, obj):
    lst = getattr(cp, OBJ_ATTR[table])
    for i, o in enumerate(lst):
        if o is obj:
            return i
    return len(lst)


def _row(table, o, cp, extras):
    """generate the stock row dict of one cfw object (without its .stock overrides)"""
    if table == "Channel":
        base = dict(CH_DEFAULT_A if o.mode == "FM" else CH_DEFAULT_D)
        base.update({"Channel Name": o.name, "Receive Frequency": hz_to_mhz(o.rx_hz), "Transmit Frequency": hz_to_mhz(o.tx_hz),
                     "Channel Type": _type_text(o.mode), "Transmit Power": POWER_R.get(o.power, "High"),
                     "Talk Around(Simplex)": "On" if o.talkaround else "Off",
                     "Scan List": cp.scanlists[o.scanlist].name if (cp and o.scanlist is not None and o.scanlist < len(cp.scanlists)) else "None"})
        if o.mode == "FM":
            base.update({"Band Width": "25K" if o.wide else "12.5K", "CTCSS/DCS Decode": tone_to_stock(o.rx_tone),
                         "CTCSS/DCS Encode": tone_to_stock(o.tx_tone)})
        else:
            base.update({"Band Width": "12.5K", "RX Color Code": str(o.cc), "Slot": str(o.slot or 1),
                         "Contact/Talk Group TG/DMR ID": str(o.tg)})
            if cp and o.contact is not None and o.contact < len(cp.contacts):
                ct = cp.contacts[o.contact]
                base.update({"Contact/Talk Group": ct.name, "Contact/Talk Group Call Type": CALLTYPE_R.get(ct.kind, "Group Call")})
            if cp and o.tglist is not None and o.tglist < len(cp.tglists):
                base["Receive Group List"] = cp.tglists[o.tglist].name
        return base
    if table in ("DMRZone", "ScanList"):
        pre = "Zone Channel Member" if table == "DMRZone" else "Scan Channel Member"
        chans = [cp.channels[i] for i in o.channels if cp and i < len(cp.channels)]
        cols = TABLES[table]["columns"]
        base = dict(zip(cols, TABLES[table]["defaults"])) if TABLES[table]["defaults"] else {}
        base.update({cols[1]: o.name, pre: "|".join(c.name for c in chans),
                     pre + " RX Frequency": "|".join(hz_to_mhz(c.rx_hz) for c in chans),
                     pre + " TX Frequency": "|".join(hz_to_mhz(c.tx_hz) for c in chans)})
        return base
    if table == "DMRTalkGroups":
        return {"Radio ID": str(o.id), "Name": o.name, "Call Type": CALLTYPE_R.get(o.kind, "Group Call"), "Call Alert": "None"}
    if table == "DMRReceiveGroupCallList":
        if cp is None:
            return None
        return {"Group Name": o.name, "Contact": "|".join(cp.contacts[i].name for i in o.contacts if i < len(cp.contacts)),
                "Contact TG/DMR ID": "|".join(str(cp.contacts[i].id) for i in o.contacts if i < len(cp.contacts))}
    raise KeyError(table)


def to_stock(cp, for_rdt=False):
    """cfw Codeplug -> {table: rows} in the stock CSV format (all tables of the codeplug's model)."""
    use(getattr(cp, "model", None))
    out = {}
    for t in ORDER:
        if t in MAPPED:
            continue
        out[t] = [list(r) for r in cp.stock.get(t, default_rows(t))]
    for table, objs in (("Channel", cp.channels), ("DMRZone", cp.zones), ("ScanList", cp.scanlists),
                        ("DMRTalkGroups", cp.contacts), ("DMRReceiveGroupCallList", cp.tglists)):
        cols = TABLES[table]["columns"]
        rows = []
        # channel numbers (= .rdt slots) must be unique: numbers kept from a stock file can have gaps, so a new
        # channel does not simply get its position (the stock CPS would merge two channels with one number)
        kept = {(getattr(o, "stock", None) or {}).get("No.") for o in objs} - {None} if table == "Channel" else set()
        taken = kept | {str(i + 1) for i, o in enumerate(objs) if "No." not in (getattr(o, "stock", None) or {})}
        # next number after the highest one below the VFO numbers (4001/4002), so an added channel stays last
        free = max([int(x) for x in taken if x.isdigit() and int(x) <= 4000] + [0]) + 1
        for i, o in enumerate(objs):
            d = _row(table, o, cp, {})
            d["No."] = str(i + 1)
            if table == "Channel" and d["No."] in kept and "No." not in (getattr(o, "stock", None) or {}):
                while str(free) in taken:
                    free = free + 1 if free < 4000 else 1
                taken.add(str(free))
                d["No."] = str(free)
            d.update(getattr(o, "stock", None) or {})
            rows.append([d.get(c, "") for c in cols])
        out[table] = rows
    rid = out.get("RadioIDList")
    if rid and cp.settings.dmr_id:
        cols = TABLES["RadioIDList"]["columns"]
        rid[0][cols.index("Radio ID")] = str(cp.settings.dmr_id)
    return out


CH_DIGITAL_ONLY = ["Contact/Talk Group", "Contact/Talk Group Call Type", "Contact/Talk Group TG/DMR ID", "RX Color Code",
                   "Slot", "Receive Group List"]
CH_FM_ONLY = ["CTCSS/DCS Decode", "CTCSS/DCS Encode"]


def clear_mapped_overrides(obj, table):
    """call after editing a cfw field of a channel/zone/...: drop stock overrides of the columns cfw generates for it"""
    skip = []
    if table == "Channel":
        skip = CH_DIGITAL_ONLY if obj.mode == "FM" else CH_FM_ONLY
    for k in TABLES[table]["cfw_mapped"]:
        if k not in skip:
            (obj.stock or {}).pop(k, None)


def channel_key(c):
    return (c.name, hz_to_mhz(c.rx_hz), hz_to_mhz(c.tx_hz))


def rename_channel_refs(cp, old, new):
    """a channel's (name, rx, tx) changed: update the stock text references to it (zone A/B channel, scan list
    priority / revert channels)"""
    pairs = [("DMRZone", "zones", ("A Channel", "B Channel")),
             ("ScanList", "scanlists", ("Priority Channel 1", "Priority Channel 2"))]
    for table, attr, cols in pairs:
        for o in getattr(cp, attr):
            st = o.stock or {}
            for col in cols:
                if not has_col(table, col + " RX Frequency"):          # D168: referenced by name only
                    if col in st and st[col] == old[0]:
                        st[col] = new[0]
                elif (st.get(col), st.get(col + " RX Frequency"), st.get(col + " TX Frequency")) == old:
                    st[col], st[col + " RX Frequency"], st[col + " TX Frequency"] = new


def stock_settings_view(cp, table):
    """record table -> {column: value} (defaults filled in)"""
    use(getattr(cp, "model", None))
    t = TABLES[table]
    row = (cp.stock.get(table) or default_rows(table))[0]
    return dict(zip(t["columns"], row))


def set_stock_value(cp, table, column, value, row=0):
    use(getattr(cp, "model", None))
    rows = cp.stock.setdefault(table, default_rows(table))
    while len(rows) <= row:
        rows.append(list(TABLES[table]["defaults"]))
    rows[row][TABLES[table]["columns"].index(column)] = str(value)


# ------------------------------------------------------------------ binary (codeplug section 10 "STOCK")

OBJ_ID = {"Channel": 0xF0, "DMRZone": 0xF1, "ScanList": 0xF2, "DMRTalkGroups": 0xF3, "DMRReceiveGroupCallList": 0xF4}
OBJ_ATTR = {"Channel": "channels", "DMRZone": "zones", "ScanList": "scanlists", "DMRTalkGroups": "contacts",
            "DMRReceiveGroupCallList": "tglists"}
ROWS = 0xFF                                  # col 0xFF entry = number of rows of a list table


def encode_stock(cp, for_radio=False):
    """-> bytes: entries u8 table, u8 col, u16 row, u16 len, data (latin1). Record tables: only non-default cells.
    List tables: a row-count entry + every non-empty cell. Per-object extras (channel/zone/...): their .stock dict.
    Table ids are positions in the codeplug model's stock table order."""
    use(getattr(cp, "model", None))
    b = bytearray()

    def put(tid, col, row, data):
        data = data.encode("latin1", "replace")
        b.extend(struct.pack("<BBHH", tid, col, row, len(data)))
        b.extend(data)

    for t in ORDER:
        if t in MAPPED or t not in cp.stock or (for_radio and t in FILE_ONLY):
            continue
        tab, cols = TABLES[t], TABLES[t]["columns"]
        rows = cp.stock[t]
        if tab["kind"] == "record":
            for ci, (v, dv) in enumerate(zip(rows[0], tab["defaults"])):
                if v != dv:
                    put(TAB_ID[t], ci, 0, v)
        else:
            if rows == default_rows(t):
                continue
            put(TAB_ID[t], ROWS, 0, str(len(rows)))
            for ri, r in enumerate(rows):
                for ci, v in enumerate(r):
                    if v != "":
                        put(TAB_ID[t], ci, ri, v)
    for t, tid in OBJ_ID.items():
        cols = TABLES[t]["columns"]
        for ri, o in enumerate(getattr(cp, OBJ_ATTR[t])):
            for k, v in sorted((getattr(o, "stock", None) or {}).items(), key=lambda kv: cols.index(kv[0]) if kv[0] in cols else 999):
                if k in cols:
                    put(tid, cols.index(k), ri, v)
    b.extend(b"\0" * (-len(b) % 4))
    if for_radio:
        b.extend(b"\0" * STOCK_SPARE)     # room for the radio's edits journal (radio menu settings, see below)
    return bytes(b)


def _put(row, col, v):
    while len(row) <= col:                 # some stock rows have more fields than the header (HotKey_HotKey, APRS)
        row.append("")
    row[col] = v


# Radio edits journal: the firmware (cfw/app/cfwcp.c cfwcp_journal_write) writes settings changed in the radio menu into
# the spare zero bytes at the end of section 10: a marker entry (table 0xEE), edit entries, then a 4-byte CRC fix entry
# (0xEF) that keeps the header CRC valid. Tables: 21 OptionalSetting (stock value, applied like any entry: the last
# one wins), 0xE0 cfw settings record (col = key slot 0..5 -> settings.keys[col] = KEY_FUNCS[value], 8 start zone,
# 9 start channel), 0xE2 cfw channel field (col 0 = TX power index, row = channel). Decoding folds them into the model,
# so the next write puts them in their normal places and the journal is empty again.
STOCK_SPARE = 1024
JT_SETTINGS, JT_CHANNEL, JT_MARK, JT_CRCFIX = 0xE0, 0xE2, 0xEE, 0xEF


def _journal_edit(cp, tid, col, row, v):
    from . import codeplug as C
    if not v.isdigit() or not v.isascii():
        return
    n = int(v)
    if tid == JT_SETTINGS and col == 6:      # cfw: encryption (privacy keys) on / off
        cp.settings.encryption = n == 1
    elif tid == JT_SETTINGS and col == 7:    # cfw: SMS format (1 = M-SMS)
        cp.settings.sms_msms = n == 1
    elif tid == JT_SETTINGS and col < 6 and 0 <= n < len(C.KEY_FUNCS):
        keys = (list(cp.settings.keys) + ["none"] * 6)[:6]
        keys[col] = C.KEY_FUNCS[n]
        cp.settings.keys = keys
    elif tid == JT_CHANNEL and col == 0 and row < len(cp.channels) and 0 <= n < len(C.POWERS):
        cp.channels[row].power = C.POWERS[n]


def decode_stock(data, cp):
    """inverse of encode_stock: fills cp.stock and the .stock dicts of cp's objects"""
    use(getattr(cp, "model", None))
    p = 0
    lists = {}
    while p + 6 <= len(data):
        a = (p + 3) & ~3
        if p % 4 and a < len(data) and 0xE0 <= data[a] < 0xF0 and not any(data[p:a]):
            p = a                           # the radio edits journal starts 4-aligned after the CPS entries' zero padding
            continue
        tid, col, row, ln = struct.unpack_from("<BBHH", data, p)
        if tid == 0 and col == 0 and row == 0 and ln == 0 and not any(data[p:]):
            break
        v = data[p + 6:p + 6 + ln].decode("latin1")
        p += 6 + ln
        if 0xE0 <= tid < 0xF0:              # radio edits journal
            _journal_edit(cp, tid, col, row, v)
            continue
        if tid >= 0xF0:
            t = [k for k, x in OBJ_ID.items() if x == tid][0]
            objs = getattr(cp, OBJ_ATTR[t])
            if row < len(objs):
                if not isinstance(getattr(objs[row], "stock", None), dict):
                    objs[row].stock = {}
                objs[row].stock[TABLES[t]["columns"][col]] = v
            continue
        t = ORDER[tid]
        tab = TABLES[t]
        if tab["kind"] == "record":
            rows = cp.stock.setdefault(t, default_rows(t))
            _put(rows[0], col, v)
        elif col == ROWS:
            lists[t] = [[""] * len(tab["columns"]) for _ in range(int(v))]
            cp.stock[t] = lists[t]
        else:
            _put(lists[t][row], col, v)
    return cp


# ------------------------------------------------------------------ radio model conversion

def convert_model(cp, model):
    """switch a codeplug to another radio model (D890UV <-> D168UV). cfw data (channels, zones, digital modes, ...) is
    kept as is; stock tables both CPS have keep the columns both have (by name), the rest gets the new model's defaults;
    stock tables / columns the new model does not have are dropped."""
    from . import codeplug as C
    if model not in C.MODELS:
        raise ValueError("unknown radio model %r" % model)
    if cp.model == model:
        return cp
    old_t, new_t = schema_of(cp.model)["tables"], schema_of(model)["tables"]
    stock = {}
    for t, rows in cp.stock.items():
        if t not in new_t:
            continue
        oc, nt = old_t[t]["columns"], new_t[t]
        nd = dict(zip(nt["columns"], nt["defaults"])) if nt["defaults"] else {}
        out = []
        for r in rows:
            d = dict(zip(oc, r))
            out.append([d.get(c, nd.get(c, "")) for c in nt["columns"]])
        stock[t] = out
    cp.stock = stock
    for t, attr in OBJ_ATTR.items():
        cols = set(new_t[t]["columns"])
        for o in getattr(cp, attr):
            if getattr(o, "stock", None):
                o.stock = {k: v for k, v in o.stock.items() if k in cols}
    if cp.settings.radio_name == C.MODELS[cp.model]["name"]:
        cp.settings.radio_name = C.MODELS[model]["name"]
    cp.model = model
    for attr in ("_rdt", "_rdt_stock", "_rdt_opt"):            # an .rdt of the old model cannot be the save template
        if hasattr(cp, attr):
            delattr(cp, attr)
    for c in cp.channels:
        if hasattr(c, "_rdt"):
            del c._rdt
    use(model)
    return cp
