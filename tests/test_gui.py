import os

import pytest

from fake_radio import FakeCfwRadio
from test_codeplug import sample

tk = pytest.importorskip("tkinter")


@pytest.fixture
def root():
    if not os.environ.get("DISPLAY"):
        pytest.skip("no display")
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    r.withdraw()
    yield r
    r.destroy()


def test_gui_edit_and_write(root, tmp_path):
    from cps import gui, codeplug as C
    radio = FakeCfwRadio()
    p = tmp_path / "s.json"
    C.save(sample(), str(p))
    app = gui.App(root, str(p), "tcp:127.0.0.1:%d" % radio.port)
    assert len(app.tree.get_children()) == len(sample().channels)
    app.tree.selection_set("3")
    app.edit_channel()
    assert app.cf.get("mode") == "DMR" and app.mf["DMR"].get("tg") == "91"
    app.cf.set("name", "EDITED")
    app.mf["DMR"].set("cc", "7")
    app.ch_apply()
    assert app.cp.channels[3].name == "EDITED" and app.cp.channels[3].cc == 7
    app.mf["DMR"].set("cc", "99")
    app.ch_apply()
    assert "colour code" in app.ch_msg.get()
    app.mf["DMR"].set("cc", "7")
    app.ch_apply()
    app.ask_diff = lambda lines: True
    app.write_radio()
    for _ in range(200):
        root.update()
        if not app.busy:
            break
        root.after(20)
    assert radio.valid()
    back = C.decode(bytes(radio.flash[:C.check_header(bytes(radio.flash))[0]]))
    assert back.channels[3].name == "EDITED"
    app.changed = False
    radio.close()


def test_gui_tree_stock_and_digital_pages(root):
    from cps import gui, codeplug as C, stock as ST
    import os
    from conftest import SYNTH_CSV
    cp = ST.from_stock(ST.read_csv_set(SYNTH_CSV))
    app = gui.App(root, None, "tcp:127.0.0.1:1")
    app.cp = cp
    app.refresh_all()
    pages = set(app.nav_page.values())
    assert {"channels", "zones", "keys", "dstar", "digi", "stock:OptionalSetting", "stock:RoamingChannel"} <= pages
    app.show_page("stock:OptionalSetting")
    rec = app.pages["stock:OptionalSetting"]
    rec.vars["TOT"].set("4")
    rec.apply()
    assert ST.stock_settings_view(app.cp, "OptionalSetting")["TOT"] == "4"
    app.show_page("stock:RoamingChannel")
    grid = app.pages["stock:RoamingChannel"]
    assert len(grid.tv.get_children()) == len(cp.stock["RoamingChannel"]) == 8
    grid.tv.selection_set("0")
    grid.show()
    grid.vars[5].set("RENAMED ROAM")
    grid.apply()
    assert app.cp.stock["RoamingChannel"][0][5] == "RENAMED ROAM"
    # channel digital extension through the editor
    app.show_page("channels")
    i = next(k for k, c in enumerate(app.cp.channels) if c.mode == "DMR")
    app.tree.selection_set(str(i))
    app.edit_channel()
    app.cf.set("talkaround", True)
    app.mf["DMR"].set("vocoder", "AMBE+2")
    app.ch_apply()
    c = app.cp.channels[i]
    assert c.talkaround and c.vocoder == "AMBE+2" and c.stock.get("Busy Lock/TX Permit") is not None
    # keys page
    app.show_page("keys")
    app.changed = False


def test_gui_d168_model(root, tmp_path):
    from cps import gui, codeplug as C, stock as ST
    import os
    from conftest import SYNTH_CSV_D168
    app = gui.App(root, None, "tcp:127.0.0.1:1", model="D168UV")
    assert app.cp.model == "D168UV" and app.model_var.get() == "D168UV"
    pages = set(app.nav_page.values())
    assert {"stock:QDC1200EnCodeTable", "stock:OptionalSetting", "trunksys", "keys"} <= pages and "stock:NXSetting" not in pages
    app.show_page("stock:OptionalSetting")
    app.pages["stock:OptionalSetting"].vars["TOT"].set("2")
    app.pages["stock:OptionalSetting"].apply()
    assert ST.stock_settings_view(app.cp, "OptionalSetting")["TOT"] == "2"
    # Bluetooth page: radio value lists, stored as the list index
    assert "stock:OptionalSetting#Bluetooth" in pages
    app.show_page("stock:OptionalSetting#Bluetooth")
    bt = app.pages["stock:OptionalSetting#Bluetooth"]
    assert set(bt.vars) == set(ST.PAGES["OptionalSetting#Bluetooth"]["keys"])
    assert bt.vars["BhtMicGain"].get() == ST.choice_text("BhtMicGain", ST.stock_settings_view(app.cp, "OptionalSetting")["BhtMicGain"])
    bt.vars["BhtHoldTime"].set("1S")
    bt.vars["BlueToothOn"].set("BT On")
    bt.apply()
    view = ST.stock_settings_view(app.cp, "OptionalSetting")
    assert view["BhtHoldTime"] == "1" and view["BlueToothOn"] == "1"
    # open a D168 stock CSV set, then convert to the D890UV and back
    app.changed = False
    app.open(SYNTH_CSV_D168)
    assert app.cp.model == "D168UV" and len(app.cp.channels) == 179
    gui.messagebox.askyesno = lambda *a, **k: True
    app.set_model("D890UV")             # messagebox: the codeplug has channels
    assert app.cp.model == "D890UV" and "stock:NXSetting" in set(app.nav_page.values())
    app.set_model("D168UV")
    assert app.cp.model == "D168UV" and "stock:NXSetting" not in set(app.nav_page.values())
    app.changed = False
    ST.use("D890UV")
