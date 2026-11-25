#!/usr/bin/env python3
"""Build schema/stock_d890uv.json: the stock D890UV CPS (V1.05) data model, shared by the Python core and the web CPS.

Sources:
  stock_defaults/*.CSV         "Export All" of a new (factory default) codeplug from the stock CPS: table names, column
                               names + order (= the stock CSV import/export format), defaults, CSV line quirks. Made by
                               the stock CPS, so not shipped: the folder is $CFW_CPS_PRIVATE/schema/stock_defaults
                               (stock_defaults_d168 for the D168UV). The generated schema/*.json are shipped.
  OPT_TABS / TREE below        transcribed from screenshots of the stock CPS (docs/STOCK_CPS_MAP.md; screens not shipped)
  schema/rdt_map.json          .rdt (V1323) byte offsets from tools/stock_rdt_experiments (when present)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRIV = os.environ.get("CFW_CPS_PRIVATE") or os.path.join(ROOT, "..", "..", "private", "cfw_cps")
DEF = os.path.join(PRIV, "schema", "stock_defaults")

# Stock CPS tree (main window, left), in order. node -> (stock table or dialog, kind)
TREE = [
    ["Common Settings", [
        ["Channel", "Channel"], ["Zone", "DMRZone"], ["Scan List", "ScanList"], ["AM Air", "AMAir"], ["AM Zone", "AMZone"],
        ["Pre-defined SMS", "PrefabricatedSMS"], ["FM", "FM"], ["Auto Repeater Offset Frequencies", "AutoRepeaterOffsetFrequencys"],
        ["Device Information", "@device"], ["Optional Settings", "OptionalSetting"], ["Alarm Setting", "@alarm"],
        ["Local Information", "@local"], ["Hot Key", "HotKey_HotKey"], ["APRS", "APRS"], ["GPS Roaming", "GPSRoaming"]]],
    ["DMR", [
        ["Master ID", "@masterid"], ["Radio ID List", "RadioIDList"], ["Contact/Talk Group", "DMRTalkGroups"],
        ["Roaming Channel", "RoamingChannel"], ["Roaming Zone", "RoamingZone"], ["Receive Group Call List", "DMRReceiveGroupCallList"],
        ["Encryption Code", "EncryptionCode"], ["ARC4 Encryption Code", "ARC4EncryptionCode"], ["AES Encryption Code", "AESEncryptionCode"],
        ["Digital Contact List", "DMRDigitalContactList"], ["Talk Group Whitelist (Repeater)", "TalkGroupWhitelist(Repeater)"],
        ["Digital Contact Whitelist (Repeater)", "DigitalContactWhitelist(Repeater)"]]],
    ["NXDN", [
        ["NX Setting", "NXSetting"], ["NX Talk Group", "NXTalkGroup"], ["NX Receive Group Call List", "NXReceiveGroupCallList"],
        ["NX Encryption Code", "NXEncryptionCode"], ["NX State Message", "NXStateMSG"], ["NX Digital Contact List", "NXDigitalContactList"]]],
    ["Analog", [
        ["Analog Address Book", "AnalogAddressBook"], ["5Tone Encode", "5ToneEncode"], ["2Tone Encode", "2ToneEncode"],
        ["DTMF Encode", "DTMFEncode"], ["MDC1200 Address Book", "MDC1200AddressBook"], ["MDC1200 Encode", "MDC1200Encode"],
        ["Alert Tone", "AlertTone"], ["Hot Key Quick Call", "HotKey_QuickCall"], ["Hot Key State", "HotKey_State"]]],
]

# Optional Settings dialog: tab -> [(CSV key, GUI label)], in the dialog's order (stock CPS screenshots opt_*.png).
# Keys without a confirmed GUI field are listed under "More (CSV only)".
OPT_TABS = [
    ["Work Mode", [("FreqDis", "Display mode"), ("Work_Zone1", "MEM Zone(A)"), ("Work_Zone2", "MEM Zone(B)"),
                   ("MainState", "Main Channel Set"), ("SubMode", "Sub-Channel Mode"), ("RepMode", "choose working mode")]],
    ["Vox/BT", [("VOX", "VOX On/Off"), ("VOX_Delay", "VOX Delay"), ("VoxHeadset", "VOX Detection"),
                ("BlueToothOn", "Bluetooth"), ("MicInBlueTooth", "Mic in Bluetooth"), ("SpkInBlueTooth", "Speaker in Bluetooth"),
                ("BhtMicGain", "BT Mic Gain"), ("BhtSpkGain", "BT Speaker Gain"), ("BhtHoldTime", "BT Hold Time"),
                ("BhtHoldDelay", "BT Hold Delay"), ("BhtPttHold", "BT PTT Hold"), ("BtNrBefore", "BT NR Before"), ("BtNrAfter", "BT NR After")]],
    ["STE", [("STE_Type", "STE Type Of CTCSS"), ("STE_Freq", "STE When No Signal"), ("SteTime", "Ste Time"), ("DcsSte", "DCS STE")]],
    ["AM/FM", [("FM_En", "AM/FM Function"), ("FM_VFO", "FM VFO/MEM"), ("Work_FMCH", "FM Work Channel"), ("FmMon", "FM Monitor"),
               ("AmChanVfo", "AM VFO/MEM"), ("CurAmChan", "AM Work Zone"), ("AmOffset", "AM Offset"), ("AmSqLevel", "Am SqlLevel")]],
    ["Power Save", [("AutoPowerOff", "Auto Shutdown"), ("PowerSave", "Power save"), ("ApoKind", "Auto Shutdown Type"),
                    ("PttSleepTime", "PTT Sleep Time")]],
    ["Key Function", [("KeyLock", "Key Lock"), ("PfLongTime", "Long Key Time[s]")]],
    ["Other", [("ContactOutSetEn", "Address Book Is Sent With Its Own Code"), ("TOT", "TOT"), ("Language", "Language"),
               ("Step", "Frequency Step"), ("SQL1", "SQL Level(A)"), ("SQL2", "SQL Level(B)"), ("TBST", "TBST"),
               ("AnaHoldTime", "Analog Call Hold Time[s]"), ("CurTalkPathHold", "call channel is maintained"),
               ("PriZoneA", "Priority Zone A"), ("PriZoneB", "Priority Zone B"), ("FixTimeMute", "Mute timing"),
               ("TotPreEn", "TOT Predict"), ("TxAgcCon", "TxPow Agc"), ("WxAlarmSign", "NOAA Alert"), ("CurWxChan", "NOAA Channel")]],
    ["Digital Func", [("GroupTalkHold", "Group Call Hold Time"), ("PersonTalkHold", "Private Call Hold Time"),
                      ("DialGroupHold", "Manual Dial - Group TG Hold Time"), ("DialPrivateHold", "Manual Dial - Private TG Hold Time"),
                      ("Preamble", "Voice header repetitions"), ("PreWave", "TX preamble duration"),
                      ("MissCallFilter", "Filter Own ID In MissCall"), ("DigiStunKillEn", "Digital Remote Kill"),
                      ("DigiMoni", "Digital Monitor"), ("DigiMoniCc", "Digital Monitor CC"), ("DigiMoniId", "Digital Monitor ID"),
                      ("Scan_Pri_Current", "Monitor Slot Hold"), ("RemoteMoniEn", "Remote Monitor"), ("SmsFormat", "SMS Format"),
                      ("DigiProtocal", "Digital Protocol"), ("ResetDigiProtocal", "Reset Digital Protocol"),
                      ("DigiEmgKind", "Digital Emergency Type"), ("DmrRasEn", "DMR RAS"), ("VcallRpheader", "Voice Call Repeat Header")]],
    ["Satellite", [("SateLocalKind", "Sate Location"), ("SateTxPower", "Sate TX Power"), ("SateAnaSql", "Sate ANA Sql"),
                   ("SateAosLimit", "Sate Aos Limit")]],
    ["Power-on", [("StartDspSet", "Power-on Interface"), ("Start_Char", "Power-on Display (line 1)"),
                  ("Start_Char2", "Power-on Display (line 2)"), ("Password", "Power-on Password"),
                  ("Password_Char", "Power-on Password Char"), ("StartChUse", "Default Startup Channel"),
                  ("StartZone1", "Startup Zone A"), ("StartCurChan1", "Startup Channel A"), ("StartZone2", "Startup Zone B"),
                  ("StartCurChan2", "Startup Channel B"), ("StartTestGps", "Startup GPS test"), ("StartResetEn", "Startup Reset")]],
    ["Alert Tone", [("MsgRing", "SMS Alert"), ("CallRing", "Call Alert"), ("OverVoice", "Digi Call ResetTone"),
                    ("TalkTips", "Talk Permit"), ("Beep", "Key Tone"), ("SqOnVoice", "Digi Idle Channel Tone"),
                    ("Boot_Sound", "Startup Sound"), ("AnaSqOnVoice", "Ana Idle Channel Tone")]],
    ["Display", [("Lightness", "Brightness"), ("AutoBKLightTime", "Auto Backlight Duration"), ("TxDimWait", "Backlight Delay Of TX[s]"),
                 ("MenuLowPower", "Menu Exit Time[s]"), ("DateDisKind", "Time Display"), ("LastCallDis", "Last Caller"),
                 ("CallModeDisKind", "Call Display Mode"), ("CallSignColour", "Call Sign Display Color"),
                 ("IdleWait", "Call End Prompt Box"), ("ChanNumDisKind", "Display Channel Number"),
                 ("MenuDisWorkContact", "Display Current Contact"), ("WorkCharDisColour", "Standby Char Color"),
                 ("bkpic", "Standby BK Picture"), ("GpsTextUsed", "Show Last Call On Launch"), ("DiviDisEn", "Separate display"),
                 ("LastHeardChanSet", "CH Switching Keeps Last Caller"), ("ChanNameColour", "A Channel Name Color"),
                 ("RxDimWait", "Receive Backlight Delay[s]"), ("ChanNameColourB", "B Channel Name Color"),
                 ("ZoneNameColourA", "Zone Name Colour A"), ("ZoneNameColourB", "Zone Name Colour B"),
                 ("ChanDisCtr", "Display Channel Type"), ("DateDisFormat", "Date Display Format"), ("ZoneBarsEn", "Volume Bar"),
                 ("NightMode", "Night Mode")]],
    ["GPS/Ranging", [("Gps", "Get GPS Positioning"), ("TmZone", "Time Zone"), ("GpsMode", "Gps Mode"),
                     ("GpsReplyEn", "GPS Reply"), ("MeasurePeriod", "Ranging Period"), ("AprsDistanceDis", "APRS Distance Display")]],
    ["VFO Scan", [("ScanType", "VFO Scan Type"), ("VfoScanFreq0", "VFO Scan Start Freq(UHF)"), ("VfoScanFreq1", "VFO Scan End Freq(UHF)"),
                  ("VfoScanFreq2", "VFO Scan Start Freq(VHF)"), ("VfoScanFreq3", "VFO Scan End Freq(VHF)")]],
    ["Auto repeater", [("AutoRepeater", "Auto Repeater A"), ("AutoRepeaterB", "Auto Repeater B"), ("UhfAutoRep", "Auto Repeater1(UHF)"),
                       ("VhfAutoRep", "Auto Repeater1(VHF)"), ("UhfAutoRep2", "Auto Repeater2(UHF)"), ("VhfAutoRep2", "Auto Repeater2(VHF)"),
                       ("BsModeCheck", "Repeater Check"), ("TimeBsCheck", "Repeater Check Interval[s]"),
                       ("BsCheckTimes", "Repeater Check Reconnections"), ("OutRepNote", "Repeater Out of Range Notify"),
                       ("OutNoteTimes", "Out of Range Notify(times)"), ("TimeRoamOn", "Auto Roaming"),
                       ("FixRomanStartOp", "Auto Roaming start condition"), ("WanderPerod", "Auto Roaming at Fixed Time[m]"),
                       ("WanderEffectWait", "Roaming Effect Wait Time[s]"), ("CurRoamZone", "Roaming Zone"),
                       ("AutoRepFreq0", "Min Freq Of Auto Repeater1(VHF)"), ("AutoRepFreq1", "Max Freq Of Auto Repeater1(VHF)"),
                       ("AutoRepFreq2", "Min Freq Of Auto Repeater1(UHF)"), ("AutoRepFreq3", "Max Freq Of Auto Repeater1(UHF)"),
                       ("AutoRepMinFreqV2", "Min Freq Of Auto Repeater2(VHF)"), ("AutoRepMaxFreqV2", "Max Freq Of Auto Repeater2(VHF)"),
                       ("AutoRepMinFreqU2", "Min Freq Of Auto Repeater2(UHF)"), ("autoRepMaxFreqU2", "Max Freq Of Auto Repeater2(UHF)"),
                       ("RepCcLimit", "Rep Cc Limit"), ("RepSlotPathA", "Rep Slot PathA"), ("RepSlotPathB", "Rep Slot PathB"),
                       ("CurUhfAutoRep", "Current UHF Auto Repeater"), ("CurVhfAutoRep", "Current VHF Auto Repeater")]],
    ["Record", [("Record_En", "Record Function"), ("RecordDelay", "Record Delay"), ("WtRecordNote", "Record Note")]],
    ["Volume/Audio", [("MaxVol", "Maximum Volume"), ("VolType", "Power On Volume Type"), ("MinVolData", "Power On Volume"),
                      ("EarMaxVol", "Max Headphone Volume"), ("MicLevel", "DMR Mic Gain"), ("EnSoundEffect", "Enhanced Sound Quality"),
                      ("AnaMic", "Ana Mic Gain"), ("Drc", "DRC Dynamic Ranagle Control(Rx AGC)"), ("NxdnMic", "NX Mic Gain"),
                      ("RxNr", "RX Noise Reduction"), ("TxNr", "TX Noise Reduction"), ("TalkOverPoint", "Sub SpkInTx")]],
]

LIST_KEY = {"Channel": "No.", "DMRZone": "No.", "ScanList": "No."}

# columns of the stock tables that the cfw model holds natively (everything else is kept verbatim)
CFW_MAPPED = {
    "Channel": ["No.", "Channel Name", "Receive Frequency", "Transmit Frequency", "Channel Type", "Transmit Power", "Band Width",
                "CTCSS/DCS Decode", "CTCSS/DCS Encode", "Contact/Talk Group", "Contact/Talk Group Call Type",
                "Contact/Talk Group TG/DMR ID", "RX Color Code", "Slot", "Scan List", "Receive Group List", "Talk Around(Simplex)"],
    "DMRZone": ["No.", "Zone Name", "Zone Channel Member", "Zone Channel Member RX Frequency", "Zone Channel Member TX Frequency"],
    "ScanList": ["No.", "Scan List Name", "Scan Channel Member", "Scan Channel Member RX Frequency", "Scan Channel Member TX Frequency"],
    "DMRTalkGroups": ["No.", "Radio ID", "Name", "Call Type"],
    "DMRReceiveGroupCallList": ["No.", "Group Name", "Contact", "Contact TG/DMR ID"],
}
FILE_ONLY = ["DMRDigitalContactList", "NXDigitalContactList"]       # too big for the radio region: kept in files


def read_stock_csv(path):
    """-> (rows, trail flags); fields keep their text exactly; trail = line ended with an unquoted empty field"""
    text = open(path, "rb").read().decode("latin1")
    rows, trails = [], []
    for line in text.split("\r\n"):
        if line == "":
            continue
        f, i, trail = [], 0, False
        while i <= len(line):
            if i < len(line) and line[i] == '"':
                j = line.index('"', i + 1)
                k = line.find(",", j)
                k = len(line) if k < 0 else k
                f.append(line[i + 1:j] + line[j + 1:k])      # text after the closing quote: APRS header quirk
                i = k
            else:
                j = line.find(",", i)
                j = len(line) if j < 0 else j
                f.append(line[i:j])
                if j == len(line) and i == j:
                    trail = True
                i = j
            if i < len(line) and line[i] == ",":
                i += 1
                if i == len(line):
                    trail = True
                    break
            else:
                break
        rows.append(f)
        trails.append(trail)
    return rows, trails


# ---------------------------------------------------------------- D168UV (stock D168UV CPS V1.07, .rdt V1292)
# Screens: stock D168 CPS screenshots (not shipped). Tables and columns are stored under the D890UV ("canonical") names where the two
# CPS differ only in naming, so the cfw code handles both models with one set of names; csv_name / csv_columns keep
# the stock D168 names for the CSV files.
D168_TREE = [
    ["Public", [
        ["Channel", "Channel"], ["Zone", "DMRZone"], ["Scan List", "ScanList"], ["Roaming Channel", "RoamingChannel"],
        ["Roaming Zone", "RoamingZone"], ["FM", "FM"], ["Auto Repeater Offset Frequencies", "AutoRepeaterOffsetFrequencys"],
        ["Device Information", "@device"], ["Optional Setting", "OptionalSetting"], ["Alarm Setting", "@alarm"],
        ["Local Information", "@local"], ["Hot Key", "HotKey_HotKey"], ["Hot Key Quick Call", "HotKey_QuickCall"],
        ["Hot Key State", "HotKey_State"], ["Alert Tone", "AlertTone"], ["APRS", "APRS"], ["GPS Roaming", "GPSRoaming"]]],
    ["Digital", [
        ["Master ID", "@masterid"], ["Radio ID List", "RadioIDList"], ["Contact/Talk Groups", "DMRTalkGroups"],
        ["Prefabricated SMS", "PrefabricatedSMS"], ["Receive Group Call List", "DMRReceiveGroupCallList"],
        ["Encryption Code", "@enccode"], ["AES Encryption Code", "AESEncryptionCode"], ["ARC4 Encryption Code", "ARC4EncryptionCode"],
        ["Digital Contact List", "DMRDigitalContactList"], ["Friends List", "@friends"], ["Talk Alias", "@talkalias"]]],
    ["Analog", [
        ["Analog Address Book", "AnalogAddressBook"], ["QDC Address Book", "QDC1200AddressBook"],
        ["QDC1200 Setting", "QDC1200EnCodeTable"], ["QDC1200 Decode", "QDC1200DECodeTable"], ["5Tone Setting", "5ToneEncode"],
        ["2Tone Setting", "2ToneEncode"], ["DTMF Setting", "DTMFEncode"]]],
]
# Optional Setting dialog of the D168 CPS: 18 tabs (stock CPS screenshots opt_*.png); labels as shown there
D168_OPT_TABS = [
    ["Work Mode", [("FreqDis", "Display mode"), ("Work_Zone1", "MEM Zone(A)"), ("Work_Zone2", "MEM Zone(B)"),
                   ("MainState", "Main Channel Set"), ("SubMode", "Sub-Channel Mode")]],
    ["Vox/BT", [("VOX", "VOX Level"), ("VOX_Delay", "VOX Delay"), ("VoxHeadset", "VOX Detection")]],
    ["STE", [("STE_Type", "STE Type Of CTCSS"), ("STE_Freq", "STE When No Signal"), ("SteTime", "Ste Time"), ("DcsSte", "Dcs Ste")]],
    ["FM", [("FM_VFO", "FM VFO/MEM"), ("Work_FMCH", "FM Work Channel"), ("FmMon", "FM Monitor"), ("FM_En", "FM Function")]],
    ["Power Save", [("AutoPowerOff", "Auto Shutdown"), ("PowerSave", "Power save"), ("ApoKind", "Auto Shutdown Type")]],
    ["Key Function", [("KeyLock", "Key Lock"), ("PfLongTime", "Long Key 2 Time[s]")]],
    ["Other", [("ContactOutSetEn", "Address Book Is Sent With Its Own Code"), ("TOT", "TOT"), ("Step", "Frequency Step"),
               ("SQL1", "SQL Level(A)"), ("SQL2", "SQL Level(B)"), ("TBST", "TBST"), ("AnaHoldTime", "Analog Call Hold Time[s]"),
               ("CurTalkPathHold", "call channel is maintained"), ("PriZoneA", "Priority Zone A"), ("PriZoneB", "Priority Zone B"),
               ("FixTimeMute", "Mute timing"), ("TotPreEn", "TOT Predict"), ("TxAgcCon", "TX Power AGC")]],
    ["Digital Func", [("GroupTalkHold", "Group Call Hold Time"), ("PersonTalkHold", "Person Call Hold Time"),
                      ("DialGroupHold", "Manual Dial - Group TG Hold Time"), ("DialPrivateHold", "Manual Dial - Private TG Hold Time"),
                      ("Preamble", "Voice Header Repetitions"), ("PreWave", "TX Preamble Duration"),
                      ("MissCallFilter", "Filter Own ID In MissCall"), ("DigiStunKillEn", "Digital Remote Kill"),
                      ("DigiMoni", "Digital Monitor"), ("DigiMoniCc", "Digital Monitor CC"), ("DigiMoniId", "Digital Monitor ID"),
                      ("Scan_Pri_Current", "Monitor Slot Hold"), ("RemoteMoniEn", "Remote Monitor"), ("SmsFormat", "SMS Format")]],
    ["Power-on", [("StartDspSet", "Power-on Interface"), ("Start_Char", "Power-on Display (line 1)"),
                  ("Start_Char2", "Power-on Display (line 2)"), ("Password", "Power-on Password"),
                  ("Password_Char", "Power-on Password Char"), ("StartChUse", "Default Startup Channel"),
                  ("StartZone1", "Startup Zone A"), ("StartCurChan1", "Startup Channel A"), ("StartZone2", "Startup Zone B"),
                  ("StartCurChan2", "Startup Channel B"), ("StartResetEn", "Startup Reset")]],
    ["Alert Tone", [("MsgRing", "SMS Alert"), ("CallRing", "Call Alert"), ("OverVoice", "Digi Call ResetTone"),
                    ("TalkTips", "Call Tone"), ("Beep", "Key Tone"), ("SqOnVoice", "Digi Idle Channel Tone"),
                    ("Boot_Sound", "Startup Sound"), ("VolNoteEn", "Key Sound Adjustable"), ("AnaSqOnVoice", "Ana Idle Channel Tone")]],
    ["Display", [("Lightness", "Brightness"), ("AutoBKLightTime", "Auto Backlight Duration"), ("TxDimWait", "Backlight Delay Of TX[s]"),
                 ("MenuLowPower", "Menu Exit Time[s]"), ("DateDisKind", "Time Display"), ("LastCallDis", "Last Caller"),
                 ("CallModeDisKind", "Call Display Mode"), ("CallSignColour", "Call Sign Display Color"),
                 ("ChanNumDisKind", "Display Channel Number"), ("MenuDisWorkContact", "Display Current Contact"),
                 ("WorkCharDisColour", "Standby Char Color"), ("bkpic", "Standby BK Picture"), ("GpsTextUsed", "Show Last Call On Launch"),
                 ("DiviDisEn", "Separate display"), ("LastHeardChanSet", "CH Switching Keeps Last Caller"),
                 ("ChanNameColour", "A Channel Name Color"), ("RxDimWait", "Receive Backlight Delay[s]"),
                 ("ChanNameColourB", "B Channel Name Color"), ("ZoneNameColourA", "Zone Name Colour A"),
                 ("ZoneNameColourB", "Zone Name Colour B"), ("ChanDisCtr", "Display Channel Type"),
                 ("DateDisFormat", "Date Display Format"), ("NightMode", "Night Mode"), ("NlightStartHour", "Night Start Hour"),
                 ("NlightStartMin", "Night Start Min"), ("NlightEndHour", "Night End Hour"), ("NlightEndMin", "Night End Min")]],
    ["GPS/Ranging", [("TmZone", "Time Zone"), ("Gps", "GPS Roaming")]],
    ["VFO Scan", [("ScanType", "VFO Scan Type"), ("VfoScanFreq0", "VFO Scan Start Freq(UHF)"), ("VfoScanFreq1", "VFO Scan End Freq(UHF)"),
                  ("VfoScanFreq2", "VFO Scan Start Freq(VHF)"), ("VfoScanFreq3", "VFO Scan End Freq(VHF)")]],
    ["Auto repeater", [("AutoRepeater", "Auto Repeater A"), ("AutoRepeaterB", "Auto Repeater B"), ("UhfAutoRep", "Auto Repeater1(UHF)"),
                       ("VhfAutoRep", "Auto Repeater1(VHF)"), ("UhfAutoRep2", "Auto Repeater2(UHF)"), ("VhfAutoRep2", "Auto Repeater2(VHF)"),
                       ("BsModeCheck", "Repeater Check"), ("TimeBsCheck", "Repeater Check Interval[s]"),
                       ("BsCheckTimes", "Repeater Check Reconnections"), ("OutRepNote", "Alert Out Of Repeat Range"),
                       ("OutNoteTimes", "Repeater out of range reminder(times)"), ("TimeRoamOn", "Auto Roaming"),
                       ("FixRomanStartOp", "Timed Roaming Start Condition"), ("WanderPerod", "Auto Roaming Interval[m]"),
                       ("WanderEffectWait", "Roaming Effect Wait Time[s]"), ("CurRoamZone", "Roaming Zone"),
                       ("AutoRepFreq0", "Min Freq Of Auto Repeater1(VHF)"), ("AutoRepFreq1", "Max Freq Of Auto Repeater1(VHF)"),
                       ("AutoRepFreq2", "Min Freq Of Auto Repeater1(UHF)"), ("AutoRepFreq3", "Max Freq Of Auto Repeater1(UHF)"),
                       ("AutoRepMinFreqV2", "Min Freq Of Auto Repeater2(VHF)"), ("AutoRepMaxFreqV2", "Max Freq Of Auto Repeater2(VHF)"),
                       ("AutoRepMinFreqU2", "Min Freq Of Auto Repeater2(UHF)"), ("autoRepMaxFreqU2", "Max Freq Of Auto Repeater2(UHF)")]],
    ["Record", [("Record_En", "Record Function"), ("RecordDelay", "Record Delay")]],
    ["Volume/Audio", [("MaxVol", "Maximum Volume"), ("EarMaxVol", "Max Headphone Volume"), ("MicLevel", "Digit Mic Gain"),
                      ("EnSoundEffect", "Enhanced Sound Quality"), ("AnaMic", "Ana Mic Gain"), ("TxNr", "TX Noise Reduction"),
                      ("RxNr", "RX Noise Reduction"), ("Drc", "DRC Dynamic Range Control(Rx AGC)")]],
    ["Satellite", [("SateLocalKind", "Satellite Location"), ("SateTxPower", "Sate TX Power"), ("SateAnaSql", "Sate ANA Sql"),
                   ("SateAosLimit", "Sate Aos Limit")]],
]
D168_TABLE_ALIAS = {"Zone": "DMRZone", "TalkGroups": "DMRTalkGroups", "ReceiveGroupCallList": "DMRReceiveGroupCallList",
                    "DigitalContactList": "DMRDigitalContactList"}
D168_COL_ALIAS = {"Channel": {"Contact": "Contact/Talk Group", "Contact Call Type": "Contact/Talk Group Call Type", "TxCc": "txcc"}}
D168_CFW_MAPPED = {
    "Channel": ["No.", "Channel Name", "Receive Frequency", "Transmit Frequency", "Channel Type", "Transmit Power", "Band Width",
                "CTCSS/DCS Decode", "CTCSS/DCS Encode", "Contact/Talk Group", "Contact/Talk Group Call Type", "RX Color Code", "Slot",
                "Scan List", "Receive Group List", "Talk Around(Simplex)"],
    "DMRZone": ["No.", "Zone Name", "Zone Channel Member"],
    "ScanList": ["No.", "Scan List Name", "Scan Channel Member"],
    "DMRTalkGroups": ["No.", "Radio ID", "Name", "Call Type"],
    "DMRReceiveGroupCallList": ["No.", "Group Name", "Contact"],
}

# Radio menu names of D168 Optional Setting keys that the CPS GUI does not label ("More (CSV only)"), from the stock
# V1.07 menu crawl in the D168UV emulator (D168UV/emu/MENUS.md, COMPARE_MENUS_CPS.md). "?" = value range agrees, byte
# not checked. Emitted as "radio_menu" (informational; labels stay GUI-confirmed only).
D168_RADIO_MENU = {
    "Language": "Settings > Radio Set > DISP Func > Language (English, Chinese)",
    "WxAlarmSign": "Settings > Radio Set > Other Func > WX Alarm (Off, On)",
    "GpsMode": "GPS > GPS Mode (GPS, BDS, GPS+BDS, GLONASS, GPS+GLON, BDS+GLON, ALL) ?",
    "BlueToothOn": "BT > On/Off (BT Off, BT On)",
    "BhtMicGain": "BT > Mic Gain (Level 1-5)",
    "BhtSpkGain": "BT > Spk Gain (Level 1-5)",
    "BhtHoldTime": "BT > Hold Time (OFF, 1S-30S, 60S, 120S, infinite)",
    "BhtHoldDelay": "BT > RX Delay (30ms, 1S-5.5S)",
    "SpkInBlueTooth": "BT > BT+int spk (Off, On)",
    "BhtPttHold": "no radio menu (checked: BT > PTT Pair > PTT HOLD is not stored in the settings block)",
}

# Extra Optional Setting tabs (GUI only). D168 Man Down: stock CPS Public > Alarm Setting "Man Down" checkbox is the CSV
# column FailAlarm (.rdt 0x71, found by ticking it in the stock CPS and diffing the saved .rdt) and "Man Down Delay[s]"
# is ManDownWait (.rdt 0x93). Radio settings block NAND 0x02500000 +0x24 (on/off) / +0x4F (delay s); stock V1.07
# firmware 0x08028A20 / FUN_08031e78 (D168UV/emu/README.md "Man down").
D168_EXTRA_TABS = [["Man Down", [("FailAlarm", "Man Down"), ("ManDownWait", "Man Down Delay[s]")]]]

# Bluetooth (GUI only: the stock D168 CPS has no BT page). Labels = the radio's Settings > BT menu. Byte placement
# checked by a stock CPS "Write To Radio" capture (fake radio): .rdt byte -> radio settings block NAND 0x02500000
# (+0xB1 On/Off, +0xB2 Mic in BT, +0xB3 BT+int spk, +0xB6/+0xB7 Mic/Spk Gain, +0xED Hold Time, +0xEE RX Delay,
# +0x15 BhtPttHold); value lists = the radio menu lists (stored value = list index), checked in the D168 emulator by
# writing the settings byte and opening the menu (docs/STOCK_CPS_MAP_D168.md "Bluetooth"). The radio's PTT Pair > PTT HOLD
# (Off/On) does not change the settings block, and +0x15 does not change it: BhtPttHold stays a raw value.
D168_BT_TAB = ["Bluetooth", [("BlueToothOn", "BT On/Off"), ("BhtHoldTime", "Hold Time"), ("BhtHoldDelay", "RX Delay"),
                             ("SpkInBlueTooth", "BT+int spk"), ("BhtMicGain", "Mic Gain"), ("BhtSpkGain", "Spk Gain"),
                             ("BhtPttHold", "BT PTT Hold (no radio menu)"), ("MicInBlueTooth", "Mic In BT (no radio menu)")]]
D168_EXTRA_TABS.append(D168_BT_TAB)
D168_CHOICES = {
    "BlueToothOn": ["BT Off", "BT On"],
    "BhtHoldTime": ["OFF"] + ["%dS" % i for i in range(1, 31)] + ["60S", "120S", "infinite"],
    "BhtHoldDelay": ["30ms"] + ["%gS" % (i / 2) for i in range(2, 12)],
    "SpkInBlueTooth": ["Off", "On"],
    "BhtMicGain": ["Level %d" % i for i in range(1, 6)],
    "BhtSpkGain": ["Level %d" % i for i in range(1, 6)],
}
# Radio BT settings that are not in the codeplug (sent to the BT module as AT commands or kept by the module)
D168_BT_MODULE_ONLY = ["Pairing", "BT Names", "Pair-Names", "Pin Code", "NR BEL", "NR AFL",
                       "PTT Pair (Connect / Disconnect, PTT HOLD, PTT Name, PTT Sleep, PTT Bat)"]
# dedicated pages in the tree (after the section's "Optional Setting" node): section, label, table, keys, note
D168_PAGES = [["Public", "Bluetooth", "OptionalSetting", [k for k, _ in D168_BT_TAB[1]],
               "Bluetooth (radio menu Settings > BT; the stock D168 CPS has no BT page). Not in the codeplug (kept by the "
               "BT module, set on the radio): " + ", ".join(D168_BT_MODULE_ONLY) + "."]]
# D890UV: the stock CPS lists the BT keys on its Vox/BT tab (CSV only, no dialog fields); same page, raw values
D890_PAGES = [["Common Settings", "Bluetooth", "OptionalSetting",
               ["BlueToothOn", "MicInBlueTooth", "SpkInBlueTooth", "BhtMicGain", "BhtSpkGain", "BhtHoldTime", "BhtHoldDelay",
                "BhtPttHold", "BtNrBefore", "BtNrAfter"],
               "Bluetooth (stock CSV keys of the Vox/BT tab; values are the stock CSV values, value lists not checked on "
               "the D890UV radio)."]]

MODELS = {
    "D890UV": {"defaults": DEF, "tree": TREE, "opt_tabs": OPT_TABS, "out": "stock_d890uv.json", "cps": "D890UV CPS V1.05",
               "rdt": "V1323", "table_alias": {}, "col_alias": {}, "mapped": CFW_MAPPED,
               "record": ("OptionalSetting", "NXSetting", "APRS", "AlertTone"), "rdt_map": "rdt_map.json",
               "pages": D890_PAGES},
    "D168UV": {"defaults": os.path.join(PRIV, "schema", "stock_defaults_d168"), "tree": D168_TREE, "opt_tabs": D168_OPT_TABS,
               "out": "stock_d168uv.json", "cps": "D168UV CPS V1.07", "rdt": "V1292", "table_alias": D168_TABLE_ALIAS,
               "col_alias": D168_COL_ALIAS, "mapped": D168_CFW_MAPPED,
               "record": ("OptionalSetting", "APRS", "AlertTone", "QDC1200DECodeTable"), "rdt_map": "rdt_map_d168.json",
               "radio_menu": D168_RADIO_MENU, "extra_tabs": D168_EXTRA_TABS, "choices": D168_CHOICES,
               "pages": D168_PAGES},
}


def main():
    import sys
    for model in (sys.argv[1:] or list(MODELS)):
        build(model)


def build(model):
    M = MODELS[model]
    DEF, TREE, OPT_TABS, CFW_MAPPED = M["defaults"], M["tree"], M["opt_tabs"], M["mapped"]
    if not os.path.isdir(DEF):
        raise SystemExit("stock CPS defaults export not found: %s (set $CFW_CPS_PRIVATE; the shipped schema/*.json "
                         "stay as they are)" % DEF)
    lst = [l.strip() for l in open(os.path.join(DEF, "base.LST"), encoding="latin1") if "," in l]
    tables = {}
    for l in lst:
        idx, f = l.split(",", 1)
        csv_name = f.strip('"')[:-4]
        name = M["table_alias"].get(csv_name, csv_name)
        rows, trails = read_stock_csv(os.path.join(DEF, csv_name + ".CSV"))
        csv_head = rows[0]
        ca = M["col_alias"].get(name, {})
        head = [ca.get(c, c) for c in csv_head]
        record = csv_name in M["record"]
        raw_head = open(os.path.join(DEF, csv_name + ".CSV"), "rb").read().decode("latin1").split("\r\n")[0]
        tables[name] = {"lst_index": int(idx), "columns": head, "header_raw": raw_head, "header_trail": trails[0],
                        "row_trail": trails[1] if len(trails) > 1 else trails[0],
                        "kind": "record" if record else "list",
                        "defaults": rows[1] if len(rows) > 1 else [""] * len(head),
                        "default_rows": rows[1:] if not record else [],
                        "cfw_mapped": CFW_MAPPED.get(name, []), "file_only": name in FILE_ONLY}
        if csv_name != name or head != csv_head:
            tables[name]["csv_name"] = csv_name
            tables[name]["csv_columns"] = csv_head
    OPT_TABS = OPT_TABS + M.get("extra_tabs", [])
    labels = {}
    for tab, fields in OPT_TABS:
        for k, lab in fields:
            labels[k] = lab
    cols = tables["OptionalSetting"]["columns"]
    missing = [c for c in cols if c not in labels]
    unknown = [k for k in labels if k not in cols]
    assert not unknown, unknown
    opt_tabs = [[t, [k for k, _ in f]] for t, f in OPT_TABS] + [["More (CSV only)", missing]]
    rdt_map = {}
    mp = os.path.join(ROOT, "schema", M["rdt_map"])
    # the .rdt map is served as its own file (schema/rdt_map*.json); not embedded here
    if model != "D890UV":
        out_model = {"model": model}
    else:
        out_model = {}
    out = {"format": "cfw-stock-schema", "stock_cps": M["cps"], "rdt_version": M["rdt"],
           "tree": TREE, "tables": tables,
           "lst_order": [M["table_alias"].get(n, n) for n in (l.split(",", 1)[1].strip('"')[:-4] for l in lst)],
           "optional_tabs": opt_tabs, "labels": labels, "rdt_map": rdt_map}
    out.update(out_model)
    if M.get("pages"):
        # page target "<table>#<label>": a record page that shows only these keys
        out["pages"] = {}
        for sec, label, table, keys, note in M["pages"]:
            assert all(k in tables[table]["columns"] for k in keys), [k for k in keys if k not in tables[table]["columns"]]
            target = "%s#%s" % (table, label)
            nodes = dict(out["tree"])[sec]             # after the table's own node (Optional Setting)
            at = [t_ for _, t_ in nodes].index(table) + 1
            out["tree"] = [[s_, (n_ if s_ != sec else n_[:at] + [[label, target]] + n_[at:])] for s_, n_ in out["tree"]]
            out["pages"][target] = {"table": table, "title": label, "keys": keys, "note": note}
    if M.get("choices"):
        assert all(k in cols for k in M["choices"])
        out["choices"] = M["choices"]
    if M.get("radio_menu"):
        assert all(k in cols for k in M["radio_menu"]), [k for k in M["radio_menu"] if k not in cols]
        out["radio_menu"] = M["radio_menu"]
    p = os.path.join(ROOT, "schema", M["out"])
    json.dump(out, open(p, "w"), indent=0)
    os.makedirs(os.path.join(ROOT, "web", "schema"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "web", "schema", M["out"]), "w"), indent=0)     # served with the web CPS
    print("wrote", p, len(tables), "tables;", len(cols), "optional settings,", len(missing), "without a GUI label")


if __name__ == "__main__":
    main()
