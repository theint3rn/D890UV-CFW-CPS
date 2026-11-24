import os

import pytest

from cps import codeplug as C, stock as ST, validate as V
from conftest import SYNTH_CSV, need, pvec

STOCKCSV = pvec("stock_csv_d890", "export.LST")     # the stock CPS's own CSV export of a real codeplug (not shipped)
# synthetic CSV set (tools/make_synth.py) and the stock export, with their counts (channels, zones, scan lists, contacts, TG lists)
CSV_SETS = [pytest.param(SYNTH_CSV, (179, 12, 6, 22, 3), id="synth"),
            pytest.param(STOCKCSV, (1405, 53, 24, 69, 1), id="stock-export", marks=need(STOCKCSV))]


@pytest.fixture(scope="module")
def synth():
    return ST.read_csv_set(SYNTH_CSV)


def test_schema_matches_stock_export():
    assert len(ST.ORDER) == 38 and len(ST.TABLES["OptionalSetting"]["columns"]) == 199
    assert ST.TABLES["Channel"]["columns"][:3] == ["No.", "Channel Name", "Receive Frequency"]
    tabs = [t for t, _ in ST.SCHEMA["optional_tabs"]]
    assert tabs[:3] == ["Work Mode", "Vox/BT", "STE"] and "Digital Func" in tabs
    assert [n for n, _ in ST.SCHEMA["tree"]] == ["Common Settings", "DMR", "NXDN", "Analog"]


@pytest.mark.parametrize("path,counts", CSV_SETS)
def test_csv_set_round_trip_byte_exact(path, counts, tmp_path):
    cp = ST.from_stock(ST.read_csv_set(path))
    assert (len(cp.channels), len(cp.zones), len(cp.scanlists), len(cp.contacts), len(cp.tglists)) == counts
    out = tmp_path / "out.LST"
    ST.write_csv_set(ST.to_stock(cp), str(out))
    d = os.path.dirname(path)
    for t in ST.ORDER:
        a = open(os.path.join(d, t + ".CSV"), "rb").read()
        b = open(os.path.join(tmp_path, t + ".CSV"), "rb").read()
        assert a == b, t


def test_stock_survives_binary_and_json(synth):
    cp = ST.from_stock(synth)
    b = C.encode(cp, for_radio=False)
    cp2 = C.decode(b)
    assert ST.to_stock(cp2) == ST.to_stock(cp)
    cp3 = C.from_dict(C.to_dict(cp))
    assert ST.to_stock(cp3) == ST.to_stock(cp)
    # radio: the stock contact database is not in section 10; ID / callsign / name go to section 16 (user database)
    radio = C.encode(cp, for_radio=True)
    assert len(radio) < len(b) and C.LAST_USERDB == {"written": 200, "dropped": 0}
    back = C.decode(radio).stock["DMRDigitalContactList"]
    rows = cp.stock["DMRDigitalContactList"]
    assert [(r[1], r[2], r[3][:12]) for r in back] == sorted((r[1], r[2], r[3][:12]) for r in rows)


def test_cfw_edits_reach_the_stock_export(synth):
    cp = ST.from_stock(synth)
    c = cp.channels[0]
    c.name, c.rx_hz, c.talkaround = "EDITED", 145500000, True
    ST.clear_mapped_overrides(c, "Channel")
    ST.set_stock_value(cp, "OptionalSetting", "TOT", "5")
    out = ST.to_stock(cp)
    row = dict(zip(ST.CH_COLS, out["Channel"][0]))
    assert (row["Channel Name"], row["Receive Frequency"], row["Talk Around(Simplex)"]) == ("EDITED", "145.50000", "On")
    assert row["Busy Lock/TX Permit"] == dict(zip(ST.CH_COLS, synth["Channel"][0]))["Busy Lock/TX Permit"]   # stock extra kept
    assert ST.stock_settings_view(cp, "OptionalSetting")["TOT"] == "5"
    assert ST.TABLES["OptionalSetting"]["columns"].index("TOT") is not None


def test_stock_validation():
    cp = C.new_codeplug()
    ST.set_stock_value(cp, "OptionalSetting", "TOT", "abc")
    assert any("TOT" in i.msg for i in V.errors(V.validate(cp)))


def test_new_codeplug_has_no_stock_overhead():
    cp = C.new_codeplug()
    assert ST.encode_stock(cp) == b""


def test_userdb_fills_the_region_and_reads_back(synth):
    """section 16: as many user database entries as fit (journal reserve kept), stock list order first, sorted by
    mode / ID; NXDN IDs > 65535 and duplicates skipped; read back from a radio into the stock tables"""
    cp = ST.from_stock(synth)
    cp.stock["DMRDigitalContactList"] = [[str(i + 1), str(9000000 + (7919 * i) % 900000), "C%d" % i, "Name %d" % i,
                                          "", "", "", "", "Private Call", ""] for i in range(20000)]
    cp.stock["NXDigitalContactList"] = [["1001", "NX1", "Ann", "Bee"] + [""] * 6, ["70000", "BAD"] + [""] * 8]
    radio = C.encode(cp, for_radio=True)
    w, d = C.LAST_USERDB["written"], C.LAST_USERDB["dropped"]
    assert w + d == 20001 and d > 0 and len(radio) <= C.REGION_SIZE - C.JOURNAL_RESERVE
    assert len(radio) + C.USER_REC > C.REGION_SIZE - C.JOURNAL_RESERVE - 16          # full
    back = C.decode(radio).stock["DMRDigitalContactList"]
    ids = [int(r[1]) for r in back]
    assert ids == sorted(ids) and len(ids) == w                                     # the DMR rows, sorted
    assert "NXDigitalContactList" not in C.decode(radio).stock                     # the NX row was dropped (no room)
    cp.stock["DMRDigitalContactList"] = cp.stock["DMRDigitalContactList"][:10]
    nx = C.decode(C.encode(cp, for_radio=True)).stock["NXDigitalContactList"]
    assert nx == [["1001", "NX1", "Ann Bee"] + [""] * 7]
