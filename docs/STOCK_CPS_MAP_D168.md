# Stock D168UV CPS (V1.07) map

What the stock AnyTone D168UV CPS V1.07 shows and stores, as found by running it under Wine (scratch prefix, all COM
ports pointed at `/dev/null`, no radio attached, nothing written to a radio). The cfw CPS uses this as its D168UV stock
model: `schema/stock_d168uv.json` is generated from the same sources by `tools/make_stock_schema.py` (model D168UV).

The D168 CPS is the same AnyTone CPS family as the D890UV one (D878UV lineage) without NXDN, AM air band, satellite
data in the tree, Bluetooth and the D890 extras; it adds QDC1200 (an MDC1200-like analog signalling), Friends List and
Talk Alias. Inside the cfw CPS the D168 tables carry the D890 names where the two differ only in naming
(Zone = DMRZone, TalkGroups = DMRTalkGroups, ReceiveGroupCallList = DMRReceiveGroupCallList, DigitalContactList =
DMRDigitalContactList; Channel columns Contact = Contact/Talk Group, Contact Call Type = Contact/Talk Group Call Type,
TxCc = txcc). The CSV files keep the stock D168 names (`csv_name`, `csv_columns` in the schema).

Sources:
1. **Screenshots** of the main window, tree, menus and all 18 Optional Setting tabs (not shipped).
2. **Tool > Export > Export All** of a new codeplug (factory defaults) and of a real codeplug opened in the D168 CPS
   (contact list trimmed to 500): 28 CSV tables.
3. **.rdt layout (V1292, model "D168UV")**: decoded structurally against a real codeplug the D168 CPS saved and its own CSV
   export (every table except a few channel bytes agrees), then field by field like the D890 map
   (`tools/stock_rdt_experiments/rdtmap.py` with `MODEL=D168UV`; offsets in `schema/rdt_map_d168.json`, positions in the
   24 713-byte reference file). Differences from the D890UV V1323 layout:
   * header segment C is 90 bytes (D890: 94); OptionalSetting segments A (< 0x81), B (0x83-0x8D), C (0x8F-0xE8) with
     empty power-on texts;
   * channel record: 48 fixed bytes (V1270 layout), name cstr, a 35-byte tail (D890: 50);
   * one extra byte after each zone name (D890: 3 bytes per zone after the zone list);
   * scan list header 11 bytes (D890: 14);
   * talkgroups and the user database start with a byte length, not a count: `u8, u16 len, u8` / `u8, u24 len, u8`
     (the length counts from the byte after the length field);
   * FM records have no name; the last FM record is the FM VFO (index 100);
   * no NXDN block.
   * header u32 at offset 5 = file length - 14 (both models; the stock CPS answers "file error" otherwise; the cfw writer
     sets it since 2026-11-21);
   * channel record bytes found besides the V1270 ones: 17 = Talk Around(Simplex) on analog channels / Work Alone on
     digital ones, 42 = Idle TX, tail 0 = 2TONE Decode, tail 34 = TxCc, others in `rdt_map_d168.json`; analog busy lock
     is called "Busy" (D890: "Channel Free").

Checks: every decoded table of a real codeplug saved by the D168 CPS equals the D168 CPS's own CSV export
(`tests/test_d168.py`); that file written by the cfw CPS (contact list trimmed) opened in the stock D168 CPS and saved
again comes back byte for byte.

Limits:
* Combo boxes are windowless VB6 controls (as on the D890): the CSV holds the raw value, labels are in the screenshots.
* PF key assignments (PF1/PF2 short, long 1/2), Knob/Keyboard/Side/Forced key locks, Alarm Setting, Local Information,
  Encryption Code, Friends List and Talk Alias are not in the CSV export; they stay byte for byte in the .rdt.
* The D168 CPS's CSV export does not reflect the Optional Settings held in the .rdt header (segments A-C; it writes
  0 or the power-on default there, and empty power-on texts) while its dialog shows the file's values; the settings in
  the tail block (from AutoRepeaterB on) export correctly. Checked: an .rdt written by cfw with TOT / SQL(A) / Step / ...
  = 2 shows TOT 60s, SQL 2, 6.25K in the stock dialog. The cfw .rdt reader takes all of them from the file.
* 11 Optional Setting columns changed no byte (reserved / not used by the D168), 12 are multi-byte (VFO scan and auto
  repeater frequencies) and are kept, not written. A second Optional Setting block sits in the .rdt tail at a fixed
  distance (23 360 B) from the end of the file; cfw addresses it from the end (`LAYOUT["D168UV"]["end_from"]`).
* For a few fields (Step, VOX_Delay, Group/PersonTalkHold, IdleWait, ContactOutSetEn, MeasurePeriod) the stock CSV
  default differs from the byte in a new stock file; cfw writes only settings that differ from the file it starts from.
* Checked against the stock D168 CPS: a cfw-written .rdt (CSV import + an added channel + an Optional Setting) opens
  and saves back byte for byte (`csvset_stock_v1292.rdt`, not shipped). Channel numbers: VFO A/B are 4001/4002; the
  stock CPS keeps channel records in number order and merges channels with the same number, so cfw gives an added
  channel the next free number and writes the records in number order.

Files made by the stock CPS (its screenshots, its new-file `.rdt` templates, its saves and exports of real codeplugs) are not shipped with cfw_cps; the tests that use them skip without them (README "Stock CPS files"). Example values below come from the synthetic test codeplug (`tools/make_synth.py`).

## Main window

| Menu | Items |
|---|---|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As, Exit |
| Model | Model Information |
| Set | Set COM, Set Initialization |
| Program | Read From Radio, Write To Radio |
| Tool | Radio Recording, Import, Export, Mode, eXtended, Firmware and Icon Update, Boot Image, Default Channel Information, Options, Standby BK Picture1, Standby BK Picture2, export Data Conversion File, Satellite Data Updating |
| View | Toolbar, Status Bar, Quick Help |
| Help | About D168UV |

Title: `D168UV[D168UV:UHF{400 - 480 MHz} VHF{136 - 174 MHz}][:file] Version 1.07`. The channel grid shows No., RX/TX
frequency, Channel Type, Power, Band Width, CTCSS/DCS Decode/Encode, Channel Name, Contact, Radio ID, Optional Signal;
VFO A / VFO B rows first. Export dialog: 28 tables, "Excluding Key Function".

The cfw CPS keeps File / Program (Read, Write) / Tool (Import, Export, Validate, Diff) / Print and the same tree, with no
firmware / icon / boot image / satellite update or radio recording (codeplug only).

### Tree (left) -> stock CSV table -> cfw


| Section | Node | Stock table (CSV) | Rows (test codeplug) | cfw |
|---|---|---|---|---|
| Public | Channel | Channel | 179 | channels |
| Public | Zone | Zone | 12 | zones |
| Public | Scan List | ScanList | 6 | scan lists |
| Public | Roaming Channel | RoamingChannel | 8 | used by cfw |
| Public | Roaming Zone | RoamingZone | 2 | used by cfw |
| Public | FM | FM | 12 | used by cfw |
| Public | Auto Repeater Offset Frequencies | AutoRepeaterOffsetFrequencys | 0 | used by cfw |
| Public | Device Information | (dialog, .rdt only) |  | used by cfw |
| Public | Optional Setting | OptionalSetting | 1 | partly used by cfw (130 of 195 keys stored, not used yet) |
| Public | Bluetooth (cfw) | OptionalSetting (8 keys) | | cfw page, partly used by cfw (5 of 8 keys stored, not used yet) |
| Public | Alarm Setting | (dialog, .rdt only) |  | partly used by cfw (4 of 25 keys stored, not used yet) |
| Public | Hot Key | HotKey_HotKey | 18 | used by cfw |
| Public | Hot Key Quick Call | HotKey_QuickCall | 4 | used by cfw |
| Public | Hot Key State | HotKey_State | 0 | stored, not used by cfw yet |
| Public | Alert Tone | AlertTone | 1 | used by cfw |
| Public | APRS | APRS | 1 | partly used by cfw (213 of 232 keys stored, not used yet) |
| Public | GPS Roaming | GPSRoaming | 32 | used by cfw |
| Digital | Master ID | (dialog, .rdt only) |  | Radio Settings |
| Digital | Radio ID List | RadioIDList | 1 | used by cfw |
| Digital | Contact/Talk Groups | TalkGroups | 22 | contacts |
| Digital | Prefabricated SMS | PrefabricatedSMS | 5 | used by cfw |
| Digital | Receive Group Call List | ReceiveGroupCallList | 3 | TG lists |
| Digital | Encryption Code | (dialog, .rdt only) |  | used by cfw |
| Digital | AES Encryption Code | AESEncryptionCode | 0 | used by cfw |
| Digital | ARC4 Encryption Code | ARC4EncryptionCode | 0 | used by cfw |
| Digital | Digital Contact List | DigitalContactList | 200 | used by cfw |
| Digital | Friends List | (dialog, .rdt only) |  | used by cfw |
| Digital | Talk Alias | (dialog, .rdt only) |  | partly used by cfw (1 of 2 keys stored, not used yet) |
| Analog | Analog Address Book | AnalogAddressBook | 0 | used by cfw |
| Analog | QDC Address Book | QDC1200AddressBook | 0 | used by cfw |
| Analog | QDC1200 Setting | QDC1200EnCodeTable | 0 | used by cfw |
| Analog | QDC1200 Decode | QDC1200DECodeTable | 1 | partly used by cfw (5 of 7 keys stored, not used yet) |
| Analog | 5Tone Setting | 5ToneEncode | 0 | used by cfw |
| Analog | 5Tone Information Codes | T5InfoCodes | 0 | used by cfw |
| Analog | 5Tone Settings | T5Setting | 0 | partly used by cfw (6 of 20 keys stored, not used yet) |
| Analog | 2Tone Setting | 2ToneEncode | 0 | used by cfw |
| Analog | 2Tone Settings | T2Setting | 0 | partly used by cfw (2 of 6 keys stored, not used yet) |
| Analog | DTMF Setting | DTMFEncode | 0 | used by cfw |
| Analog | DTMF Settings | DTMFSetting | 0 | partly used by cfw (6 of 17 keys stored, not used yet) |

cfw column: schema/cfw_support.json (tools/make_cfw_support.py). Hidden on this radio (n/a): AM Air, AM Zone, Digital Contact Whitelist (Repeater), Encryption Code, Local Information, MDC1200 Address Book, MDC1200 Encode, NX Digital Contact List, NX Encryption Code, NX Receive Group Call List, NX Setting, NX State Message, NX Talk Group, Talk Group Whitelist (Repeater).

cfw adds: Tier III Systems (Digital) and a *cfw Digital Modes* section (Radio Settings, Trunk Systems with P25 band plans, Encryption Keys, D-STAR Repeaters, D-STAR / YSF / registration settings).

## Optional Setting dialog

18 tabs (Alert Tone1 = tone table, CSV AlertTone). Value = stock CSV value (default of a new codeplug); Test = value in the synthetic test codeplug; .rdt = byte offset in a V1292 .rdt (one byte unless noted).

### Work Mode

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Display mode | `FreqDis` | 0 | 0 | 0x77 |
| MEM Zone(A) | `Work_Zone1` | 0 | 0 | 0x6D |
| MEM Zone(B) | `Work_Zone2` | 0 | 0 | 0x6E |
| Main Channel Set | `MainState` | 0 | 0 | 0x79 |
| Sub-Channel Mode | `SubMode` | 0 | 0 | 0x7A |

### Vox/BT

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| VOX Level | `VOX` | 0 | 0 | 0x55 |
| VOX Delay | `VOX_Delay` | 0 | 0 | 0x56 |
| VOX Detection | `VoxHeadset` | 0 | 0 | 0x80 |

### STE

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| STE Type Of CTCSS | `STE_Type` | 0 | 0 | 0x65 |
| STE When No Signal | `STE_Freq` | 0 | 0 | 0x66 |
| Ste Time | `SteTime` | 0 | 25 | 0x57C |
| Dcs Ste | `DcsSte` | 0 | 0 | 0x5A0 |

### FM

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| FM VFO/MEM | `FM_VFO` | 0 | 0 | 0x6C |
| FM Work Channel | `Work_FMCH` | 0 | 0 | 0x6B |
| FM Monitor | `FmMon` | 0 | 0 | 0x78 |
| FM Function | `FM_En` | 0 | 0 | 0x6F |

### Power Save

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Auto Shutdown | `AutoPowerOff` | 0 | 0 | 0x4C |
| Power save | `PowerSave` | 0 | 0 | 0x54 |
| Auto Shutdown Type | `ApoKind` | 0 | 0 | 0x598 |

### Key Function

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Key Lock | `KeyLock` | 0 | 0 | 0x4B |
| Long Key 2 Time[s] | `PfLongTime` | 0 | 0 | 0x8F |

### Other

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Address Book Is Sent With Its Own Code | `ContactOutSetEn` | 0 | 0 | 0x8D |
| TOT | `TOT` | 0 | 3 | 0x4D |
| Frequency Step | `Step` | 0 | 0 | 0x51 |
| SQL Level(A) | `SQL1` | 0 | 0 | 0x52 |
| SQL Level(B) | `SQL2` | 0 | 0 | 0x53 |
| TBST | `TBST` | 0 | 0 | 0x7B |
| Analog Call Hold Time[s] | `AnaHoldTime` | 0 | 0 | 0x94 |
| call channel is maintained | `CurTalkPathHold` | 0 | 0 | 0xA8 |
| Priority Zone A | `PriZoneA` | 0 | 0 | 0xA9 |
| Priority Zone B | `PriZoneB` | 0 | 0 | 0xAA |
| Mute timing | `FixTimeMute` | 0 | 0 | 0x56D |
| TOT Predict | `TotPreEn` | 0 | 0 | 0x594 |
| TX Power AGC | `TxAgcCon` | 0 | 0 | 0x595 |

### Digital Func

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Group Call Hold Time | `GroupTalkHold` | 0 | 0 | 0x67 |
| Person Call Hold Time | `PersonTalkHold` | 0 | 0 | 0x68 |
| Manual Dial - Group TG Hold Time | `DialGroupHold` | 0 | 0 | 0x58E |
| Manual Dial - Private TG Hold Time | `DialPrivateHold` | 0 | 0 | 0x58F |
| Voice Header Repetitions | `Preamble` | 0 | 0 | 0x6A |
| TX Preamble Duration | `PreWave` | 0 | 0 | 0x69 |
| Filter Own ID In MissCall | `MissCallFilter` | 0 | 0 | 0x86 |
| Digital Remote Kill | `DigiStunKillEn` | 0 | 0 | 0x8A |
| Digital Monitor | `DigiMoni` | 0 | 0 | 0x92 |
| Digital Monitor CC | `DigiMoniCc` | 0 | 0 | 0xAD |
| Digital Monitor ID | `DigiMoniId` | 0 | 0 | 0xAE |
| Monitor Slot Hold | `Scan_Pri_Current` | 0 | 0 | no effect |
| Remote Monitor | `RemoteMoniEn` | 0 | 0 | 0x8B |
| SMS Format | `SmsFormat` | 0 | 0 | 0x599 |

### Power-on

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Power-on Interface | `StartDspSet` | 0 | 0 | 0x4F |
| Power-on Display (line 1) | `Start_Char` |  | SYNTH |  |
| Power-on Display (line 2) | `Start_Char2` |  | TEST |  |
| Power-on Password | `Password` | 0 | 0 | 0x50 |
| Power-on Password Char | `Password_Char` |  |  |  |
| Default Startup Channel | `StartChUse` | 0 | 0 | 0x55A |
| Startup Zone A | `StartZone1` | 0 | 0 | 0x55B |
| Startup Channel A | `StartCurChan1` | 0 | 0 | 0x55D |
| Startup Zone B | `StartZone2` | 0 | 0 | 0x55C |
| Startup Channel B | `StartCurChan2` | 0 | 0 | 0x55E |
| Startup Reset | `StartResetEn` | 0 | 1 | 0x571 |

### Alert Tone

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| SMS Alert | `MsgRing` | 0 | 0 | 0x76 |
| Call Alert | `CallRing` | 0 | 0 | 0x7C |
| Digi Call ResetTone | `OverVoice` | 0 | 0 | 0x7F |
| Call Tone | `TalkTips` | 0 | 0 | 0x7E |
| Key Tone | `Beep` | 0 | 0 | 0x49 |
| Digi Idle Channel Tone | `SqOnVoice` | 0 | 0 | 0x84 |
| Startup Sound | `Boot_Sound` | 0 | 0 | 0x87 |
| Key Sound Adjustable | `VolNoteEn` | 0 | 0 | 0x90 |
| Ana Idle Channel Tone | `AnaSqOnVoice` | 0 | 0 | 0x59B |

### Display

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Brightness | `Lightness` | 0 | 0 | 0x73 |
| Auto Backlight Duration | `AutoBKLightTime` | 0 | 0 | 0x74 |
| Backlight Delay Of TX[s] | `TxDimWait` | 0 | 0 | 0x564 |
| Menu Exit Time[s] | `MenuLowPower` | 0 | 0 | 0x55F |
| Time Display | `DateDisKind` | 0 | 0 | 0x95 |
| Last Caller | `LastCallDis` | 0 | 0 | 0xB0 |
| Call Display Mode | `CallModeDisKind` | 0 | 0 | 0xB4 |
| Call Sign Display Color | `CallSignColour` | 0 | 0 | 0x57D |
| Display Channel Number | `ChanNumDisKind` | 0 | 0 | 0xBC |
| Display Current Contact | `MenuDisWorkContact` | 0 | 0 | 0xBD |
| Standby Char Color | `WorkCharDisColour` | 0 | 0 | 0x592 |
| Standby BK Picture | `bkpic` | 0 | 0 | 0x593 |
| Show Last Call On Launch | `GpsTextUsed` | 0 | 0 | 0xB2 |
| Separate display | `DiviDisEn` | 0 | 0 | 0x565 |
| CH Switching Keeps Last Caller | `LastHeardChanSet` | 0 | 0 | 0x566 |
| A Channel Name Color | `ChanNameColour` | 0 | 0 | 0x567 |
| Receive Backlight Delay[s] | `RxDimWait` | 0 | 0 | 0x569 |
| B Channel Name Color | `ChanNameColourB` | 0 | 0 | 0x590 |
| Zone Name Colour A | `ZoneNameColourA` | 0 | 0 | 0x596 |
| Zone Name Colour B | `ZoneNameColourB` | 0 | 0 | 0x597 |
| Display Channel Type | `ChanDisCtr` | 0 | 0 | 0x59A |
| Date Display Format | `DateDisFormat` | 0 | 0 | 0x59C |
| Night Mode | `NightMode` | 0 | 0 | 0x5A5 |
| Night Start Hour | `NlightStartHour` | 0 | 0 | 0x5AC |
| Night Start Min | `NlightStartMin` | 0 | 0 | 0x5AD |
| Night End Hour | `NlightEndHour` | 0 | 0 | 0x5AE |
| Night End Min | `NlightEndMin` | 0 | 0 | 0x5AF |

### GPS/Ranging

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Time Zone | `TmZone` | 0 | 0 | 0x7D |
| GPS Roaming | `Gps` | 0 | 0 | 0x75 |

### VFO Scan

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| VFO Scan Type | `ScanType` | 0 | 0 | 0x57 |
| VFO Scan Start Freq(UHF) | `VfoScanFreq0` | 0 | 0 | 0x97, 0x98, 0x99 |
| VFO Scan End Freq(UHF) | `VfoScanFreq1` | 0 | 0 | 0x9B, 0x9C, 0x9D |
| VFO Scan Start Freq(VHF) | `VfoScanFreq2` | 0 | 0 | 0x9F, 0xA0 |
| VFO Scan End Freq(VHF) | `VfoScanFreq3` | 0 | 0 | 0xA2, 0xA3, 0xA4, 0xA5 |

### Auto repeater

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Auto Repeater A | `AutoRepeater` | 0 | 0 | 0x91 |
| Auto Repeater B | `AutoRepeaterB` | 0 | 0 | 0x547 |
| Auto Repeater1(UHF) | `UhfAutoRep` | 0 | 0 | 0xA6 |
| Auto Repeater1(VHF) | `VhfAutoRep` | 0 | 0 | 0xA7 |
| Auto Repeater2(UHF) | `UhfAutoRep2` | 0 | 0 | 0x575 |
| Auto Repeater2(VHF) | `VhfAutoRep2` | 0 | 0 | 0x576 |
| Repeater Check | `BsModeCheck` | 0 | 0 | 0x560 |
| Repeater Check Interval[s] | `TimeBsCheck` | 0 | 0 | 0x561 |
| Repeater Check Reconnections | `BsCheckTimes` | 0 | 0 | 0x562 |
| Alert Out Of Repeat Range | `OutRepNote` | 0 | 0 | 0x568 |
| Repeater out of range reminder(times) | `OutNoteTimes` | 0 | 0 | 0x56F |
| Auto Roaming | `TimeRoamOn` | 0 | 0 | 0x56A |
| Timed Roaming Start Condition | `FixRomanStartOp` | 0 | 0 | 0x563 |
| Auto Roaming Interval[m] | `WanderPerod` | 0 | 0 | 0xBE |
| Roaming Effect Wait Time[s] | `WanderEffectWait` | 0 | 0 | 0xC0 |
| Roaming Zone | `CurRoamZone` | 0 | 0 | 0x56B |
| Min Freq Of Auto Repeater1(VHF) | `AutoRepFreq0` | 136 | 136 | 0x548, 0x549, 0x54A |
| Max Freq Of Auto Repeater1(VHF) | `AutoRepFreq1` | 174 | 174 | 0x54C, 0x54D, 0x54E |
| Min Freq Of Auto Repeater1(UHF) | `AutoRepFreq2` | 400 | 400 | 0x550, 0x551, 0x552 |
| Max Freq Of Auto Repeater1(UHF) | `AutoRepFreq3` | 480 | 480 | 0x554, 0x555, 0x556 |
| Min Freq Of Auto Repeater2(VHF) | `AutoRepMinFreqV2` | 0 | 0 | 0x57E, 0x57F, 0x580 |
| Max Freq Of Auto Repeater2(VHF) | `AutoRepMaxFreqV2` | 0 | 0 | 0x582, 0x583, 0x584 |
| Min Freq Of Auto Repeater2(UHF) | `AutoRepMinFreqU2` | 0 | 0 | 0x586, 0x587, 0x588 |
| Max Freq Of Auto Repeater2(UHF) | `autoRepMaxFreqU2` | 0 | 0 | 0x58A, 0x58B, 0x58C |

### Record

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Record Function | `Record_En` | 0 | 0 | 0x70 |
| Record Delay | `RecordDelay` | 0 | 0 | 0xB3 |

### Volume/Audio

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Maximum Volume | `MaxVol` | 0 | 0 | 0x89 |
| Max Headphone Volume | `EarMaxVol` | 0 | 0 | 0xB1 |
| Digit Mic Gain | `MicLevel` | 0 | 0 | 0x58 |
| Enhanced Sound Quality | `EnSoundEffect` | 0 | 0 | 0xAB |
| Ana Mic Gain | `AnaMic` | 0 | 0 | 0x59D |
| TX Noise Reduction | `TxNr` | 0 | 0 | 0x5A1 |
| RX Noise Reduction | `RxNr` | 0 | 0 | 0x5A2 |
| DRC Dynamic Range Control(Rx AGC) | `Drc` | 0 | 0 | 0x5A3 |

### Satellite

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Satellite Location | `SateLocalKind` | 0 | 0 | 0x5A8 |
| Sate TX Power | `SateTxPower` | 0 | 0 | 0x5A9 |
| Sate ANA Sql | `SateAnaSql` | 0 | 0 | 0x5AA |
| Sate Aos Limit | `SateAosLimit` | 0 | 0 | 0x5AB |

### Man Down

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Man Down | `FailAlarm` | 0 | 0 | 0x71 |
| Man Down Delay[s] | `ManDownWait` | 0 | 0 | 0x93 |

### Bluetooth

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| BT On/Off | `BlueToothOn` | 0 | 1 | 0xB5 |
| Hold Time | `BhtHoldTime` | 0 | 33 | 0x572 |
| RX Delay | `BhtHoldDelay` | 0 | 3 | 0x573 |
| BT+int spk | `SpkInBlueTooth` | 0 | 1 | 0xB7 |
| Mic Gain | `BhtMicGain` | 0 | 4 | 0xBA |
| Spk Gain | `BhtSpkGain` | 0 | 2 | 0xBB |
| BT PTT Hold (no radio menu) | `BhtPttHold` | 0 | 1 | 0x63 |
| Mic In BT (no radio menu) | `MicInBlueTooth` | 0 | 1 | 0xB6 |

### More (CSV only)

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| (CSV only) | `DSP` | 0 | 0 | 0x4A |
| (CSV only; radio menu: Settings > Radio Set > DISP Func > Language (English, Chinese)) | `Language` | 0 | 0 | 0x4E |
| (CSV only) | `RMV1` | 0 | 0 | no effect |
| (CSV only) | `RMV2` | 0 | 0 | 0x64 |
| (CSV only) | `MonType` | 0 | 0 | 0x72 |
| (CSV only) | `Reserved_Start_Char` |  |  | no effect |
| (CSV only) | `Reserved_EMG_Kind` | 0 | 0 | no effect |
| (CSV only) | `Voice_Note` | 0 | 0 | 0x83 |
| (CSV only) | `IdleWait` | 0 | 0 | 0x85 |
| (CSV only) | `TalkOverPoint` | 0 | 0 | 0x88 |
| (CSV only) | `Reserved_DigiKillEn` | 0 | 0 | no effect |
| (CSV only) | `GpsReplyEn` | 0 | 0 | 0x8C |
| (CSV only) | `AprsUpDate` | 0 | 0 | no effect |
| (CSV only) | `AprsTxFreq` | 0 | 0 | no effect |
| (CSV only) | `MsgOacsuSet` | 0 | 0 | 0xAC |
| (CSV only) | `WtRecordNote` | 0 | 0 | 0xB8 |
| (CSV only) | `MeasurePeriod` | 0 | 0 | 0xB9 |
| (CSV only) | `Ext_Opt1` | 0 | 0 | 0xBF |
| (CSV only) | `Ext_Opt2` | 0 | 0 | 0xC1 |
| (CSV only) | `GroupCallS_Ext` | 0 | 0 | no effect |
| (CSV only) | `Contact_Compression` | 0 | 0 | no effect |
| (CSV only) | `RX_Contact_Compression` | 0 | 0 | no effect |
| (CSV only) | `File_Optimization` | 0 | 0 | no effect |
| (CSV only) | `BookOwnId` | 0 | 0 | 0x558 |
| (CSV only) | `AprsDistanceDis` | 0 | 0 | 0x559 |
| (CSV only) | `RoamEffectChanDis` | 0 | 0 | 0x56C |
| (CSV only) | `comVersion` | 0 | 0 | 0x56E |
| (CSV only) | `StartTestGps` | 0 | 0 | 0x570 |
| (CSV only; radio menu: Settings > Radio Set > Other Func > WX Alarm (Off, On)) | `WxAlarmSign` | 0 | 0 | 0x574 |
| (CSV only) | `CurUhfAutoRep` | 0 | 0 | 0x577 |
| (CSV only) | `CurVhfAutoRep` | 0 | 0 | 0x578 |
| (CSV only) | `PttSleepTime` | 0 | 1 | 0x57A |
| (CSV only; radio menu: GPS > GPS Mode (GPS, BDS, GPS+BDS, GLONASS, GPS+GLON, BDS+GLON, ALL) ?) | `GpsMode` | 0 | 0 | 0x57B |
| (CSV only) | `DigiEmgKind` | 0 | 1 | 0x591 |
| (CSV only) | `ZoneBarsEn` | 0 | 0 | 0x59E |
| (CSV only) | `VcallRpheader` | 0 | 0 | 0x59F |
| (CSV only) | `DmrRasEn` | 0 | 0 | 0x5A4 |
| (CSV only) | `SateFixPointName1` |  |  |  |
| (CSV only) | `SateFixPointName2` |  |  |  |
| (CSV only) | `SateFixPointName3` |  |  |  |
| (CSV only) | `SateFixPointName4` |  |  |  |
| (CSV only) | `SateFixPointName5` |  |  |  |
| (CSV only) | `SateFixPointName6` |  |  |  |
| (CSV only) | `SateFixPointName7` |  |  |  |
| (CSV only) | `SateFixPointName8` |  |  |  |

Key Function tab (not in CSV, .rdt only): PF1/PF2 Short Key, PF1/PF2 Long Key 1, PF1/PF2 Long Key 2, Knob Lock, Keyboard Lock, Side Key Lock, Forced Lock Key (screenshot opt_06). Other tab: Encryption Type (.rdt only). Display tab: Display Time Slot, Display Color Code (.rdt only).

## Bluetooth (cfw page; the stock D168 CPS has none)

The D168UV radio has a full BT menu (Settings > BT, `D168UV/emu/MENUS.md`) but the stock D168 CPS shows no Bluetooth
fields; its CSV export and .rdt still carry the BT settings (Optional Setting keys, CSV only). The cfw CPS shows them on
a **Bluetooth** page (tree: Public > Bluetooth, also a Bluetooth tab in Optional Setting) with the radio's labels and value
lists; the stored stock CSV value is the index in the list.

Checked two ways:
1. **.rdt -> radio**: an .rdt with marker values in these bytes was written by the stock D168 CPS ("Write To Radio")
   to a fake radio on a pty (ident `D168UV`): the bytes land in the radio settings block (NAND 0x02500000, 0xF0 bytes,
   RAM copy 0x20009BC8), column "NAND" below. FailAlarm (+0x24) and ManDownWait (+0x4F) came out as already known.
2. **value lists**: in the stock V1.07 emulator the settings byte was set and the menu opened (lists open on the
   current value): Hold Time 0 = OFF, 1 = 1S, 30 = 30S, 31 = 60S, 33 = infinite; RX Delay 0 = 30ms, 1 = 1S, 10 = 5.5S;
   Mic / Spk Gain 0 = Level 1, 4 = Level 5; On/Off 0 = BT Off, 1 = BT On; BT+int spk 0 = Off, 1 = On.

| Radio menu (cfw label) | CSV key | .rdt | NAND +off | Values (stored = index) |
|---|---|---|---|---|
| BT On/Off | `BlueToothOn` | 0xB5 | 0xB1 | 0 BT Off, 1 BT On |
| Hold Time | `BhtHoldTime` | 0x572 | 0xED | 0 OFF, 1-30 = 1S-30S, 31 60S, 32 120S, 33 infinite |
| RX Delay | `BhtHoldDelay` | 0x573 | 0xEE | 0 30ms, 1 1S, 2 1.5S, 3 2S, 4 2.5S, 5 3S, 6 3.5S, 7 4S, 8 4.5S, 9 5S, 10 5.5S |
| BT+int spk | `SpkInBlueTooth` | 0xB7 | 0xB3 | 0 Off, 1 On |
| Mic Gain | `BhtMicGain` | 0xBA | 0xB6 | 0 Level 1, 1 Level 2, 2 Level 3, 3 Level 4, 4 Level 5 |
| Spk Gain | `BhtSpkGain` | 0xBB | 0xB7 | 0 Level 1, 1 Level 2, 2 Level 3, 3 Level 4, 4 Level 5 |
| BT PTT Hold (no radio menu) | `BhtPttHold` | 0x63 | 0x15 | raw |
| Mic In BT (no radio menu) | `MicInBlueTooth` | 0xB6 | 0xB2 | raw |

Not in the codeplug: Pairing, BT Names, Pair-Names, Pin Code, NR BEL, NR AFL, PTT Pair (Connect / Disconnect, PTT HOLD, PTT Name, PTT Sleep, PTT Bat). Checked in the emulator: selecting another NR BEL / NR AFL / PTT HOLD value leaves the
settings block unchanged (BT Names / Pin Code go to the JieLi module as AT commands, `D168UV/emu/models/Bt168.cs`); the
stock CPS has no field for any of them. `MicInBlueTooth` (+0xB2) and `BhtPttHold` (+0x15) are stock keys whose bytes
reach the settings block but no BT menu shows them (+0x15 does not change PTT HOLD, which the crawl had guessed): raw
values.

## Dialogs kept only in the .rdt

Measured in the stock CPS: change one field in the dialog, OK, save, diff; and the other way round, change one byte of the file and look which dialog field moves (tools/make_rdt_dialogs.py). The cfw CPS edits them as ordinary pages and stores them in the codeplug (section 10 tables 64+, docs/CODEPLUG.md). Offsets: A / C = header segments (cps/rdt.py LAYOUT, A with its variable strings taken out), E = bytes before the end of the tail, H = variable header string, list = own record list.

### Alarm Setting (table 64, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | Analog Emergency Alarm | C+0x33 u8 | 0 | 0 Alarm, 1 Transpond+Background, 2 Transpond+Alarm, 3 Both |
| 1 | Analog ENI Type | C+0x34 u8 | 0 |  |
| 2 | Analog Alarm Time [s] | C+0x36 u8 | 20 |  |
| 3 | Analog Duration of TX [s] | C+0x37 u8 | 31 |  |
| 4 | Analog Duration of RX [s] | C+0x38 u8 | 31 |  |
| 5 | Analog Emergency Channel | C+0x39 chan | 1 |  |
| 6 | Analog ENI Send Select | C+0x3B u8 | 0 | 0 Assigned Channel, 1 Selected Channel |
| 7 | Analog Emergency Cycle (0 = Continuous) | C+0x3C u8 | 0 |  |
| 8 | Digital Emergency Alarm | C+0x3D u8 | 0 | 0 Alarm, 1 Transpond+Background, 2 Transpond+NoLocalAlarm, 3 Transpond+LocalAlarm |
| 9 | Digital Emergency Channel | C+0x3E chan | 1 |  |
| 10 | Digital Alarm Time [s] | C+0x40 u8 | 20 |  |
| 11 | Digital Duration of TX [s] | C+0x41 u8 | 31 |  |
| 12 | Digital Duration of RX [s] | C+0x42 u8 | 31 |  |
| 13 | Digital ENI Send Select | C+0x43 u8 | 0 | 0 Assigned Channel, 1 Selected Channel |
| 14 | Digital Emergency Cycle (0 = Continuous) | C+0x44 u8 | 0 |  |
| 15 | Digital TG/DMR ID | C+0x4A u32 | 0 |  |
| 16 | Digital Call Type | C+0x49 u8 | 0 | 0 Private Call, 1 Group Call, 2 All Call |
| 17 | Receive Alarm | C+0x48 u8 | 0 | 0 Off, 1 On |
| 18 | QDC1200 Kind | C+0x4E u8 | 0 | 0 Private Call, 1 Group Call, 2 All Call |
| 19 | QDC1200 Group ID | C+0x4F hex3 | 000 |  |
| 20 | QDC1200 Private ID | C+0x51 hex4 | 0000 |  |
| 21 | Analog alarm signaling type | C+0x53 u8 | 0 | 0 None, 1 DTMF, 2 5TONE, 3 MDC1200 |
| 22 | Work Alone Response Time (0 = 1 min) | C+0x45 u8 | 0 |  |
| 23 | Work Alone Warning Time (0 = 1 s) | C+0x46 u8 | 0 |  |
| 24 | Work Alone Response | C+0x47 u8 | 0 | 0 Key, 1 Voice Transmit |

### DTMF Settings (table 65, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | DTMF Transmitting Time | A+0x3F u8 | 1 | 0 50 ms, 1 100 ms, 2 200 ms, 3 300 ms, 4 500 ms |
| 1 | DTMF Self ID (3 digits; the stock CPS shows letters blank) | A+0x39 str3 | 000 |  |
| 2 | DTMF Interval Character (10 A, 11 B, 12 C, 13 D, 14 *, 15 #) | A+0x33 u8 | 14 |  |
| 3 | Group Code (0 Off, 10 A .. 13 D, 14 *, 15 #) | A+0x34 u8 | 0 |  |
| 4 | Decoding Response | A+0x35 u8 | 0 | 0 None, 1 Beep Tone, 2 Beep Tone & Respond |
| 5 | First Digit Time (x 10 ms) | A+0x37 u8 | 20 |  |
| 6 | Pretime (x 10 ms) | A+0x36 u8 | 20 |  |
| 7 | Auto Reset Time (D890UV: s, D168UV: 0.1 s) | A+0x38 u8 | 0 |  |
| 8 | Time-Lapse After Encode (x 10 ms) | A+0x3D u8 | 20 |  |
| 9 | PTT ID Pause Time (raw) | A+0x3E u8 | 0 |  |
| 10 | D Code Pause (s, 0 = Off) | A+0x41 u8 | 10 |  |
| 11 | Side Tone | A+0x3C u8 | 0 | 0 Off, 1 On |
| 12 | PTT ID | A+0x40 u8 | 0 | 0 Off, 1 On |
| 13 | PTT ID Starting (BOT) | H dtmf_bot hstr |  |  |
| 14 | PTT ID Ending (EOT) | H dtmf_eot hstr |  |  |
| 15 | Remotely Kill | H dtmf_kill hstr |  |  |
| 16 | Remotely Stun | H dtmf_stun hstr |  |  |

### 2Tone Settings (table 66, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | 1st Tone Duration (x 0.1 s) | A+0x42 u8 | 5 |  |
| 1 | 2nd Tone Duration (x 0.1 s) | A+0x43 u8 | 5 |  |
| 2 | Long Tone Duration (x 0.1 s) | A+0x44 u8 | 10 |  |
| 3 | Gap Time (x 100 ms) | A+0x45 u8 | 0 |  |
| 4 | Auto Reset Time (D890UV: s, D168UV: 0.1 s) | A+0x46 u8 | 0 |  |
| 5 | Side Tone | A+0x47 u8 | 0 | 0 Off, 1 On |

### 5Tone Settings (table 67, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | Self ID | H t5_self hstr |  |  |
| 1 | Decode Standard | A+0x19 u8 | 0 |  |
| 2 | Decoding Response | A+0x18 u8 | 0 | 0 None, 1 Beep Tone, 2 Beep Tone & Respond |
| 3 | Time Of Decode Tone [ms] | A+0x1B u8 | 70 |  |
| 4 | Decode Time (x 10 ms) | A+0x26 u8 | 2 |  |
| 5 | 5TONE Dec Units (bit mask, bit 0 = unit 1) | A+0x2C u8 | 0 |  |
| 6 | Disp AnyID | A+0x2D u8 | 0 | 0 Off, 1 On |
| 7 | Pretime (x 10 ms) | A+0x1D u8 | 20 |  |
| 8 | Time-Lapse After Encode (x 10 ms) | A+0x1E u8 | 20 |  |
| 9 | PTT ID Pause Time [s] (0 = Off) | A+0x1F u8 | 10 |  |
| 10 | Auto Reset Time [s] | A+0x20 u8 | 0 |  |
| 11 | First Delay (x 10 ms) | A+0x21 u8 | 20 |  |
| 12 | Side Tone | A+0x22 u8 | 0 | 0 Off, 1 On |
| 13 | First Delay Time After Stop (x 10 ms) | A+0x27 u8 | 0 |  |
| 14 | PTT ID Starting (BOT): Encode ID | H t5_bot hstr |  |  |
| 15 | PTT ID Starting (BOT): standard (index) | H t5_bot_std hnum | 0 |  |
| 16 | PTT ID Starting (BOT): tone time [ms] | H t5_bot_time hnum | 70 |  |
| 17 | PTT ID Ending (EOT): Encode ID | H t5_eot hstr |  |  |
| 18 | PTT ID Ending (EOT): standard (index) | H t5_eot_std hnum | 0 |  |
| 19 | PTT ID Ending (EOT): tone time [ms] | H t5_eot_time hnum | 70 |  |

### 5Tone Information Codes (table 68, list)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | No. | list |  |  |
| 1 | Function Option (index) | list |  |  |
| 2 | Decoding Response (index) | list |  |  |
| 3 | Information ID | list |  |  |

### Talk Alias / AIR Alias (table 70, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | Talker Alias Type | E 23248 u8 | 0 | 0 Radio Alias, 1 Custom Text |
| 1 | Alias Display Priority | E 23247 u8 | 0 | 0 No Display, 1 Contact Alias, 2 Air Alias |

### Friends List (table 71, list)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | No. | list |  |  |
| 1 | DMR ID | list |  |  |

### Encryption Code (basic privacy) (table 72, list)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | No. | list |  |  |
| 1 | Encryption KEY (hex) | list |  |  |
| 2 | Encryption ID | list |  |  |

Not decoded: Alarm Setting > Analog > Emergency ID (list content depends on the signalling tables); Alarm Setting > ENI Type list texts (the value is stored raw); 5Tone Setting: Stop Code, Stop Time (header bytes 0x23-0x25 are not tied to one field); the Function Name of an information code (the string after the ID is kept as it is); 2Tone Setting > Decode tab; DTMF Setting > Special Call; Encode ID tables (CSV); Talk Alias > Custom Text: the V1.07 dialog shows no text field when it is chosen; where (or if) a text is kept is not known; QDC1200 Setting: Max ACK wait, Sync headers, Pretime, Try times, Side Tone; Local Information: the stock CPS opens the COM port for it; it is live radio data, not in the .rdt.

## Tables (stock CSV columns, in order)

### Channel (list, LST index 0)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 (+175 more) | cfw field |
| 1 | Channel Name | Channel 1 | Simplex 1, Simplex 2, Simplex 3, Simplex 4 (+175 more) | cfw field |
| 2 | Receive Frequency | 440.00000 | 446.02500, 446.07500, 446.12500, 446.17500 (+98 more) | cfw field .rdt 0xC8, 0xED, 0xEE, 0xEF, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5 |
| 3 | Transmit Frequency | 440.00000 | 441.02500, 441.07500, 441.12500, 441.17500 (+102 more) | cfw field .rdt 0xC8, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5 |
| 4 | Channel Type | D-Digital | D-Digital, A-Analog | cfw field .rdt 0xC8, 0xF6 |
| 5 | Transmit Power | High | Middle, High, Low, Turbo | cfw field .rdt 0xC8, 0xF7 |
| 6 | Band Width | 12.5K | 12.5K, 25K | cfw field .rdt 0xC8, 0xF8 |
| 7 | CTCSS/DCS Decode | Off | Off, 88.5, 103.5, 110.9 (+3 more) | cfw field .rdt 0xC8, 0xFD, 0xFE |
| 8 | CTCSS/DCS Encode | Off | Off, 67.0, 88.5, 100.0 (+9 more) | cfw field .rdt 0xC8, 0x101, 0x102 |
| 9 | Contact/Talk Group | Contact 1 | Contact 1, World, Local, Region (+8 more) | cfw field |
| 10 | Contact/Talk Group Call Type | Group Call | Group Call, Private Call | cfw field |
| 11 | Radio ID |  | '' | used by cfw .rdt 0xC8 |
| 12 | Busy Lock/TX Permit | Always | Always, Off, Channel Free | used by cfw .rdt 0xC8 |
| 13 | Squelch Mode | Carrier | Carrier, CTCSS/DCS | used by cfw .rdt 0x10C |
| 14 | Optional Signal | Off | Off, DTMF | used by cfw .rdt 0xC8 |
| 15 | DTMF ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 16 | 2Tone ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 17 | 5Tone ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 18 | PTT ID | Off | Off | used by cfw .rdt 0xC8 |
| 19 | RX Color Code | 1 | 1, 0, 2, 3 (+5 more) | cfw field .rdt 0xC8, 0x113 |
| 20 | Slot | 1 | 1, 2 | cfw field .rdt 0xC8 |
| 21 | Scan List | None | None, FM Simplex, FM Rpt | cfw field .rdt 0x114 |
| 22 | Receive Group List | None | None, Local+Region, Wide, Nets | cfw field .rdt 0xC8 |
| 23 | PTT Prohibit | Off | Off | used by cfw .rdt 0xFA |
| 24 | Reverse | Off | Off | used by cfw .rdt 0xC8 |
| 25 | Idle TX | Off | Off | stored .rdt 0xC8 |
| 26 | Slot Suit | Off | Off | stored .rdt 0xC8 |
| 27 | AES Digital Encryption | Normal Encryption | Normal Encryption | used by cfw .rdt 0x11A |
| 28 | Digital Encryption | Off | Off | used by cfw .rdt 0xC8 |
| 29 | Call Confirmation | Off | Off | stored .rdt 0xC8 |
| 30 | Talk Around(Simplex) | Off | Off, On | cfw field .rdt 0xC8 |
| 31 | Work Alone | Off | Off | used by cfw .rdt 0xFC |
| 32 | Custom CTCSS | 251.1 | 251.1, 0.0 | stored .rdt 0xC8, 0x105, 0x106 |
| 33 | 2TONE Decode | 0 | 0, 1 | used by cfw .rdt 0xC8, 0x125 |
| 34 | Ranging | Off | Off | stored .rdt 0xC8 |
| 35 | Through Mode | Off | Off | stored .rdt 0xC8 |
| 36 | APRS RX | Off | Off | stored .rdt 0xC8 |
| 37 | Analog APRS PTT Mode | Off | Off | used by cfw .rdt 0xC8 |
| 38 | Digital APRS PTT Mode | Off | Off | stored .rdt 0xC8 |
| 39 | APRS Report Type | Off | Off | used by cfw .rdt 0xC8 |
| 40 | Digital APRS Report Channel | 1 | 1 | stored .rdt 0xC8 |
| 41 | Correct Frequency[Hz] | 0 | 0 | used by cfw .rdt 0x12B |
| 42 | SMS Confirmation | Off | Off | stored .rdt 0xC8 |
| 43 | Exclude channel from roaming | 0 | 0 | used by cfw .rdt 0x130 |
| 44 | DMR MODE | 0 | 0 | used by cfw .rdt 0xC8, 0x127, 0x131 |
| 45 | DataACK Disable | 0 | 0 | stored .rdt 0xC8, 0x136 |
| 46 | R5ToneBot | 0 | 0 | used by cfw .rdt 0xC8, 0x137 |
| 47 | R5ToneEot | 0 | 0 | used by cfw .rdt 0xC8, 0x138 |
| 48 | Auto Scan | 0 | 0 | used by cfw .rdt 0xC8, 0x139 |
| 49 | Ana Aprs Mute | 0 | 0 | stored .rdt 0xC8, 0x13A |
| 50 | Send Talker Aias | 0 | 0 | used by cfw .rdt 0xC8, 0x13B |
| 51 | AnaAprsTxPath | 0 | 0 | stored .rdt 0xC8, 0x13D |
| 52 | ARC4 | 0 | 0 | used by cfw .rdt 0xC8 |
| 53 | ex_emg_kind | 0 | 0 | stored .rdt 0x13E |
| 54 | idle_tx | 0 | 0 | stored .rdt 0x13F |
| 55 | Compand | 0 | 0 | stored .rdt 0x140 |
| 56 | DisturEn | 0 | 0 | stored .rdt 0xC8, 0x143 |
| 57 | DisturFreq | 0 | 0 | stored .rdt 0xC8, 0x144 |
| 58 | Rpga_Mdc | 0 | 0 | used by cfw .rdt 0xC8, 0x145 |
| 59 | dmr_crc_ignore | 0 | 0 | stored .rdt 0xC8, 0x146 |
| 60 | txcc | 1 | 1 | stored |

### RadioIDList (list, LST index 1)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1 |  |
| 1 | Radio ID |  | 9990001 |  |
| 2 | Name |  | N0CALL |  |

### Zone = cfw DMRZone (list, LST index 2)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+8 more) | cfw field |
| 1 | Zone Name |  | FM Simplex, FM Repeaters, Site Alpha, Site Bravo (+8 more) | cfw field |
| 2 | Zone Channel Member |  | Simplex 1/Simplex 2/Simplex 3/Simplex 4/Simplex 5/Simplex 6/Simplex 7/Simplex 8/Simplex 9/ | cfw field |
| 3 | A Channel |  | '' |  |
| 4 | B Channel |  | '' |  |

### ScanList (list, LST index 3)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+2 more) | cfw field |
| 1 | Scan List Name |  | FM Simplex, FM Rpt, Site Alpha, Site Bravo (+2 more) | cfw field |
| 2 | Scan Channel Member |  | Simplex 1/Simplex 2/Simplex 3/Simplex 4/Simplex 5/Simplex 6/Simplex 7/Simplex 8/Simplex 9/ | cfw field |
| 3 | Scan Mode |  | '' |  |
| 4 | Priority Channel Select |  | '' |  |
| 5 | Priority Channel 1 |  | '' |  |
| 6 | Priority Channel 2 |  | '' |  |
| 7 | Revert Channel |  | '' |  |
| 8 | Look Back Time A[s] |  | '' |  |
| 9 | Look Back Time B[s] |  | '' |  |
| 10 | Dropout Delay Time[s] |  | '' |  |
| 11 | Dwell Time[s] |  | '' |  |

### AnalogAddressBook (list, LST index 4)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Number |  |  |  |
| 2 | Name |  |  |  |

### TalkGroups = cfw DMRTalkGroups (list, LST index 5)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 (+18 more) | cfw field |
| 1 | Radio ID | 1 | 2, 9, 91, 3100 (+18 more) | cfw field |
| 2 | Name | Contact 1 | Local, Region, World, Test TG 3100 (+18 more) | cfw field |
| 3 | Call Type | Group Call | Group Call, Private Call, All Call | cfw field |
| 4 | Call Alert | None | None |  |

### PrefabricatedSMS (list, LST index 6)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+1 more) |  |
| 1 | Text |  | Hello, 73, QSY 446.500, On my way (+1 more) |  |

### FM (list, LST index 7)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 (+8 more) |  |
| 1 | Frequency[MHz] | 88.000 | 88.100, 88.900, 89.700, 90.500 (+8 more) |  |
| 2 | Scan | Add | Add |  |

### ReceiveGroupCallList = cfw DMRReceiveGroupCallList (list, LST index 8)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3 | cfw field |
| 1 | Group Name |  | Local+Region, Wide, Nets | cfw field |
| 2 | Contact |  | Local/Region, Region/World/Test TG 3100, Net A/Net B/Net C | cfw field |

### 5ToneEncode (list, LST index 9)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | NO. |  |  |  |
| 1 | Encode ID |  |  |  |
| 2 | Encode Standard |  |  |  |
| 3 | Time Of Encode Tone[ms] |  |  |  |
| 4 | Name |  |  |  |

### 2ToneEncode (list, LST index 10)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | NO. |  |  |  |
| 1 | 1st Tone Frequency[Hz] |  |  |  |
| 2 | 2nd Tone Frequency[Hz] |  |  |  |
| 3 | Name |  |  |  |

### DTMFEncode (list, LST index 11)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | DTMF ID |  |  |  |
| 1 | DTMF Encode |  |  |  |

### HotKey_QuickCall (list, LST index 12)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 |  |
| 1 | Operation Type | Off | Off |  |
| 2 | Call ID | Off | Off |  |

### HotKey_State (list, LST index 13)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | State Content |  |  |  |

### HotKey_HotKey (list, LST index 14)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Key | 1 | 1, 2, 3, 4 (+14 more) |  |
| 1 | Mode | Menu | Menu |  |
| 2 | Menu | SMS | SMS, New SMS, Hot Text, Received SMS (+9 more) |  |
| 3 | Call Type | Analog | Analog |  |
| 4 | Call Object | Off | Off |  |
| 5 | Call Object Call Type |  | '' |  |
| 6 | Digi Call Type | Group Call | Group Call |  |
| 7 | Content | Off | Off |  |

### DigitalContactList = cfw DMRDigitalContactList (list, LST index 15) - file only (too big for the radio)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+196 more) |  |
| 1 | Radio ID |  | 9990101, 9990102, 9990103, 9990104 (+196 more) |  |
| 2 | Callsign |  | TEST01, TEST02, TEST03, TEST04 (+196 more) |  |
| 3 | Name |  | Test User 1, Test User 2, Test User 3, Test User 4 (+196 more) |  |
| 4 | City |  | Testville |  |
| 5 | State |  | Nowhere |  |
| 6 | Country |  | Testland |  |
| 7 | Remarks |  | '' |  |
| 8 | Call Type |  | Private Call |  |
| 9 | Call Alert |  | '' |  |

### AutoRepeaterOffsetFrequencys (list, LST index 16)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Offset Frequency |  |  |  |

### RoamingChannel (list, LST index 17)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 (+4 more) |  |
| 1 | Receive Frequency | 440.00000 | 446.02500, 446.07500, 446.12500, 446.17500 (+4 more) |  |
| 2 | Transmit Frequency | 439.90000 | 441.02500, 441.07500, 441.12500, 441.17500 (+4 more) |  |
| 3 | Color Code | 0 | 1, 2, 3, 4 (+4 more) |  |
| 4 | Slot | Slot1 | Slot1, Slot2 |  |
| 5 | Name | Roam Channel 1 | Alpha Roam, Bravo Roam, Charlie Roam, Delta Roam (+4 more) |  |

### RoamingZone (list, LST index 18)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2 |  |
| 1 | Name | Roam Zone 1 | Roam All, Roam North |  |
| 2 | Roaming Channel Member | Roam Channel 1 | Alpha Roam/Bravo Roam/Charlie Roam/Delta Roam/Echo Roam/Foxtrot Roam/Golf Roam/Hotel Roam, |  |

### APRS (record, LST index 19)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Manual TX Intervals[s] | 0 | 0 |  |
| 1 | APRS Auto TX Intervals[s] | 0 | 0 |  |
| 2 | Support For Roaming | 0 | 0 |  |
| 3 | Fixed Location Beacon | 1 | 1 |  |
| 4 | LatiDegree | 23 | 45 |  |
| 5 | LatiMinInt | 0 | 0 |  |
| 6 | LatiMinMark | 0 | 0 |  |
| 7 | North And South Latitude | 0 | 0 |  |
| 8 | LongtiDegree | 113 | 100 |  |
| 9 | LongtiMinInt | 0 | 0 |  |
| 10 | LongtiMinMark | 0 | 0 |  |
| 11 | East  And West Things | 0 | 0 |  |
| 12 | channel1 | 0 | 0 |  |
| 13 | slot1 | 0 | 0 |  |
| 14 | Aprs Tg1 | 0 | 0 |  |
| 15 | Call Type1 | 0 | 0 |  |
| 16 | channel2 | 0 | 0 |  |
| 17 | slot2 | 0 | 0 |  |
| 18 | Aprs Tg2 | 0 | 0 |  |
| 19 | Call Type2 | 0 | 0 |  |
| 20 | channel3 | 0 | 0 |  |
| 21 | slot3 | 0 | 0 |  |
| 22 | Aprs Tg3 | 0 | 0 |  |
| 23 | Call Type3 | 0 | 0 |  |
| 24 | channel4 | 0 | 0 |  |
| 25 | slot4 | 0 | 0 |  |
| 26 | Aprs Tg4 | 0 | 0 |  |
| 27 | Call Type4 | 0 | 0 |  |
| 28 | channel5 | 0 | 0 |  |
| 29 | slot5 | 0 | 0 |  |
| 30 | Aprs Tg5 | 0 | 0 |  |
| 31 | Call Type5 | 0 | 0 |  |
| 32 | channel6 | 0 | 0 |  |
| 33 | slot6 | 0 | 0 |  |
| 34 | Aprs Tg6 | 0 | 0 |  |
| 35 | Call Type6 | 0 | 0 |  |
| 36 | channel7 | 0 | 0 |  |
| 37 | slot7 | 0 | 0 |  |
| 38 | Aprs Tg7 | 0 | 0 |  |
| 39 | Call Type7 | 0 | 0 |  |
| 40 | channel8 | 0 | 0 |  |
| 41 | slot8 | 0 | 0 |  |
| 42 | Aprs Tg8 | 0 | 0 |  |
| 43 | Call Type8 | 0 | 0 |  |
| 44 | APRS TG | 1 | 1 |  |
| 45 | Call Type | 0 | 0 |  |
| 46 | Repeater Activation Delay[ms] | 0 | 0 |  |
| 47 | APRS TX Tone | 0 | 0 |  |
| 48 | TOCALL | APAT81 | APAT81 |  |
| 49 | TOCALL SSID | 1 | 0 |  |
| 50 | Your Call Sign | BG6LKT | BG6LKT |  |
| 51 | Your SSID | 0 | 0 |  |
| 52 | APRS Symbol Table | / | / |  |
| 53 | APRS Map Icon | [ | [ |  |
| 54 | APRS Signal Path | WIDE1-1WIDE2-1 | WIDE1-1WIDE2-1 |  |
| 55 | Enter Your Sending Text | APRSCN | APRSCN |  |
| 56 | Transmission Frequency | 145 | 145 |  |
| 57 | Transmit Delay[ms] | 0 | 0 |  |
| 58 | Send Sub Tone | 0 | 0 |  |
| 59 | CTCSS | 0 | 0 |  |
| 60 | DCS | 17 | 17 |  |
| 61 | Prewave Time[ms] | 0 | 0 |  |
| 62 | Transmit Power | 0 | 0 |  |
| 63 | Receive Filter1 | 0 | 0 |  |
| 64 | Call Sign1 |  | '' |  |
| 65 | SSID1 | 0 | 16 |  |
| 66 | Receive Filter2 | 0 | 0 |  |
| 67 | Call Sign2 |  | '' |  |
| 68 | SSID2 | 0 | 16 |  |
| 69 | Receive Filter3 | 0 | 0 |  |
| 70 | Call Sign3 |  | '' |  |
| 71 | SSID3 | 0 | 16 |  |
| 72 | Receive Filter4 | 0 | 0 |  |
| 73 | Call Sign4 |  | '' |  |
| 74 | SSID4 | 0 | 16 |  |
| 75 | Receive Filter5 | 0 | 0 |  |
| 76 | Call Sign5 |  | '' |  |
| 77 | SSID5 | 0 | 16 |  |
| 78 | Receive Filter6 | 0 | 0 |  |
| 79 | Call Sign6 |  | '' |  |
| 80 | SSID6 | 0 | 16 |  |
| 81 | Receive Filter7 | 0 | 0 |  |
| 82 | Call Sign7 |  | '' |  |
| 83 | SSID7 | 0 | 16 |  |
| 84 | Receive Filter8 | 0 | 0 |  |
| 85 | Call Sign8 |  | '' |  |
| 86 | SSID8 | 0 | 16 |  |
| 87 | Receive Filter9 | 0 | 0 |  |
| 88 | Call Sign9 |  | '' |  |
| 89 | SSID9 | 0 | 16 |  |
| 90 | Receive Filter10 | 0 | 0 |  |
| 91 | Call Sign10 |  | '' |  |
| 92 | SSID10 | 0 | 16 |  |
| 93 | Receive Filter11 | 0 | 0 |  |
| 94 | Call Sign11 |  | '' |  |
| 95 | SSID11 | 0 | 16 |  |
| 96 | Receive Filter12 | 0 | 0 |  |
| 97 | Call Sign12 |  | '' |  |
| 98 | SSID12 | 0 | 16 |  |
| 99 | Receive Filter13 | 0 | 0 |  |
| 100 | Call Sign13 |  | '' |  |
| 101 | SSID13 | 0 | 16 |  |
| 102 | Receive Filter14 | 0 | 0 |  |
| 103 | Call Sign14 |  | '' |  |
| 104 | SSID14 | 0 | 16 |  |
| 105 | Receive Filter15 | 0 | 0 |  |
| 106 | Call Sign15 |  | '' |  |
| 107 | SSID15 | 0 | 16 |  |
| 108 | Receive Filter16 | 0 | 0 |  |
| 109 | Call Sign16 |  | '' |  |
| 110 | SSID16 | 0 | 16 |  |
| 111 | Receive Filter17 | 0 | 0 |  |
| 112 | Call Sign17 |  | '' |  |
| 113 | SSID17 | 0 | 16 |  |
| 114 | Receive Filter18 | 0 | 0 |  |
| 115 | Call Sign18 |  | '' |  |
| 116 | SSID18 | 0 | 16 |  |
| 117 | Receive Filter19 | 0 | 0 |  |
| 118 | Call Sign19 |  | '' |  |
| 119 | SSID19 | 0 | 16 |  |
| 120 | Receive Filter20 | 0 | 0 |  |
| 121 | Call Sign20 |  | '' |  |
| 122 | SSID20 | 0 | 16 |  |
| 123 | Receive Filter21 | 0 | 0 |  |
| 124 | Call Sign21 |  | '' |  |
| 125 | SSID21 | 0 | 16 |  |
| 126 | Receive Filter22 | 0 | 0 |  |
| 127 | Call Sign22 |  | '' |  |
| 128 | SSID22 | 0 | 16 |  |
| 129 | Receive Filter23 | 0 | 0 |  |
| 130 | Call Sign23 |  | '' |  |
| 131 | SSID23 | 0 | 16 |  |
| 132 | Receive Filter24 | 0 | 0 |  |
| 133 | Call Sign24 |  | '' |  |
| 134 | SSID24 | 0 | 16 |  |
| 135 | Receive Filter25 | 0 | 0 |  |
| 136 | Call Sign25 |  | '' |  |
| 137 | SSID25 | 0 | 16 |  |
| 138 | Receive Filter26 | 0 | 0 |  |
| 139 | Call Sign26 |  | '' |  |
| 140 | SSID26 | 0 | 16 |  |
| 141 | Receive Filter27 | 0 | 0 |  |
| 142 | Call Sign27 |  | '' |  |
| 143 | SSID27 | 0 | 16 |  |
| 144 | Receive Filter28 | 0 | 0 |  |
| 145 | Call Sign28 |  | '' |  |
| 146 | SSID28 | 0 | 16 |  |
| 147 | Receive Filter29 | 0 | 0 |  |
| 148 | Call Sign29 |  | '' |  |
| 149 | SSID29 | 0 | 16 |  |
| 150 | Receive Filter30 | 0 | 0 |  |
| 151 | Call Sign30 |  | '' |  |
| 152 | SSID30 | 0 | 16 |  |
| 153 | Receive Filter31 | 0 | 0 |  |
| 154 | Call Sign31 |  | '' |  |
| 155 | SSID31 | 0 | 16 |  |
| 156 | Receive Filter32 | 0 | 0 |  |
| 157 | Call Sign32 |  | '' |  |
| 158 | SSID32 | 0 | 16 |  |
| 159 | POSITION | 0 | 0 |  |
| 160 | MIC-E | 0 | 0 |  |
| 161 | OBJECT | 0 | 0 |  |
| 162 | ITEM | 0 | 0 |  |
| 163 | MESSAGE | 0 | 0 |  |
| 164 | WX REPORT | 0 | 0 |  |
| 165 | NMEA REPORT | 0 | 0 |  |
| 166 | STATUS REPORT | 0 | 0 |  |
| 167 | OTHER | 0 | 0 |  |
| 168 | Transmission Frequency0 | 0 | 0 |  |
| 169 | Transmission Frequency1 | 0 | 0 |  |
| 170 | Transmission Frequency2 | 0 | 0 |  |
| 171 | Transmission Frequency3 | 0 | 0 |  |
| 172 | Transmission Frequency4 | 0 | 0 |  |
| 173 | Transmission Frequency5 | 0 | 0 |  |
| 174 | Transmission Frequency6 | 0 | 0 |  |
| 175 | Transmission Frequency7 | 0 | 0 |  |
| 176 | LatiDegree1 | 0 | 0 |  |
| 177 | LatiMinInt1 | 0 | 0 |  |
| 178 | LatiMinMark1 | 0 | 0 |  |
| 179 | North And South Latitude1 | 0 | 0 |  |
| 180 | LongtiDegree1 | 0 | 0 |  |
| 181 | LongtiMinInt1 | 0 | 0 |  |
| 182 | LongtiMinMark1 | 0 | 0 |  |
| 183 | East  And West Things1 | 0 | 0 |  |
| 184 | LatiDegree2 | 0 | 0 |  |
| 185 | LatiMinInt2 | 0 | 0 |  |
| 186 | LatiMinMark2 | 0 | 0 |  |
| 187 | North And South Latitude2 | 0 | 0 |  |
| 188 | LongtiDegree2 | 0 | 0 |  |
| 189 | LongtiMinInt2 | 0 | 0 |  |
| 190 | LongtiMinMark2 | 0 | 0 |  |
| 191 | East  And West Things2 | 0 | 0 |  |
| 192 | LatiDegree3 | 0 | 0 |  |
| 193 | LatiMinInt3 | 0 | 0 |  |
| 194 | LatiMinMark3 | 0 | 0 |  |
| 195 | North And South Latitude3 | 0 | 0 |  |
| 196 | LongtiDegree3 | 0 | 0 |  |
| 197 | LongtiMinInt3 | 0 | 0 |  |
| 198 | LongtiMinMark3 | 0 | 0 |  |
| 199 | East  And West Things3 | 0 | 0 |  |
| 200 | LatiDegree4 | 0 | 0 |  |
| 201 | LatiMinInt4 | 0 | 0 |  |
| 202 | LatiMinMark4 | 0 | 0 |  |
| 203 | North And South Latitude4 | 0 | 0 |  |
| 204 | LongtiDegree4 | 0 | 0 |  |
| 205 | LongtiMinInt4 | 0 | 0 |  |
| 206 | LongtiMinMark4 | 0 | 0 |  |
| 207 | East  And West Things4 | 0 | 0 |  |
| 208 | LatiDegree_21 | 0 | 0 |  |
| 209 | LatiMinInt_21 | 0 | 0 |  |
| 210 | LatiMinMark_21 | 0 | 0 |  |
| 211 | North And South Latitude_21 | 0 | 0 |  |
| 212 | LongtiDegree_21 | 0 | 0 |  |
| 213 | LongtiMinInt_21 | 0 | 0 |  |
| 214 | LongtiMinMark_21 | 0 | 0 |  |
| 215 | East  And West Things_21 | 0 | 0 |  |
| 216 | LatiDegree_22 | 0 | 0 |  |
| 217 | LatiMinInt_22 | 0 | 0 |  |
| 218 | LatiMinMark_22 | 0 | 0 |  |
| 219 | North And South Latitude_22 | 0 | 0 |  |
| 220 | LongtiDegree_22 | 0 | 0 |  |
| 221 | LongtiMinInt_22 | 0 | 0 |  |
| 222 | LongtiMinMark_22 | 0 | 0 |  |
| 223 | East  And West Things_22 | 0 | 0 |  |
| 224 | LatiDegree_23 | 0 | 0 |  |
| 225 | LatiMinInt_23 | 0 | 0 |  |
| 226 | LatiMinMark_23 | 0 | 0 |  |
| 227 | North And South Latitude_23 | 0 | 0 |  |
| 228 | LongtiDegree_23 | 0 | 0 |  |
| 229 | LongtiMinInt_23 | 0 | 0 |  |
| 230 | LongtiMinMark_23 | 0 | 0 |  |
| 231 | East  And West Things_23 | 0 | 0 |  |

### GPSRoaming (list, LST index 20)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | OnOff | 0 | 0 |  |
| 1 | Zone | 0 | 0 |  |
| 2 | Latitude Degree | 0 | 0 |  |
| 3 | North or South | 0 | 0 |  |
| 4 | Longtitude Degree | 0 | 0 |  |
| 5 | East or West | 0 | 0 |  |
| 6 | Latitude Minute | 00.00 | 00.00 |  |
| 7 | Latitude Minute1 | 00.00 | 00.00 |  |
| 8 | Longtitude Minute | 00.00 | 00.00 |  |
| 9 | Longtitude Minute1 | 00.00 | 00.00 |  |
| 10 | Radius(Meter) | 0 | 0 |  |

### OptionalSetting (record, LST index 21)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Beep | 0 | 0 |  .rdt 0x49 |
| 1 | DSP | 0 | 0 |  .rdt 0x4A |
| 2 | KeyLock | 0 | 0 |  .rdt 0x4B |
| 3 | AutoPowerOff | 0 | 0 |  .rdt 0x4C |
| 4 | TOT | 0 | 3 |  .rdt 0x4D |
| 5 | Language | 0 | 0 |  .rdt 0x4E |
| 6 | StartDspSet | 0 | 0 |  .rdt 0x4F |
| 7 | Password | 0 | 0 |  .rdt 0x50 |
| 8 | Step | 0 | 0 |  .rdt 0x51 |
| 9 | SQL1 | 0 | 0 |  .rdt 0x52 |
| 10 | SQL2 | 0 | 0 |  .rdt 0x53 |
| 11 | PowerSave | 0 | 0 |  .rdt 0x54 |
| 12 | VOX | 0 | 0 |  .rdt 0x55 |
| 13 | VOX_Delay | 0 | 0 |  .rdt 0x56 |
| 14 | ScanType | 0 | 0 |  .rdt 0x57 |
| 15 | MicLevel | 0 | 0 |  .rdt 0x58 |
| 16 | RMV1 | 0 | 0 |  .rdt no change |
| 17 | RMV2 | 0 | 0 |  .rdt 0x64 |
| 18 | STE_Type | 0 | 0 |  .rdt 0x65 |
| 19 | STE_Freq | 0 | 0 |  .rdt 0x66 |
| 20 | GroupTalkHold | 0 | 0 |  .rdt 0x67 |
| 21 | PersonTalkHold | 0 | 0 |  .rdt 0x68 |
| 22 | PreWave | 0 | 0 |  .rdt 0x69 |
| 23 | Preamble | 0 | 0 |  .rdt 0x6A |
| 24 | Work_FMCH | 0 | 0 |  .rdt 0x6B |
| 25 | FM_VFO | 0 | 0 |  .rdt 0x6C |
| 26 | Work_Zone1 | 0 | 0 |  .rdt 0x6D |
| 27 | Work_Zone2 | 0 | 0 |  .rdt 0x6E |
| 28 | FM_En | 0 | 0 |  .rdt 0x6F |
| 29 | Record_En | 0 | 0 |  .rdt 0x70 |
| 30 | FailAlarm | 0 | 0 |  .rdt 0x71 |
| 31 | MonType | 0 | 0 |  .rdt 0x72 |
| 32 | Lightness | 0 | 0 |  .rdt 0x73 |
| 33 | AutoBKLightTime | 0 | 0 |  .rdt 0x74 |
| 34 | Gps | 0 | 0 |  .rdt 0x75 |
| 35 | MsgRing | 0 | 0 |  .rdt 0x76 |
| 36 | FreqDis | 0 | 0 |  .rdt 0x77 |
| 37 | FmMon | 0 | 0 |  .rdt 0x78 |
| 38 | MainState | 0 | 0 |  .rdt 0x79 |
| 39 | SubMode | 0 | 0 |  .rdt 0x7A |
| 40 | TBST | 0 | 0 |  .rdt 0x7B |
| 41 | CallRing | 0 | 0 |  .rdt 0x7C |
| 42 | TmZone | 0 | 0 |  .rdt 0x7D |
| 43 | TalkTips | 0 | 0 |  .rdt 0x7E |
| 44 | OverVoice | 0 | 0 |  .rdt 0x7F |
| 45 | VoxHeadset | 0 | 0 |  .rdt 0x80 |
| 46 | Start_Char |  | SYNTH |  |
| 47 | Reserved_Start_Char |  | '' |  .rdt no change |
| 48 | Password_Char |  | '' |  |
| 49 | Reserved_EMG_Kind | 0 | 0 |  .rdt no change |
| 50 | Voice_Note | 0 | 0 |  .rdt 0x83 |
| 51 | SqOnVoice | 0 | 0 |  .rdt 0x84 |
| 52 | IdleWait | 0 | 0 |  .rdt 0x85 |
| 53 | MissCallFilter | 0 | 0 |  .rdt 0x86 |
| 54 | Boot_Sound | 0 | 0 |  .rdt 0x87 |
| 55 | TalkOverPoint | 0 | 0 |  .rdt 0x88 |
| 56 | MaxVol | 0 | 0 |  .rdt 0x89 |
| 57 | DigiStunKillEn | 0 | 0 |  .rdt 0x8A |
| 58 | Reserved_DigiKillEn | 0 | 0 |  .rdt no change |
| 59 | RemoteMoniEn | 0 | 0 |  .rdt 0x8B |
| 60 | GpsReplyEn | 0 | 0 |  .rdt 0x8C |
| 61 | ContactOutSetEn | 0 | 0 |  .rdt 0x8D |
| 62 | Start_Char2 |  | TEST |  |
| 63 | PfLongTime | 0 | 0 |  .rdt 0x8F |
| 64 | VolNoteEn | 0 | 0 |  .rdt 0x90 |
| 65 | AutoRepeater | 0 | 0 |  .rdt 0x91 |
| 66 | DigiMoni | 0 | 0 |  .rdt 0x92 |
| 67 | AprsUpDate | 0 | 0 |  .rdt no change |
| 68 | AprsTxFreq | 0 | 0 |  .rdt no change |
| 69 | ManDownWait | 0 | 0 |  .rdt 0x93 |
| 70 | AnaHoldTime | 0 | 0 |  .rdt 0x94 |
| 71 | DateDisKind | 0 | 0 |  .rdt 0x95 |
| 72 | VfoScanFreq0 | 0 | 0 |  .rdt 0x97, 0x98, 0x99 |
| 73 | VfoScanFreq1 | 0 | 0 |  .rdt 0x9B, 0x9C, 0x9D |
| 74 | VfoScanFreq2 | 0 | 0 |  .rdt 0x9F, 0xA0 |
| 75 | VfoScanFreq3 | 0 | 0 |  .rdt 0xA2, 0xA3, 0xA4, 0xA5 |
| 76 | UhfAutoRep | 0 | 0 |  .rdt 0xA6 |
| 77 | VhfAutoRep | 0 | 0 |  .rdt 0xA7 |
| 78 | CurTalkPathHold | 0 | 0 |  .rdt 0xA8 |
| 79 | PriZoneA | 0 | 0 |  .rdt 0xA9 |
| 80 | PriZoneB | 0 | 0 |  .rdt 0xAA |
| 81 | EnSoundEffect | 0 | 0 |  .rdt 0xAB |
| 82 | MsgOacsuSet | 0 | 0 |  .rdt 0xAC |
| 83 | DigiMoniCc | 0 | 0 |  .rdt 0xAD |
| 84 | DigiMoniId | 0 | 0 |  .rdt 0xAE |
| 85 | LastCallDis | 0 | 0 |  .rdt 0xB0 |
| 86 | EarMaxVol | 0 | 0 |  .rdt 0xB1 |
| 87 | GpsTextUsed | 0 | 0 |  .rdt 0xB2 |
| 88 | RecordDelay | 0 | 0 |  .rdt 0xB3 |
| 89 | CallModeDisKind | 0 | 0 |  .rdt 0xB4 |
| 90 | BlueToothOn | 0 | 1 |  .rdt 0xB5 |
| 91 | MicInBlueTooth | 0 | 1 |  .rdt 0xB6 |
| 92 | SpkInBlueTooth | 0 | 1 |  .rdt 0xB7 |
| 93 | WtRecordNote | 0 | 0 |  .rdt 0xB8 |
| 94 | MeasurePeriod | 0 | 0 |  .rdt 0xB9 |
| 95 | BhtMicGain | 0 | 4 |  .rdt 0xBA |
| 96 | BhtSpkGain | 0 | 2 |  .rdt 0xBB |
| 97 | ChanNumDisKind | 0 | 0 |  .rdt 0xBC |
| 98 | MenuDisWorkContact | 0 | 0 |  .rdt 0xBD |
| 99 | WanderPerod | 0 | 0 |  .rdt 0xBE |
| 100 | Ext_Opt1 | 0 | 0 |  .rdt 0xBF |
| 101 | WanderEffectWait | 0 | 0 |  .rdt 0xC0 |
| 102 | Ext_Opt2 | 0 | 0 |  .rdt 0xC1 |
| 103 | Scan_Pri_Current | 0 | 0 |  .rdt no change |
| 104 | GroupCallS_Ext | 0 | 0 |  .rdt no change |
| 105 | Contact_Compression | 0 | 0 |  .rdt no change |
| 106 | RX_Contact_Compression | 0 | 0 |  .rdt no change |
| 107 | File_Optimization | 0 | 0 |  .rdt no change |
| 108 | AutoRepFreq0 | 136 | 136 |  .rdt 0x548, 0x549, 0x54A |
| 109 | AutoRepFreq1 | 174 | 174 |  .rdt 0x54C, 0x54D, 0x54E |
| 110 | AutoRepFreq2 | 400 | 400 |  .rdt 0x550, 0x551, 0x552 |
| 111 | AutoRepFreq3 | 480 | 480 |  .rdt 0x554, 0x555, 0x556 |
| 112 | AutoRepeaterB | 0 | 0 |  .rdt 0x547 |
| 113 | BookOwnId | 0 | 0 |  .rdt 0x558 |
| 114 | AprsDistanceDis | 0 | 0 |  .rdt 0x559 |
| 115 | StartChUse | 0 | 0 |  .rdt 0x55A |
| 116 | StartZone1 | 0 | 0 |  .rdt 0x55B |
| 117 | StartZone2 | 0 | 0 |  .rdt 0x55C |
| 118 | StartCurChan1 | 0 | 0 |  .rdt 0x55D |
| 119 | StartCurChan2 | 0 | 0 |  .rdt 0x55E |
| 120 | MenuLowPower | 0 | 0 |  .rdt 0x55F |
| 121 | BsModeCheck | 0 | 0 |  .rdt 0x560 |
| 122 | TimeBsCheck | 0 | 0 |  .rdt 0x561 |
| 123 | BsCheckTimes | 0 | 0 |  .rdt 0x562 |
| 124 | FixRomanStartOp | 0 | 0 |  .rdt 0x563 |
| 125 | TxDimWait | 0 | 0 |  .rdt 0x564 |
| 126 | DiviDisEn | 0 | 0 |  .rdt 0x565 |
| 127 | LastHeardChanSet | 0 | 0 |  .rdt 0x566 |
| 128 | ChanNameColour | 0 | 0 |  .rdt 0x567 |
| 129 | OutRepNote | 0 | 0 |  .rdt 0x568 |
| 130 | RxDimWait | 0 | 0 |  .rdt 0x569 |
| 131 | TimeRoamOn | 0 | 0 |  .rdt 0x56A |
| 132 | CurRoamZone | 0 | 0 |  .rdt 0x56B |
| 133 | RoamEffectChanDis | 0 | 0 |  .rdt 0x56C |
| 134 | FixTimeMute | 0 | 0 |  .rdt 0x56D |
| 135 | comVersion | 0 | 0 |  .rdt 0x56E |
| 136 | OutNoteTimes | 0 | 0 |  .rdt 0x56F |
| 137 | StartTestGps | 0 | 0 |  .rdt 0x570 |
| 138 | StartResetEn | 0 | 1 |  .rdt 0x571 |
| 139 | BhtHoldTime | 0 | 33 |  .rdt 0x572 |
| 140 | BhtHoldDelay | 0 | 3 |  .rdt 0x573 |
| 141 | WxAlarmSign | 0 | 0 |  .rdt 0x574 |
| 142 | BhtPttHold | 0 | 1 |  .rdt 0x63 |
| 143 | UhfAutoRep2 | 0 | 0 |  .rdt 0x575 |
| 144 | VhfAutoRep2 | 0 | 0 |  .rdt 0x576 |
| 145 | CurUhfAutoRep | 0 | 0 |  .rdt 0x577 |
| 146 | CurVhfAutoRep | 0 | 0 |  .rdt 0x578 |
| 147 | PttSleepTime | 0 | 1 |  .rdt 0x57A |
| 148 | GpsMode | 0 | 0 |  .rdt 0x57B |
| 149 | SteTime | 0 | 25 |  .rdt 0x57C |
| 150 | CallSignColour | 0 | 0 |  .rdt 0x57D |
| 151 | AutoRepMinFreqV2 | 0 | 0 |  .rdt 0x57E, 0x57F, 0x580 |
| 152 | AutoRepMaxFreqV2 | 0 | 0 |  .rdt 0x582, 0x583, 0x584 |
| 153 | AutoRepMinFreqU2 | 0 | 0 |  .rdt 0x586, 0x587, 0x588 |
| 154 | autoRepMaxFreqU2 | 0 | 0 |  .rdt 0x58A, 0x58B, 0x58C |
| 155 | DialGroupHold | 0 | 0 |  .rdt 0x58E |
| 156 | DialPrivateHold | 0 | 0 |  .rdt 0x58F |
| 157 | ChanNameColourB | 0 | 0 |  .rdt 0x590 |
| 158 | DigiEmgKind | 0 | 1 |  .rdt 0x591 |
| 159 | WorkCharDisColour | 0 | 0 |  .rdt 0x592 |
| 160 | bkpic | 0 | 0 |  .rdt 0x593 |
| 161 | TotPreEn | 0 | 0 |  .rdt 0x594 |
| 162 | TxAgcCon | 0 | 0 |  .rdt 0x595 |
| 163 | ZoneNameColourA | 0 | 0 |  .rdt 0x596 |
| 164 | ZoneNameColourB | 0 | 0 |  .rdt 0x597 |
| 165 | ApoKind | 0 | 0 |  .rdt 0x598 |
| 166 | SmsFormat | 0 | 0 |  .rdt 0x599 |
| 167 | ChanDisCtr | 0 | 0 |  .rdt 0x59A |
| 168 | AnaSqOnVoice | 0 | 0 |  .rdt 0x59B |
| 169 | DateDisFormat | 0 | 0 |  .rdt 0x59C |
| 170 | AnaMic | 0 | 0 |  .rdt 0x59D |
| 171 | ZoneBarsEn | 0 | 0 |  .rdt 0x59E |
| 172 | VcallRpheader | 0 | 0 |  .rdt 0x59F |
| 173 | DcsSte | 0 | 0 |  .rdt 0x5A0 |
| 174 | TxNr | 0 | 0 |  .rdt 0x5A1 |
| 175 | RxNr | 0 | 0 |  .rdt 0x5A2 |
| 176 | Drc | 0 | 0 |  .rdt 0x5A3 |
| 177 | DmrRasEn | 0 | 0 |  .rdt 0x5A4 |
| 178 | NightMode | 0 | 0 |  .rdt 0x5A5 |
| 179 | SateLocalKind | 0 | 0 |  .rdt 0x5A8 |
| 180 | SateTxPower | 0 | 0 |  .rdt 0x5A9 |
| 181 | SateAnaSql | 0 | 0 |  .rdt 0x5AA |
| 182 | SateAosLimit | 0 | 0 |  .rdt 0x5AB |
| 183 | NlightStartHour | 0 | 0 |  .rdt 0x5AC |
| 184 | NlightStartMin | 0 | 0 |  .rdt 0x5AD |
| 185 | NlightEndHour | 0 | 0 |  .rdt 0x5AE |
| 186 | NlightEndMin | 0 | 0 |  .rdt 0x5AF |
| 187 | SateFixPointName1 |  | '' |  |
| 188 | SateFixPointName2 |  | '' |  |
| 189 | SateFixPointName3 |  | '' |  |
| 190 | SateFixPointName4 |  | '' |  |
| 191 | SateFixPointName5 |  | '' |  |
| 192 | SateFixPointName6 |  | '' |  |
| 193 | SateFixPointName7 |  | '' |  |
| 194 | SateFixPointName8 |  | '' |  |

### AlertTone (record, LST index 22)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Freq11 | 1000 | 1000 |  |
| 1 | Time11 | 100 | 100 |  |
| 2 | Freq12 | 0 | 0 |  |
| 3 | Time12 | 100 | 100 |  |
| 4 | Freq13 | 1000 | 1000 |  |
| 5 | Time13 | 100 | 100 |  |
| 6 | Freq14 | 0 | 0 |  |
| 7 | Time14 | 100 | 100 |  |
| 8 | Freq15 | 1000 | 1000 |  |
| 9 | Time15 | 100 | 100 |  |
| 10 | Freq21 | 2000 | 2000 |  |
| 11 | Time21 | 100 | 100 |  |
| 12 | Freq22 | 0 | 0 |  |
| 13 | Time22 | 100 | 100 |  |
| 14 | Freq23 | 2000 | 2000 |  |
| 15 | Time23 | 100 | 100 |  |
| 16 | Freq24 | 0 | 0 |  |
| 17 | Time24 | 100 | 100 |  |
| 18 | Freq25 | 2000 | 2000 |  |
| 19 | Time25 | 100 | 100 |  |
| 20 | Freq31 | 3000 | 3000 |  |
| 21 | Time31 | 100 | 100 |  |
| 22 | Freq32 | 0 | 0 |  |
| 23 | Time32 | 100 | 100 |  |
| 24 | Freq33 | 3000 | 3000 |  |
| 25 | Time33 | 100 | 100 |  |
| 26 | Freq34 | 0 | 0 |  |
| 27 | Time34 | 100 | 100 |  |
| 28 | Freq35 | 3000 | 3000 |  |
| 29 | Time35 | 100 | 100 |  |
| 30 | Freq41 | 0 | 0 |  |
| 31 | Time41 | 0 | 0 |  |
| 32 | Freq42 | 0 | 0 |  |
| 33 | Time42 | 0 | 0 |  |
| 34 | Freq43 | 0 | 0 |  |
| 35 | Time43 | 0 | 0 |  |
| 36 | Freq44 | 0 | 0 |  |
| 37 | Time44 | 0 | 0 |  |
| 38 | Freq45 | 0 | 0 |  |
| 39 | Time45 | 0 | 0 |  |
| 40 | Freq51 | 0 | 0 |  |
| 41 | Time51 | 0 | 0 |  |
| 42 | Freq52 | 0 | 0 |  |
| 43 | Time52 | 0 | 0 |  |
| 44 | Freq53 | 0 | 0 |  |
| 45 | Time53 | 0 | 0 |  |
| 46 | Freq54 | 0 | 0 |  |
| 47 | Time54 | 0 | 0 |  |
| 48 | Freq55 | 0 | 0 |  |
| 49 | Time55 | 0 | 0 |  |

### QDC1200EnCodeTable (list, LST index 23)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Call Type |  |  |  |
| 2 | Private Call ID |  |  |  |
| 3 | Group Call ID |  |  |  |
| 4 | Type |  |  |  |
| 5 | Need To Answer |  |  |  |
| 6 | Name |  |  |  |

### QDC1200DECodeTable (record, LST index 24)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Auto Reset Time[s] | 0 | 0 |  |
| 1 | Self ID - Private Call | 0 | 0 |  |
| 2 | Self ID - Group Call | 0 | 0 |  |
| 3 | Remote Listening Duration[S] | 0 | 0 |  |
| 4 | Remotely Kill Allow | 0 | 0 |  |
| 5 | Remotely Moniton Allow | 0 | 0 |  |
| 6 | PttId Lock Time[S] | 0 | 0 |  |

### QDC1200AddressBook (list, LST index 25)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Call Type |  |  |  |
| 2 | Private ID |  |  |  |
| 3 | Group ID |  |  |  |
| 4 | Type |  |  |  |
| 5 | Ack |  |  |  |
| 6 | Name |  |  |  |

### AESEncryptionCode (list, LST index 26)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | id |  |  |  |
| 1 | num |  |  |  |
| 2 | aeskey |  |  |  |

### ARC4EncryptionCode (list, LST index 27)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | id |  |  |  |
| 1 | aeskey |  |  |  |

