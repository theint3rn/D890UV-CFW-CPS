# Stock D890UV CPS (V1.05) map

What the stock AnyTone D890UV CPS shows and stores, as found by running it under Wine (scratch prefix, COM ports pointed
at `/dev/null`, no radio attached, nothing written to a radio). The cfw CPS (desktop, web, binaries) uses this as its
stock model: `schema/stock_d890uv.json` is generated from the same sources by `tools/make_stock_schema.py`.

Sources:
1. **Screenshots** of the main window, tree, menus and all Optional Setting tabs (not shipped).
2. **Tool > Export > Export All** of a new codeplug (factory defaults) and of a real codeplug: 38 CSV tables. Their
   columns are the stock data model, in the stock order.
3. **.rdt layout**: for each column, a CSV with only that value changed is imported (Tool > Import > Import From File List)
   and saved; the byte diff against the reference save gives the offset (`tools/stock_rdt_experiments.md`).
   Offsets are positions in the 23 627-byte reference file (`schema/rdt_map.json`, `_ref_len`). How to read them:
   * OptionalSetting: header segments A (< 0x81), B (0x8A-0x94), C (0x9D-0xFA), the same in every file.
   * Channel: the first channel record starts at 0xEF (48 fixed bytes, the name cstr, a 50-byte tail starting at
     0x129 in the reference because its name is "Channel 1"). 0xC8 is the file's channel count/flags byte and
     changes on every channel edit. Columns that show only 0xC8 did not change the record for a digital channel.
   * NXSetting: in the undecoded tail. The TxAliasName cstr ends 483 bytes before the end of the file; fields after it
     sit at a fixed distance from the end of the file, fields before it at a fixed distance from the alias. The cfw
     reader/writer finds the block this way (`cps/rdt.py` nx_row / nx_patch). This is checked against a file the stock
     CPS saved itself (`nx_stock_v1323.rdt`, not shipped).
   * The header u32 at offset 5 is the file length - 14 (all stock-saved files); the stock D168 CPS refuses a file where it is wrong ("file error"), the D890 CPS was not tried.
     cfw writes it (fixed 2026-11-21; before, an .rdt whose length changed kept the old value).
   * Columns marked "no change" were accepted by the import but changed no byte; for example `*_nop` columns, or a
     value the import ignores for this channel type.

Limits (honest list):
* The dialog combo boxes are windowless VB6 controls; their option lists could not be enumerated automatically. The
  CSV holds the raw value (mostly the 0-based option index); the label and the current value are in the screenshots.
  The cfw CPS shows these fields with the stock label and the raw CSV value.
* Key Function assignments (PF1..P2 short/long), Alarm Setting and Local Information are not in the stock CSV export
  ("Optional Setting - Excluding Key Function"). They live only in the .rdt and are kept byte for byte by the cfw .rdt
  reader/writer, but are not editable in the cfw CPS yet.
* The stock channel editor dialog runs out of memory (VB6 "Run-time error 7") with a 142 332-entry user database
  loaded; channel fields were mapped from the CSV columns instead.

Files made by the stock CPS (its screenshots, its new-file `.rdt` templates, its saves and exports of real codeplugs) are not shipped with cfw_cps; the tests that use them skip without them (README "Stock CPS files"). Example values below come from the synthetic test codeplug (`tools/make_synth.py`).

## Main window

| Menu | Items |
|---|---|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As, Exit |
| Model | Model Information |
| Set | Set COM, Set Initialization |
| Program | Read From Radio, Write To Radio |
| Tool | Radio Recording, APRS Information Manager, Import, Export, Mode, eXtended, Firmware and Icon Update, Boot Image, Default Channel Information, Options, Standby BK Picture1, Standby BK Picture2, Zone Hide Operation, Channel Talker Alias Operation, export Data Conversion File, Satellite Data Updating |
| View | Toolbar, Status Bar, Quick Help |
| Help | About D890UV |

Toolbar: New, Open, Save, Read, Write, (Import/Export), Help. Status bar + "Quick Help" pane (context help text).

The cfw CPS keeps File / Program (Read, Write) / Tool (Import, Export, Validate, Diff) / Print and the same tree. It
has **no** firmware / icon / boot image update, satellite update or radio recording functions (codeplug only).

### Tree (left) -> stock CSV table -> cfw


| Section | Node | Stock table (CSV) | Rows (test codeplug) | cfw |
|---|---|---|---|---|
| Common Settings | Channel | Channel | 179 | channels |
| Common Settings | Zone | DMRZone | 12 | zones |
| Common Settings | Scan List | ScanList | 6 | scan lists |
| Common Settings | AM Air | AMAir | 2 | used by cfw |
| Common Settings | AM Zone | AMZone | 0 | used by cfw |
| Common Settings | Pre-defined SMS | PrefabricatedSMS | 5 | used by cfw |
| Common Settings | FM | FM | 12 | used by cfw |
| Common Settings | Auto Repeater Offset Frequencies | AutoRepeaterOffsetFrequencys | 0 | used by cfw |
| Common Settings | Device Information | (dialog, .rdt only) |  | used by cfw |
| Common Settings | Optional Settings | OptionalSetting | 1 | partly used by cfw (133 of 199 keys stored, not used yet) |
| Common Settings | Bluetooth (cfw) | OptionalSetting (10 keys) | | cfw page, partly used by cfw (7 of 10 keys stored, not used yet) |
| Common Settings | Alarm Setting | (dialog, .rdt only) |  | partly used by cfw (3 of 23 keys stored, not used yet) |
| Common Settings | Hot Key | HotKey_HotKey | 18 | used by cfw |
| Common Settings | APRS | APRS | 1 | partly used by cfw (157 of 176 keys stored, not used yet) |
| Common Settings | GPS Roaming | GPSRoaming | 32 | used by cfw |
| DMR | Master ID | (dialog, .rdt only) |  | Radio Settings |
| DMR | Radio ID List | RadioIDList | 1 | used by cfw |
| DMR | Contact/Talk Group | DMRTalkGroups | 22 | contacts |
| DMR | Roaming Channel | RoamingChannel | 8 | used by cfw |
| DMR | Roaming Zone | RoamingZone | 2 | used by cfw |
| DMR | Receive Group Call List | DMRReceiveGroupCallList | 3 | TG lists |
| DMR | Encryption Code | EncryptionCode | 32 | used by cfw |
| DMR | ARC4 Encryption Code | ARC4EncryptionCode | 0 | used by cfw |
| DMR | AES Encryption Code | AESEncryptionCode | 0 | used by cfw |
| DMR | Digital Contact List | DMRDigitalContactList | 200 | used by cfw |
| DMR | Friends List | (dialog, .rdt only) |  | used by cfw |
| DMR | Talk Alias / AIR Alias | (dialog, .rdt only) |  | used by cfw |
| DMR | Talk Group Whitelist (Repeater) | TalkGroupWhitelist(Repeater) | 0 | stored, not used by cfw yet |
| DMR | Digital Contact Whitelist (Repeater) | DigitalContactWhitelist(Repeater) | 0 | stored, not used by cfw yet |
| NXDN | NX Setting | NXSetting | 1 | partly used by cfw (40 of 43 keys stored, not used yet) |
| NXDN | NX Talk Group | NXTalkGroup | 0 | used by cfw |
| NXDN | NX Receive Group Call List | NXReceiveGroupCallList | 0 | stored, not used by cfw yet |
| NXDN | NX Encryption Code | NXEncryptionCode | 32 | used by cfw |
| NXDN | NX State Message | NXStateMSG | 50 | stored, not used by cfw yet |
| NXDN | NX Digital Contact List | NXDigitalContactList | 0 | used by cfw |
| Analog | Analog Address Book | AnalogAddressBook | 0 | used by cfw |
| Analog | 5Tone Encode | 5ToneEncode | 0 | used by cfw |
| Analog | 5Tone Information Codes | T5InfoCodes | 0 | used by cfw |
| Analog | 5Tone Settings | T5Setting | 0 | partly used by cfw (5 of 19 keys stored, not used yet) |
| Analog | 2Tone Encode | 2ToneEncode | 0 | used by cfw |
| Analog | 2Tone Settings | T2Setting | 0 | partly used by cfw (2 of 6 keys stored, not used yet) |
| Analog | DTMF Encode | DTMFEncode | 0 | used by cfw |
| Analog | DTMF Settings | DTMFSetting | 0 | partly used by cfw (6 of 17 keys stored, not used yet) |
| Analog | MDC1200 Address Book | MDC1200AddressBook | 0 | used by cfw |
| Analog | MDC1200 Encode | MDC1200Encode | 0 | used by cfw |
| Analog | Alert Tone | AlertTone | 1 | used by cfw |
| Analog | Hot Key Quick Call | HotKey_QuickCall | 4 | used by cfw |
| Analog | Hot Key State | HotKey_State | 0 | stored, not used by cfw yet |

cfw column: schema/cfw_support.json (tools/make_cfw_support.py). Hidden on this radio (n/a): Encryption Code (dialog), Local Information, QDC Address Book, QDC1200 Decode, QDC1200 Setting.

cfw adds: Tier III Systems (DMR), Type-C/Type-D Systems (NXDN), and a *cfw Digital Modes* section (Radio Settings, Trunk Systems with P25 band plans, Encryption Keys, D-STAR Repeaters, D-STAR / YSF / registration settings).

## Optional Setting dialog

17 tabs + Alert Tone1 (tone table, CSV AlertTone). Value = stock CSV value (default of a new codeplug); Test = value in the synthetic test codeplug; .rdt = byte offset in a V1323 .rdt (one byte unless noted).

### Work Mode

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Display mode | `FreqDis` | 0 | 0 | 0x77 |
| MEM Zone(A) | `Work_Zone1` | 0 | 0 | 0x6D |
| MEM Zone(B) | `Work_Zone2` | 0 | 0 | 0x6E |
| Main Channel Set | `MainState` | 0 | 0 | 0x79 |
| Sub-Channel Mode | `SubMode` | 0 | 0 | 0x7A |
| choose working mode | `RepMode` | 0 | 0 | no effect |

### Vox/BT

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| VOX On/Off | `VOX` | 0 | 0 | 0x55 |
| VOX Delay | `VOX_Delay` | 0 | 0 | 0x56 |
| VOX Detection | `VoxHeadset` | 0 | 0 | 0x80 |
| Bluetooth | `BlueToothOn` | 0 | 1 | 0xB5 |
| Mic in Bluetooth | `MicInBlueTooth` | 0 | 1 | 0xB6 |
| Speaker in Bluetooth | `SpkInBlueTooth` | 0 | 1 | 0xB7 |
| BT Mic Gain | `BhtMicGain` | 0 | 4 | 0xBA |
| BT Speaker Gain | `BhtSpkGain` | 0 | 2 | 0xBB |
| BT Hold Time | `BhtHoldTime` | 10 | 33 | 0x63 |
| BT Hold Delay | `BhtHoldDelay` | 2 | 3 | 0x5CF |
| BT PTT Hold | `BhtPttHold` | 0 | 1 | 0x5D1 |
| BT NR Before | `BtNrBefore` | 0 | 0 | 0x60D |
| BT NR After | `BtNrAfter` | 0 | 0 | 0x60E |

### STE

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| STE Type Of CTCSS | `STE_Type` | 0 | 0 | 0x65 |
| STE When No Signal | `STE_Freq` | 0 | 0 | 0x66 |
| Ste Time | `SteTime` | 25 | 25 | 0x5D9 |
| DCS STE | `DcsSte` | 0 | 0 | 0x602 |

### AM/FM

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| AM/FM Function | `FM_En` | 0 | 0 | 0x6F |
| FM VFO/MEM | `FM_VFO` | 0 | 0 | 0x6C |
| FM Work Channel | `Work_FMCH` | 0 | 0 | 0x6B |
| FM Monitor | `FmMon` | 0 | 0 | 0x78 |
| AM VFO/MEM | `AmChanVfo` | 0 | 0 | 0x609 |
| AM Work Zone | `CurAmChan` | 0 | 0 | 0x60A |
| AM Offset | `AmOffset` | 0 | 0 | 0x60B |
| Am SqlLevel | `AmSqLevel` | 0 | 0 | 0x60C |

### Power Save

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Auto Shutdown | `AutoPowerOff` | 0 | 0 | 0x4C |
| Power save | `PowerSave` | 0 | 0 | 0x54 |
| Auto Shutdown Type | `ApoKind` | 0 | 0 | 0x5F5 |
| PTT Sleep Time | `PttSleepTime` | 1 | 1 | 0x5D7 |

### Key Function

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Key Lock | `KeyLock` | 0 | 0 | 0x4B |
| Long Key Time[s] | `PfLongTime` | 0 | 0 | 0x8F |

### Other

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Address Book Is Sent With Its Own Code | `ContactOutSetEn` | 0 | 0 | 0x8D |
| TOT | `TOT` | 0 | 3 | 0x4D |
| Language | `Language` | 0 | 0 | 0x4E |
| Frequency Step | `Step` | 0 | 0 | 0x51 |
| SQL Level(A) | `SQL1` | 0 | 0 | 0x52 |
| SQL Level(B) | `SQL2` | 0 | 0 | 0x53 |
| TBST | `TBST` | 0 | 0 | 0x7B |
| Analog Call Hold Time[s] | `AnaHoldTime` | 0 | 0 | 0x94 |
| call channel is maintained | `CurTalkPathHold` | 0 | 0 | 0xA8 |
| Priority Zone A | `PriZoneA` | 0 | 0 | 0xA9 |
| Priority Zone B | `PriZoneB` | 0 | 0 | 0xAA |
| Mute timing | `FixTimeMute` | 0 | 0 | 0x5CA |
| TOT Predict | `TotPreEn` | 0 | 0 | 0x5F1 |
| TxPow Agc | `TxAgcCon` | 0 | 0 | 0x5F2 |
| NOAA Alert | `WxAlarmSign` | 0 | 0 | 0x5D0 |
| NOAA Channel | `CurWxChan` | 0 | 0 | 0x608 |

### Digital Func

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Group Call Hold Time | `GroupTalkHold` | 0 | 0 | 0x67 |
| Private Call Hold Time | `PersonTalkHold` | 0 | 0 | 0x68 |
| Manual Dial - Group TG Hold Time | `DialGroupHold` | 0 | 0 | 0x5EB |
| Manual Dial - Private TG Hold Time | `DialPrivateHold` | 0 | 0 | 0x5EC |
| Voice header repetitions | `Preamble` | 0 | 0 | 0x6A |
| TX preamble duration | `PreWave` | 0 | 0 | 0x69 |
| Filter Own ID In MissCall | `MissCallFilter` | 0 | 0 | 0x86 |
| Digital Remote Kill | `DigiStunKillEn` | 0 | 0 | 0x8A |
| Digital Monitor | `DigiMoni` | 0 | 0 | 0x92 |
| Digital Monitor CC | `DigiMoniCc` | 0 | 0 | 0xAD |
| Digital Monitor ID | `DigiMoniId` | 0 | 0 | 0xAE |
| Monitor Slot Hold | `Scan_Pri_Current` | 0 | 0 | no effect |
| Remote Monitor | `RemoteMoniEn` | 0 | 0 | 0x8B |
| SMS Format | `SmsFormat` | 0 | 0 | 0x5F6 |
| Digital Protocol | `DigiProtocal` | 0 | 0 | 0x613 |
| Reset Digital Protocol | `ResetDigiProtocal` | 0 | 0 | 0x615 |
| Digital Emergency Type | `DigiEmgKind` | 1 | 1 | 0x5EE |
| DMR RAS | `DmrRasEn` | 0 | 0 | 0x604 |
| Voice Call Repeat Header | `VcallRpheader` | 0 | 0 | 0x5FC |

### Satellite

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Sate Location | `SateLocalKind` | 0 | 0 | 0x60F |
| Sate TX Power | `SateTxPower` | 0 | 0 | 0x610 |
| Sate ANA Sql | `SateAnaSql` | 0 | 0 | 0x611 |
| Sate Aos Limit | `SateAosLimit` | 0 | 0 | 0x612 |

### Power-on

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Power-on Interface | `StartDspSet` | 0 | 0 | 0x4F |
| Power-on Display (line 1) | `Start_Char` |  | SYNTH |  |
| Power-on Display (line 2) | `Start_Char2` |  | TEST |  |
| Power-on Password | `Password` | 0 | 0 | 0x50 |
| Power-on Password Char | `Password_Char` |  |  |  |
| Default Startup Channel | `StartChUse` | 0 | 0 | 0x5B7 |
| Startup Zone A | `StartZone1` | 0 | 0 | 0x5B8 |
| Startup Channel A | `StartCurChan1` | 0 | 0 | 0x5BA |
| Startup Zone B | `StartZone2` | 0 | 0 | 0x5B9 |
| Startup Channel B | `StartCurChan2` | 0 | 0 | 0x5BB |
| Startup GPS test | `StartTestGps` | 0 | 0 | 0x5CD |
| Startup Reset | `StartResetEn` | 1 | 1 | 0x5CE |

### Alert Tone

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| SMS Alert | `MsgRing` | 0 | 0 | 0x76 |
| Call Alert | `CallRing` | 0 | 0 | 0x7C |
| Digi Call ResetTone | `OverVoice` | 0 | 0 | 0x7F |
| Talk Permit | `TalkTips` | 0 | 0 | 0x7E |
| Key Tone | `Beep` | 0 | 0 | 0x49 |
| Digi Idle Channel Tone | `SqOnVoice` | 0 | 0 | 0x84 |
| Startup Sound | `Boot_Sound` | 0 | 0 | 0x87 |
| Ana Idle Channel Tone | `AnaSqOnVoice` | 0 | 0 | 0x5F8 |

### Display

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Brightness | `Lightness` | 0 | 0 | 0x73 |
| Auto Backlight Duration | `AutoBKLightTime` | 0 | 0 | 0x74 |
| Backlight Delay Of TX[s] | `TxDimWait` | 0 | 0 | 0x5C1 |
| Menu Exit Time[s] | `MenuLowPower` | 0 | 0 | 0x5BC |
| Time Display | `DateDisKind` | 0 | 0 | 0x95 |
| Last Caller | `LastCallDis` | 0 | 0 | 0xB0 |
| Call Display Mode | `CallModeDisKind` | 0 | 0 | 0xB4 |
| Call Sign Display Color | `CallSignColour` | 0 | 0 | 0x5DA |
| Call End Prompt Box | `IdleWait` | 0 | 0 | 0x85 |
| Display Channel Number | `ChanNumDisKind` | 0 | 0 | 0xBC |
| Display Current Contact | `MenuDisWorkContact` | 0 | 0 | 0xBD |
| Standby Char Color | `WorkCharDisColour` | 0 | 0 | 0x5EF |
| Standby BK Picture | `bkpic` | 0 | 0 | 0x5F0 |
| Show Last Call On Launch | `GpsTextUsed` | 0 | 0 | 0xB2 |
| Separate display | `DiviDisEn` | 0 | 0 | 0x5C2 |
| CH Switching Keeps Last Caller | `LastHeardChanSet` | 0 | 0 | 0x5C3 |
| A Channel Name Color | `ChanNameColour` | 0 | 0 | 0x5C4 |
| Receive Backlight Delay[s] | `RxDimWait` | 0 | 0 | 0x5C6 |
| B Channel Name Color | `ChanNameColourB` | 0 | 0 | 0x5ED |
| Zone Name Colour A | `ZoneNameColourA` | 0 | 0 | 0x5F3 |
| Zone Name Colour B | `ZoneNameColourB` | 0 | 0 | 0x5F4 |
| Display Channel Type | `ChanDisCtr` | 0 | 0 | 0x5F7 |
| Date Display Format | `DateDisFormat` | 0 | 0 | 0x5F9 |
| Volume Bar | `ZoneBarsEn` | 0 | 0 | 0x5FB |
| Night Mode | `NightMode` | 0 | 0 | 0x607 |

### GPS/Ranging

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Get GPS Positioning | `Gps` | 0 | 0 | 0x75 |
| Time Zone | `TmZone` | 0 | 0 | 0x7D |
| Gps Mode | `GpsMode` | 0 | 0 | 0x5D8 |
| GPS Reply | `GpsReplyEn` | 0 | 0 | 0x8C |
| Ranging Period | `MeasurePeriod` | 0 | 0 | 0xB9 |
| APRS Distance Display | `AprsDistanceDis` | 0 | 0 | 0x5B6 |

### VFO Scan

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| VFO Scan Type | `ScanType` | 0 | 0 | 0x57 |
| VFO Scan Start Freq(UHF) | `VfoScanFreq0` | 0 | 0 | 0x96, 0x97, 0x98 |
| VFO Scan End Freq(UHF) | `VfoScanFreq1` | 0 | 0 | 0x9A, 0x9B, 0x9C |
| VFO Scan Start Freq(VHF) | `VfoScanFreq2` | 0 | 0 | 0x9E, 0x9F, 0xA0 |
| VFO Scan End Freq(VHF) | `VfoScanFreq3` | 0 | 0 | 0xA2, 0xA3, 0xA4 |

### Auto repeater

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Auto Repeater A | `AutoRepeater` | 0 | 0 | 0x91 |
| Auto Repeater B | `AutoRepeaterB` | 0 | 0 | 0x5A4 |
| Auto Repeater1(UHF) | `UhfAutoRep` | 0 | 0 | 0xA6 |
| Auto Repeater1(VHF) | `VhfAutoRep` | 0 | 0 | 0xA7 |
| Auto Repeater2(UHF) | `UhfAutoRep2` | 0 | 0 | 0x5D2 |
| Auto Repeater2(VHF) | `VhfAutoRep2` | 0 | 0 | 0x5D3 |
| Repeater Check | `BsModeCheck` | 0 | 0 | 0x5BD |
| Repeater Check Interval[s] | `TimeBsCheck` | 0 | 0 | 0x5BE |
| Repeater Check Reconnections | `BsCheckTimes` | 0 | 0 | 0x5BF |
| Repeater Out of Range Notify | `OutRepNote` | 0 | 0 | 0x5C5 |
| Out of Range Notify(times) | `OutNoteTimes` | 0 | 0 | 0x5CC |
| Auto Roaming | `TimeRoamOn` | 0 | 0 | 0x5C7 |
| Auto Roaming start condition | `FixRomanStartOp` | 0 | 0 | 0x5C0 |
| Auto Roaming at Fixed Time[m] | `WanderPerod` | 0 | 0 | 0xBE |
| Roaming Effect Wait Time[s] | `WanderEffectWait` | 0 | 0 | 0xC0 |
| Roaming Zone | `CurRoamZone` | 0 | 0 | 0x5C8 |
| Min Freq Of Auto Repeater1(VHF) | `AutoRepFreq0` | 136 | 136 | 0x5A5, 0x5A6, 0x5A7 |
| Max Freq Of Auto Repeater1(VHF) | `AutoRepFreq1` | 174 | 174 | 0x5A9, 0x5AA, 0x5AB |
| Min Freq Of Auto Repeater1(UHF) | `AutoRepFreq2` | 400 | 400 | 0x5AD, 0x5AE, 0x5AF |
| Max Freq Of Auto Repeater1(UHF) | `AutoRepFreq3` | 480 | 480 | 0x5B1, 0x5B2, 0x5B3 |
| Min Freq Of Auto Repeater2(VHF) | `AutoRepMinFreqV2` | 0 | 0 | 0x5DB, 0x5DC, 0x5DD |
| Max Freq Of Auto Repeater2(VHF) | `AutoRepMaxFreqV2` | 0 | 0 | 0x5DF, 0x5E0, 0x5E1 |
| Min Freq Of Auto Repeater2(UHF) | `AutoRepMinFreqU2` | 0 | 0 | 0x5E3, 0x5E4, 0x5E5 |
| Max Freq Of Auto Repeater2(UHF) | `autoRepMaxFreqU2` | 0 | 0 | 0x5E7, 0x5E8, 0x5E9 |
| Rep Cc Limit | `RepCcLimit` | 0 | 0 | 0x5FE |
| Rep Slot PathA | `RepSlotPathA` | 0 | 0 | 0x5FF |
| Rep Slot PathB | `RepSlotPathB` | 0 | 0 | 0x600 |
| Current UHF Auto Repeater | `CurUhfAutoRep` | 0 | 0 | 0x5D4 |
| Current VHF Auto Repeater | `CurVhfAutoRep` | 0 | 0 | 0x5D5 |

### Record

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Record Function | `Record_En` | 0 | 0 | 0x70 |
| Record Delay | `RecordDelay` | 0 | 0 | 0xB3 |
| Record Note | `WtRecordNote` | 0 | 0 | 0xB8 |

### Volume/Audio

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| Maximum Volume | `MaxVol` | 0 | 0 | 0x89 |
| Power On Volume Type | `VolType` | 0 | 0 | 0x616 |
| Power On Volume | `MinVolData` | 0 | 0 | no effect |
| Max Headphone Volume | `EarMaxVol` | 0 | 0 | 0xB1 |
| DMR Mic Gain | `MicLevel` | 0 | 0 | 0x58 |
| Enhanced Sound Quality | `EnSoundEffect` | 0 | 0 | 0xAB |
| Ana Mic Gain | `AnaMic` | 0 | 0 | 0x5FA |
| DRC Dynamic Ranagle Control(Rx AGC) | `Drc` | 0 | 0 | 0x603 |
| NX Mic Gain | `NxdnMic` | 0 | 0 | 0x614 |
| RX Noise Reduction | `RxNr` | 0 | 0 | 0x605 |
| TX Noise Reduction | `TxNr` | 0 | 0 | 0x606 |
| Sub SpkInTx | `TalkOverPoint` | 0 | 0 | 0x88 |

### More (CSV only)

| Label (stock GUI) | CSV key | Default | Test | .rdt |
|---|---|---|---|---|
| (CSV only) | `DSP` | 0 | 0 | 0x4A |
| (CSV only) | `RMV1` | 0 | 0 | no effect |
| (CSV only) | `RMV2` | 0 | 0 | 0x64 |
| (CSV only) | `FailAlarm` | 0 | 0 | 0x71 |
| (CSV only) | `MonType` | 0 | 0 | 0x72 |
| (CSV only) | `Reserved_Start_Char` |  |  | no effect |
| (CSV only) | `Reserved_EMG_Kind` | 0 | 0 | no effect |
| (CSV only) | `Voice_Note` | 0 | 0 | 0x83 |
| (CSV only) | `Reserved_DigiKillEn` | 0 | 0 | no effect |
| (CSV only) | `VolNoteEn` | 0 | 0 | 0x90 |
| (CSV only) | `AprsUpDate` | 0 | 0 | no effect |
| (CSV only) | `AprsTxFreq` | 0 | 0 | no effect |
| (CSV only) | `ManDownWait` | 0 | 0 | 0x93 |
| (CSV only) | `MsgOacsuSet` | 0 | 0 | 0xAC |
| (CSV only) | `Ext_Opt1` | 0 | 0 | 0xBF |
| (CSV only) | `Ext_Opt2` | 0 | 0 | 0xC1 |
| (CSV only) | `GroupCallS_Ext` | 0 | 0 | no effect |
| (CSV only) | `Contact_Compression` | 0 | 0 | no effect |
| (CSV only) | `RX_Contact_Compression` | 0 | 0 | no effect |
| (CSV only) | `File_Optimization` | 0 | 0 | no effect |
| (CSV only) | `BookOwnId` | 0 | 0 | 0x5B5 |
| (CSV only) | `RoamEffectChanDis` | 0 | 0 | 0x5C9 |
| (CSV only) | `comVersion` | 0 | 0 | 0x5CB |

Key Function tab (not in CSV, .rdt only): Key Lock, PF1/PF2/PF3/P1/P2 Short Key, PF1/PF2/PF3/P1/P2 Long Key, Long Key Time, Knob Lock, Keyboard Lock, Side Key Lock, Forced Lock Key (screenshot opt_05).

## Bluetooth (cfw page)

The stock D890UV CPS lists the BT keys only in the CSV (Vox/BT tab, no dialog fields). The cfw CPS shows them on a Bluetooth page (Common Settings > Bluetooth): `BlueToothOn`, `MicInBlueTooth`, `SpkInBlueTooth`, `BhtMicGain`, `BhtSpkGain`, `BhtHoldTime`, `BhtHoldDelay`, `BhtPttHold`, `BtNrBefore`, `BtNrAfter`. Values are the stock CSV values (the D890UV radio's BT value lists are not checked).

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
| 20 | QDC1200 Private ID | C+0x51 hex4 | 0000 |  |
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
| 7 | Auto Reset Time (D890UV: s, D168UV: 0.1 s) | A+0x38 u8 | 10 |  |
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
| 4 | Auto Reset Time (D890UV: s, D168UV: 0.1 s) | A+0x46 u8 | 10 |  |
| 5 | Side Tone | A+0x47 u8 | 0 | 0 Off, 1 On |

### 5Tone Settings (table 67, record)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | Self ID | H t5_self hstr |  |  |
| 1 | Decode Standard | A+0x19 u8 | 0 |  |
| 2 | Decoding Response | A+0x18 u8 | 0 | 0 None, 1 Beep Tone, 2 Beep Tone & Respond |
| 4 | Decode Time (x 10 ms) | A+0x26 u8 | 2 |  |
| 5 | 5TONE Dec Units (bit mask, bit 0 = unit 1) | A+0x2C u8 | 0 |  |
| 6 | Disp AnyID | A+0x2D u8 | 0 | 0 Off, 1 On |
| 7 | Pretime (x 10 ms) | A+0x1D u8 | 20 |  |
| 8 | Time-Lapse After Encode (x 10 ms) | A+0x1E u8 | 20 |  |
| 9 | PTT ID Pause Time [s] (0 = Off) | A+0x1F u8 | 10 |  |
| 10 | Auto Reset Time [s] | A+0x20 u8 | 10 |  |
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
| 1 | Alias Display Priority | E 22059 u8 | 0 | 0 Off, 1 Contact Alias, 2 Air Alias DMR/NX |
| 2 | Alias Data Format | E 22058 u8 | 0 | 0 ISO 8, 1 ISO 7, 2 Unicode |

### Friends List (table 71, list)

| # | Field | Where | Default | Values |
|---|---|---|---|---|
| 0 | No. | list |  |  |
| 1 | DMR ID | list |  |  |

Not decoded: Alarm Setting > Analog > Emergency ID (list content depends on the signalling tables); Alarm Setting > ENI Type list texts (the value is stored raw); 5Tone Setting: Stop Code, Stop Time (header bytes 0x23-0x25 are not tied to one field); the Function Name of an information code (the string after the ID is kept as it is); 2Tone Setting > Decode tab; DTMF Setting > Special Call; Encode ID tables (CSV); Alarm Setting > QDC1200 Group ID: the stock D890UV CPS shows the bytes at C+0x56 but saves to C+0x4F, so it does not survive its own save (the frame is greyed out there); Local Information: the stock CPS opens the COM port for it; it is live radio data, not in the .rdt.

## Tables (stock CSV columns, in order)

### Channel (list, LST index 0)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2, 3, 4 (+175 more) | cfw field |
| 1 | Channel Name | Channel 1 | Simplex 1, Simplex 2, Simplex 3, Simplex 4 (+175 more) | cfw field |
| 2 | Receive Frequency | 440.00000 | 446.02500, 446.07500, 446.12500, 446.17500 (+98 more) | cfw field .rdt 0xC8, 0xF1, 0xF2, 0xF3, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9 |
| 3 | Transmit Frequency | 440.00000 | 441.02500, 441.07500, 441.12500, 441.17500 (+102 more) | cfw field .rdt 0xC8, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9 |
| 4 | Channel Type | D-Digital | D-Digital, A-Analog | cfw field .rdt 0xC8, 0xFA |
| 5 | Transmit Power | High | Middle, High, Low, Turbo | cfw field .rdt 0xC8, 0xFB |
| 6 | Band Width | 12.5K | 12.5K, 25K | cfw field .rdt 0xC8, 0xFC |
| 7 | CTCSS/DCS Decode | Off | Off, 88.5, 103.5, 110.9 (+3 more) | cfw field .rdt 0xC8, 0x101, 0x102 |
| 8 | CTCSS/DCS Encode | Off | Off, 67.0, 88.5, 100.0 (+9 more) | cfw field .rdt 0xC8, 0x105, 0x106 |
| 9 | Contact/Talk Group | Contact 1 | Contact 1, World, Local, Region (+8 more) | cfw field .rdt 0xC8 |
| 10 | Contact/Talk Group Call Type | Group Call | Group Call, Private Call | cfw field .rdt 0xC8 |
| 11 | Contact/Talk Group TG/DMR ID | 1 | 1, 91, 2, 9 (+12 more) | cfw field .rdt 0xC8 |
| 12 | Radio ID |  | '' | used by cfw .rdt 0xC8 |
| 13 | Busy Lock/TX Permit | Always | Always, Off, Channel Free | used by cfw .rdt 0xC8 |
| 14 | Squelch Mode | Carrier | Carrier, CTCSS/DCS | used by cfw .rdt 0xC8 |
| 15 | Optional Signal | Off | Off, DTMF | used by cfw .rdt 0x110 |
| 16 | DTMF ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 17 | 2Tone ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 18 | 5Tone ID | 1 | 1 | used by cfw .rdt 0xC8 |
| 19 | PTT ID | Off | Off | used by cfw .rdt 0xC8 |
| 20 | RX Color Code | 1 | 1, 0, 2, 3 (+5 more) | cfw field .rdt 0xC8, 0x117 |
| 21 | Slot | 1 | 1, 2 | cfw field .rdt 0xC8, 0x118 |
| 22 | Scan List | None | None, FM Simplex, FM Rpt | cfw field .rdt 0xC8 |
| 23 | Receive Group List | None | None, Local+Region, Wide, Nets | cfw field .rdt 0xC8 |
| 24 | PTT Prohibit | Off | Off | used by cfw .rdt 0xC8 |
| 25 | Reverse | Off | Off | used by cfw .rdt 0xFE |
| 26 | Digital Duplex | Off | Off | stored .rdt 0xC8 |
| 27 | Slot Suit | Off | Off | stored .rdt 0xC8 |
| 28 | AES Digital Encryption | Normal Encryption | Normal Encryption | used by cfw .rdt 0xC8 |
| 29 | Digital Encryption | Off | Off | used by cfw .rdt 0x11E |
| 30 | Call Confirmation | Off | Off | stored .rdt 0xC8 |
| 31 | Talk Around(Simplex) | Off | Off, On | cfw field .rdt 0x100 |
| 32 | Work Alone | Off | Off | used by cfw .rdt 0xC8 |
| 33 | Custom CTCSS | 251.1 | 251.1, 0.0 | stored .rdt 0xC8, 0x109, 0x10A |
| 34 | 2TONE Decode | 0 | 0, 1 | used by cfw .rdt 0xC8 |
| 35 | Ranging | Off | Off | stored .rdt 0x129 |
| 36 | Idle TX | Off | Off | stored .rdt 0xC8 |
| 37 | APRS RX | Off | Off | stored .rdt 0xC8 |
| 38 | Analog APRS PTT Mode | Off | Off | used by cfw .rdt 0xC8 |
| 39 | Digital APRS PTT Mode | Off | Off | stored .rdt 0xC8 |
| 40 | APRS Report Type | Off | Off | used by cfw .rdt 0xC8 |
| 41 | Digital APRS Report Channel | 1 | 1 | stored .rdt 0x12F |
| 42 | Correct Frequency[Hz] | 0 | 0 | used by cfw .rdt 0xC8 |
| 43 | SMS Confirmation | Off | Off | stored .rdt 0xC8 |
| 44 | Exclude channel from roaming | 0 | 0 | used by cfw .rdt 0xC8, 0x134 |
| 45 | DMR MODE | 0 | 0 | used by cfw .rdt 0xC8, 0x12B, 0x135 |
| 46 | DataACK Disable | 0 | 0 | stored .rdt 0xC8, 0x13A |
| 47 | R5toneBot | 0 | 0 | used by cfw .rdt 0xC8, 0x13B |
| 48 | R5ToneEot | 0 | 0 | used by cfw .rdt 0xC8, 0x13C |
| 49 | Auto Scan | 0 | 0 | used by cfw .rdt 0xC8, 0x13D |
| 50 | Ana APRS Mute | 0 | 0 | stored .rdt 0xC8, 0x13E |
| 51 | Send Talker Alias DMR/NX | 0 | 0 | used by cfw .rdt 0xC8, 0x13F |
| 52 | AnaAprsTxPath | 0 | 0 | stored .rdt 0xC8, 0x141 |
| 53 | ARC4 | 0 | 0 | used by cfw .rdt 0xC8, 0x142 |
| 54 | ex_emg_kind | 0 | 0 | stored .rdt 0xC8, 0x143 |
| 55 | Rpga_Mdc | 0 | 0 | used by cfw .rdt 0xC8, 0x144 |
| 56 | DisturEn | 0 | 0 | stored .rdt 0xC8, 0x145 |
| 57 | DisturFreq | 0 | 0 | stored .rdt 0xC8, 0x146 |
| 58 | dmr_crc_ignore | 0 | 0 | stored .rdt 0xC8, 0x147 |
| 59 | compand | 0 | 0 | stored .rdt 0xC8, 0x148 |
| 60 | tx_talkalaes | 0 | 0 | stored .rdt 0xC8, 0x14D |
| 61 | dup_call | 0 | 0 | stored .rdt 0xC8, 0x149 |
| 62 | tx_int | 0 | 0 | stored .rdt 0xC8, 0x14A |
| 63 | BtRxState | 0 | 0 | stored .rdt 0xC8, 0x14B |
| 64 | idle_tx | 0 | 0 | stored .rdt 0xC8, 0x14C |
| 65 | nxdn_wn | 0 | 0 | stored .rdt 0xC8, 0x14E |
| 66 | NxdnRpga | 0 | 0 | stored .rdt 0xC8, 0x14F |
| 67 | nxdnSqCon | 0 | 0 | stored .rdt 0xC8, 0x150 |
| 68 | NxdnTxBusy | 0 | 0 | stored .rdt 0xC8, 0x151 |
| 69 | NxDnPttId | 0 | 0 | stored .rdt 0xC8, 0x152 |
| 70 | EnRan | 0 | 0 | stored .rdt 0xC8, 0x153 |
| 71 | DeRan | 0 | 0 | stored .rdt 0xC8, 0x154 |
| 72 | NxdnEncry | 0 | 0 | used by cfw .rdt 0xC8, 0x155 |
| 73 | NxdnGroupId | 0 | 0 | stored .rdt 0xC8, 0x156 |
| 74 | NxdnIdNum | 0 | 0 | stored .rdt 0xC8, 0x157 |
| 75 | NxdnStateNum | 0 | 0 | stored .rdt 0xC8, 0x159 |
| 76 | txcc | 1 | 1 | stored .rdt 0xC8, 0x15A |

### RadioIDList (list, LST index 1)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1 |  |
| 1 | Radio ID |  | 9990001 |  |
| 2 | Name |  | N0CALL |  |

### DMRZone (list, LST index 2)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+8 more) | cfw field |
| 1 | Zone Name |  | FM Simplex, FM Repeaters, Site Alpha, Site Bravo (+8 more) | cfw field |
| 2 | Zone Channel Member |  | Simplex 1/Simplex 2/Simplex 3/Simplex 4/Simplex 5/Simplex 6/Simplex 7/Simplex 8/Simplex 9/ | cfw field |
| 3 | Zone Channel Member RX Frequency |  | 146.52000/146.53500/146.55000/146.56500/146.58000/146.59500/146.61000/146.62500/146.64000/ | cfw field |
| 4 | Zone Channel Member TX Frequency |  | 146.52000/146.53500/146.55000/146.56500/146.58000/146.59500/146.61000/146.62500/146.64000/ | cfw field |
| 5 | A Channel |  | '' |  |
| 6 | A Channel RX Frequency |  | '' |  |
| 7 | A Channel TX Frequency |  | '' |  |
| 8 | B Channel |  | '' |  |
| 9 | B Channel RX Frequency |  | '' |  |
| 10 | B Channel TX Frequency |  | '' |  |
| 11 | Zone Hide  |  | '' |  |

### ScanList (list, LST index 3)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3, 4 (+2 more) | cfw field |
| 1 | Scan List Name |  | FM Simplex, FM Rpt, Site Alpha, Site Bravo (+2 more) | cfw field |
| 2 | Scan Channel Member |  | Simplex 1/Simplex 2/Simplex 3/Simplex 4/Simplex 5/Simplex 6/Simplex 7/Simplex 8/Simplex 9/ | cfw field |
| 3 | Scan Channel Member RX Frequency |  | 146.52000/146.53500/146.55000/146.56500/146.58000/146.59500/146.61000/146.62500/146.64000/ | cfw field |
| 4 | Scan Channel Member TX Frequency |  | 146.52000/146.53500/146.55000/146.56500/146.58000/146.59500/146.61000/146.62500/146.64000/ | cfw field |
| 5 | Scan Mode |  | '' |  |
| 6 | Priority Channel Select |  | '' |  |
| 7 | Priority Channel 1 |  | '' |  |
| 8 | Priority Channel 1 RX Frequency |  | '' |  |
| 9 | Priority Channel 1 TX Frequency |  | '' |  |
| 10 | Priority Channel 2 |  | '' |  |
| 11 | Priority Channel 2 RX Frequency |  | '' |  |
| 12 | Priority Channel 2 TX Frequency |  | '' |  |
| 13 | Revert Channel |  | '' |  |
| 14 | Look Back Time A[s] |  | '' |  |
| 15 | Look Back Time B[s] |  | '' |  |
| 16 | Dropout Delay Time[s] |  | '' |  |
| 17 | Dwell Time[s] |  | '' |  |

### AnalogAddressBook (list, LST index 4)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Number |  |  |  |
| 2 | Name |  |  |  |

### DMRTalkGroups (list, LST index 5)

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
| 3 | Name | FM-001 | '', FM-001, FM-003, FM-005 (+3 more) |  |

### DMRReceiveGroupCallList (list, LST index 8)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  | 1, 2, 3 | cfw field |
| 1 | Group Name |  | Local+Region, Wide, Nets | cfw field |
| 2 | Contact |  | Local/Region, Region/World/Test TG 3100, Net A/Net B/Net C | cfw field |
| 3 | Contact TG/DMR ID |  | 2/9, 9/91/3100, 31001/31002/31003 | cfw field |

### 5ToneEncode (list, LST index 9)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | NO. |  |  |  |
| 1 | Encode ID |  |  |  |
| 2 | Encode/Decode Standard |  |  |  |
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
| 6 | Call Object TG/DMR ID | Group Call | Group Call |  |
| 7 | Digi Call Type |  | '' |  |
| 8 | Content | Off | Off |  |

### DMRDigitalContactList (list, LST index 15) - file only (too big for the radio)

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
| 5 | Name | Roaming CH 1 | Alpha Roam, Bravo Roam, Charlie Roam, Delta Roam (+4 more) |  |

### RoamingZone (list, LST index 18)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 2 |  |
| 1 | Name | Roam Zone 1 | Roam All, Roam North |  |
| 2 | Roaming Channel Member | Roaming CH 1 | Alpha Roam/Bravo Roam/Charlie Roam/Delta Roam/Echo Roam/Foxtrot Roam/Golf Roam/Hotel Roam, |  |

### APRS (record, LST index 19)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Manual TX Interval[s] | 0 | 120 |  |
| 1 | APRS Auto TX Interval[s] | 0 | 0 |  |
| 2 | Support For Roaming | 0 | 0 |  |
| 3 | Fixed Location Beacon | 0 | 1 |  |
| 4 | LatiDegree | 23 | 45 |  |
| 5 | LatiMinInt | 0 | 0 |  |
| 6 | LatiMinMark | 0 | 0 |  |
| 7 | North or South | 0 | 0 |  |
| 8 | LongtiDegree | 113 | 100 |  |
| 9 | LongtiMinInt | 0 | 0 |  |
| 10 | LongtiMinMark | 0 | 0 |  |
| 11 | East or West Hemisphere | 0 | 0 |  |
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
| 49 | TOCALL SSID | 0 | 0 |  |
| 50 | Your Call Sign | BG6LKT | BG6LKT |  |
| 51 | Your SSID | 0 | 0 |  |
| 52 | APRS Symbol Table | / | / |  |
| 53 | APRS Map Icon | [ | [ |  |
| 54 | Digipeater Path | WIDE1-1,WIDE2-1 | WIDE1-1,WIDE2-1 |  |
| 55 | Enter Your Sending Text | APRSCN | APRSCN |  |
| 56 | Transmission Frequency [MHz] | 145 | 145 |  |
| 57 | Transmit Delay[ms] | 0 | 0 |  |
| 58 | Send Sub Tone | 0 | 0 |  |
| 59 | CTCSS | 0 | 0 |  |
| 60 | DCS | 17 | 17 |  |
| 61 | Prewave Time[ms] | 0 | 0 |  |
| 62 | Transmit Power | 0 | 0 |  |
| 63 | Receive Filter1 | 0 | 0 |  |
| 64 | Call Sign1 |  | '' |  |
| 65 | SSID1 | 16 | 16 |  |
| 66 | Receive Filter2 | 0 | 0 |  |
| 67 | Call Sign2 |  | '' |  |
| 68 | SSID2 | 16 | 16 |  |
| 69 | Receive Filter3 | 0 | 0 |  |
| 70 | Call Sign3 |  | '' |  |
| 71 | SSID3 | 16 | 16 |  |
| 72 | Receive Filter4 | 0 | 0 |  |
| 73 | Call Sign4 |  | '' |  |
| 74 | SSID4 | 16 | 16 |  |
| 75 | Receive Filter5 | 0 | 0 |  |
| 76 | Call Sign5 |  | '' |  |
| 77 | SSID5 | 16 | 16 |  |
| 78 | Receive Filter6 | 0 | 0 |  |
| 79 | Call Sign6 |  | '' |  |
| 80 | SSID6 | 16 | 16 |  |
| 81 | Receive Filter7 | 0 | 0 |  |
| 82 | Call Sign7 |  | '' |  |
| 83 | SSID7 | 16 | 16 |  |
| 84 | Receive Filter8 | 0 | 0 |  |
| 85 | Call Sign8 |  | '' |  |
| 86 | SSID8 | 16 | 16 |  |
| 87 | Receive Filter9 | 0 | 0 |  |
| 88 | Call Sign9 |  | '' |  |
| 89 | SSID9 | 16 | 16 |  |
| 90 | Receive Filter10 | 0 | 0 |  |
| 91 | Call Sign10 |  | '' |  |
| 92 | SSID10 | 16 | 16 |  |
| 93 | Receive Filter11 | 0 | 0 |  |
| 94 | Call Sign11 |  | '' |  |
| 95 | SSID11 | 16 | 16 |  |
| 96 | Receive Filter12 | 0 | 0 |  |
| 97 | Call Sign12 |  | '' |  |
| 98 | SSID12 | 16 | 16 |  |
| 99 | Receive Filter13 | 0 | 0 |  |
| 100 | Call Sign13 |  | '' |  |
| 101 | SSID13 | 16 | 16 |  |
| 102 | Receive Filter14 | 0 | 0 |  |
| 103 | Call Sign14 |  | '' |  |
| 104 | SSID14 | 16 | 16 |  |
| 105 | Receive Filter15 | 0 | 0 |  |
| 106 | Call Sign15 |  | '' |  |
| 107 | SSID15 | 16 | 16 |  |
| 108 | Receive Filter16 | 0 | 0 |  |
| 109 | Call Sign16 |  | '' |  |
| 110 | SSID16 | 16 | 16 |  |
| 111 | Receive Filter17 | 0 | 0 |  |
| 112 | Call Sign17 |  | '' |  |
| 113 | SSID17 | 16 | 16 |  |
| 114 | Receive Filter18 | 0 | 0 |  |
| 115 | Call Sign18 |  | '' |  |
| 116 | SSID18 | 16 | 16 |  |
| 117 | Receive Filter19 | 0 | 0 |  |
| 118 | Call Sign19 |  | '' |  |
| 119 | SSID19 | 16 | 16 |  |
| 120 | Receive Filter20 | 0 | 0 |  |
| 121 | Call Sign20 |  | '' |  |
| 122 | SSID20 | 16 | 16 |  |
| 123 | Receive Filter21 | 0 | 0 |  |
| 124 | Call Sign21 |  | '' |  |
| 125 | SSID21 | 16 | 16 |  |
| 126 | Receive Filter22 | 0 | 0 |  |
| 127 | Call Sign22 |  | '' |  |
| 128 | SSID22 | 16 | 16 |  |
| 129 | Receive Filter23 | 0 | 0 |  |
| 130 | Call Sign23 |  | '' |  |
| 131 | SSID23 | 16 | 16 |  |
| 132 | Receive Filter24 | 0 | 0 |  |
| 133 | Call Sign24 |  | '' |  |
| 134 | SSID24 | 16 | 16 |  |
| 135 | Receive Filter25 | 0 | 0 |  |
| 136 | Call Sign25 |  | '' |  |
| 137 | SSID25 | 16 | 16 |  |
| 138 | Receive Filter26 | 0 | 0 |  |
| 139 | Call Sign26 |  | '' |  |
| 140 | SSID26 | 16 | 16 |  |
| 141 | Receive Filter27 | 0 | 0 |  |
| 142 | Call Sign27 |  | '' |  |
| 143 | SSID27 | 16 | 16 |  |
| 144 | Receive Filter28 | 0 | 0 |  |
| 145 | Call Sign28 |  | '' |  |
| 146 | SSID28 | 16 | 16 |  |
| 147 | Receive Filter29 | 0 | 0 |  |
| 148 | Call Sign29 |  | '' |  |
| 149 | SSID29 | 16 | 16 |  |
| 150 | Receive Filter30 | 0 | 0 |  |
| 151 | Call Sign30 |  | '' |  |
| 152 | SSID30 | 16 | 16 |  |
| 153 | Receive Filter31 | 0 | 0 |  |
| 154 | Call Sign31 |  | '' |  |
| 155 | SSID31 | 16 | 16 |  |
| 156 | Receive Filter32 | 0 | 0 |  |
| 157 | Call Sign32 |  | '' |  |
| 158 | SSID32 | 16 | 16 |  |
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

### GPSRoaming (list, LST index 20)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | OnOff | 0 | 0 |  |
| 1 | Zone | 255 | 255 |  |
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
| 72 | VfoScanFreq0 | 0 | 0 |  .rdt 0x96, 0x97, 0x98 |
| 73 | VfoScanFreq1 | 0 | 0 |  .rdt 0x9A, 0x9B, 0x9C |
| 74 | VfoScanFreq2 | 0 | 0 |  .rdt 0x9E, 0x9F, 0xA0 |
| 75 | VfoScanFreq3 | 0 | 0 |  .rdt 0xA2, 0xA3, 0xA4 |
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
| 108 | AutoRepFreq0 | 136 | 136 |  .rdt 0x5A5, 0x5A6, 0x5A7 |
| 109 | AutoRepFreq1 | 174 | 174 |  .rdt 0x5A9, 0x5AA, 0x5AB |
| 110 | AutoRepFreq2 | 400 | 400 |  .rdt 0x5AD, 0x5AE, 0x5AF |
| 111 | AutoRepFreq3 | 480 | 480 |  .rdt 0x5B1, 0x5B2, 0x5B3 |
| 112 | AutoRepeaterB | 0 | 0 |  .rdt 0x5A4 |
| 113 | BookOwnId | 0 | 0 |  .rdt 0x5B5 |
| 114 | AprsDistanceDis | 0 | 0 |  .rdt 0x5B6 |
| 115 | StartChUse | 0 | 0 |  .rdt 0x5B7 |
| 116 | StartZone1 | 0 | 0 |  .rdt 0x5B8 |
| 117 | StartZone2 | 0 | 0 |  .rdt 0x5B9 |
| 118 | StartCurChan1 | 0 | 0 |  .rdt 0x5BA |
| 119 | StartCurChan2 | 0 | 0 |  .rdt 0x5BB |
| 120 | MenuLowPower | 0 | 0 |  .rdt 0x5BC |
| 121 | BsModeCheck | 0 | 0 |  .rdt 0x5BD |
| 122 | TimeBsCheck | 0 | 0 |  .rdt 0x5BE |
| 123 | BsCheckTimes | 0 | 0 |  .rdt 0x5BF |
| 124 | FixRomanStartOp | 0 | 0 |  .rdt 0x5C0 |
| 125 | TxDimWait | 0 | 0 |  .rdt 0x5C1 |
| 126 | DiviDisEn | 0 | 0 |  .rdt 0x5C2 |
| 127 | LastHeardChanSet | 0 | 0 |  .rdt 0x5C3 |
| 128 | ChanNameColour | 0 | 0 |  .rdt 0x5C4 |
| 129 | OutRepNote | 0 | 0 |  .rdt 0x5C5 |
| 130 | RxDimWait | 0 | 0 |  .rdt 0x5C6 |
| 131 | TimeRoamOn | 0 | 0 |  .rdt 0x5C7 |
| 132 | CurRoamZone | 0 | 0 |  .rdt 0x5C8 |
| 133 | RoamEffectChanDis | 0 | 0 |  .rdt 0x5C9 |
| 134 | FixTimeMute | 0 | 0 |  .rdt 0x5CA |
| 135 | comVersion | 0 | 0 |  .rdt 0x5CB |
| 136 | OutNoteTimes | 0 | 0 |  .rdt 0x5CC |
| 137 | StartTestGps | 0 | 0 |  .rdt 0x5CD |
| 138 | StartResetEn | 1 | 1 |  .rdt 0x5CE |
| 139 | BhtHoldTime | 10 | 33 |  .rdt 0x63 |
| 140 | BhtHoldDelay | 2 | 3 |  .rdt 0x5CF |
| 141 | WxAlarmSign | 0 | 0 |  .rdt 0x5D0 |
| 142 | BhtPttHold | 0 | 1 |  .rdt 0x5D1 |
| 143 | UhfAutoRep2 | 0 | 0 |  .rdt 0x5D2 |
| 144 | VhfAutoRep2 | 0 | 0 |  .rdt 0x5D3 |
| 145 | CurUhfAutoRep | 0 | 0 |  .rdt 0x5D4 |
| 146 | CurVhfAutoRep | 0 | 0 |  .rdt 0x5D5 |
| 147 | PttSleepTime | 1 | 1 |  .rdt 0x5D7 |
| 148 | GpsMode | 0 | 0 |  .rdt 0x5D8 |
| 149 | SteTime | 25 | 25 |  .rdt 0x5D9 |
| 150 | CallSignColour | 0 | 0 |  .rdt 0x5DA |
| 151 | AutoRepMinFreqV2 | 0 | 0 |  .rdt 0x5DB, 0x5DC, 0x5DD |
| 152 | AutoRepMaxFreqV2 | 0 | 0 |  .rdt 0x5DF, 0x5E0, 0x5E1 |
| 153 | AutoRepMinFreqU2 | 0 | 0 |  .rdt 0x5E3, 0x5E4, 0x5E5 |
| 154 | autoRepMaxFreqU2 | 0 | 0 |  .rdt 0x5E7, 0x5E8, 0x5E9 |
| 155 | DialGroupHold | 0 | 0 |  .rdt 0x5EB |
| 156 | DialPrivateHold | 0 | 0 |  .rdt 0x5EC |
| 157 | ChanNameColourB | 0 | 0 |  .rdt 0x5ED |
| 158 | DigiEmgKind | 1 | 1 |  .rdt 0x5EE |
| 159 | WorkCharDisColour | 0 | 0 |  .rdt 0x5EF |
| 160 | bkpic | 0 | 0 |  .rdt 0x5F0 |
| 161 | TotPreEn | 0 | 0 |  .rdt 0x5F1 |
| 162 | TxAgcCon | 0 | 0 |  .rdt 0x5F2 |
| 163 | ZoneNameColourA | 0 | 0 |  .rdt 0x5F3 |
| 164 | ZoneNameColourB | 0 | 0 |  .rdt 0x5F4 |
| 165 | ApoKind | 0 | 0 |  .rdt 0x5F5 |
| 166 | SmsFormat | 0 | 0 |  .rdt 0x5F6 |
| 167 | ChanDisCtr | 0 | 0 |  .rdt 0x5F7 |
| 168 | AnaSqOnVoice | 0 | 0 |  .rdt 0x5F8 |
| 169 | DateDisFormat | 0 | 0 |  .rdt 0x5F9 |
| 170 | AnaMic | 0 | 0 |  .rdt 0x5FA |
| 171 | ZoneBarsEn | 0 | 0 |  .rdt 0x5FB |
| 172 | VcallRpheader | 0 | 0 |  .rdt 0x5FC |
| 173 | RepMode | 0 | 0 |  .rdt no change |
| 174 | RepCcLimit | 0 | 0 |  .rdt 0x5FE |
| 175 | RepSlotPathA | 0 | 0 |  .rdt 0x5FF |
| 176 | RepSlotPathB | 0 | 0 |  .rdt 0x600 |
| 177 | DcsSte | 0 | 0 |  .rdt 0x602 |
| 178 | Drc | 0 | 0 |  .rdt 0x603 |
| 179 | DmrRasEn | 0 | 0 |  .rdt 0x604 |
| 180 | RxNr | 0 | 0 |  .rdt 0x605 |
| 181 | TxNr | 0 | 0 |  .rdt 0x606 |
| 182 | NightMode | 0 | 0 |  .rdt 0x607 |
| 183 | CurWxChan | 0 | 0 |  .rdt 0x608 |
| 184 | AmChanVfo | 0 | 0 |  .rdt 0x609 |
| 185 | CurAmChan | 0 | 0 |  .rdt 0x60A |
| 186 | AmOffset | 0 | 0 |  .rdt 0x60B |
| 187 | AmSqLevel | 0 | 0 |  .rdt 0x60C |
| 188 | BtNrBefore | 0 | 0 |  .rdt 0x60D |
| 189 | BtNrAfter | 0 | 0 |  .rdt 0x60E |
| 190 | SateLocalKind | 0 | 0 |  .rdt 0x60F |
| 191 | SateTxPower | 0 | 0 |  .rdt 0x610 |
| 192 | SateAnaSql | 0 | 0 |  .rdt 0x611 |
| 193 | SateAosLimit | 0 | 0 |  .rdt 0x612 |
| 194 | DigiProtocal | 0 | 0 |  .rdt 0x613 |
| 195 | NxdnMic | 0 | 0 |  .rdt 0x614 |
| 196 | ResetDigiProtocal | 0 | 0 |  .rdt 0x615 |
| 197 | VolType | 0 | 0 |  .rdt 0x616 |
| 198 | MinVolData | 0 | 0 |  .rdt no change |

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
| 30 | Freq41 | 3000 | 3000 |  |
| 31 | Time41 | 100 | 100 |  |
| 32 | Freq42 | 0 | 0 |  |
| 33 | Time42 | 100 | 100 |  |
| 34 | Freq43 | 3000 | 3000 |  |
| 35 | Time43 | 100 | 100 |  |
| 36 | Freq44 | 0 | 0 |  |
| 37 | Time44 | 100 | 100 |  |
| 38 | Freq45 | 3000 | 3000 |  |
| 39 | Time45 | 100 | 100 |  |
| 40 | Freq51 | 3000 | 3000 |  |
| 41 | Time51 | 100 | 100 |  |
| 42 | Freq52 | 0 | 0 |  |
| 43 | Time52 | 100 | 100 |  |
| 44 | Freq53 | 3000 | 3000 |  |
| 45 | Time53 | 100 | 100 |  |
| 46 | Freq54 | 0 | 0 |  |
| 47 | Time54 | 100 | 100 |  |
| 48 | Freq55 | 3000 | 3000 |  |
| 49 | Time55 | 100 | 100 |  |

### NXEncryptionCode (list, LST index 23)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Valid | 0 | 0 |  |
| 1 | EMGCode | 0 | 0 |  |
| 2 | KeyId | 1 | 1, 2, 3, 4 (+28 more) |  |

### NXStateMSG (list, LST index 24)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Valid | 0 | 0 |  |
| 1 | StateNum | 0 | 0 |  |
| 2 | TxForbid | 0 | 0 |  |
| 3 | Name |                  |                  |  |
| 4 | Beep | 0 | 0 |  |

### NXReceiveGroupCallList (list, LST index 25)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Group Name |  |  |  |
| 2 | Contact |  |  |  |
| 3 | Contact TG/DMR ID |  |  |  |

### NXTalkGroup (list, LST index 26)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | RADIO_ID |  |  |  |
| 1 | CALLSIGN |  |  |  |
| 2 | FIRST_NAME |  |  |  |
| 3 | LAST_NAME |  |  |  |
| 4 | CITY |  |  |  |
| 5 | STATE |  |  |  |
| 6 | COUNTRY |  |  |  |
| 7 | Attr |  |  |  |
| 8 | TxForbid |  |  |  |
| 9 | Ring |  |  |  |

### AMAir (list, LST index 27)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. | 1 | 1, 257 |  |
| 1 | Frequency[MHz] | 108.0000 | 108.0000 |  |
| 2 | Name | AM-001           | AM-001          , VFO              |  |

### AESEncryptionCode (list, LST index 28)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | id |  |  |  |
| 1 | num |  |  |  |
| 2 | aeskey |  |  |  |

### ARC4EncryptionCode (list, LST index 29)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | id |  |  |  |
| 1 | aeskey |  |  |  |

### AMZone (list, LST index 30)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No. |  |  |  |
| 1 | Zone Name |  |  |  |
| 2 | Zone Channel Member |  |  |  |
| 3 | A Channel |  |  |  |
| 4 | Scan Channel  |  |  |  |

### NXDigitalContactList (list, LST index 31) - file only (too big for the radio)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | RADIO_ID |  |  |  |
| 1 | CALLSIGN |  |  |  |
| 2 | FIRST_NAME |  |  |  |
| 3 | LAST_NAME |  |  |  |
| 4 | CITY |  |  |  |
| 5 | STATE |  |  |  |
| 6 | COUNTRY |  |  |  |
| 7 | Attr |  |  |  |
| 8 | TxForbid |  |  |  |
| 9 | Ring |  |  |  |

### TalkGroupWhitelist(Repeater) (list, LST index 32)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Code |  |  |  |
| 1 | Call Type |  |  |  |

### DigitalContactWhitelist(Repeater) (list, LST index 33)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | Code |  |  |  |

### NXSetting (record, LST index 34)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | OwnId | 1 | 1 |  .rdt 0x5A5E |
| 1 | StationId  | 1 | 1 |  .rdt 0x5A60 |
| 2 | StationType | 0 | 0 |  .rdt 0x5A62 |
| 3 | OwnIdAbleMin | 1 | 1 |  .rdt 0x5A63 |
| 4 | OwnIdAbleMax | 1 | 1 |  .rdt 0x5A65 |
| 5 | TxAliasEn | 0 | 0 |  .rdt 0x5A67 |
| 6 | TxAliasName |  | '' |  |
| 7 | NxdnRemoteAck | 0 | 0 |  .rdt 0x5A69 |
| 8 | SecondCallBeep | 0 | 0 |  .rdt 0x5A6A |
| 9 | BeppInGroupCall | 0 | 0 |  .rdt 0x5A6B |
| 10 | GroupInPriCall | 0 | 0 |  .rdt 0x5A6C |
| 11 | ReTryTimes | 0 | 0 |  .rdt 0x5A6D |
| 12 | TxBusyWait | 0 | 0 |  .rdt 0x5A6E |
| 13 | DataAckWait | 0 | 0 |  .rdt 0x5A6F |
| 14 | MicEnhance | 0 | 0 |  .rdt 0x5A70 |
| 15 | ResetTime | 0 | 0 |  .rdt 0x5A71 |
| 16 | SoundMode | 0 | 0 |  .rdt 0x5A72 |
| 17 | PriConfirm | 0 | 0 |  .rdt 0x5A73 |
| 18 | RespondTime_nop | 0 | 0 |  .rdt no change |
| 19 | PttDelayTime_NOP | 0 | 0 |  .rdt no change |
| 20 | TxModuDelay | 0 | 0 |  .rdt 0x5A74 |
| 21 | TxPreTime | 0 | 0 |  .rdt 0x5A75 |
| 22 | PriConfirmBeep | 0 | 0 |  .rdt 0x5A76 |
| 23 | PriProBeeo | 0 | 0 |  .rdt 0x5A77 |
| 24 | PriCallBeepDelay | 0 | 0 |  .rdt 0x5A78 |
| 25 | SelCallAck | 0 | 0 |  .rdt 0x5A79 |
| 26 | SelCallAckWait_nop | 0 | 0 |  .rdt no change |
| 27 | PriCallBeep | 0 | 0 |  .rdt 0x5A7A |
| 28 | GroupCallBeep | 0 | 0 |  .rdt 0x5A7B |
| 29 | SelCallBeep_nop | 0 | 0 |  .rdt no change |
| 30 | PriCallLed | 0 | 0 |  .rdt 0x5A7C |
| 31 | GroupCallLed | 0 | 0 |  .rdt 0x5A7D |
| 32 | SelCallLed_nop | 0 | 0 |  .rdt no change |
| 33 | SelCallLedEn_nop | 0 | 0 |  .rdt no change |
| 34 | StateMsg1 | 0 | 0 |  .rdt 0x5A7E |
| 35 | StateMsg2 | 0 | 0 |  .rdt 0x5A7F |
| 36 | DefaultState | 0 | 0 |  .rdt 0x5A80 |
| 37 | StartState | 0 | 0 |  .rdt 0x5A81 |
| 38 | RemoteKillState | 0 | 0 |  .rdt 0x5A82 |
| 39 | ShutState | 0 | 0 |  .rdt 0x5A83 |
| 40 | NxdnMoni | 0 | 0 |  .rdt 0x5A85 |
| 41 | NxdnMoniRan | 0 | 0 |  .rdt 0x5A86 |
| 42 | NxdnMoniId | 0 | 0 |  .rdt 0x5A87 |

### MDC1200AddressBook (list, LST index 35)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | ID |  |  |  |
| 1 | Type |  |  |  |
| 2 | Attr |  |  |  |
| 3 | ACK |  |  |  |
| 4 | GROUP_ID |  |  |  |
| 5 | PRI_ID |  |  |  |
| 6 | Name |  |  |  |

### MDC1200Encode (list, LST index 36)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | ID |  |  |  |
| 1 | Enc_Type |  |  |  |
| 2 | ENC_KIND |  |  |  |
| 3 | ENC_MDC_ACK |  |  |  |
| 4 | ENC_GROUP_ID |  |  |  |
| 5 | ENC_PRI_ID |  |  |  |
| 6 | ENC_MDC_ENC_NAME |  |  |  |

### EncryptionCode (list, LST index 37)

| # | Column | Default | Values in the test codeplug | cfw |
|---|---|---|---|---|
| 0 | No | 1 | 1, 2, 3, 4 (+28 more) |  |
| 1 | Encryption Key | 65535 | 65535 |  |
| 2 | Encryption ID | 65535 | 65535 |  |

