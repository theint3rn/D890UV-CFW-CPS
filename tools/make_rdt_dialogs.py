#!/usr/bin/env python3
"""Write schema/rdt_dialogs.json (copied to web/schema/): the stock CPS dialogs that exist only in the .rdt (no CSV), as
extra stock tables. How the fields were found: docs/STOCK_CPS_MAP.md "Dialogs kept only in the .rdt" and
tools/stock_rdt_experiments (change one field in the stock CPS, save, diff; change one byte, look which field moves).
Only fields whose place in the file was measured are listed; the others are in UNDECODED.

tables: name -> {id (table id in codeplug section 10, the same on both radios), kind, node (tree node "@...") or after
({model: stock node the extra tree entry follows}), title, models, note, groups, fields [{name, label, choices?,
<model>: {type, seg, off, default}}]}
types: u8 / u16 / u32 (little endian), hex3 / hex4 (u16 shown as hex), chan (u16 channel index; the value is the
channel's number), str3 (3 characters), hstr (header string: length byte + cstr), list (rows; see cps/rdt.py)
seg: A / B / C = header segments (cps/rdt.py LAYOUT, A with its variable strings taken out), E = distance from the end of the
tail (D890UV: the NX alias length is added), H = the variable header strings (name)
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOTH = ["D890UV", "D168UV"]
D8, D1 = "D890UV", "D168UV"
MS10 = "x 10 ms"
STD = ["ZVEI1", "ZVEI2", "ZVEI3", "PZVEI", "DZVEI", "PDZVEI", "CCIR1", "CCIR2"]        # the first 8 entries of the list
RESP = ["None", "Beep Tone", "Beep Tone & Respond"]


def F(name, label, loc, default="0", choices=None, typ="u8", models=None):
    """field at the same segment offset on the models (loc = {model: (seg, off)} or (seg, off))"""
    d = {"name": name, "label": label}
    if choices:
        d["choices"] = choices
    locs = loc if isinstance(loc, dict) else {m: loc for m in (models or BOTH)}
    for m, (seg, off) in locs.items():
        d[m] = {"type": typ, "seg": seg, "off": off, "default": str(default[m] if isinstance(default, dict) else default)}
    return d


def alarm():
    c = lambda o: ("C", o)
    return [
        F("AlarmAEmergency", "Analog Emergency Alarm", c(0x33), 0, ["Alarm", "Transpond+Background", "Transpond+Alarm", "Both"]),
        F("AlarmAEniType", "Analog ENI Type", c(0x34), 0),
        F("AlarmATime", "Analog Alarm Time [s]", c(0x36), 20),
        F("AlarmATxTime", "Analog Duration of TX [s]", c(0x37), 31),
        F("AlarmARxTime", "Analog Duration of RX [s]", c(0x38), 31),
        F("AlarmAChannel", "Analog Emergency Channel", c(0x39), 1, typ="chan"),
        F("AlarmAEniSend", "Analog ENI Send Select", c(0x3B), 0, ["Assigned Channel", "Selected Channel"]),
        F("AlarmACycle", "Analog Emergency Cycle (0 = Continuous)", c(0x3C), 0),
        F("AlarmDEmergency", "Digital Emergency Alarm", c(0x3D), 0,
          ["Alarm", "Transpond+Background", "Transpond+NoLocalAlarm", "Transpond+LocalAlarm"]),
        F("AlarmDChannel", "Digital Emergency Channel", c(0x3E), 1, typ="chan"),
        F("AlarmDTime", "Digital Alarm Time [s]", c(0x40), 20),
        F("AlarmDTxTime", "Digital Duration of TX [s]", c(0x41), 31),
        F("AlarmDRxTime", "Digital Duration of RX [s]", c(0x42), 31),
        F("AlarmDEniSend", "Digital ENI Send Select", c(0x43), 0, ["Assigned Channel", "Selected Channel"]),
        F("AlarmDCycle", "Digital Emergency Cycle (0 = Continuous)", c(0x44), 0),
        F("AlarmDId", "Digital TG/DMR ID", c(0x4A), 0, typ="u32"),
        F("AlarmDCallType", "Digital Call Type", c(0x49), 0, ["Private Call", "Group Call", "All Call"]),
        F("AlarmDReceive", "Receive Alarm", c(0x48), 0, ["Off", "On"]),
        F("AlarmQKind", "QDC1200 Kind", c(0x4E), 0, ["Private Call", "Group Call", "All Call"]),
        F("AlarmQGroup", "QDC1200 Group ID", {D1: ("C", 0x4F)}, "000", typ="hex3"),
        F("AlarmQPrivate", "QDC1200 Private ID", c(0x51), "0000", typ="hex4"),
        F("AlarmSigType", "Analog alarm signaling type", {D1: ("C", 0x53)}, 0, ["None", "DTMF", "5TONE", "MDC1200"]),
        F("AlarmWResponse", "Work Alone Response Time (0 = 1 min)", c(0x45), 0),
        F("AlarmWWarning", "Work Alone Warning Time (0 = 1 s)", c(0x46), 0),
        F("AlarmWMode", "Work Alone Response", c(0x47), 0, ["Key", "Voice Transmit"]),
    ]


def dtmf():
    a = lambda o: ("A", o)
    h = lambda n: ("H", n)
    return [
        F("DtmfTxTime", "DTMF Transmitting Time", a(0x3F), 1, ["50 ms", "100 ms", "200 ms", "300 ms", "500 ms"]),
        F("DtmfSelfId", "DTMF Self ID (3 digits; the stock CPS shows letters blank)", a(0x39), "000", typ="str3"),
        F("DtmfInterval", "DTMF Interval Character (10 A, 11 B, 12 C, 13 D, 14 *, 15 #)", a(0x33), 14),
        F("DtmfGroup", "Group Code (0 Off, 10 A .. 13 D, 14 *, 15 #)", a(0x34), 0),
        F("DtmfDecResp", "Decoding Response", a(0x35), 0, RESP),
        F("DtmfFirstDigit", "First Digit Time (" + MS10 + ")", a(0x37), 20),
        F("DtmfPretime", "Pretime (" + MS10 + ")", a(0x36), 20),
        F("DtmfAutoReset", "Auto Reset Time (D890UV: s, D168UV: 0.1 s)", a(0x38), {D8: 10, D1: 0}),
        F("DtmfTimeLapse", "Time-Lapse After Encode (" + MS10 + ")", a(0x3D), 20),
        F("DtmfPttPause", "PTT ID Pause Time (raw)", a(0x3E), 0),
        F("DtmfDCodePause", "D Code Pause (s, 0 = Off)", a(0x41), 10),
        F("DtmfSideTone", "Side Tone", a(0x3C), 0, ["Off", "On"]),
        F("DtmfPttId", "PTT ID", a(0x40), 0, ["Off", "On"]),
        F("DtmfBot", "PTT ID Starting (BOT)", h("dtmf_bot"), "", typ="hstr"),
        F("DtmfEot", "PTT ID Ending (EOT)", h("dtmf_eot"), "", typ="hstr"),
        F("DtmfKill", "Remotely Kill", h("dtmf_kill"), "", typ="hstr"),
        F("DtmfStun", "Remotely Stun", h("dtmf_stun"), "", typ="hstr"),
    ]


def twotone():
    a = lambda o: ("A", o)
    return [F("T2First", "1st Tone Duration (x 0.1 s)", a(0x42), 5), F("T2Second", "2nd Tone Duration (x 0.1 s)", a(0x43), 5),
            F("T2Long", "Long Tone Duration (x 0.1 s)", a(0x44), 10), F("T2Gap", "Gap Time (x 100 ms)", a(0x45), 0),
            F("T2AutoReset", "Auto Reset Time (D890UV: s, D168UV: 0.1 s)", a(0x46), {D8: 10, D1: 0}),
            F("T2SideTone", "Side Tone", a(0x47), 0, ["Off", "On"])]


def fivetone():
    a = lambda o: ("A", o)
    h = lambda n: ("H", n)
    return [
        F("T5SelfId", "Self ID", h("t5_self"), "", typ="hstr"),
        F("T5DecStd", "Decode Standard", a(0x19), 0, None),
        F("T5DecResp", "Decoding Response", a(0x18), 0, RESP),
        F("T5TimeDecTone", "Time Of Decode Tone [ms]", a(0x1B), 70, models=[D1]),
        F("T5DecTime", "Decode Time (" + MS10 + ")", a(0x26), 2),
        F("T5Units", "5TONE Dec Units (bit mask, bit 0 = unit 1)", a(0x2C), 0),
        F("T5DispAny", "Disp AnyID", a(0x2D), 0, ["Off", "On"]),
        F("T5Pretime", "Pretime (" + MS10 + ")", a(0x1D), 20),
        F("T5TimeLapse", "Time-Lapse After Encode (" + MS10 + ")", a(0x1E), 20),
        F("T5PttPause", "PTT ID Pause Time [s] (0 = Off)", a(0x1F), 10),
        F("T5AutoReset", "Auto Reset Time [s]", a(0x20), {D8: 10, D1: 0}),
        F("T5FirstDelay", "First Delay (" + MS10 + ")", a(0x21), 20),
        F("T5SideTone", "Side Tone", a(0x22), 0, ["Off", "On"]),
        F("T5FirstAfterStop", "First Delay Time After Stop (" + MS10 + ")", a(0x27), 0),
        F("T5BotId", "PTT ID Starting (BOT): Encode ID", h("t5_bot"), "", typ="hstr"),
        F("T5BotStd", "PTT ID Starting (BOT): standard (index)", h("t5_bot_std"), 0, None, typ="hnum"),
        F("T5BotTime", "PTT ID Starting (BOT): tone time [ms]", h("t5_bot_time"), 70, typ="hnum"),
        F("T5EotId", "PTT ID Ending (EOT): Encode ID", h("t5_eot"), "", typ="hstr"),
        F("T5EotStd", "PTT ID Ending (EOT): standard (index)", h("t5_eot_std"), 0, None, typ="hnum"),
        F("T5EotTime", "PTT ID Ending (EOT): tone time [ms]", h("t5_eot_time"), 70, typ="hnum"),
    ]


def record(id_, title, fields, node=None, after=None, note="", groups=None, models=BOTH):
    d = {"id": id_, "kind": "record", "title": title, "models": models, "note": note, "fields": fields}
    if node:
        d["node"] = node
        d["node_after"] = {D8: "DMRDigitalContactList"}        # tree place when the model's schema tree has no such node
    if after:
        d["after"] = after
    if groups:
        d["groups"] = groups
    return d


def lst(id_, title, fields, node=None, after=None, note="", models=BOTH, default_rows=None):
    d = record(id_, title, fields, node, after, note, None, models)
    d["kind"] = "list"
    d["default_rows"] = default_rows or {m: [] for m in models}
    return d


def L(name, label, models=BOTH):
    return {"name": name, "label": label, **{m: {"type": "list", "default": ""} for m in models}}


NOTE = "Values of the stock CPS dialog, read from and written to .rdt files (not in the stock CSV export)."
UNDECODED = {
    "both": ["Alarm Setting > Analog > Emergency ID (list content depends on the signalling tables)",
             "Alarm Setting > ENI Type list texts (the value is stored raw)",
             "5Tone Setting: Stop Code, Stop Time (header bytes 0x23-0x25 are not tied to one field); the Function Name of an "
             "information code (the string after the ID is kept as it is)", "2Tone Setting > Decode tab", "DTMF Setting > Special Call", "Encode ID tables (CSV)"],
    "D890UV": ["Alarm Setting > QDC1200 Group ID: the stock D890UV CPS shows the bytes at C+0x56 but saves to C+0x4F, so it "
               "does not survive its own save (the frame is greyed out there)"],
    "D168UV": ["Talk Alias > Custom Text: the V1.07 dialog shows no text field when it is chosen; where (or if) a text is kept is "
               "not known", "QDC1200 Setting: Max ACK wait, Sync headers, Pretime, Try times, Side Tone"],
    "both_live": ["Local Information: the stock CPS opens the COM port for it; it is live radio data, not in the .rdt"],
}


def tables():
    t = {
        "AlarmSetting": record(64, "Alarm Setting", alarm(), node="@alarm", note=NOTE),
        "DTMFSetting": record(65, "DTMF Settings", dtmf(), after={D8: "DTMFEncode", D1: "DTMFEncode"}, note=NOTE),
        "T2Setting": record(66, "2Tone Settings", twotone(), after={D8: "2ToneEncode", D1: "2ToneEncode"}, note=NOTE),
        "T5Setting": record(67, "5Tone Settings", fivetone(), after={D8: "5ToneEncode", D1: "5ToneEncode"}, note=NOTE),
        "T5InfoCodes": lst(68, "5Tone Information Codes", [L("T5InfoNo", "No."), L("T5InfoFunc", "Function Option (index)"),
                                                          L("T5InfoResp", "Decoding Response (index)"), L("T5InfoId", "Information ID")],
                           after={D8: "5ToneEncode", D1: "5ToneEncode"}, note=NOTE),
        "TalkAlias": record(70, "Talk Alias / AIR Alias", [
            F("AliasType", "Talker Alias Type", {D1: ("E", 23248)}, 0, ["Radio Alias", "Custom Text"]),
            F("AliasPrio", "Alias Display Priority", {D1: ("E", 23247), D8: ("E", 22059)}, 0,
              {D1: ["No Display", "Contact Alias", "Air Alias"], D8: ["Off", "Contact Alias", "Air Alias DMR/NX"]}),
            F("AliasFormat", "Alias Data Format", {D8: ("E", 22058)}, 0, ["ISO 8", "ISO 7", "Unicode"])], node="@talkalias", note=NOTE),
        "FriendsList": lst(71, "Friends List", [L("FriendNo", "No."), L("FriendId", "DMR ID")], node="@friends",
                           note=NOTE + " Friends are entries of the digital contact list (by DMR ID)."),
        "EncryptionCodeRdt": lst(72, "Encryption Code (basic privacy)", [L("EncNo", "No."), L("EncKey", "Encryption KEY (hex)"),
                                                                        L("EncId", "Encryption ID")],
                                 node="@enccode", models=[D1], note=NOTE),
    }
    return t


def main():
    d = {"format": "rdt_dialogs 1", "about": __doc__.strip().split("\n")[0], "undecoded": UNDECODED, "tables": tables()}
    for p in (os.path.join(ROOT, "schema", "rdt_dialogs.json"), os.path.join(ROOT, "web", "schema", "rdt_dialogs.json")):
        json.dump(d, open(p, "w"), indent=1, ensure_ascii=False)
        open(p, "a").write("\n")
        print("wrote", p)


if __name__ == "__main__":
    main()
