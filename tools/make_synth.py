#!/usr/bin/env python3
"""Synthetic test codeplug: made-up names, IDs and frequencies (no real callsigns, users or repeater lists).

It covers every mode and section the tests need: FM (simplex, repeaters, CTCSS/DCS, narrow/wide, AM air band), DMR
(colour codes, both slots, talkgroups, private calls, RX group lists, zones, Tier III), P25 (conventional, Phase 2,
trunked), NXDN (48 / 96, trunked), D-STAR (repeater routing), YSF (DG-ID, Wires-X), scan lists with priority channels,
encryption keys, stock CPS tables (user contact database, roaming channels / zones, APRS, FM broadcast, SMS, radio IDs,
hot keys) and the Bluetooth settings, for both radio models.

  python3 tools/make_synth.py            write examples/synth*.{d8cp,json,csv} and the stock CSV sets
                                         tests/vectors/stock_synth{,_d168}/synth.LST (written by cfw_cps itself)
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cps import codeplug as C, stock as ST, import_csv  # noqa: E402

CREATED = 1763600000
# made-up sites: (name, output MHz, offset MHz, colour code) - not real repeaters
SITES = [("Alpha", 446.025, -5.0, 1), ("Bravo", 446.075, -5.0, 2), ("Charlie", 446.125, -5.0, 3),
         ("Delta", 446.175, -5.0, 4), ("Echo", 446.225, -5.0, 5), ("Foxtrot", 446.275, -5.0, 6),
         ("Golf", 446.325, -5.0, 7), ("Hotel", 446.375, -5.0, 8)]
TGS = [("Local", 2), ("Region", 9), ("World", 91), ("Test TG 3100", 3100), ("Talk 1", 101), ("Talk 2", 102),
       ("Parrot", 9990), ("Net A", 31001), ("Net B", 31002), ("Net C", 31003)]
TONES = ["67.0", "88.5", "100.0", "103.5", "107.2", "110.9", "123.0", "127.3", "131.8", "146.2", "D023N", "D754I"]


def mhz(x):
    return int(round(x * 1e6))


def stock_row(table, **vals):
    cols = ST.TABLES[table]["columns"]
    d = dict(zip(cols, ST.TABLES[table]["defaults"] or ST.default_rows(table)[0]))
    for k, v in vals.items():
        assert k in d, (table, k)
        d[k] = v
    return [d[c] for c in cols]


def synth(model="D890UV"):
    """the synthetic codeplug for a radio model (D890UV data converted for the D168UV)"""
    ST.use("D890UV")
    cp = C.new_codeplug()
    s = cp.settings
    s.callsign, s.dmr_id, s.radio_name = "N0CALL", 9990001, "SYNTH TEST"
    s.p25_unit_id, s.nxdn_unit_id = 9990002, 4321
    s.ur, s.rpt1, s.rpt2, s.dstar_msg = "CQCQCQ", "XX0RPT B", "XX0RPT G", "synthetic test"
    # contacts (DMR talkgroups + private calls, P25 / NXDN groups)
    cp.contacts = [C.Contact(n, i) for n, i in TGS]
    cp.contacts += [C.Contact("Test User %d" % k, 9990100 + k, kind="private") for k in range(1, 9)]
    cp.contacts += [C.Contact("All Call", 16777215, kind="all"), C.Contact("P25 TG 1", 1, mode="P25"),
                    C.Contact("P25 TG 100", 100, mode="P25"), C.Contact("NX Group 300", 300, mode="NXDN")]
    cp.tglists = [C.TgList("Local+Region", [0, 1]), C.TgList("Wide", [1, 2, 3]), C.TgList("Nets", [7, 8, 9])]
    cp.trunksys = [C.TrunkSystem("Test P25 Trunk", "P25", 0x293, 0xBEE00, 0x3C1, 1, [460500000, 460525000]),
                   C.TrunkSystem("Test T3 Site", "DMR_T3", 1, control_channels=[439500000], chan_step_hz=12500),
                   C.TrunkSystem("Test NX Site", "NXDN_C", 5, control_channels=[451000000])]
    cp.trunksys[0].bandplan = [C.BandPlan(1, 851006250, 6250, -45000000, 12500, False, 1),
                               C.BandPlan(2, 762006250, 12500, 30000000, 12500, True, 2)]
    cp.trunksys[0].rfss, cp.trunksys[0].site, cp.trunksys[0].phase2 = 1, 2, True
    cp.keys = [C.Key("Test P25 key", "P25_AES256", 1, 0x84, "00112233445566778899AABBCCDDEEFF" * 2),
               C.Key("Test DMR BP", "DMR_BP", 7, 0, "1234")]
    cp.dstar_rpts = [C.DstarRepeater("Test Rpt B", "XX0RPT B", "XX0RPT G", 145670000, 145070000, True),
                     C.DstarRepeater("Test Rpt C", "XX0RPT C", "XX0RPT G", 438010000, 430610000, False)]
    cp.digi.dstar_dprs, cp.digi.ysf_wiresx_room, cp.digi.dprs_comment = True, 12345, "cfw synth test"
    ch = cp.channels = []
    # FM: 2 m / 70 cm simplex, repeaters with tones, narrow, RX only, air band AM
    for k in range(40):
        f = 146.52 + 0.015 * k if k < 20 else 446.0 + 0.0125 * (k - 20)
        ch.append(C.Channel(name="Simplex %d" % (k + 1), rx_hz=mhz(f), tx_hz=mhz(f), mode="FM", wide=k % 3 != 0,
                            power=C.POWERS[k % 4], scan_skip=k % 7 == 6))
    for k in range(40):
        out = 145.21 + 0.03 * k if k < 20 else 442.0 + 0.025 * (k - 20)
        off = -0.6 if k < 20 else 5.0
        t = TONES[k % len(TONES)]
        ch.append(C.Channel(name="Rpt %s%d" % ("AB"[k // 20], k % 20 + 1), rx_hz=mhz(out), tx_hz=mhz(out + off),
                            mode="FM", wide=True, rx_tone=t if k % 2 else None, tx_tone=t))
    ch.append(C.Channel(name="RX only 1", rx_hz=mhz(162.55), tx_hz=0, mode="FM", wide=True))
    # DMR: every site x every talkgroup, both slots, RX group lists
    for sn, f, off, cc in SITES:
        for ti, (tn, _) in enumerate(TGS):
            ch.append(C.Channel(name="%s %s" % (sn[:3].upper(), tn)[:16], rx_hz=mhz(f), tx_hz=mhz(f + off), mode="DMR",
                                cc=cc, slot=1 + ti % 2, tg=TGS[ti][1], contact=ti, tglist=ti % 3, power="mid"))
    ch.append(C.Channel(name="DMR Simplex 1", rx_hz=mhz(441.0), tx_hz=mhz(441.0), mode="DMR", cc=1, tg=99, contact=None))
    ch.append(C.Channel(name="DMR Direct 2", rx_hz=mhz(446.5), tx_hz=mhz(446.5), mode="DMR", cc=1, slot=2, tg=91,
                        contact=2, tdma_direct=True, talkaround=True))
    ch.append(C.Channel(name="T3 Control", rx_hz=439500000, tx_hz=434500000, mode="DMR", cc=1, tg=91, trunk=True,
                        trunksys=1))
    ch.append(C.Channel(name="DMR Private", rx_hz=mhz(441.1), tx_hz=mhz(441.1), mode="DMR", cc=2, tg=9990101,
                        contact=10, key=1))
    # P25 conventional / Phase 2 / trunked
    ch.append(C.Channel(name="P25 Trunk", rx_hz=460500000, tx_hz=465500000, mode="P25", nac=0x293, tg=100, trunk=True,
                        trunksys=0))
    for k in range(4):
        ch.append(C.Channel(name="P25 Conv %d" % (k + 1), rx_hz=mhz(441.3 + 0.0125 * k), tx_hz=mhz(446.3 + 0.0125 * k),
                            mode="P25", nac=0x293 + k, tg=1 if k % 2 else 100, key=0 if k == 3 else None))
    ch.append(C.Channel(name="P25 Phase 2", rx_hz=460550000, tx_hz=465550000, mode="P25P2", nac=0x293, slot=1,
                        wacn=0xBEE00, sysid=0x3C1))
    # NXDN 48 / 96, trunked
    for k in range(3):
        ch.append(C.Channel(name="NXDN %d" % (k + 1), rx_hz=mhz(441.5 + 0.00625 * k), tx_hz=mhz(441.5 + 0.00625 * k),
                            mode="NXDN", ran=k + 1, tg=300, nxdn_rate=9600 if k == 2 else 4800))
    ch.append(C.Channel(name="NXDN Trunk", rx_hz=451000000, tx_hz=456000000, mode="NXDN", ran=5, tg=300, trunk=True,
                        trunksys=2, vocoder="AMBE+2 EFR", nxdn_rate=9600))
    # D-STAR
    ch.append(C.Channel(name="DSTAR Rpt B", rx_hz=145670000, tx_hz=145070000, mode="DSTAR", ur="CQCQCQ",
                        rpt1="XX0RPT B", rpt2="XX0RPT G", dstar_rpt=0))
    ch.append(C.Channel(name="DSTAR Simplex", rx_hz=mhz(145.375), tx_hz=mhz(145.375), mode="DSTAR", ur="CQCQCQ"))
    # YSF
    ch.append(C.Channel(name="YSF DGID 20", rx_hz=mhz(145.3875), tx_hz=0, mode="YSF", dgid=20, power="low"))
    ch.append(C.Channel(name="YSF WiresX", rx_hz=mhz(439.9), tx_hz=mhz(434.9), mode="YSF", dgid=0, dgid_tx=30,
                        ysf_mode="VW", wiresx=True))
    ch[0].stock = {"Busy Lock/TX Permit": "Channel Free", "Optional Signal": "DTMF"}
    # zones: one per DMR site, FM, digital, all modes
    idx = {c.name: i for i, c in enumerate(ch)}
    first_dmr = idx["%s %s" % (SITES[0][0][:3].upper(), TGS[0][0])]
    ch[first_dmr].stock = {"Busy Lock/TX Permit": "Channel Free"}
    cp.zones = [C.Zone("FM Simplex", list(range(0, 40))), C.Zone("FM Repeaters", list(range(40, 81)))]
    for k, (sn, *_r) in enumerate(SITES):
        cp.zones.append(C.Zone("Site " + sn, list(range(first_dmr + 10 * k, first_dmr + 10 * k + 10))))
    digi = [i for i, c in enumerate(ch) if c.mode not in ("FM", "DMR")]
    cp.zones += [C.Zone("Digital Voice", digi), C.Zone("Mixed", [0, 40, first_dmr, digi[0], digi[-1]])]
    cp.scanlists = [C.ScanList("FM Simplex", list(range(0, 20)), prio1=0),
                    C.ScanList("FM Rpt", list(range(40, 60)), prio1=40, prio2=41, dwell_100ms=30)]
    for k, (sn, *_r) in enumerate(SITES[:4]):
        cp.scanlists.append(C.ScanList("Site " + sn, list(range(first_dmr + 10 * k, first_dmr + 10 * k + 10))))
    for i in range(0, 20):
        ch[i].scanlist = 0
    for i in range(40, 60):
        ch[i].scanlist = 1
    # stock CPS tables cfw keeps but does not use
    users = [stock_row("DMRDigitalContactList", **{"No.": str(k), "Radio ID": str(9990100 + k), "Callsign": "TEST%02d" % k,
                                                   "Name": "Test User %d" % k, "City": "Testville",
                                                   "State": "Nowhere", "Country": "Testland",
                                                   "Call Type": "Private Call"}) for k in range(1, 201)]
    roam = [stock_row("RoamingChannel", **{"No.": str(k + 1), "Receive Frequency": "%.5f" % f,
                                           "Transmit Frequency": "%.5f" % (f + off), "Color Code": str(cc),
                                           "Slot": "Slot%d" % (1 + k % 2), "Name": sn + " Roam"})
            for k, (sn, f, off, cc) in enumerate(SITES)]
    rzone = [stock_row("RoamingZone", **{"No.": "1", "Name": "Roam All",
                                         "Roaming Channel Member": "|".join(sn + " Roam" for sn, *_r in SITES)}),
             stock_row("RoamingZone", **{"No.": "2", "Name": "Roam North",
                                         "Roaming Channel Member": "|".join(sn + " Roam" for sn, *_r in SITES[:3])})]
    fm = [stock_row("FM", **{"No.": str(k + 1), "Frequency[MHz]": "%.3f" % (88.1 + 0.8 * k), "Scan": "Add",
                             "Name": "FM-%03d" % (k + 1) if k % 2 == 0 else ""}) for k in range(12)]
    sms = [stock_row("PrefabricatedSMS", **{"No.": str(k + 1), "Text": t})
           for k, t in enumerate(["Hello", "73", "QSY 446.500", "On my way", "Test message 5"])]
    rid = [stock_row("RadioIDList", **{"No.": "1", "Radio ID": str(s.dmr_id), "Name": "N0CALL"})]
    cp.stock = {"DMRDigitalContactList": users, "RoamingChannel": roam, "RoamingZone": rzone, "FM": fm,
                "PrefabricatedSMS": sms, "RadioIDList": rid, "OptionalSetting": ST.default_rows("OptionalSetting"),
                "APRS": ST.default_rows("APRS")}
    for k, v in (("TOT", "3"), ("Start_Char", "SYNTH"), ("Start_Char2", "TEST")):
        ST.set_stock_value(cp, "OptionalSetting", k, v)
    for k, v in (("Manual TX Interval[s]", "120"), ("Fixed Location Beacon", "1"), ("LatiDegree", "45"),
                 ("LongtiDegree", "100")):
        if ST.has_col("APRS", k):
            ST.set_stock_value(cp, "APRS", k, v)
    cp.created = CREATED
    cp.normalize()
    if model != "D890UV":
        ST.convert_model(cp, model)
    # Bluetooth page values (the radio's value lists where it has them)
    bt = {"BlueToothOn": "1", "BhtHoldTime": "33", "BhtHoldDelay": "3", "SpkInBlueTooth": "1", "BhtMicGain": "4",
          "BhtSpkGain": "2", "BhtPttHold": "1", "MicInBlueTooth": "1"}
    for k, v in bt.items():
        if ST.has_col("OptionalSetting", k):
            ST.set_stock_value(cp, "OptionalSetting", k, v)
    return cp


def main():
    ex, vec = os.path.join(ROOT, "examples"), os.path.join(ROOT, "tests", "vectors")
    for model, sfx in (("D890UV", ""), ("D168UV", "_d168")):
        cp = synth(model)
        C.save(cp, os.path.join(ex, "synth%s.d8cp" % sfx))
        C.save(cp, os.path.join(ex, "synth%s.json" % sfx))
        if not sfx:
            open(os.path.join(ex, "synth.csv"), "w").write(import_csv.export_csv(cp))
        d = os.path.join(vec, "stock_synth" + sfx)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        ST.write_csv_set(ST.to_stock(copy.deepcopy(cp)), os.path.join(d, "synth.LST"))
        print(model, "channels %d zones %d scan lists %d contacts %d TG lists %d" % (
            len(cp.channels), len(cp.zones), len(cp.scanlists), len(cp.contacts), len(cp.tglists)))
    ST.use("D890UV")


if __name__ == "__main__":
    main()
