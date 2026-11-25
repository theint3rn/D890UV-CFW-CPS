# cfw codeplug format ("D8CP", version 1)

The codeplug of the D890UV custom firmware (cfw). One binary blob, stored in the radio's internal flash and read in
place by the firmware. Region: `0x081C0000–0x081DFFFF` (128 KB) in the current cfw; growing it to
`0x08180000–0x081DFFFF` (384 KB) is requested from the platform owner. The radio reports its region size in the info
block and the CPS refuses a codeplug that does not fit.

* Reference encoder: `cps/codeplug.py`. Encoding is canonical: the same model always gives the same bytes.
* Firmware reader: `cfw/app/cfwcp.h` / `cfw/app/cfwcp.c`. The structs there match this document; `_Static_assert`s check the sizes.

All integers are little endian. "none" references are `0xFFFF` (u16) or `0xFF` (u8). Strings are ASCII, NUL padded. A string that fills its field has no NUL.

## Layout

```
0x00  header (32 B)
0x20  section directory: n x 16 B
....  sections, each 4-byte aligned; the total is padded to a multiple of 16 (one flash quad-word)
```

### Header

| Off | Type | Field |
|---|---|---|
| 0 | char[4] | magic `D8CP` |
| 4 | u16 | format version = 1 |
| 6 | u16 | header size = 32 |
| 8 | u32 | total length in bytes, including the header (≤ 0x20000) |
| 12 | u32 | CRC-32 (IEEE 802.3, zlib) of bytes `[16, total)` |
| 16 | u16 | number of sections |
| 18 | u16 | radio model: 0 = D890UV, 1 = D168UV (was "flags (0)": codeplugs from before the D168 support are D890UV) |
| 20 | u32 | generation: the CPS adds 1 on every write to the radio |
| 24 | u32 | creation time (unix), informational only |
| 28 | u32 | reserved (0) |

The model selects the stock CPS data model of section 10 (table ids are positions in that model's stock table order) and
the radio the codeplug may be written to: the CPS refuses to write a D890UV codeplug to a D168UV cfw and vice versa
(convert it first: GUI Radio model, `cfw_cps.py export --model`, web "Radio" selector). Everything else in the format is
the same for both radios. A firmware should reject a codeplug whose model is not its own.

The firmware accepts the codeplug only if all of these hold: the magic matches, the version is 1, the length is in range, the CRC matches, every section is inside the blob, and there is at least one channel. Otherwise it falls back to the stock NAND channels plus its built-in channels.

### Section directory entry (16 B)

`u16 id, u16 record size, u32 count, u32 offset (from the start of the blob), u32 reserved`

| id | Section | Record | Used by the firmware today |
|---|---|---|---|
| 1 | settings | 128 | yes: IDs, callsign, step, RX polarity, de-emphasis, test tone, start channel, boot in VFO |
| 2 | channels | 64 | yes |
| 3 | zones | 24 | yes: Menu > Zone, channel stepping, zone scan |
| 4 | scan lists | 28 | yes: Menu > Scan (members, priority channel 1, dwell) |
| 5 | contacts / talkgroups | 24 | yes: a channel with TG 0 takes the ID of its contact |
| 6 | TG lists (RX group lists, priority order) | 24 | stored only |
| 7 | trunk systems | 48 | yes: sets the trunk flag, P25 NAC / WACN / system ID, DMR CC, and the control channel if the channel RX is 0 |
| 8 | pool32 (u32: control channel frequencies) | 4 | through trunk systems |
| 9 | pool16 (u16: zone / scan list / TG list members) | 2 | through lists |
| 10 | stock CPS data (byte stream, see below) + radio edits journal | 1 (count = bytes) | Optional Settings in the radio's Settings menu, quick texts; the journal is written by the radio |
| 11 | channel digital extensions (CHEXT), only channels that differ from the defaults, in channel order | 32 | talkaround; rest via `cfwcp_chext()` |
| 12 | encryption keys (user-entered) | 56 | `cfwcp_key()` accessor (then the keys of the stock key tables, see below) |
| 13 | band plans (P25 IDEN_UP / NXDN channel plan) of trunk systems | 24 | `cfwcp_bandplans()` accessor |
| 14 | D-STAR repeater / routing list | 48 | stored |
| 15 | digital settings (D-PRS, YSF, registration) | 64 | stored |
| 16 | user database (DMR / NX Digital Contact List), written to radios only | 24 | yes: caller callsign + name on RX (`stockcp.c`) |

Sections are written in id order. The firmware ignores ids it does not know, so new sections can be added without a version bump. A layout change to an existing record does need a version bump.

### Settings (128 B)

| Off | Type | Field |
|---|---|---|
| 0 | char[8] | callsign (D-STAR MY, YSF) |
| 8 | u32 | DMR / radio ID (also the default P25 / NXDN unit ID) |
| 12 | u32 | P25 unit ID (0 = DMR ID) |
| 16 | u16 | NXDN unit ID (0 = DMR ID) |
| 18 | u16 | flags: b0 RX polarity inverted, b1 key beep, b2 auto key lock, b3 boot in VFO, b4 encryption on (privacy keys used; off by default, refused on amateur bands), b5 SMS TX format M-SMS (else cfw format), b6 battery shown as percent (else icon) |
| 20 | u32 | VFO step, Hz |
| 24 | u16 | de-emphasis compensation, µs (0 or 750) |
| 26 | u16 | test tone, Hz (0 = off) |
| 28 | u8 ×4 | backlight level 0..10, backlight timeout (s), VFO mode, key lock timeout (s) |
| 32 | u16 | start channel (index, `0xFFFF` = keep the last used one) |
| 34 | u8[6] | key functions for P1, P2, PF1, PF2, PF3, PF3-long (D168UV: PF1 = P1, PF2 = P2): 0 none, 1 next mode, 2 mode picker, 3 VFO/MEM, 4 key lock, 5 monitor, 6 scan, 7 test tone, 8 next zone, 9 talkaround, 10 TX power, 11 call log, 12 GPS info, 13 alarm (emergency) |
| 40 | u8, u8, u16 | defaults: DMR CC, DMR slot, pad |
| 44 | u32 | default DMR TG |
| 48 | u16, u8, u8 | default P25 NAC, NXDN RAN, YSF DG-ID |
| 52 | u32 ×3 | default P25 TG, NXDN group, P25 WACN |
| 64 | u16, u16 | default P25 system ID, pad |
| 68 | char[8] ×3 | default D-STAR UR, RPT1, RPT2 |
| 92 | char[20] | D-STAR message |
| 112 | char[16] | radio name |

Key functions are applied (cfw UI v0.3). Backlight level/timeout, key beep, key lock and the mode defaults of this record are not used: the radio menu uses the stock Optional Settings of section 10 for those (see the radio edits journal).

### Channel (64 B)

| Off | Type | Field |
|---|---|---|
| 0 | char[16] | name |
| 16 | u32 | RX frequency, Hz |
| 20 | u32 | TX frequency, Hz (0 = RX only) |
| 24 | u8 | mode = `cfw_mode_t`: 0 FM, 1 DMR, 2 P25 (Phase 1), 3 P25P2, 4 D-STAR, 5 NXDN, 6 YSF |
| 25 | u8 | flags: b0 25 kHz (FM only), b1 trunk (P25 control channel / DMR Tier III TSCC), b2 scan skip |
| 26 | u8 | power: 0 low, 1 mid, 2 high, 3 turbo |
| 27 | u8 | scan list index (`0xFF` none) |
| 28 | u16 | RX tone (FM only) |
| 30 | u16 | TX tone (FM only) |
| 32 | 32 B | mode data, see below |

Tones: 0 = none. `1..0x3FFF` = CTCSS in 0.1 Hz (885 = 88.5 Hz). `0x8000 | code` = DCS, where code is the octal DCS number (D023 → 0o23); bit 14 set = inverted. The firmware uses one CTCSS tone per channel: the TX tone if there is one, else the RX tone. DCS is stored but not generated yet.

Mode data (only the current mode's fields are written; all other bytes are 0):

| Off | DMR | P25 / P25P2 | NXDN | D-STAR | YSF |
|---|---|---|---|---|---|
| 0 | u8 colour code, u8 slot 1/2, u16 0 | u16 NAC, u8 slot (P25P2: 1/2, P25: 0), u8 0 | u8 RAN, 3 B 0 | char[8] UR | u8 DG-ID (0 = all) |
| 4 | u32 talkgroup | u32 talkgroup | u32 group | | |
| 8 | u16 contact | u16 contact | u16 contact | char[8] RPT1 | |
| 10 | u16 TG list | u16 TG list | u16 TG list | | |
| 12 | u16 trunk system (Tier III) | u16 trunk system | u16 trunk system (Type-C/D) | | |
| 14 | | u16 system ID | | | |
| 16 | | u32 WACN | | char[8] RPT2 | |

### Channel digital extensions (section 11, 32 B)

| Off | Type | Field |
|---|---|---|
| 0 | u16 | channel index |
| 2 | u8 | vocoder: 0 auto, 1 AMBE+2, 2 AMBE+2 half-rate, 3 IMBE, 4 AMBE (D-STAR), 5 AMBE+2 EHR, 6 AMBE+2 EFR, 7 YSF V/D, 8 YSF VW (allowed per mode: DMR 0/1, P25 0/3, P25P2 0/2, NXDN 0/5/6, D-STAR 0/4, YSF 0/7/8) |
| 3 | u8 | flags: b0 talkaround (simplex on the RX frequency; also the stock "Talk Around(Simplex)" column), b1 YSF Wires-X, b2 DMR TDMA direct (dual-capacity simplex: TS1/TS2 direct syncs, slot from the channel; off = normal DMR direct with MS syncs) |
| 4 | u8 | encryption key index (0xFF none; the key kind must match the mode) |
| 5 | u8 | NXDN rate: 0 NXDN48 (4800 bit/s), 1 NXDN96 |
| 6 | u8 | YSF TX DG-ID (0xFF = same as the RX DG-ID) |
| 7 | u8 | YSF mode: 0 DN, 1 VW, 2 DATA |
| 8 | u16 | D-STAR repeater list index (0xFFFF none) |
| 10 | 22 B | 0 |

### Encryption key (section 12, 56 B)

`char[16] name, u8 kind, u8 ALGID, u16 key ID, u8 length, 3 B 0, u8[32] key`. Kinds (length): 0 DMR basic privacy (2),
1 DMR ARC4 (5), 2 DMR AES-128 (16), 3 DMR AES-256 (32), 4 P25 DES (8), 5 P25 AES-256 (32), 6 P25 ADP (5),
7 NXDN scrambler (2), 8 NXDN DES (8), 9 NXDN AES (32). Keys are entered by the user; the CPS never generates or fetches
keys. They are plain bytes in the codeplug (and in the radio's flash) - treat codeplug files as sensitive.

### Band plan (section 13, 24 B)

`u16 trunk system, u8 identifier 0..15, u8 flags (b0 TDMA), u32 base Hz, u32 channel spacing Hz, i32 TX offset Hz,
u32 bandwidth Hz, u8 TDMA slots (1 FDMA, 2 Phase 2), 3 B 0`.

### D-STAR repeater (section 14, 48 B)

`char[16] name, char[8] RPT1 (repeater + module), char[8] RPT2 (gateway), u32 RX Hz, u32 TX Hz, u8 flags (b0 GPS /
D-PRS), 7 B 0`.

### Digital settings (section 15, 64 B)

`u8 flags (b0 D-STAR D-PRS, b1 D-STAR auto reply, b2 DMR Tier III registration, b3 P25 registration, b4 NXDN
registration, b5 Wires-X auto connect), u8 default YSF mode, u16 D-PRS interval s, u32 Wires-X room, char[2] D-PRS
symbol, char[20] D-PRS comment, 34 B 0`. Registration needs TX; the cfw is receive-only on trunked systems today.

### Man down (D168UV)

The stock CPS "Man Down" checkbox (Public > Alarm Setting) is the stock CSV column `FailAlarm` (OptionalSetting col 30,
.rdt byte 0x71, 0 Off / 1 On); "Man Down Delay[s]" is `ManDownWait` (.rdt 0x93). Found by ticking the box in the stock
D168 CPS V1.07, saving and diffing the .rdt (both directions). The cfw CPS shows both on the Optional Setting tab
"Man Down"; they travel in section 10, the stock CSV set and .rdt files like any mapped setting. Stock radio: settings
block NAND 0x02500000 +0x24 (on/off), +0x4F (delay s). The cfw firmware does not implement man down yet. (The D890UV
map also puts `FailAlarm` at .rdt 0x71; not checked there.)

### Radio edits journal (end of section 10)

When it writes a radio, the CPS appends `STOCK_SPARE` = 1024 zero bytes to section 10 (files do not have them). The cfw
writes settings changed in its radio menu there, so the CPS can read them back:

```
... CPS entries ... | EE 00 0000 0000 | edit entries ... | EF 00 0000 0400 xx xx xx xx | 00 ...
```

* `0xEE` marks the start; the firmware rewrites everything from the marker on (only the flash page(s) holding it).
* Edits use the normal entry format. Tables: 21 = stock OptionalSetting (value text as in the stock CSV; the last entry
  of a cell wins, as for every entry), `0xE0` = cfw settings record (col 0..5 = key slot P1, P2, PF1, PF2, PF3, PF3 long,
  value = key function number; col 6 = encryption 0/1 -> flags b4; col 7 = SMS format 0 cfw / 1 M-SMS -> flags b5; col 10 = battery display 0 icon / 1 percent -> flags b6),
  `0xE2` = cfw channel field (col 0 = TX power 0..3, row = channel index).
* `0xEF`, length 4: four bytes chosen so that the CRC-32 of the whole blob still equals the CRC in the header (the
  header page is never rewritten). Readers skip `0xE0..0xEF` entries they do not apply.
* The CPS decoder folds the edits into its model; the next write puts them in their normal places and leaves the
  journal empty. A codeplug without spare bytes makes the radio keep its menu edits in its own settings blob.
* Power-loss safety (redo copy): before rewriting the journal page(s) the firmware writes the new page images into the
  last three 8 KB pages of the codeplug region (image pages at `size - 3 * 8 KB`, a 32-byte record "JBK1" with
  generation, header CRC, page numbers, image CRC and its own CRC at `size - 8 KB`, written last = commit), then
  rewrites the codeplug pages, then erases the record. At boot (`cfwcp_recover`) a committed record is applied again if
  the codeplug is invalid or still the same generation/CRC; a stale record (older codeplug) is dropped. So journal writes
  need `total_len <= size - 24 KB` (else the radio keeps its edits in its settings blob); a CPS write may still use the
  whole region. Emulator test: `cfw/tools/powercut_test.py` stops the CPU at every erase / 1 KB program step.

### Stock CPS data (section 10)

Everything of the stock D890UV CPS V1.05 that cfw does not model, as the stock CSV text (the format of the stock CPS
"Export All"; tables, columns and defaults in `schema/stock_d890uv.json`, map in `docs/STOCK_CPS_MAP.md`). Entries:

`u8 table, u8 column, u16 row, u16 length, text (latin-1)`, padded with zeros to 4 bytes.

* table 0..37 = the stock .LST order; record tables (OptionalSetting 21, NXSetting 34, APRS 19, AlertTone 22) store only
  values that differ from the stock default; list tables store a row count (column 0xFF) and every non-empty cell.
* table 0xF0..0xF4 = per-object stock columns of channels, zones, scan lists, contacts, TG lists (row = object index):
  the stock columns cfw does not model, only where they differ from what the CPS would generate.
* Analog signalling (firmware `cfw/app/sig.c`): tables AnalogAddressBook (4), 5ToneEncode (9), 2ToneEncode (10),
  DTMFEncode (11), AlertTone (22), D890UV MDC1200AddressBook (35) / MDC1200Encode (36), D168UV QDC1200EnCodeTable
  (23) / QDC1200DECodeTable (24) / QDC1200AddressBook (25), and the channel columns Optional Signal, DTMF ID, 2Tone ID,
  5Tone ID, PTT ID, 2TONE Decode, R5toneBot / R5ToneEot, Rpga_Mdc (table 0xF0) are read by the radio. Entry numbers
  are decimal, MDC / QDC unit ids hex (4 digits), option texts matched by keyword (cfw/README.md).
* The stock digital contact databases (DMR / NX Digital Contact List) are kept in files; a radio gets them as section
  16 instead (below), not as CSV text.

### User database (section 16, 24 B)

`u32 key = mode << 24 | id` (mode 1 DMR, 5 NXDN; DMR IDs 24 bit, NXDN 16 bit), `char[8] callsign`, `char[12] name`
(DMR "Name"; NXDN FIRST_NAME + " " + LAST_NAME), sorted by key (the firmware does a binary search). Written only when
encoding for a radio (`encode(for_radio=True)`): from the stock DMR / NX Digital Contact Lists, first row of an ID wins,
as many rows as fit in the region after everything else and a 24 KB reserve for the radio edits journal (384 KB region:
about 12 000 entries next to a typical codeplug); when they do not all fit, the rows earlier in the stock list stay
and the CPS log says how many were left out (`codeplug.LAST_USERDB`). Reading a radio turns section 16 back into the
stock contact lists (ID, callsign, name only) when the codeplug has none.

### Stock sections used by the firmware (`cfw/app/stockcp.c`)

The firmware reads these stock CPS tables from section 10 (table / column numbers of the radio's own stock model,
`stockcp_map()`); `schema/cfw_support.json` marks them "used".

| Stock data | Radios | Firmware use |
|---|---|---|
| Radio ID List + channel "Radio ID" (name) | both | DMR source ID of that channel (else the master ID) |
| Encryption Code (basic privacy: 32 rows, 16-bit key, ID) | both: D890UV table 37 (decimal key); D168UV table 72 `EncryptionCodeRdt` (list of set rows: No. 1-32, hex key, ID; a row that is not listed = the default key / ID 65535, taken from the D890UV dialog) | keys of kind 0 (2 bytes, big endian); key ID = Encryption ID if <= 255, else the row number; rows with key 65535 that no channel uses are left out |
| ARC4 Encryption Code (id, 10 hex digits) | both | kind 1 (40 bit), key ID = id |
| AES Encryption Code (id, num, 32 or 64 hex digits) | both | kind 2 (AES-128) / 3 (AES-256), key ID = id |
| channel "ARC4" N / "Digital Encryption" N / "AES Digital Encryption" | both | the channel's key when section 11 sets none: ARC4 N = ARC4 key id N; else Digital Encryption N with Enhanced = AES key id N, Normal = Encryption Code row N |
| NX Encryption Code (Valid, EMGCode, KeyId) + channel "NxdnEncry" N | D890UV | valid rows = kind 7 NXDN scrambler, EMGCode = the 15-bit code; NxdnEncry N = row N |
| NX Setting | D890UV | OwnId = NXDN unit ID (the cfw settings NXDN unit ID wins); NxdnMoni on + NxdnMoniRan Any = receive every RAN. Other columns stored |
| NX Talk Group | D890UV | group name on RX (CALLSIGN, else FIRST_NAME); TxForbid refuses TX to that group |
| DMR / NX Digital Contact List | both / D890UV | section 16: callsign + name of the caller on the call screen |

The channel-column meanings (which table "Digital Encryption" points into) come from the stock CPS labels, the
programming guide and the radio's menu strings ("Encrypt Type": Common / ARC4 Type / AES Type); they were not checked
against a stock radio. Settings > Encryption and the amateur-band gate apply to these keys like to section 12 keys.
**Not interoperable with stock radios:** the stock radios encrypt inside the SCT3288 baseband (encrypted firmware), so
their basic privacy / ARC4 / AES air formats are unknown; the cfw uses its own DMR schemes for these key sizes
(`proto/dmr_nxdn/dmr/dmr_priv.h`: DMR_PRIV_CFW_BP / _RC4 / _AES128 / _AES256) and only talks to other cfw radios. NXDN
scrambling (NX Encryption Code) is the NXDN standard (TS 1-D, checked against its test vectors), so it should match
any radio that follows it; not tried against a stock radio.

Stored, not used: NX Receive Group Call List (the channel column that selects it is shared with the DMR RX group list;
the cfw receivers have no RX group filter for DMR either), NX State Message (no NXDN status calls in the cfw), the
repeater whitelists (Talk Group / Digital Contact Whitelist: the cfw has no cross-band repeater), D168UV
Friends List (section 10 `FriendsList`, see "Stock CPS dialogs that exist only in the `.rdt`"; the firmware does not read
it yet).

### Stock CPS dialogs that exist only in the `.rdt` (section 10 tables 64-72)

Dialogs with no stock CSV table are carried as extra tables of section 10, in the same entry format (`u8 table, u8 column, u16 row, u16 len, text`,
values as decimal / hex text). Table ids and column numbers are the same on both radios (`schema/rdt_dialogs.json`, generated by
`tools/make_rdt_dialogs.py`; JS `DIALOGS`); a column a radio's dialog does not have is never written for it. Record tables: only cells that
differ from the default are stored, column = position below, row 0. List tables: row-count entry (column 0xFF) + cells. So an absent table or
cell = the default shown. All are readable with `cfwcp_stock_value(table, col, ...)`; an older CPS / firmware ignores the ids. A filled set costs
about 1 KB in the radio codeplug (typical use: 20-200 B).

| table (id) | columns (number: name, default D890UV / D168UV; `-` = not on that radio) |
|---|---|
| AlarmSetting (64, record) | 0 Analog Emergency Alarm (0 / 0); 1 Analog ENI Type (0 / 0); 2 Analog Alarm Time [s] (20 / 20); 3 Analog Duration of TX [s] (31 / 31); 4 Analog Duration of RX [s] (31 / 31); 5 Analog Emergency Channel (1 / 1); 6 Analog ENI Send Select (0 / 0); 7 Analog Emergency Cycle (0 = Continuous) (0 / 0); 8 Digital Emergency Alarm (0 / 0); 9 Digital Emergency Channel (1 / 1); 10 Digital Alarm Time [s] (20 / 20); 11 Digital Duration of TX [s] (31 / 31); 12 Digital Duration of RX [s] (31 / 31); 13 Digital ENI Send Select (0 / 0); 14 Digital Emergency Cycle (0 = Continuous) (0 / 0); 15 Digital TG/DMR ID (0 / 0); 16 Digital Call Type (0 / 0); 17 Receive Alarm (0 / 0); 18 QDC1200 Kind (0 / 0); 19 QDC1200 Group ID (- / 000); 20 QDC1200 Private ID (0000 / 0000); 21 Analog alarm signaling type (- / 0); 22 Work Alone Response Time (0 = 1 min) (0 / 0); 23 Work Alone Warning Time (0 = 1 s) (0 / 0); 24 Work Alone Response (0 / 0) |
| DTMFSetting (65, record) | 0 DTMF Transmitting Time (1 / 1); 1 DTMF Self ID (3 digits; the stock CPS shows letters blank) (000 / 000); 2 DTMF Interval Character (10 A, 11 B, 12 C, 13 D, 14 *, 15 #) (14 / 14); 3 Group Code (0 Off, 10 A .. 13 D, 14 *, 15 #) (0 / 0); 4 Decoding Response (0 / 0); 5 First Digit Time (x 10 ms) (20 / 20); 6 Pretime (x 10 ms) (20 / 20); 7 Auto Reset Time (D890UV: s, D168UV: 0.1 s) (10 / 0); 8 Time-Lapse After Encode (x 10 ms) (20 / 20); 9 PTT ID Pause Time (raw) (0 / 0); 10 D Code Pause (s, 0 = Off) (10 / 10); 11 Side Tone (0 / 0); 12 PTT ID (0 / 0); 13 PTT ID Starting (BOT) ('' / ''); 14 PTT ID Ending (EOT) ('' / ''); 15 Remotely Kill ('' / ''); 16 Remotely Stun ('' / '') |
| T2Setting (66, record) | 0 1st Tone Duration (x 0.1 s) (5 / 5); 1 2nd Tone Duration (x 0.1 s) (5 / 5); 2 Long Tone Duration (x 0.1 s) (10 / 10); 3 Gap Time (x 100 ms) (0 / 0); 4 Auto Reset Time (D890UV: s, D168UV: 0.1 s) (10 / 0); 5 Side Tone (0 / 0) |
| T5Setting (67, record) | 0 Self ID ('' / ''); 1 Decode Standard (0 / 0); 2 Decoding Response (0 / 0); 3 Time Of Decode Tone [ms] (- / 70); 4 Decode Time (x 10 ms) (2 / 2); 5 5TONE Dec Units (bit mask, bit 0 = unit 1) (0 / 0); 6 Disp AnyID (0 / 0); 7 Pretime (x 10 ms) (20 / 20); 8 Time-Lapse After Encode (x 10 ms) (20 / 20); 9 PTT ID Pause Time [s] (0 = Off) (10 / 10); 10 Auto Reset Time [s] (10 / 0); 11 First Delay (x 10 ms) (20 / 20); 12 Side Tone (0 / 0); 13 First Delay Time After Stop (x 10 ms) (0 / 0); 14 PTT ID Starting (BOT): Encode ID ('' / ''); 15 PTT ID Starting (BOT): standard (index) (0 / 0); 16 PTT ID Starting (BOT): tone time [ms] (70 / 70); 17 PTT ID Ending (EOT): Encode ID ('' / ''); 18 PTT ID Ending (EOT): standard (index) (0 / 0); 19 PTT ID Ending (EOT): tone time [ms] (70 / 70) |
| T5InfoCodes (68, list) | 0 No.; 1 Function Option (index); 2 Decoding Response (index); 3 Information ID |
| TalkAlias (70, record) | 0 Talker Alias Type (- / 0); 1 Alias Display Priority (0 / 0); 2 Alias Data Format (0 / -) |
| FriendsList (71, list) | 0 No.; 1 DMR ID |
| EncryptionCodeRdt (72, list, D168UV) | 0 No.; 1 Encryption KEY (hex); 2 Encryption ID |

Value rules: `AlarmAChannel` / `AlarmDChannel` = 1-based channel number in the channel list; `AlarmQPrivate` / `AlarmQGroup` = hex;
FriendsList `DMR ID` = an ID of the digital contact list (the `.rdt` stores the list index); EncryptionCodeRdt key = 4 hex digits (65535 ID = none).
Times are in the stock raw unit named in the label. D168UV `Encryption Code` is this table (the D890UV one is the CSV table EncryptionCode, id 37).
Not decoded (kept byte for byte in the `.rdt`, not in the codeplug): Alarm Setting > Analog > Emergency ID (list content depends on the signalling tables); Alarm Setting > ENI Type list texts (the value is stored raw); 5Tone Setting: Stop Code, Stop Time (header bytes 0x23-0x25 are not tied to one field); the Function Name of an information code (the string after the ID is kept as it is); 2Tone Setting > Decode tab; DTMF Setting > Special Call; Encode ID tables (CSV); Alarm Setting > QDC1200 Group ID: the stock D890UV CPS shows the bytes at C+0x56 but saves to C+0x4F, so it does not survive its own save (the frame is greyed out there); Talk Alias > Custom Text: the V1.07 dialog shows no text field when it is chosen; where (or if) a text is kept is not known; QDC1200 Setting: Max ACK wait, Sync headers, Pretime, Try times, Side Tone; Local Information: the stock CPS opens the COM port for it; it is live radio data, not in the .rdt.

### Stock common sections used by the firmware (`cfw/app/stockopt.c`)

Read from section 10 like the tables above (table id = stock .LST position, same on both radios for these). Absent values act as the stock default. List tables
are cached in one walk of section 10 at boot and after a CPS write; a list table equal to the stock default is not
stored, so the firmware applies the stock default rows (FM-001 88.000, AM-001 108.000, the 18 default hot keys).

| table (id) | columns used |
|---|---|
| OptionalSetting (21) | Step 8, StartDspSet 6, Start_Char 46 / Start_Char2 62, Boot_Sound 54, MsgRing 35, CallRing 41, TmZone 42, TotPreEn 161, MenuLowPower 120, StartChUse 115 / StartZone1 116 / StartCurChan1 118, AutoRepeater 65, UhfAutoRep 76 / VhfAutoRep 77, AutoRepFreq0..3 108..111, WanderPerod 99, FixRomanStartOp 124, TimeRoamOn 131, CurRoamZone 132, AmOffset 186 (D890UV); plus the v0.4/v0.5 ones (rset.c) |
| PrefabricatedSMS (6) | Text (quick texts, hot key message) |
| FM (7) | No. (101 = VFO), Frequency[MHz], Scan, Name (D890UV) |
| HotKey_QuickCall (12) | Operation Type (DTMF / 2Tone / 5Tone / MDC1200 / QDC1200), Call ID (encode list entry) |
| HotKey_HotKey (14) | Mode (Menu / Call), Menu, Call Type, Call Object (contact name / quick call), Digi Call Type, Content |
| AutoRepeaterOffsetFrequencys (16) | Offset Frequency (MHz) |
| RoamingChannel (17) / RoamingZone (18) | RX, TX, Color Code, Slot, Name / Name, members ("a\|b", channel names) |
| APRS (19) | 1 auto interval, 3 fixed beacon, 4..11 position, 48/49 TOCALL + SSID, 50/51 call + SSID, 52/53 symbol, 54 path, 55 comment, 56 TX frequency |
| GPSRoaming (20) | OnOff, Zone, latitude / longitude degree + N/S, E/W + minute, Radius(Meter) |
| AMAir (27) / AMZone (30), D890UV | No. (257 = VFO), Frequency, Name / Zone Name, members |
| channel extras (0xF0) | Busy Lock/TX Permit, PTT Prohibit, Reverse, Correct Frequency[Hz], Exclude channel from roaming |

Radio edits of these OptionalSetting columns (Menu > Radio extras > Options) go into the radio edits journal as table 21
entries, like the Settings page.

### Zone (24 B), TG list (24 B)

`char[16] name, u32 first (index into pool16), u16 count, u16 reserved`. Zone members are channel indices. TG list members are contact indices, in priority order.

### Scan list (28 B)

`char[16] name, u32 first (pool16), u16 count, u16 priority channel 1, u16 priority channel 2, u8 dwell (100 ms units), u8 flags`

### Contact (24 B)

`char[16] name, u32 id, u8 kind (0 group, 1 private, 2 all-call), u8 mode (1 DMR, 2 P25, 5 NXDN, 0xFF any), u16 reserved`

### Trunk system (48 B)

| Off | Type | Field |
|---|---|---|
| 0 | char[16] | name |
| 16 | u8 | type: 1 P25, 2 DMR Tier III |
| 17 | u8 | flags (0) |
| 18 | u16 | P25 NAC / DMR colour code (0 = use the channel's) |
| 20 | u32 | WACN (P25) |
| 24 | u16 | system ID (P25) |
| 26 | u16 | TG priority list (TG list index) |
| 28 | u32 | first control channel (index into pool32) |
| 32 | u16 | number of control channels |
| 34 | u16 | (rfss << 8) \| site |
| 36 | u32 | Tier III channel step, Hz (f(lpcn) = base + (lpcn − 1) × step) |
| 40 | u32 | Tier III LPCN 1 frequency, Hz (0 = the first control channel) |
| 44 | u32 | flags2: b0 registration, b1 P25 Phase 2 TDMA |

Types: 1 P25, 2 DMR Tier III, 3 NXDN Type-C, 4 NXDN Type-D (nac_cc = RAN for NXDN).

## Limits and validation (`cps/validate.py`)

* Total size ≤ 128 KB, which is about 1 900 channels with a few lists. Firmware limit: 4 000 channels.
* RX in 136–174 or 400–480 MHz (the cfw's `freq_in_band`). TX is 0 or in band.
* DMR: CC 0–15, slot 1/2, TG ≤ 16 776 415. P25: NAC ≤ 0xFFF, TG ≤ 65 535, WACN 20 bit, system ID 12 bit. NXDN: RAN 0–63, group ≤ 65 535. D-STAR: calls of up to 8 characters from A–Z 0–9 / space. YSF: DG-ID 0–99.
* Consistency: 25 kHz and tones on FM only; the trunk flag on DMR / P25 / P25P2 only; a trunk system's type must match the channel mode; every reference (scan list, contact, TG list, trunk system, zone / scan list / TG list members, start channel) must exist.
* Errors block a write. Warnings (non-standard CTCSS, missing Phase 2 WACN, duplicate members, size > 90 %) do not.

## JSON / YAML export

`cfw_cps.py export x.d8cp -o x.json` gives:

```json
{"format": "cfw-codeplug", "version": 1, "generation": 3, "created": 0,
 "settings": {"callsign": "N0CALL", "dmr_id": 9990001, "...": "..."},
 "channels": [{"name": "RPT", "rx_hz": 146970000, "tx_hz": 146370000, "mode": "FM", "trunk": false,
               "scan_skip": false, "power": "high", "scanlist": null, "wide": true, "rx_tone": "103.5", "tx_tone": "D023N"},
              {"name": "DMR TG91", "rx_hz": 440512500, "...": "...", "mode": "DMR", "cc": 1, "slot": 2, "tg": 91,
               "contact": 0, "tglist": 0, "trunksys": null}],
 "zones": [{"name": "All", "channels": [0, 1]}], "scanlists": [], "contacts": [], "tglists": [], "trunksys": []}
```

A channel only lists the fields of its mode. References are 0-based indices; `null` means none. Frequencies are integer Hz. JSON → binary → JSON is lossless, and so is binary → JSON → binary, byte for byte (tested).

## Link (radio side, `cfw/app/prog.c`)

The link uses USART1, the programming-cable UART: 115200 8N1, PB6 TX / PB7 RX AF7. These pins are not verified on a real radio. The framing is the stock D890UV PC link (project notes "PC link"). Addresses are big endian.

| Host → radio | Radio → host |
|---|---|
| `PROGRAM` | `QX 06`: program mode, the radio shows PROGRAM MODE, keys and PTT are ignored, any TX is dropped |
| `02` | `'I' "D890CFW" 00 fwMaj fwMin cpVer caps maxKB_hi maxKB_lo 06` (16 B; the D168UV cfw sends `"D168CFW"`). caps: b0 read, b1 write, b2 write-protected |
| `'R' a3 a2 a1 a0 len` | `'W' a3..a0 len data cs 06`, where cs = sum(address bytes, len, data) & 0xFF |
| `'W' a3..a0 len data cs 06` | `06` ok, or `15` (bad checksum, out of range, unaligned, write-protected build, or flash verify failed) |
| `END` | `06` if the codeplug is valid or nothing was written; `15` if something was written but the result is invalid. Then the radio reloads its channels and settings and leaves program mode. |

Address space:

* `0x00000000–0x0001FFFF` is the codeplug region. Writes must be 16-byte aligned and a multiple of 16 bytes long. Each 8 KB page is erased the first time it is written in a session.
* `0x00F00000` is a 64-byte read-only info block:

| Off | Field |
|---|---|
| 0 | `CFWI` |
| 4 | u16 link version (1), u16 codeplug version (1) |
| 8 | u32 region base (`0x081C0000`) |
| 12 | u32 region size |
| 16 | u32 codeplug length (0 if none is valid) |
| 20 | u32 CRC |
| 24 | u32 generation |
| 28 | u32 number of codeplug channels |
| 32 | u32 number of channels the radio has (codeplug or NAND, plus built-ins) |
| 36 | u8 valid |
| 37 | u8 write-protected (`HW=1` build) |
| 38 | u8 fw major |
| 39 | u8 fw minor |
| 40 | char[24] firmware string |

The CPS writes the header block (offset 0) **last**. If a write is aborted, the radio is left with no valid cfw codeplug and falls back to the NAND channels. A codeplug that is valid but different from the intended one cannot result. Program mode also ends after 5 s without a byte.

The protocol has **no** firmware, bootloader, option-byte or NAND command. The CPS refuses any radio that does not identify as `D890CFW` or `D168CFW`, so a stock radio is never written. The
ident gives the radio model; a codeplug of the other model is refused.

### D168UV

Same protocol and info block on the D168UV cfw (`D168UV/cfw`, AT32F403A); ident `D168CFW`, codeplug model 1, region
`0x080A0000-0x080FFFFF` (384 KB, flash bank 2; link addresses 0x00000000-0x0005FFFF as on the D890UV), link on USART1
PA9 TX / PA10 RX (programming jack), 115200 8N1. Board details: `D168UV/cfw/docs/CODEPLUG.md`.

## RDT import (`cps/import_rdt.py`)

AnyTone D878UV CPS files (`V1270 … D878UV … V100`) serialise the CPS tables field by field. They are not a memory image. The layout below was decoded from a real 1405-channel D878UV codeplug (not shipped). The stock D890UV CPS converted the same file into its NAND image (`emu/out/codeplug_capture/writes.bin`). All 1405 channels agree with that image on name, RX, TX, mode, colour code, slot, bandwidth and tones (`tests/test_import.py`).

| Part | Layout |
|---|---|
| general settings | `0x00–0xF3`; power-on text at `0x7F` |
| channels | u16 count, then per channel: u16 slot, u32 RX (10 Hz), u8 shift (0 none, 1 +, 2 −), u32 offset (10 Hz; with shift 0 it equals RX), u8 type (0 A, 1 D, 2 A+D, 3 D+A), u8 power 0..3, u8 bandwidth (1 = 25 kHz), 4 B, u8 RX signalling (0 off, 1 CTCSS, 2 DCS), u8 RX CTCSS index, u16 RX DCS, u8 TX signalling, u8 TX CTCSS index, u16 TX DCS, u16 custom CTCSS, u16 contact (0-based TG index), 4 B, u8 scan list (`FF` none), 5 B, u8 colour code, u8 slot (0 = TS1), 6 B, name (≤16, NUL), 12 B |
| radio IDs | u8 count, then {u8 idx, u24 ID, name} |
| zones | u8 count, then {u8 idx, u8 n, n + 2 × u16 (members, then the A / B channel), name} |
| scan lists | u8 count, then {u8 idx, name, 11 B, u8 n, n × (u8, u16 channel slot)} |
| talkgroups | 4 B, then {u24 ID, u16 idx (1-based), u8 type (0x10 group, 0 private, 0x20 all-call), six 7-bit-packed NUL-terminated strings (name, city, call, state, country, remark), padded to a byte}, until the idx sequence breaks |
| user database | 4 B, then the same records: 142 332 RadioID users in that file. Counted, not imported. |
| SMS, FM broadcast list | {u8 idx, text}; {u8 idx, 01, u16 freq / 10 kHz} |
| RX group lists | u8 count, then {u8 idx, name, u8 n, n × u16 TG index} |

Mapping to cfw:

* Channel order is slot order. Zones and scan lists are remapped to that order.
* Digital channels (types 1 and 3) become DMR, or the mode given with `--digital-as`. They get CC and slot, their contact, and that contact's ID as the TG.
* Analog channels (types 0 and 2) become FM with bandwidth and tones.
* Power: 0..3 → low / mid / high / turbo.
* The first radio ID becomes the DMR ID. The power-on text becomes the radio name. The callsign stays N0CALL, because the D878UV has none.
* Not mapped: the RX group list of a channel (the field is unknown), roaming, APRS, and the user database.
