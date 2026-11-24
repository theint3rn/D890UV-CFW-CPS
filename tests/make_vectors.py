#!/usr/bin/env python3
"""Write the shared Python<->JS test vectors (tests/vectors/). The JS side (web/test/run_tests.mjs) must decode each
.d8cp to the .json, encode the .json to the same bytes, and produce the same validation issues and diff lines."""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
from cps import codeplug as C, validate as V, diff as D, import_csv, import_rdt  # noqa: E402
from test_codeplug import sample  # noqa: E402
from conftest import RDT, PRIV, PVEC, SYNTH, SYNTH_CSV, SYNTH_CSV_D168, TEMPLATES  # noqa: E402

OUT = os.path.join(HERE, "vectors")
# vectors made from stock-CPS files (not shipped) go to $CFW_CPS_PRIVATE/vectors when that folder exists (conftest.py)


def put(name, cp, out=OUT, keep_created=False):
    cp.created = cp.created if keep_created else 1763600000
    b = C.encode(cp)
    open(os.path.join(out, name + ".d8cp"), "wb").write(b)
    open(os.path.join(out, name + ".json"), "w").write(C.dumps_json(cp))
    open(os.path.join(out, name + ".decoded.json"), "w").write(C.dumps_json(C.decode(b)))   # = .json unless lossy
    iss = [{"level": i.level, "where": i.where, "msg": i.msg} for i in V.validate(cp)]
    json.dump(iss, open(os.path.join(out, name + ".issues.json"), "w"), indent=1)


def diff_vector(name, cp, out=OUT):
    k2 = copy.deepcopy(cp)
    k2.channels[5].name = "CHANGED"
    k2.channels[7].rx_hz += 12500
    del k2.channels[-3:]
    k2.zones.append(C.Zone("NEW ZONE", [1, 2]))
    k2.settings.dmr_id = 9990001
    json.dump({"old": name, "new": C.to_dict(k2), "lines": D.diff(cp, k2), "summary": D.summary(cp, k2)},
              open(os.path.join(out, "diff_%s.json" % name), "w"), indent=1)


def stock_set(lst, name, out=OUT):
    from cps import stock as ST
    cp = ST.from_stock(ST.read_csv_set(lst))
    open(os.path.join(out, name + ".d8cp"), "wb").write(C.encode(cp, for_radio=False))
    open(os.path.join(out, name + ".json"), "w").write(C.dumps_json(cp))


def main():
    os.makedirs(OUT, exist_ok=True)
    s = sample()
    put("sample", s)
    e = C.new_codeplug()
    e.channels = [C.Channel(name="ONLY", rx_hz=145500000, tx_hz=0)]
    put("minimal", e.normalize())
    bad = copy.deepcopy(s)
    bad.channels[0].rx_hz = 300000000
    bad.channels[1].tx_tone = "99.9"
    bad.channels[3].cc, bad.channels[3].slot, bad.channels[3].contact = 16, 2, 99
    bad.channels[5].trunksys = 1
    bad.channels[6].nac, bad.channels[6].wacn = 0x1000, 0
    bad.channels[7].ran = 64
    bad.channels[8].ur = "lower"
    bad.channels[9].dgid = 120
    bad.zones[0].channels += [500, 0]
    bad.trunksys[0].control_channels = []
    bad.settings.dmr_id = 99999999
    bad.settings.callsign = "TOO LONG CALL"
    put("bad", bad)
    # synthetic codeplug (tools/make_synth.py) and its stock CSV sets
    syn = C.load(SYNTH)
    syn.stock.pop("DMRDigitalContactList", None)        # radio encoding leaves the user DB out: keep .json == decode
    put("synth", syn, keep_created=True)
    diff_vector("synth", syn)
    from cps import stock as ST
    stock_set(SYNTH_CSV, "synthstock")
    priv = os.path.isdir(PVEC)
    if priv and os.path.exists(RDT):            # a real D878UV codeplug through the importer
        cp, _ = import_rdt.import_rdt(RDT)
        put("d878", cp, PVEC, keep_created=True)
        diff_vector("d878", cp, PVEC)
    if priv and os.path.exists(os.path.join(PVEC, "stock_csv_d890", "export.LST")):
        stock_set(os.path.join(PVEC, "stock_csv_d890", "export.LST"), "stockcsv", PVEC)
    s2 = sample()
    s2.keys = [C.Key("P25 key 1", "P25_AES256", 1, 0x84, "00112233445566778899AABBCCDDEEFF00112233445566778899AABBCCDDEEFF"),
               C.Key("DMR basic", "DMR_BP", 7, 0, "1234")]
    s2.dstar_rpts = [C.DstarRepeater("Test Rpt B", "XX0RPT B", "XX0RPT G", 145670000, 145070000, True)]
    s2.digi.dstar_dprs, s2.digi.ysf_wiresx_room, s2.digi.dprs_comment = True, 12345, "cfw test"
    s2.trunksys[0].bandplan = [C.BandPlan(1, 851006250, 6250, -45000000, 12500, False, 1), C.BandPlan(2, 762006250, 12500, 30000000, 12500, True, 2)]
    s2.trunksys[0].rfss, s2.trunksys[0].site, s2.trunksys[0].phase2 = 1, 2, True
    s2.trunksys.append(C.TrunkSystem("NX site", "NXDN_C", 5, control_channels=[451000000]))
    s2.channels[7].trunksys, s2.channels[7].nxdn_rate, s2.channels[7].vocoder, s2.channels[7].key = 2, 9600, "AMBE+2 EFR", None
    s2.channels[5].key, s2.channels[5].talkaround = 0, True
    s2.channels[9].dgid_tx, s2.channels[9].ysf_mode, s2.channels[9].wiresx = 30, "VW", True
    s2.channels[8].dstar_rpt = 0
    s2.channels[4].talkaround, s2.channels[4].tdma_direct = True, True
    s2.channels[3].key = 1
    s2.channels[0].stock = {"Busy Lock/TX Permit": "Channel Free", "Optional Signal": "DTMF"}
    s2.stock = {"OptionalSetting": ST.default_rows("OptionalSetting"), "PrefabricatedSMS": [["1", "Hello"], ["2", "73"]]}
    ST.set_stock_value(s2, "OptionalSetting", "TOT", "3")
    put("digital", s2)
    from cps import rdt as RD
    # stock .rdt files -> JSON (JS reader == Python reader); private: they hold stock CPS data
    rdts = [(os.path.join(TEMPLATES, "new_v1323.rdt"), "new_v1323.json"), (os.path.join(PVEC, "stock_small_v1323.rdt"),
            "stock_small_v1323.json"), (os.path.join(TEMPLATES, "new_v1292.rdt"), "new_v1292.json"),
            (os.path.join(PVEC, "stock_small_v1292.rdt"), "stock_small_v1292.json")]
    for src, name in rdts:
        if priv and os.path.exists(src):
            open(os.path.join(PVEC, name), "w").write(C.dumps_json(RD.load(src)))
    # built-in blank .rdt files and the synthetic codeplug written on them (no stock template)
    tp = RD.template_path
    RD.template_path = lambda model="D890UV": None
    for model, syn_path in (("D890UV", SYNTH), ("D168UV", SYNTH.replace("synth.d8cp", "synth_d168.d8cp"))):
        ver = RD.LAYOUT[model]["version"].lower()
        open(os.path.join(OUT, "blank_%s.rdt" % ver), "wb").write(RD.blank_rdt(model))
        RD.save(C.load(syn_path), os.path.join(OUT, "synth_%s.rdt" % ver))
    RD.template_path = tp
    ST.use("D890UV")
    # D168UV: synthetic D168 CSV set, the digital vector converted to the D168
    stock_set(SYNTH_CSV_D168, "synthstock_d168")
    if priv and os.path.exists(os.path.join(PVEC, "stock_csv_d168", "export.LST")):
        stock_set(os.path.join(PVEC, "stock_csv_d168", "export.LST"), "stockcsv_d168", PVEC)
    s3 = copy.deepcopy(s2)
    ST.convert_model(s3, "D168UV")
    put("digital_d168", s3)
    small = os.path.join(PVEC, "stock_small_v1292.rdt")
    if priv and os.path.exists(small):           # Bluetooth page values (test_d168.py BT_LABELS)
        from test_d168 import BT_LABELS
        bt = RD.load(small)
        for k, v in BT_LABELS.items():
            ST.set_stock_value(bt, "OptionalSetting", k, ST.choice_value(k, v))
        RD.save(bt, os.path.join(PVEC, "bt_v1292.rdt"))
    ST.use("D890UV")
    chirp = ("Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip\n"
             "0,RPT 1,146.970000,-,0.600000,Tone,103.5,88.5,023,NN,FM,5.00,\n"
             "1,TSQ,446.500000,,0.000000,TSQL,88.5,123.0,023,NN,NFM,5.00,S\n"
             "2,DCS,147.000000,+,0.600000,DTCS,88.5,88.5,754,NR,FM,5.00,\n"
             "3,AIR,121.500000,,0.000000,,88.5,88.5,023,NN,AM,5.00,\n")
    open(os.path.join(OUT, "chirp.csv"), "w").write(chirp)
    open(os.path.join(OUT, "sample.csv"), "w").write(import_csv.export_csv(s))
    for nm in ("chirp", "sample"):
        p = os.path.join(OUT, nm + ".csv")
        cp, _ = import_csv.import_csv(p)
        cp.created = 1763600000
        open(os.path.join(OUT, nm + ".csv.d8cp"), "wb").write(C.encode(cp))
    print("vectors in", OUT, sorted(os.listdir(OUT)))
    if priv:
        print("private vectors in", PVEC)


if __name__ == "__main__":
    main()
