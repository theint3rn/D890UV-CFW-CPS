"""Which stock CPS data the cfw firmware uses, per radio model (schema/cfw_support.json; JS: web/js/support.js).

cfw_support.json:
  sections: {node: {"label": ..., "<model>": state}}   node = a stock CPS tree target of schema/stock_*.json "tree"
            (stock table name, "@dialog" or "<table>#<page>")
  keys:     {table: {column: {"<model>": state}}}       per column; "Channel" lists every stock channel column cfw does
            not model itself (the channel dialog's "Stock settings"), other tables only the columns that differ from
            their section
  state:    "used"   the firmware uses it (show it plainly)
            "stored" kept in the cfw codeplug, the firmware ignores it (shown with the "not used by cfw yet" note, `*`)
            "n/a"    the radio / its stock CPS has no such feature (hidden for that model)
A node or key missing for a model counts as "stored"; a key missing from "keys" has its section's state.
tools/make_cfw_support.py adds new nodes / columns (keeps the states already set).
"""
import json
import os
import sys

STATES = ("used", "stored", "n/a")
NOTE = "Stock CPS data: stored in the cfw codeplug and kept in stock .rdt / CSV files, not used by cfw yet."
STAR_NOTE = "* = stored in the cfw codeplug, not used by cfw yet."
FILE = "cfw_support.json"
_DATA = None


def _path():
    base = getattr(sys, "_MEIPASS", None)
    for root in ([base] if base else []) + [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")]:
        p = os.path.join(root, "schema", FILE)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("schema/" + FILE)


def data():
    global _DATA
    if _DATA is None:
        _DATA = json.load(open(_path()))
    return _DATA


def set_data(d):
    """use this map instead of the file (tests)"""
    global _DATA
    _DATA = d


def section(node, model):
    return data()["sections"].get(node, {}).get(model, "stored")


def table_of(node, tables):
    """the table a node's values live in (None: a dialog that is not decoded). "@..." nodes: the .rdt-only dialogs of
    schema/rdt_dialogs.json"""
    t = node.split("#")[0]
    if t in tables:
        return t
    return next((n for n, v in tables.items() if v.get("node") == node), None)


def key(table, k, model, node=None):
    """state of one column of a stock table (node: the page it is shown on, for the section default)"""
    v = data()["keys"].get(table, {}).get(k, {}).get(model)
    return v if v else section(node or table, model)


def page_marks(model, node, keys, table=None):
    """for a page showing `keys` of `table`: (visible keys, show the "not used" note, keys to mark with `*`).
    n/a keys are hidden; the note shows when any visible key is stored; `*` only when the page mixes used and stored."""
    table = table or node.split("#")[0]
    st = {k: key(table, k, model, node) for k in keys}
    vis = [k for k in keys if st[k] != "n/a"]
    stored = [k for k in vis if st[k] == "stored"]
    return vis, bool(stored), (stored if len(stored) < len(vis) else [])


def node_state(model, node, tables, pages=None):
    """state shown in the tree: "n/a" (hidden), "stored" (`*`: something on the page is stored) or "used".
    Record pages (settings, "#" pages) look at their keys; list tables and dialogs at the section only."""
    s = section(node, model)
    if s == "n/a":
        return s
    pages = pages or {}
    t = table_of(node, tables)
    if t and (node in pages or tables[t]["kind"] == "record"):
        keys = pages[node]["keys"] if node in pages else tables[t]["columns"]
        return "stored" if page_marks(model, node, keys, t)[1] else "used"
    return s


def channel_marks(model, cols):
    """channel dialog: (visible stock columns, note, starred) for the columns cfw does not model itself"""
    return page_marks(model, "Channel", cols, "Channel")


def view(model, schema):
    """everything the GUIs decide from the map for one model (Python == JS vector, tests/vectors/cfw_support_view.json)"""
    tabs, pages = schema["tables"], schema.get("pages", {})
    out = {"nodes": {}, "pages": {}}
    for _, nodes in schema["tree"]:
        for _, n in nodes:
            out["nodes"][n] = node_state(model, n, tabs, pages)
            t = table_of(n, tabs)
            if t and (n in pages or tabs[t]["kind"] == "record"):
                keys = pages[n]["keys"] if n in pages else tabs[t]["columns"]
                vis, note, star = page_marks(model, n, keys, t)
                out["pages"][n] = {"hidden": [k for k in keys if k not in vis], "note": note, "star": star}
    ch = tabs["Channel"]
    cols = [c for c in ch["columns"] if c not in ch["cfw_mapped"]]
    vis, note, star = channel_marks(model, cols)
    out["channel"] = {"hidden": [c for c in cols if c not in vis], "note": note, "star": star}
    return out
