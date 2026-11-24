"""schema/cfw_support.json: which stock CPS data the cfw firmware uses, per model (cps/support.py; JS: web/js/support.js)"""
import json
import os

import pytest

from cps import stock as ST, support as SU
from conftest import ROOT, VEC

VIEW = os.path.join(VEC, "cfw_support_view.json")


@pytest.fixture(autouse=True)
def restore():
    real = SU.data()
    yield
    SU.set_data(real)
    ST.use("D890UV")


def test_map_covers_every_node_and_channel_column():
    d = SU.data()
    assert d["format"] == "cfw_support 1" and d["models"] == ST.MODELS
    for m in ST.MODELS:
        s = ST.use(m)
        tree = [t for _, nodes in s["tree"] for _, t in nodes]
        for n in tree:                                                   # in that model's stock CPS
            assert d["sections"][n][m] != "n/a" or n == "@local", (m, n)  # (Local Information is read live from the radio: nothing to store)
        for n, e in d["sections"].items():
            assert e[m] in SU.STATES and (n in tree or e[m] == "n/a"), (m, n)
        ch = s["tables"]["Channel"]
        for c in ch["columns"]:
            if c not in ch["cfw_mapped"]:
                assert d["keys"]["Channel"][c][m] in ("used", "stored"), (m, c)
    assert d["sections"]["AMAir"] == {"label": "AM Air", "D890UV": "used", "D168UV": "n/a"}   # cfw AM air receive (D890UV)
    assert d["sections"]["QDC1200AddressBook"]["D890UV"] == "n/a"


def test_web_copy_is_identical():
    a = open(os.path.join(ROOT, "schema", SU.FILE), "rb").read()
    assert a == open(os.path.join(ROOT, "web", "schema", SU.FILE), "rb").read()


def test_generator_keeps_states(tmp_path):
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_cfw_support as G
    old = json.loads(json.dumps(SU.data()))
    old["sections"]["FM"]["D890UV"] = "used"
    old["keys"]["Channel"]["Squelch Mode"]["D168UV"] = "used"
    old["keys"]["OptionalSetting"] = {"Beep": {"D890UV": "used"}}
    new = G.build(old)
    G.check(new)
    assert new["sections"]["FM"]["D890UV"] == "used" and new["keys"]["Channel"]["Squelch Mode"]["D168UV"] == "used"
    assert new["keys"]["OptionalSetting"] == {"Beep": {"D890UV": "used"}}
    assert G.build(SU.data()) == SU.data()                           # the shipped file is up to date


def test_gui_rules():
    SU.set_data({"sections": {"OptionalSetting": {"D890UV": "stored"}, "AMAir": {"D890UV": "n/a"}},
                 "keys": {"OptionalSetting": {"Beep": {"D890UV": "used"}, "TOT": {"D890UV": "n/a"}}}})
    vis, note, star = SU.page_marks("D890UV", "OptionalSetting", ["Beep", "TOT", "VOX"])
    assert (vis, note, star) == (["Beep", "VOX"], True, ["VOX"])      # TOT hidden; mixed page -> * on the stored key
    assert SU.page_marks("D890UV", "OptionalSetting", ["Beep"]) == (["Beep"], False, [])
    assert SU.page_marks("D890UV", "OptionalSetting", ["VOX", "Key"]) == (["VOX", "Key"], True, [])   # all stored: note only
    ST.use("D890UV")
    assert SU.node_state("D890UV", "AMAir", ST.TABLES) == "n/a"
    assert SU.node_state("D890UV", "OptionalSetting", ST.TABLES) == "stored"
    assert SU.section("FM", "D890UV") == "stored"                     # missing = stored


def test_view_vector():
    """the same decisions as tests/vectors/cfw_support_view.json (web/test/run_tests.mjs checks the JS against it)"""
    v = json.load(open(VIEW))
    for name, d in (("real", SU.data()), ("mixed", v["mixed_map"])):
        SU.set_data(d)
        for m in ST.MODELS:
            assert SU.view(m, ST.use(m)) == v["views"][name][m], (name, m)


def test_gui_hides_na_and_marks_stored():
    tk = pytest.importorskip("tkinter")
    if not os.environ.get("DISPLAY"):
        pytest.skip("no display")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    from cps import gui
    try:
        for m, hidden in (("D890UV", "stock:QDC1200AddressBook"), ("D168UV", "stock:AMAir")):
            SU.set_data(json.loads(json.dumps(SU.data())))
            SU.data()["sections"]["FM"][m] = "n/a"                    # a node the stock CPS has, hidden by the map
            app = gui.App(root, None, "tcp:127.0.0.1:1", model=m)
            pages = set(app.nav_page.values())
            assert hidden not in pages and "stock:FM" not in pages and "stock:AutoRepeaterOffsetFrequencys" in pages
            text = {app.nav.item(i, "text"): k for i, k in app.nav_page.items()}
            assert "Channel" in text and "APRS *" in text and "Zone" in text
            for w in root.winfo_children():
                w.destroy()
    finally:
        root.destroy()
