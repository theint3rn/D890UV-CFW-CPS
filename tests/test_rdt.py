"""stock D890UV .rdt (V1323) reader/writer"""
import os

import pytest

from cps import rdt, stock as ST, codeplug as C
from conftest import SYNTH, SYNTH_CSV, TEMPLATES, VEC, need, need_template, pvec

SYNTH_D168 = SYNTH.replace("synth.d8cp", "synth_d168.d8cp")

# stock-CPS-made files (not shipped; tests skip without them, see conftest.py)
SMALL = pvec("stock_small_v1323.rdt")          # a real codeplug saved by the stock CPS V1.05 (user DB trimmed)
BASE = os.path.join(TEMPLATES, "new_v1323.rdt")  # stock CPS File > New, saved
STOCKCSV = pvec("stock_csv_d890", "export.LST")  # the stock CPS's own CSV export of SMALL


@pytest.mark.parametrize("path", [pytest.param(BASE, marks=need(BASE)), pytest.param(SMALL, marks=need(SMALL))])
def test_open_save_byte_identical(path, tmp_path):
    cp = rdt.load(path)
    out = tmp_path / "x.rdt"
    assert rdt.save(cp, str(out)) == []
    assert out.read_bytes() == open(path, "rb").read()


@need(SMALL, STOCKCSV)
def test_decoded_tables_equal_stock_csv_export():
    """a codeplug saved by the stock CPS (V1323, user DB trimmed) == the stock CPS's own CSV export of it"""
    t = rdt.tables_from_file(rdt.parse(open(SMALL, "rb").read()))
    exp = ST.read_csv_set(STOCKCSV)
    for tab in ("Channel", "RadioIDList", "DMRZone", "ScanList", "DMRTalkGroups", "PrefabricatedSMS", "FM",
                "DMRReceiveGroupCallList"):
        assert t[tab] == exp[tab], tab
    assert t["DMRDigitalContactList"][:300] == exp["DMRDigitalContactList"][:300]


@need(SMALL)
def test_edits_round_trip(tmp_path):
    cp = rdt.load(SMALL)
    c = cp.channels[0]
    old = ST.channel_key(c)
    c.name, c.talkaround = "CFW EDIT", True
    ST.clear_mapped_overrides(c, "Channel")
    ST.rename_channel_refs(cp, old, ST.channel_key(c))
    cp.zones[0].channels = cp.zones[0].channels[:5]
    cp.contacts[2].name = "TG 2 RENAMED"
    cp.stock["PrefabricatedSMS"].append(["15", "cfw test"])
    ST.set_stock_value(cp, "OptionalSetting", "Start_Char", "CFW CPS")
    ST.set_stock_value(cp, "OptionalSetting", "Beep", "1")
    out = str(tmp_path / "e.rdt")
    assert rdt.save(cp, out) == []
    cp2 = rdt.load(out)
    assert (cp2.channels[0].name, cp2.channels[0].talkaround, len(cp2.zones[0].channels)) == ("CFW EDIT", True, 5)
    assert cp2.contacts[2].name == "TG 2 RENAMED" and cp2.stock["PrefabricatedSMS"][-1] == ["15", "cfw test"]
    v = ST.stock_settings_view(cp2, "OptionalSetting")
    assert (v["Start_Char"], v["Beep"]) == ("CFW CPS", "1")
    a, b = ST.to_stock(cp), ST.to_stock(cp2)
    assert [t for t in ST.ORDER if t not in rdt.tail_tables() and a[t] != b[t]] == []


@need(SMALL)
def test_tail_edits_are_reported(tmp_path):
    cp = rdt.load(SMALL)
    cp.stock.setdefault("RoamingChannel", ST.default_rows("RoamingChannel"))[0][5] = "CHANGED"
    assert "RoamingChannel" in rdt.save(cp, str(tmp_path / "t.rdt"))


@need_template("D890UV")
def test_cfw_codeplug_to_rdt_and_back(tmp_path):
    """a cfw codeplug that never was an .rdt (stock CSV import) is written on the stock default file"""
    cp = ST.from_stock(ST.read_csv_set(SYNTH_CSV))
    cp.stock = {k: v for k, v in cp.stock.items() if k in ("PrefabricatedSMS", "FM", "RadioIDList", "OptionalSetting")}
    out = str(tmp_path / "synth.rdt")
    rdt.save(cp, out)
    cp2 = rdt.load(out)
    assert [c.name for c in cp2.channels] == [c.name for c in cp.channels]
    assert [z.name for z in cp2.zones] == [z.name for z in cp.zones] and len(cp2.scanlists) == len(cp.scanlists)


def test_d878_rdt_is_refused_by_the_v1323_reader():
    with pytest.raises(rdt.RdtError):
        rdt.parse(b"V1270" + bytes(4) + b"D878UV" + bytes(189))         # D878UV header (V1270 ... D878UV)


@pytest.fixture(autouse=True)
def back_to_d890():
    yield
    ST.use("D890UV")


@pytest.mark.parametrize("model", ["D890UV", "D168UV"])
def test_builtin_blank(model, tmp_path, monkeypatch):
    """without the user's stock new file the built-in blank file (cfw_cps's own, tools: rdt.blank_rdt) is the template:
    it parses, a codeplug written on it reads back, and both equal the shipped vectors (JS: web/test/run_tests.mjs)"""
    monkeypatch.setattr(rdt, "template_path", lambda model="D890UV": None)
    b = rdt.blank_rdt(model)
    ver = rdt.LAYOUT[model]["version"]
    assert b == open(os.path.join(VEC, "blank_%s.rdt" % ver.lower()), "rb").read()
    f = rdt.parse(b)
    assert f["model"] == model and len(f["tgs"]) == 1 and rdt.serialise(f) == b
    cp = C.load(SYNTH_D168 if model == "D168UV" else SYNTH)
    out = tmp_path / "s.rdt"
    rdt.save(cp, str(out))
    assert out.read_bytes() == open(os.path.join(VEC, "synth_%s.rdt" % ver.lower()), "rb").read()
    back = rdt.load(str(out))
    assert [c.name for c in back.channels] == [c.name for c in cp.channels]
    assert [z.name for z in back.zones] == [z.name for z in cp.zones] and len(back.scanlists) == len(cp.scanlists)
    assert [(c.name, c.id) for c in back.contacts] == [(c.name, c.id) for c in cp.contacts]


@need(SMALL)
def test_reopened_rdt_saves_without_template(tmp_path, monkeypatch):
    """an opened .rdt is its own template: open + save (and a new channel) work with no template file"""
    monkeypatch.setattr(rdt, "template_path", lambda model="D890UV": None)
    cp = rdt.load(SMALL)
    out = tmp_path / "x.rdt"
    assert rdt.save(cp, str(out)) == [] and out.read_bytes() == open(SMALL, "rb").read()
    cp.channels.append(C.Channel(name="NEW FM", rx_hz=145500000, tx_hz=145500000))
    rdt.save(cp, str(out))
    assert "NEW FM" in [c.name for c in rdt.load(str(out)).channels]


@need(pvec("nx_ref_v1323.rdt"), pvec("nx_stock_v1323.rdt"))
def test_nxsetting_matches_stock_cps(tmp_path):
    """nx_stock_v1323.rdt = the stock CPS's own save after importing an NXSetting row (alias, u16 IDs, flags) into
    nx_ref_v1323.rdt; cfw decodes those values and, writing them into the reference, gives the same bytes."""
    from cps import rdt, stock as ST
    ref, stock = pvec("nx_ref_v1323.rdt"), pvec("nx_stock_v1323.rdt")
    cp = rdt.load(stock)
    nx = ST.stock_settings_view(cp, "NXSetting")
    assert nx["OwnId"] == "1234" and nx["OwnIdAbleMax"] == "4000" and nx["TxAliasName"] == "CFW7" and nx["NxdnMoniId"] == "7"
    cp2 = rdt.load(ref)
    for k in ("OwnId", "StationId ", "OwnIdAbleMax", "TxAliasEn", "TxAliasName", "ResetTime", "StateMsg2", "NxdnMoni",
              "NxdnMoniId", "PriCallBeep"):
        ST.set_stock_value(cp2, "NXSetting", k, ST.stock_settings_view(cp, "NXSetting")[k])
    out = str(tmp_path / "nx_out.rdt")
    assert rdt.save(cp2, out) == []
    a, b = open(out, "rb").read(), open(stock, "rb").read()
    assert len(a) == len(b) and a[9:] == b[9:]          # bytes < 9 hold the save counter
