"""stock CPS dialogs that exist only in the .rdt (schema/rdt_dialogs.json): codeplug section 10 tables 64+, .rdt header /
tail / friends / encryption-code list. The field places were measured in the stock CPS (docs/STOCK_CPS_MAP.md)."""
import json
import os

import pytest

from cps import codeplug as C, rdt, stock as ST
from conftest import VEC
from dialog_sample import sample

VER = {"D890UV": "v1323", "D168UV": "v1292"}
MODELS = ["D890UV", "D168UV"]


@pytest.fixture(autouse=True)
def no_template(monkeypatch):
    monkeypatch.setattr(rdt, "template_path", lambda model="D890UV": None)
    yield
    ST.use("D890UV")


@pytest.mark.parametrize("model", MODELS)
def test_tables_have_shared_ids_and_columns(model):
    d = {n: (t["id"], [f["name"] for f in t["fields"]]) for n, t in ST.dialog_defs().items()}
    ids = [i for i, _ in d.values()]
    assert len(set(ids)) == len(ids) and min(ids) >= 64 and max(ids) < 0xE0
    ST.use(model)
    for n in ST.DIALOGS:
        assert ST.TABLES[n]["columns"] == d[n][1] and ST.TAB_ID[n] == d[n][0]


@pytest.mark.parametrize("model", MODELS)
def test_codeplug_round_trip_and_size(model):
    cp = sample(model)
    for radio in (False, True):
        cp2 = C.decode(C.encode(cp, for_radio=radio))
        for n in ST.DIALOGS:
            if cp.stock.get(n):
                assert cp2.stock[n] == cp.stock[n], n
    plain = C.load(os.path.join(os.path.dirname(VEC), "..", "examples", "synth%s.d8cp" % ("_d168" if model == "D168UV" else "")))
    assert len(C.encode(cp, for_radio=True)) - len(C.encode(plain, for_radio=True)) < 1500     # small for the radio
    cp3 = C.from_dict(C.to_dict(cp))
    assert cp3.stock["AlarmSetting"] == cp.stock["AlarmSetting"]


@pytest.mark.parametrize("model", MODELS)
def test_rdt_write_read_and_vectors(model, tmp_path):
    cp = sample(model)
    out = tmp_path / "d.rdt"
    rdt.save(cp, str(out))
    assert out.read_bytes() == open(os.path.join(VEC, "dialogs_%s.rdt" % VER[model]), "rb").read()   # opened by the stock CPS
    back = rdt.load(str(out))
    for n in ST.DIALOGS:
        assert back.stock.get(n, ST.default_rows(n)) == cp.stock.get(n, ST.default_rows(n)), n
    assert json.loads(json.dumps({n: cp.stock[n] for n in ST.DIALOGS if cp.stock.get(n)})) == \
        json.load(open(os.path.join(VEC, "dialogs_%s.json" % VER[model])))
    assert rdt.save(back, str(tmp_path / "e.rdt")) == [] and (tmp_path / "e.rdt").read_bytes() == out.read_bytes()


def test_friends_not_in_the_contact_list_are_reported(tmp_path):
    cp = sample("D890UV")
    cp.stock["FriendsList"].append(["3", "1234567"])
    lost = rdt.save(cp, str(tmp_path / "f.rdt"))
    assert any("1234567" in x for x in lost)
    assert [r[1] for r in rdt.load(str(tmp_path / "f.rdt")).stock["FriendsList"]] == ["9990101", "9990103"]


def test_unknown_newer_table_is_skipped():
    cp = C.new_codeplug()
    b = bytes([0x7F, 0, 0, 0, 1, 0]) + b"x" + b"\0"
    assert ST.decode_stock(b, cp).stock == {}


def test_model_only_fields_hidden():
    from cps import support as SU
    f = [f["name"] for f in ST.dialog_defs()["TalkAlias"]["fields"]]
    assert SU.page_marks("D890UV", "@talkalias", f, "TalkAlias")[0] == ["AliasPrio", "AliasFormat"]
    assert SU.page_marks("D168UV", "@talkalias", f, "TalkAlias")[0] == ["AliasType", "AliasPrio"]
