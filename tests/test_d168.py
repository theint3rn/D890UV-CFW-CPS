"""D168UV model: stock D168UV CPS V1.07 schema, CSV set, .rdt (V1292), conversion, link (ident D168CFW)"""
import copy
import os

import pytest

from cps import codeplug as C, stock as ST, rdt, validate as V, ops, link
from conftest import ROOT, SYNTH_CSV_D168, TEMPLATES, need, need_template, pvec
from fake_radio import FakeCfwRadio
from test_codeplug import sample

# stock-CPS-made files (not shipped; tests skip without them, see conftest.py)
STOCKCSV = pvec("stock_csv_d168", "export.LST")     # stock D168 CPS CSV export of a real codeplug
BASE = os.path.join(TEMPLATES, "new_v1292.rdt")       # stock D168 CPS File > New, saved
SMALL = pvec("stock_small_v1292.rdt")                 # the STOCKCSV codeplug saved by the stock D168 CPS (user DB trimmed)
# synthetic CSV set (tools/make_synth.py) and the stock export, with their counts (channels, zones, scan lists, contacts, TG lists)
CSV_SETS = [pytest.param(SYNTH_CSV_D168, (179, 12, 6, 22, 3), id="synth"),
            pytest.param(STOCKCSV, (1405, 53, 24, 69, 1), id="stock-export", marks=need(STOCKCSV))]


@pytest.fixture(autouse=True)
def back_to_d890():
    yield
    ST.use("D890UV")


def csv_set(path):
    t = ST.read_csv_set(path)
    assert ST.MODEL == "D168UV"
    return t


def test_schema():
    s = ST.use("D168UV")
    assert len(ST.ORDER) == 28 and len(ST.TABLES["OptionalSetting"]["columns"]) == 195
    assert [n for n, _ in s["tree"]] == ["Public", "Digital", "Analog"]
    assert ST.csv_name("DMRZone") == "Zone" and ST.csv_name("DMRTalkGroups") == "TalkGroups"
    assert "Contact/Talk Group TG/DMR ID" not in ST.CH_COLS and "Contact/Talk Group" in ST.CH_COLS
    assert [t for t, _ in s["optional_tabs"]][:3] == ["Work Mode", "Vox/BT", "STE"]
    assert ST.detect_model(["Channel", "Zone", "TalkGroups"]) == "D168UV"
    assert ST.detect_model(["Channel", "DMRZone", "NXSetting"]) == "D890UV"


@need(SMALL)
def test_man_down_toggle(tmp_path):
    """stock Alarm Setting "Man Down" checkbox = CSV column FailAlarm = .rdt byte 0x71 (stock CPS tick + save + diff)"""
    s = ST.use("D168UV")
    assert s["labels"]["FailAlarm"] == "Man Down" and ["Man Down", ["FailAlarm", "ManDownWait"]] in s["optional_tabs"]
    assert rdt.opt_fields("D168UV")["FailAlarm"] == ("A", 0x71)
    orig = open(SMALL, "rb").read()
    cp = rdt.load(SMALL)
    assert ST.stock_settings_view(cp, "OptionalSetting")["FailAlarm"] == "0"
    ST.set_stock_value(cp, "OptionalSetting", "FailAlarm", 1)
    out = tmp_path / "md.rdt"
    assert rdt.save(cp, str(out)) == []
    new = out.read_bytes()
    assert len(new) == len(orig) and [i for i in range(len(orig)) if orig[i] != new[i]] == [0x71] and new[0x71] == 1
    assert ST.stock_settings_view(rdt.load(str(out)), "OptionalSetting")["FailAlarm"] == "1"


@pytest.mark.parametrize("path,counts", CSV_SETS)
def test_csv_set_round_trip_byte_exact(path, counts, tmp_path):
    cp = ST.from_stock(csv_set(path), "D168UV")
    assert cp.model == "D168UV" and cp.settings.radio_name == "D168UV cfw"
    assert (len(cp.channels), len(cp.zones), len(cp.scanlists), len(cp.contacts), len(cp.tglists)) == counts
    dig = [c for c in cp.channels if c.mode == "DMR"]
    assert dig and all(c.contact is not None and c.tg == cp.contacts[c.contact].id for c in dig[:50])
    assert all(len(z.channels) > 0 for z in cp.zones)
    out = tmp_path / "out.LST"
    ST.write_csv_set(ST.to_stock(cp), str(out))
    d = os.path.dirname(path)
    for t in ST.ORDER:
        n = ST.csv_name(t) + ".CSV"
        assert open(os.path.join(d, n), "rb").read() == open(os.path.join(tmp_path, n), "rb").read(), n


def test_binary_and_json_keep_model():
    cp = ST.from_stock(csv_set(SYNTH_CSV_D168), "D168UV")
    b = C.encode(cp, for_radio=False)
    assert b[18] == 1 and b[19] == 0                      # model id in the header
    cp2 = C.decode(b)
    assert cp2.model == "D168UV" and ST.to_stock(cp2) == ST.to_stock(cp)
    cp3 = C.from_dict(C.to_dict(cp))
    assert cp3.model == "D168UV" and ST.to_stock(cp3) == ST.to_stock(cp)
    assert C.to_dict(cp)["model"] == "D168UV" and "model" not in C.to_dict(sample())
    assert C.encode(sample())[18:20] == b"\0\0"            # D890UV codeplugs unchanged
    radio = C.encode(cp, for_radio=True)
    assert len(radio) <= C.MODELS["D168UV"]["region"]
    n = len(cp.stock.get("DMRDigitalContactList", []))       # user database (section 16): every entry fits
    assert C.LAST_USERDB["dropped"] == 0 and len(C.decode(radio).stock.get("DMRDigitalContactList", [])) == n


def test_unknown_model_rejected():
    b = bytearray(C.encode(sample()))
    b[18] = 7
    import struct
    import zlib
    struct.pack_into("<I", b, 12, zlib.crc32(bytes(b[16:])) & 0xFFFFFFFF)
    with pytest.raises(C.CodeplugError):
        C.decode(bytes(b))
    with pytest.raises(C.CodeplugError):
        C.from_dict(dict(C.to_dict(sample()), model="X1"))


@pytest.mark.parametrize("p", [pytest.param(BASE, marks=need(BASE)), pytest.param(SMALL, marks=need(SMALL))])
def test_rdt_open_save_identical(p, tmp_path):
    cp = rdt.load(p)
    assert cp.model == "D168UV"
    out = tmp_path / "x.rdt"
    assert rdt.save(cp, str(out)) == []
    assert out.read_bytes() == open(p, "rb").read()


@need(SMALL, STOCKCSV)
def test_rdt_tables_equal_stock_export():
    """a codeplug saved by the stock D168 CPS (V1292, user DB trimmed) == the stock CPS's own CSV export"""
    t = rdt.tables_from_file(rdt.parse(open(SMALL, "rb").read()))
    exp = ST.read_csv_set(STOCKCSV)
    for tab in ("Channel", "RadioIDList", "DMRZone", "ScanList", "DMRTalkGroups", "PrefabricatedSMS", "FM",
                "DMRReceiveGroupCallList"):
        assert t[tab] == exp[tab], tab


@need_template("D168UV")
def test_new_d168_codeplug_to_rdt_and_back(tmp_path):
    cp = C.new_codeplug("D168UV")
    cp.contacts = [C.Contact("TG 91", 91, "group", "DMR"), C.Contact("Local", 9, "group", "DMR")]
    cp.channels.append(C.Channel(name="DMR SIMPLEX", rx_hz=441000000, tx_hz=441000000, mode="DMR", cc=1, slot=1, tg=91, contact=0))
    cp.zones = [C.Zone("Z1", [0, 2])]
    cp.tglists = [C.TgList("RX", [0, 1])]
    cp.normalize()
    p = tmp_path / "n.rdt"
    rdt.save(cp, str(p))
    back = rdt.load(str(p))
    assert back.model == "D168UV" and [c.name for c in back.channels] == ["2M CALL", "70CM CALL", "DMR SIMPLEX"]
    assert back.channels[2].contact == 0 and back.channels[2].tg == 91
    assert back.zones[0].channels == [0, 2] and back.tglists[0].contacts == [0, 1]


def test_convert_keeps_cfw_data():
    s = sample()
    s.stock = {"OptionalSetting": ST.default_rows("OptionalSetting"), "NXSetting": ST.default_rows("NXSetting")}
    ST.set_stock_value(s, "OptionalSetting", "TOT", "3")
    s.channels[0].stock = {"Busy Lock/TX Permit": "Channel Free", "NxdnRpga": "1"}
    d = copy.deepcopy(s)
    ST.convert_model(d, "D168UV")
    assert d.model == "D168UV" and "NXSetting" not in d.stock
    assert ST.stock_settings_view(d, "OptionalSetting")["TOT"] == "3"
    assert d.channels[0].stock == {"Busy Lock/TX Permit": "Channel Free"}
    assert [c.mode for c in d.channels] == [c.mode for c in s.channels] and d.trunksys == s.trunksys
    assert not V.errors(V.validate(d))
    e = C.decode(C.encode(d))
    assert e.model == "D168UV" and e.channels == d.channels
    ST.convert_model(e, "D890UV")
    assert e.model == "D890UV" and e.settings.radio_name == "D890UV cfw"


def test_link_d168(tmp_path):
    r = FakeCfwRadio(ident=b"D168CFW")
    try:
        port = "tcp:127.0.0.1:%d" % r.port
        cp = sample()
        ST.convert_model(cp, "D168UV")
        data = ops.write_radio(port, cp, log=lambda s: None)
        back, raw, inf = ops.read_radio(port, log=lambda s: None)
        assert raw == data and back.model == "D168UV" and inf["model"] == "D168UV"
        with pytest.raises(link.LinkError, match="D168UV"):
            ops.write_radio(port, sample(), log=lambda s: None)          # D890UV codeplug -> D168 radio: refused
    finally:
        r.close()
    r = FakeCfwRadio(ident=b"D168UV\0")                                   # stock-like ident: refused
    try:
        with pytest.raises(link.LinkError, match="not the cfw"):
            ops.read_radio("tcp:127.0.0.1:%d" % r.port, log=lambda s: None)
    finally:
        r.close()


def test_cli_new_import_convert(tmp_path):
    import subprocess
    import sys
    cli = os.path.join(ROOT, "cfw_cps.py")
    n = tmp_path / "n.json"
    subprocess.run([sys.executable, cli, "new", "--model", "D168UV", "-o", str(n)], check=True, capture_output=True)
    assert C.load(str(n)).model == "D168UV"
    o = tmp_path / "k.d8cp"
    subprocess.run([sys.executable, cli, "import", SYNTH_CSV_D168, "-o", str(o)], check=True, capture_output=True)
    assert C.load(str(o)).model == "D168UV"
    o2 = tmp_path / "k890.d8cp"
    r = subprocess.run([sys.executable, cli, "export", str(o), "--model", "D890UV", "-o", str(o2)], capture_output=True, text=True)
    assert r.returncode == 0 and C.load(str(o2)).model == "D890UV"
    lst = tmp_path / "set" / "x.LST"
    subprocess.run([sys.executable, cli, "export", str(o), "-o", str(lst)], check=True, capture_output=True)
    assert (tmp_path / "set" / "Zone.CSV").exists() and (tmp_path / "set" / "QDC1200EnCodeTable.CSV").exists()


def test_new_channel_gets_a_free_number():
    """stock channel numbers can have gaps (real codeplugs do); an added channel must not reuse one (the stock CPS would
    merge them)"""
    cp = ST.from_stock(ST.read_csv_set(SYNTH_CSV_D168), "D168UV")
    for i, c in enumerate(cp.channels):
        c.stock = dict(c.stock, **{"No.": str(i + 1 + (i >= 5) * 3)})          # numbers 1-5, 9, 10, ...
    cp.channels.append(C.Channel(name="CFW NEW", rx_hz=446100000, tx_hz=446100000, mode="P25", nac=0x293, tg=1))
    cp.normalize()
    nos = [r[0] for r in ST.to_stock(cp)["Channel"]]
    assert len(nos) == len(set(nos))


@need(SMALL)
def test_rdt_header_length_field(tmp_path):
    """u32 at offset 5 = file length - 14: the stock CPS refuses ("file error") a file without it"""
    import struct
    cp = rdt.load(SMALL)
    cp.stock["DMRDigitalContactList"] = cp.stock["DMRDigitalContactList"][:10]
    out = tmp_path / "t.rdt"
    rdt.save(cp, str(out))
    b = out.read_bytes()
    assert struct.unpack_from("<I", b, 5)[0] == len(b) - 14


@need(STOCKCSV, pvec("csvset_stock_v1292.rdt"), BASE)
def test_cfw_built_rdt_equals_stock_cps_save(tmp_path, monkeypatch):
    """csvset_stock_v1292.rdt: the cfw CPS wrote this codeplug (stock D168 CSV set + an added P25 channel + TOT=3) as an
    .rdt; the stock D168 CPS V1.07 opened it and saved it again byte for byte. Writing it again must give these bytes."""
    monkeypatch.setattr(rdt, "template_path", lambda model="D890UV": BASE)
    cp = ST.from_stock(ST.read_csv_set(STOCKCSV))
    cp.stock = {k: v for k, v in cp.stock.items() if k in ("PrefabricatedSMS", "FM", "RadioIDList")}
    cp.channels.append(C.Channel(name="CFW P25", rx_hz=446100000, tx_hz=446100000, mode="P25", nac=0x293, tg=1))
    cp.normalize()
    ST.set_stock_value(cp, "OptionalSetting", "TOT", "3")
    out = tmp_path / "k.rdt"
    assert rdt.save(cp, str(out)) == []
    assert out.read_bytes() == open(pvec("csvset_stock_v1292.rdt"), "rb").read()


BT_LABELS = {"BlueToothOn": "BT On", "BhtHoldTime": "infinite", "BhtHoldDelay": "2.5S", "SpkInBlueTooth": "On",
             "BhtMicGain": "Level 5", "BhtSpkGain": "Level 3", "BhtPttHold": "1", "MicInBlueTooth": "1"}


def test_bluetooth_page():
    """D168 Bluetooth page (radio Settings > BT, no stock CPS page): keys, radio value lists"""
    s = ST.use("D168UV")
    pg = ST.PAGES["OptionalSetting#Bluetooth"]
    assert ["Bluetooth", "OptionalSetting#Bluetooth"] in dict(s["tree"])["Public"]
    assert set(pg["keys"]) == set(BT_LABELS) and ["Bluetooth", pg["keys"]] in s["optional_tabs"]
    assert not set(pg["keys"]) & set(dict(s["optional_tabs"])["More (CSV only)"])
    assert "Pin Code" in pg["note"] and "BT Names" in pg["note"]
    assert len(ST.CHOICES["BhtHoldTime"]) == 34 and ST.choice_text("BhtHoldTime", "10") == "10S"
    assert ST.choice_text("BhtHoldDelay", "0") == "30ms" and ST.choice_value("BhtHoldDelay", "5.5S") == "10"
    assert ST.choice_text("BhtMicGain", "1") == "Level 2" and ST.choice_text("BhtMicGain", "9") == "9"
    assert ST.choice_value("BhtMicGain", "7") == "7" and ST.choice_text("TOT", "3") == "3"
    ST.use("D890UV")                    # D890UV: same page with the stock CSV values (no radio lists)
    assert "OptionalSetting#Bluetooth" in ST.PAGES and not any(k in ST.CHOICES for k in ST.PAGES["OptionalSetting#Bluetooth"]["keys"])
    assert ["Bluetooth", "OptionalSetting#Bluetooth"] in dict(ST.SCHEMA["tree"])["Common Settings"]


@need(SMALL, pvec("bt_v1292.rdt"))
def test_bluetooth_rdt_bytes(tmp_path):
    """The Bluetooth .rdt bytes go to the radio settings block NAND 0x02500000 (stock CPS write capture): BT On +0xB1,
    Mic in BT +0xB2, BT+int spk +0xB3, Mic/Spk Gain +0xB6/+0xB7, Hold Time +0xED, RX Delay +0xEE, PTT HOLD +0x15."""
    ST.use("D168UV")
    cp = rdt.load(SMALL)
    for k, v in BT_LABELS.items():
        ST.set_stock_value(cp, "OptionalSetting", k, ST.choice_value(k, v))
    out = tmp_path / "bt.rdt"
    assert rdt.save(cp, str(out)) == []
    new, orig = out.read_bytes(), open(SMALL, "rb").read()
    assert new == open(pvec("bt_v1292.rdt"), "rb").read()
    n = len(new)
    assert [i for i in range(n) if new[i] != orig[i]] == [99, 200, 201, 202, 205, n - 23319, n - 23318]
    view = ST.stock_settings_view(rdt.load(str(out)), "OptionalSetting")
    assert {k: ST.choice_text(k, view[k]) for k in BT_LABELS} == BT_LABELS
