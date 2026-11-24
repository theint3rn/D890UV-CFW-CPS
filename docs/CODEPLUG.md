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
| 12 | encryption keys (user-entered) | 56 | `cfwcp_key()` accessor |
| 13 | band plans (P25 IDEN_UP / NXDN channel plan) of trunk systems | 24 | `cfwcp_bandplans()` accessor |
| 14 | D-STAR repeater / routing list | 48 | stored |
| 15 | digital settings (D-PRS, YSF, registration) | 64 | stored |

Sections are written in id order. The firmware ignores ids it does not know, so new sections can be added without a version bump. A layout change to an existing record does need a version bump.

### Settings (128 B)

| Off | Type | Field |
|---|---|---|
| 0 | char[8] | callsign (D-STAR MY, YSF) |
| 8 | u32 | DMR / radio ID (also the default P25 / NXDN unit ID) |
| 12 | u32 | P25 unit ID (0 = DMR ID) |
| 16 | u16 | NXDN unit ID (0 = DMR ID) |
| 18 | u16 | flags: b0 RX polarity inverted, b1 key beep, b2 auto key lock, b3 boot in VFO, b4 encryption on (privacy keys used; off by default, refused on amateur bands), b5 SMS TX format M-SMS (else cfw format) |
| 20 | u32 | VFO step, Hz |
| 24 | u16 | de-emphasis compensation, µs (0 or 750) |
| 26 | u16 | test tone, Hz (0 = off) |
| 28 | u8 ×4 | backlight level 0..10, backlight timeout (s), VFO mode, key lock timeout (s) |
| 32 | u16 | start channel (index, `0xFFFF` = keep the last used one) |
| 34 | u8[6] | key functions for P1, P2, PF1, PF2, PF3, PF3-long (D168UV: PF1 = P1, PF2 = P2): 0 none, 1 next mode, 2 mode picker, 3 VFO/MEM, 4 key lock, 5 monitor, 6 scan, 7 test tone, 8 next zone, 9 talkaround, 10 TX power, 11 call log, 12 GPS info |
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
  value = key function number; col 6 = encryption 0/1 -> flags b4; col 7 = SMS format 0 cfw / 1 M-SMS -> flags b5),
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
* The stock digital contact databases (DMR / NX Digital Contact List) are kept in files but never written to the radio.

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

The link uses USART1, the programming-cable UART: 115200 8N1, PB6 TX / PB7 RX AF7. These pins are not verified on a real radio. The framing is the stock D890UV PC link (CLAUDE.md "PC link"). Addresses are big endian.

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
