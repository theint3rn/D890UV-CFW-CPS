#!/usr/bin/env python3
"""Write docs/STOCK_CPS_MAP.md from schema/stock_d890uv.json (+ schema/rdt_map.json) and the synthetic test codeplug's
stock CSV set (tests/vectors/stock_synth, example values), or with argument D168UV docs/STOCK_CPS_MAP_D168.md from
schema/stock_d168uv.json (+ schema/rdt_map_d168.json, tests/vectors/stock_synth_d168)."""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from cps import stock as ST, support as SU  # noqa: E402

EXAMPLE = os.path.join(ROOT, "tests", "vectors", "stock_synth", "synth.LST")
EXAMPLE_D168 = os.path.join(ROOT, "tests", "vectors", "stock_synth_d168", "synth.LST")
NOT_SHIPPED = ("Files made by the stock CPS (its screenshots, its new-file `.rdt` templates, its saves and exports of real "
               "codeplugs) are not shipped with cfw_cps; the tests that use them skip without them (README \"Stock CPS "
               "files\"). Example values below come from the synthetic test codeplug (`tools/make_synth.py`).")
RDT = os.path.join(ROOT, "schema", "rdt_map.json")

INTRO = """# Stock D890UV CPS (V1.05) map

What the stock AnyTone D890UV CPS shows and stores, as found by running it under Wine (scratch prefix, COM ports pointed
at `/dev/null`, no radio attached, nothing written to a radio). The cfw CPS uses this as its
stock model: `schema/stock_d890uv.json` is generated from the same sources by `tools/make_stock_schema.py`.

Sources:
1. **Screenshots** of the main window, tree, menus and all Optional Setting tabs (not shipped).
2. **Tool > Export > Export All** of a new codeplug (factory defaults) and of a real codeplug: 38 CSV tables. Their
   columns are the stock data model, in the stock order.
3. **.rdt layout**: for each column, a CSV with only that value changed is imported (Tool > Import > Import From File List)
   and saved; the byte diff against the reference save gives the offset (`tools/stock_rdt_experiments.md`).
   Offsets are positions in the 23 627-byte reference file (`schema/rdt_map.json`, `_ref_len`). How to read them:
   * OptionalSetting: header segments A (< 0x81), B (0x8A-0x94), C (0x9D-0xFA), the same in every file.
   * Channel: the first channel record starts at 0xEF (48 fixed bytes, the name cstr, a 50-byte tail starting at
     0x129 in the reference because its name is "Channel 1"). 0xC8 is the file's channel count/flags byte and
     changes on every channel edit. Columns that show only 0xC8 did not change the record for a digital channel.
   * NXSetting: in the undecoded tail. The TxAliasName cstr ends 483 bytes before the end of the file; fields after it
     sit at a fixed distance from the end of the file, fields before it at a fixed distance from the alias. The cfw
     reader/writer finds the block this way (`cps/rdt.py` nx_row / nx_patch). This is checked against a file the stock
     CPS saved itself (`nx_stock_v1323.rdt`, not shipped).
   * The header u32 at offset 5 is the file length - 14 (all stock-saved files); the stock D168 CPS refuses a file where it is wrong ("file error"), the D890 CPS was not tried.
     cfw writes it (fixed 2026-11-21; before, an .rdt whose length changed kept the old value).
   * Columns marked "no change" were accepted by the import but changed no byte; for example `*_nop` columns, or a
     value the import ignores for this channel type.

Limits (honest list):
* The dialog combo boxes are windowless VB6 controls; their option lists could not be enumerated automatically. The
  CSV holds the raw value (mostly the 0-based option index); the label and the current value are in the screenshots.
  The cfw CPS shows these fields with the stock label and the raw CSV value.
* Key Function assignments (PF1..P2 short/long), Alarm Setting and Local Information are not in the stock CSV export
  ("Optional Setting - Excluding Key Function"). They live only in the .rdt and are kept byte for byte by the cfw .rdt
  reader/writer, but are not editable in the cfw CPS yet.
* The stock channel editor dialog runs out of memory (VB6 "Run-time error 7") with a 142 332-entry user database
  loaded; channel fields were mapped from the CSV columns instead.

""" + NOT_SHIPPED + "\n"

MAIN = """## Main window

| Menu | Items |
|---|---|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As, Exit |
| Model | Model Information |
| Set | Set COM, Set Initialization |
| Program | Read From Radio, Write To Radio |
| Tool | Radio Recording, APRS Information Manager, Import, Export, Mode, eXtended, Firmware and Icon Update, Boot Image, Default Channel Information, Options, Standby BK Picture1, Standby BK Picture2, Zone Hide Operation, Channel Talker Alias Operation, export Data Conversion File, Satellite Data Updating |
| View | Toolbar, Status Bar, Quick Help |
| Help | About D890UV |

Toolbar: New, Open, Save, Read, Write, (Import/Export), Help. Status bar + "Quick Help" pane (context help text).

The cfw CPS keeps File / Program (Read, Write) / Tool (Import, Export, Validate, Diff) / Print and the same tree. It
has **no** firmware / icon / boot image update, satellite update or radio recording functions (codeplug only).

### Tree (left) -> stock CSV table -> cfw

"""


INTRO_D168 = """# Stock D168UV CPS (V1.07) map

What the stock AnyTone D168UV CPS V1.07 shows and stores, as found by running it under Wine (scratch prefix, all COM
ports pointed at `/dev/null`, no radio attached, nothing written to a radio). The cfw CPS uses this as its D168UV stock
model: `schema/stock_d168uv.json` is generated from the same sources by `tools/make_stock_schema.py` (model D168UV).

The D168 CPS is the same AnyTone CPS family as the D890UV one (D878UV lineage) without NXDN, AM air band, satellite
data in the tree, Bluetooth and the D890 extras; it adds QDC1200 (an MDC1200-like analog signalling), Friends List and
Talk Alias. Inside the cfw CPS the D168 tables carry the D890 names where the two differ only in naming
(Zone = DMRZone, TalkGroups = DMRTalkGroups, ReceiveGroupCallList = DMRReceiveGroupCallList, DigitalContactList =
DMRDigitalContactList; Channel columns Contact = Contact/Talk Group, Contact Call Type = Contact/Talk Group Call Type,
TxCc = txcc). The CSV files keep the stock D168 names (`csv_name`, `csv_columns` in the schema).

Sources:
1. **Screenshots** of the main window, tree, menus and all 18 Optional Setting tabs (not shipped).
2. **Tool > Export > Export All** of a new codeplug (factory defaults) and of a real codeplug opened in the D168 CPS
   (contact list trimmed to 500): 28 CSV tables.
3. **.rdt layout (V1292, model "D168UV")**: decoded structurally against a real codeplug the D168 CPS saved and its own CSV
   export (every table except a few channel bytes agrees), then field by field like the D890 map
   (`tools/stock_rdt_experiments/rdtmap.py` with `MODEL=D168UV`; offsets in `schema/rdt_map_d168.json`, positions in the
   24 713-byte reference file). Differences from the D890UV V1323 layout:
   * header segment C is 90 bytes (D890: 94); OptionalSetting segments A (< 0x81), B (0x83-0x8D), C (0x8F-0xE8) with
     empty power-on texts;
   * channel record: 48 fixed bytes (V1270 layout), name cstr, a 35-byte tail (D890: 50);
   * one extra byte after each zone name (D890: 3 bytes per zone after the zone list);
   * scan list header 11 bytes (D890: 14);
   * talkgroups and the user database start with a byte length, not a count: `u8, u16 len, u8` / `u8, u24 len, u8`
     (the length counts from the byte after the length field);
   * FM records have no name; the last FM record is the FM VFO (index 100);
   * no NXDN block.
   * header u32 at offset 5 = file length - 14 (both models; the stock CPS answers "file error" otherwise; the cfw writer
     sets it since 2026-11-21);
   * channel record bytes found besides the V1270 ones: 17 = Talk Around(Simplex) on analog channels / Work Alone on
     digital ones, 42 = Idle TX, tail 0 = 2TONE Decode, tail 34 = TxCc, others in `rdt_map_d168.json`; analog busy lock
     is called "Busy" (D890: "Channel Free").

Checks: every decoded table of a real codeplug saved by the D168 CPS equals the D168 CPS's own CSV export
(`tests/test_d168.py`); that file written by the cfw CPS (contact list trimmed) opened in the stock D168 CPS and saved
again comes back byte for byte.

Limits:
* Combo boxes are windowless VB6 controls (as on the D890): the CSV holds the raw value, labels are in the screenshots.
* PF key assignments (PF1/PF2 short, long 1/2), Knob/Keyboard/Side/Forced key locks, Alarm Setting, Local Information,
  Encryption Code, Friends List and Talk Alias are not in the CSV export; they stay byte for byte in the .rdt.
* The D168 CPS's CSV export does not reflect the Optional Settings held in the .rdt header (segments A-C; it writes
  0 or the power-on default there, and empty power-on texts) while its dialog shows the file's values; the settings in
  the tail block (from AutoRepeaterB on) export correctly. Checked: an .rdt written by cfw with TOT / SQL(A) / Step / ...
  = 2 shows TOT 60s, SQL 2, 6.25K in the stock dialog. The cfw .rdt reader takes all of them from the file.
* 11 Optional Setting columns changed no byte (reserved / not used by the D168), 12 are multi-byte (VFO scan and auto
  repeater frequencies) and are kept, not written. A second Optional Setting block sits in the .rdt tail at a fixed
  distance (23 360 B) from the end of the file; cfw addresses it from the end (`LAYOUT["D168UV"]["end_from"]`).
* For a few fields (Step, VOX_Delay, Group/PersonTalkHold, IdleWait, ContactOutSetEn, MeasurePeriod) the stock CSV
  default differs from the byte in a new stock file; cfw writes only settings that differ from the file it starts from.
* Checked against the stock D168 CPS: a cfw-written .rdt (CSV import + an added channel + an Optional Setting) opens
  and saves back byte for byte (`csvset_stock_v1292.rdt`, not shipped). Channel numbers: VFO A/B are 4001/4002; the
  stock CPS keeps channel records in number order and merges channels with the same number, so cfw gives an added
  channel the next free number and writes the records in number order.

""" + NOT_SHIPPED + "\n"

MAIN_D168 = """## Main window

| Menu | Items |
|---|---|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As, Exit |
| Model | Model Information |
| Set | Set COM, Set Initialization |
| Program | Read From Radio, Write To Radio |
| Tool | Radio Recording, Import, Export, Mode, eXtended, Firmware and Icon Update, Boot Image, Default Channel Information, Options, Standby BK Picture1, Standby BK Picture2, export Data Conversion File, Satellite Data Updating |
| View | Toolbar, Status Bar, Quick Help |
| Help | About D168UV |

Title: `D168UV[D168UV:UHF{400 - 480 MHz} VHF{136 - 174 MHz}][:file] Version 1.07`. The channel grid shows No., RX/TX
frequency, Channel Type, Power, Band Width, CTCSS/DCS Decode/Encode, Channel Name, Contact, Radio ID, Optional Signal;
VFO A / VFO B rows first. Export dialog: 28 tables, "Excluding Key Function".

The cfw CPS keeps File / Program (Read, Write) / Tool (Import, Export, Validate, Diff) / Print and the same tree, with no
firmware / icon / boot image / satellite update or radio recording (codeplug only).

### Tree (left) -> stock CSV table -> cfw

"""


BT_D168 = """## Bluetooth (cfw page; the stock D168 CPS has none)

The D168UV radio has a full BT menu (Settings > BT, `D168UV/emu/MENUS.md`) but the stock D168 CPS shows no Bluetooth
fields; its CSV export and .rdt still carry the BT settings (Optional Setting keys, CSV only). The cfw CPS shows them on
a **Bluetooth** page (tree: Public > Bluetooth, also a Bluetooth tab in Optional Setting) with the radio's labels and value
lists; the stored stock CSV value is the index in the list.

Checked two ways:
1. **.rdt -> radio**: an .rdt with marker values in these bytes was written by the stock D168 CPS ("Write To Radio")
   to a fake radio on a pty (ident `D168UV`): the bytes land in the radio settings block (NAND 0x02500000, 0xF0 bytes,
   RAM copy 0x20009BC8), column "NAND" below. FailAlarm (+0x24) and ManDownWait (+0x4F) came out as already known.
2. **value lists**: in the stock V1.07 emulator the settings byte was set and the menu opened (lists open on the
   current value): Hold Time 0 = OFF, 1 = 1S, 30 = 30S, 31 = 60S, 33 = infinite; RX Delay 0 = 30ms, 1 = 1S, 10 = 5.5S;
   %s.

| Radio menu (cfw label) | CSV key | .rdt | NAND +off | Values (stored = index) |
|---|---|---|---|---|
%s

Not in the codeplug: %s. Checked in the emulator: selecting another NR BEL / NR AFL / PTT HOLD value leaves the
settings block unchanged (BT Names / Pin Code go to the JieLi module as AT commands, `D168UV/emu/models/Bt168.cs`); the
stock CPS has no field for any of them. `MicInBlueTooth` (+0xB2) and `BhtPttHold` (+0x15) are stock keys whose bytes
reach the settings block but no BT menu shows them (+0x15 does not change PTT HOLD, which the crawl had guessed): raw
values.
"""
BT_NAND = {"BlueToothOn": 0xB1, "MicInBlueTooth": 0xB2, "SpkInBlueTooth": 0xB3, "BhtMicGain": 0xB6, "BhtSpkGain": 0xB7,
           "BhtHoldTime": 0xED, "BhtHoldDelay": 0xEE, "BhtPttHold": 0x15}
BT_EMU = "Mic / Spk Gain 0 = Level 1, 4 = Level 5; On/Off 0 = BT Off, 1 = BT On; BT+int spk 0 = Off, 1 = On"


def bluetooth_section(d168, opt):
    pg = ST.SCHEMA.get("pages", {}).get("OptionalSetting#Bluetooth")
    if not pg:
        return []
    if not d168:
        return ["## Bluetooth (cfw page)", "", "The stock D890UV CPS lists the BT keys only in the CSV (Vox/BT tab, no dialog "
                "fields). The cfw CPS shows them on a Bluetooth page (Common Settings > Bluetooth): %s. Values are the "
                "stock CSV values (the D890UV radio's BT value lists are not checked)." % ", ".join("`%s`" % k for k in pg["keys"]), ""]
    rows = []
    for k in pg["keys"]:
        c = ST.CHOICES.get(k)
        vals = ", ".join("%d %s" % (i, v) for i, v in enumerate(c)) if c and len(c) <= 11 else \
            ("0 %s, 1 %s, ..., %d %s" % (c[0], c[1], len(c) - 1, c[-1]) if c else "raw")
        if k == "BhtHoldTime":
            vals = "0 OFF, 1-30 = 1S-30S, 31 60S, 32 120S, 33 infinite"
        o = opt.get(k)
        rows.append("| %s | `%s` | %s | 0x%02X | %s |" % (ST.LABELS.get(k, k), k, ", ".join("0x%X" % x for x in o) if o else "",
                                                     BT_NAND[k], vals))
    import re
    mod = re.sub(r"^.*?: ", "", pg["note"]).rstrip(".")
    return (BT_D168 % (BT_EMU, "\n".join(rows), mod)).split("\n")


def dialogs_section(model):
    """the dialogs of rdt_dialogs.json for this model + what is not decoded"""
    d = json.load(open(os.path.join(ROOT, "schema", "rdt_dialogs.json")))
    out = ["## Dialogs kept only in the .rdt", "",
           "Measured in the stock CPS: change one field in the dialog, OK, save, diff; and the other way round, change one byte of the "
           "file and look which dialog field moves (tools/make_rdt_dialogs.py). The cfw CPS edits them as ordinary pages and stores "
           "them in the codeplug (section 10 tables 64+, docs/CODEPLUG.md). Offsets: A / C = header segments (cps/rdt.py LAYOUT, "
           "A with its variable strings taken out), E = bytes before the end of the tail, H = variable header string, "
           "list = own record list.", ""]
    for name, t in d["tables"].items():
        if model not in t["models"]:
            continue
        out += ["### %s (table %d, %s)" % (t["title"], t["id"], t["kind"]), "",
                "| # | Field | Where | Default | Values |", "|---|---|---|---|---|"]
        for i, f in enumerate(t["fields"]):
            if model not in f:
                continue
            loc = f[model]
            where = "list" if loc["type"] == "list" else "%s+0x%X %s" % (loc["seg"], loc["off"], loc["type"]) if loc["seg"] in "AC" else \
                "%s %s %s" % (loc["seg"], loc["off"], loc["type"])
            out.append("| %d | %s | %s | %s | %s |" % (i, f["label"], where, loc["default"], ", ".join("%d %s" % (k, v) for k, v in enumerate((f["choices"].get(model) if isinstance(f.get("choices"), dict) else f.get("choices")) or []))))
        out.append("")
    u = d["undecoded"]
    out += ["Not decoded: " + "; ".join(u.get("both", []) + u.get(model, []) + u.get("both_live", [])) + ".", ""]
    return out


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "D890UV"
    ST.use(model)
    d168 = model == "D168UV"
    exp = EXAMPLE_D168 if d168 else EXAMPLE
    rp = os.path.join(ROOT, "schema", "rdt_map_d168.json") if d168 else RDT
    ex = ST.read_csv_set(exp, model) if os.path.exists(exp) else {}
    rmap = json.load(open(rp)) if os.path.exists(rp) else {}
    out = [INTRO_D168 if d168 else INTRO, MAIN_D168 if d168 else MAIN, "| Section | Node | Stock table (CSV) | Rows (test codeplug) | cfw |", "|---|---|---|---|---|"]
    cfw = {"Channel": "channels", "DMRZone": "zones", "ScanList": "scan lists", "DMRTalkGroups": "contacts",
           "DMRReceiveGroupCallList": "TG lists", "@masterid": "Radio Settings"}
    def status(t):                                     # from schema/cfw_support.json (tools/make_cfw_support.py)
        if t in cfw:
            return cfw[t]
        st = SU.node_state(model, t, ST.TABLES, ST.PAGES)
        tab = SU.table_of(t, ST.TABLES)
        if tab and (t in ST.PAGES or ST.TABLES[tab]["kind"] == "record"):
            keys = ST.PAGES[t]["keys"] if t in ST.PAGES else ST.TABLES[tab]["columns"]
            vis, stored, star = SU.page_marks(model, t, keys, tab)
            if star:
                return "partly used by cfw (%d of %d keys stored, not used yet)" % (len(star), len(vis))
        return "used by cfw" if st == "used" else "stored, not used by cfw yet"
    na = []
    for sec, nodes in ST.SCHEMA["tree"]:
        for label, t in nodes:
            if SU.section(t, model) == "n/a":
                na.append(label)
                continue
            if "#" in t:                                # cfw page of one record's keys (schema "pages")
                pg = ST.SCHEMA["pages"][t]
                out.append("| %s | %s | %s (%d keys) | | cfw page, %s |"
                           % (sec, label + " (cfw)", ST.csv_name(pg["table"]), len(pg["keys"]), status(t)))
                continue
            n = len(ex.get(t, [])) if not t.startswith("@") else ""
            out.append("| %s | %s | %s | %s | %s |" % (sec, label, ST.csv_name(t) if not t.startswith("@") else "(dialog, .rdt only)", n,
                                                     status(t)))
    others = [e["label"] for n, e in SU.data()["sections"].items() if e.get(model) == "n/a"]
    out += ["", "cfw column: schema/cfw_support.json (tools/make_cfw_support.py). Hidden on this radio (n/a): %s."
            % (", ".join(sorted(set(na + others))) or "none")]
    out += ["", ("cfw adds: Tier III Systems (Digital) and a *cfw Digital Modes* section " if d168 else
                 "cfw adds: Tier III Systems (DMR), Type-C/Type-D Systems (NXDN), and a *cfw Digital Modes* section ")
            + "(Radio Settings, Trunk Systems with P25 band plans, Encryption Keys, D-STAR Repeaters, D-STAR / YSF / "
            "registration settings).", ""]
    # Optional settings
    out += ["## Optional Setting dialog", "",
            ("18 tabs (Alert Tone1 = tone table, CSV AlertTone). "
             if d168 else "17 tabs + Alert Tone1 (tone table, CSV AlertTone). ")
            + "Value = stock CSV value (default of a new codeplug); Test = value in the synthetic test codeplug; .rdt = byte offset in "
            "a %s .rdt (one byte unless noted)." % ("V1292" if d168 else "V1323"), ""]
    opt = rmap.get("OptionalSetting", {})
    cols = ST.TABLES["OptionalSetting"]["columns"]
    dflt = dict(zip(cols, ST.TABLES["OptionalSetting"]["defaults"]))
    kv = dict(zip(cols, ex.get("OptionalSetting", [[""] * len(cols)])[0]))
    radio = ST.SCHEMA.get("radio_menu", {})          # D168: names from the emulator menu crawl (D168UV/emu)
    for tab, keys in ST.SCHEMA["optional_tabs"]:
        out += ["### " + tab, "", "| Label (stock GUI) | CSV key | Default | Test | .rdt |", "|---|---|---|---|---|"]
        for k in keys:
            o = opt.get(k)
            lab = ST.LABELS.get(k) or ("(CSV only; radio menu: %s)" % radio[k] if k in radio else "(CSV only)")
            out.append("| %s | `%s` | %s | %s | %s |" % (lab, k, dflt.get(k, ""), kv.get(k, ""),
                                                     "" if o is None else (", ".join("0x%X" % x for x in o) if o else "no effect")))
        out.append("")
    if d168:
        out += ["Key Function tab (not in CSV, .rdt only): PF1/PF2 Short Key, PF1/PF2 Long Key 1, PF1/PF2 Long Key 2, Knob "
                "Lock, Keyboard Lock, Side Key Lock, Forced Lock Key (screenshot opt_06). Other tab: Encryption Type "
                "(.rdt only). Display tab: Display Time Slot, Display Color Code (.rdt only).", ""]
    else:
        out += ["Key Function tab (not in CSV, .rdt only): Key Lock, PF1/PF2/PF3/P1/P2 Short Key, PF1/PF2/PF3/P1/P2 Long Key, "
                "Long Key Time, Knob Lock, Keyboard Lock, Side Key Lock, Forced Lock Key (screenshot opt_05).", ""]
    out += bluetooth_section(d168, opt)
    out += dialogs_section(model)
    # all tables
    out += ["## Tables (stock CSV columns, in order)", ""]
    for t in ST.ORDER:
        tab = ST.TABLES[t]
        out += ["### %s (%s, LST index %d)%s" % (ST.csv_name(t) + ("" if ST.csv_name(t) == t else " = cfw " + t), tab["kind"], tab["lst_index"],
                                                 " - file only (too big for the radio)" if tab["file_only"] else ""), ""]
        rows = ex.get(t, [])
        out += ["| # | Column | Default | Values in the test codeplug | cfw |", "|---|---|---|---|---|"]
        for i, c in enumerate(tab["columns"]):
            vals = collections.Counter(r[i] for r in rows if i < len(r))
            top = ", ".join("%s" % (v if v != "" else "''") for v, _ in vals.most_common(4))
            if len(vals) > 4:
                top += " (+%d more)" % (len(vals) - 4)
            d = tab["defaults"][i] if i < len(tab["defaults"]) else ""
            mapped = "cfw field" if c in tab["cfw_mapped"] else \
                {"used": "used by cfw", "stored": "stored", "n/a": "n/a"}[SU.key(t, c, model)] if t == "Channel" else ""
            r = rmap.get(t, {}).get(c)
            extra = "" if r is None else (" .rdt " + ", ".join("0x%X" % x for x in r) if r else " .rdt no change")
            out.append("| %d | %s | %s | %s | %s%s |" % (i, c.replace("|", "/"), d.replace("|", "/")[:30], top.replace("|", "/")[:90], mapped, extra))
        out.append("")
    p = os.path.join(ROOT, "docs", "STOCK_CPS_MAP_D168.md" if d168 else "STOCK_CPS_MAP.md")
    open(p, "w").write("\n".join(out) + "\n")
    print("wrote", p)


if __name__ == "__main__":
    main()
