#!/usr/bin/env python3
"""Create / update schema/cfw_support.json (which stock CPS data the cfw firmware uses, per model; format: cps/support.py)
and copy it to web/schema/. States already in the file are kept; new tree nodes and channel columns are added:
cfw's own pages (channels, zones, ...) "used", other nodes / columns of a model's stock CPS "stored", the rest "n/a".
Firmware work flips entries to "used" by hand (or with --set), then: python3 tools/make_cfw_support.py && make vectors.
  --set NODE|TABLE:COLUMN MODEL STATE   e.g. --set AMAir D890UV used   --set "Channel:Squelch Mode" D168UV used
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cps import stock as ST, support as SU  # noqa: E402

OUT = os.path.join(ROOT, "schema", SU.FILE)
WEB = os.path.join(ROOT, "web", "schema", SU.FILE)
CFW_PAGE = ("Channel", "DMRZone", "ScanList", "DMRTalkGroups", "DMRReceiveGroupCallList", "@masterid")
HEAD = {
    "format": "cfw_support 1",
    "about": "Which stock CPS data the cfw firmware uses, per radio model. sections: stock CPS tree node (schema/stock_*.json "
             "tree target) -> {label, model: state}. keys: table -> column -> {model: state}; Channel lists every stock "
             "channel column cfw does not model itself, other tables only columns that differ from their section. "
             "Missing = stored; a column missing from keys has its section's state. Edit states by hand or with "
             "tools/make_cfw_support.py --set, then run it (copies to web/schema) and make vectors.",
    "states": {"used": "the cfw firmware uses it", "stored": "kept in the cfw codeplug, the firmware ignores it "
               "(GUI: 'not used by cfw yet' note, *)", "n/a": "this radio / its stock CPS has no such feature (hidden)"},
}


def build(old):
    d = dict(HEAD, models=list(ST.MODELS), sections={}, keys={})
    sch = {m: ST.use(m) for m in ST.MODELS}
    ST.use(ST.DEFAULT_MODEL)
    order = []
    labels = {}
    for m in ST.MODELS:
        for _, nodes in sch[m]["tree"]:
            for lab, n in nodes:
                if n not in labels:
                    order.append(n)
                    labels[n] = lab + (" (dialog)" if n.startswith("@") and lab in labels.values() else "")
    for n in order:
        prev = old.get("sections", {}).get(n, {})
        e = {"label": prev.get("label", labels[n])}
        for m in ST.MODELS:
            here = any(n == t for _, nodes in sch[m]["tree"] for _, t in nodes)
            e[m] = prev.get(m) or (("used" if n in CFW_PAGE else "stored") if here else "n/a")
        d["sections"][n] = e
    # channel columns cfw does not model (the channel dialog's stock settings)
    ch = {}
    for m in ST.MODELS:
        t = sch[m]["tables"]["Channel"]
        for c in t["columns"]:
            if c not in t["cfw_mapped"]:
                ch.setdefault(c, {})
    prev = old.get("keys", {}).get("Channel", {})
    for c in ch:
        for m in ST.MODELS:
            t = sch[m]["tables"]["Channel"]
            here = c in t["columns"] and c not in t["cfw_mapped"]
            ch[c][m] = prev.get(c, {}).get(m) or ("stored" if here else "n/a")
    d["keys"]["Channel"] = ch
    for t, cols in old.get("keys", {}).items():         # other tables' overrides kept as they are
        if t != "Channel":
            d["keys"][t] = cols
    for m in ST.MODELS:                                  # fields of an .rdt-only dialog this radio does not have
        for t, dl in ST.use(m)["dialogs"].items():
            for f in dl["fields"]:
                if m not in f:
                    d["keys"].setdefault(t, {}).setdefault(f["name"], {})[m] = "n/a"
    ST.use(ST.DEFAULT_MODEL)
    return d


def check(d):
    bad = []
    for n, e in d["sections"].items():
        bad += ["%s %s=%r" % (n, m, e.get(m)) for m in d["models"] if e.get(m) not in SU.STATES]
    for t, cols in d["keys"].items():
        for c, e in cols.items():
            bad += ["%s:%s %s=%r" % (t, c, m, v) for m, v in e.items() if m not in d["models"] or v not in SU.STATES]
    if bad:
        raise SystemExit("bad states: " + "; ".join(bad))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", nargs=3, action="append", metavar=("WHAT", "MODEL", "STATE"), default=[])
    a = ap.parse_args()
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    d = build(old)
    for what, m, s in a.set:
        if s not in SU.STATES or m not in d["models"]:
            raise SystemExit("--set %s %s %s: model one of %s, state one of %s" % (what, m, s, d["models"], SU.STATES))
        if ":" in what:
            t, c = what.split(":", 1)
            d["keys"].setdefault(t, {}).setdefault(c, {})[m] = s
        elif what in d["sections"]:
            d["sections"][what][m] = s
        else:
            raise SystemExit("unknown node %r (one of: %s)" % (what, ", ".join(d["sections"])))
    check(d)
    txt = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    for p in (OUT, WEB):
        open(p, "w").write(txt)
        print("wrote", p)


if __name__ == "__main__":
    main()
