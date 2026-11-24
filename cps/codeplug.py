"""cfw codeplug model, binary format ("D8CP" v1) and JSON/YAML export.

The binary layout is documented in docs/CODEPLUG.md and mirrored by cfw/app/cfwcp.h in the firmware.
This module is the reference encoder: encode() is canonical (fixed section order, pools rebuilt in order),
so decode(encode(cp)) == cp and encode(decode(b)) == b for anything this module wrote.
"""
import json
import struct
import time
import zlib
from dataclasses import dataclass, field, asdict, fields

MAGIC = b"D8CP"
VERSION = 1
HEADER_SIZE = 32
REGION_SIZE = 0x60000          # max codeplug region (384 KB, cfw ≥ 2026-11-21); the radio reports its own size (info block)
# radio models: id in the header (u16 at offset 18, 0 = D890UV for codeplugs written before models existed), radio
# region size, identification string of the cfw link, default radio name
MODELS = {"D890UV": {"id": 0, "region": 0x60000, "ident": "D890CFW", "name": "D890UV cfw"},
          "D168UV": {"id": 1, "region": 0x60000, "ident": "D168CFW", "name": "D168UV cfw"}}
MODEL_BY_ID = {v["id"]: k for k, v in MODELS.items()}
MAX_CHANNELS = 4000            # firmware limit (cfwcp.c); the region size limits first (~1900)

MODES = ["FM", "DMR", "P25", "P25P2", "DSTAR", "NXDN", "YSF"]     # = cfw_mode_t order (hal/modem.h)
POWERS = ["low", "mid", "high", "turbo"]
CONTACT_KINDS = ["group", "private", "all"]
CONTACT_MODES = {"any": 0xFF, "DMR": 1, "P25": 2, "NXDN": 5}
TRUNK_TYPES = {"P25": 1, "DMR_T3": 2, "NXDN_C": 3, "NXDN_D": 4}
VOCODERS = ["auto", "AMBE+2", "AMBE+2 half-rate", "IMBE", "AMBE (D-STAR)", "AMBE+2 EHR", "AMBE+2 EFR", "YSF V/D", "YSF VW"]
MODE_VOCODERS = {"DMR": ["auto", "AMBE+2"], "P25": ["auto", "IMBE"], "P25P2": ["auto", "AMBE+2 half-rate"],
                 "NXDN": ["auto", "AMBE+2 EHR", "AMBE+2 EFR"], "DSTAR": ["auto", "AMBE (D-STAR)"], "YSF": ["auto", "YSF V/D", "YSF VW"]}
YSF_MODES = ["DN", "VW", "DATA"]
KEY_KINDS = {"DMR_BP": 2, "DMR_ARC4": 5, "DMR_AES128": 16, "DMR_AES256": 32, "P25_DES": 8, "P25_AES256": 32, "P25_ADP": 5,
             "NXDN_SCR": 2, "NXDN_DES": 8, "NXDN_AES": 32}          # kind -> key length in bytes
KEY_ALGID = {"P25_DES": 0x81, "P25_AES256": 0x84, "P25_ADP": 0xAA, "DMR_AES256": 0x24, "DMR_AES128": 0x25, "DMR_ARC4": 0x21}
KEY_FUNCS = ["none", "mode_next", "mode_picker", "vfo_mem", "key_lock", "monitor", "scan", "test_tone", "zone_next",
             "talkaround", "tx_power", "call_log", "gps_info"]
NONE16 = 0xFFFF
NONE8 = 0xFF

SEC_SETTINGS, SEC_CHANNELS, SEC_ZONES, SEC_SCANLISTS, SEC_CONTACTS, SEC_TGLISTS, SEC_TRUNKSYS, SEC_POOL32, SEC_POOL16 = range(1, 10)
SEC_STOCK = 10          # stock CPS data, byte stream (cps/stock.py encode_stock); rec_size 1, count = bytes
SEC_CHEXT, SEC_KEYS, SEC_BANDPLAN, SEC_DSTAR_RPT, SEC_DIGISET = range(11, 16)
SEC_NAMES = {1: "settings", 2: "channels", 3: "zones", 4: "scanlists", 5: "contacts", 6: "tglists", 7: "trunksys",
             8: "pool32", 9: "pool16"}
REC_SIZE = {SEC_SETTINGS: 128, SEC_CHANNELS: 64, SEC_ZONES: 24, SEC_SCANLISTS: 28, SEC_CONTACTS: 24,
            SEC_TGLISTS: 24, SEC_TRUNKSYS: 48, SEC_POOL32: 4, SEC_POOL16: 2,
            SEC_CHEXT: 32, SEC_KEYS: 56, SEC_BANDPLAN: 24, SEC_DSTAR_RPT: 48, SEC_DIGISET: 64}

# D878UV / D890UV CPS CTCSS table (index order of the stock codeplug); 0.1 Hz units
CTCSS = [625, 670, 693, 719, 744, 770, 797, 825, 854, 885, 915, 948, 974, 1000, 1035, 1072, 1109, 1148, 1188, 1230,
         1273, 1318, 1365, 1413, 1462, 1514, 1567, 1598, 1622, 1655, 1679, 1713, 1738, 1773, 1799, 1835, 1862, 1899,
         1928, 1966, 1995, 2035, 2065, 2107, 2181, 2257, 2291, 2336, 2418, 2503, 2541]


class CodeplugError(ValueError):
    pass


# ---------------------------------------------------------------- model

@dataclass
class Settings:
    callsign: str = "N0CALL"
    dmr_id: int = 0
    p25_unit_id: int = 0             # 0 = use dmr_id
    nxdn_unit_id: int = 0            # 0 = use dmr_id & 0xFFFF
    rx_invert: bool = False
    key_beep: bool = True
    auto_keylock: bool = False
    boot_vfo: bool = False
    encryption: bool = False         # privacy keys in use (radio: Settings > Encryption; illegal on amateur bands)
    sms_msms: bool = False           # SMS TX format: True = M-SMS (Motorola-style TMS over IP), False = cfw format
    step_hz: int = 12500
    deemph_us: int = 0
    test_tone_hz: int = 0
    backlight_level: int = 8
    backlight_timeout_s: int = 0
    vfo_mode: str = "FM"
    keylock_timeout_s: int = 0
    start_channel: int = None        # None = keep the last used channel
    keys: list = field(default_factory=lambda: ["mode_next", "vfo_mem", "none", "none", "mode_next", "mode_picker"])
    dmr_cc: int = 1
    dmr_slot: int = 1
    dmr_tg: int = 91
    p25_nac: int = 0x293
    nxdn_ran: int = 1
    ysf_dgid: int = 0
    p25_tg: int = 1
    nxdn_group: int = 1
    p25_wacn: int = 0xBEE00
    p25_sysid: int = 0x3C1
    ur: str = "CQCQCQ"
    rpt1: str = ""
    rpt2: str = ""
    dstar_msg: str = ""
    radio_name: str = "D890UV cfw"


@dataclass
class Channel:
    name: str = ""
    rx_hz: int = 446000000
    tx_hz: int = 446000000           # 0 = RX only
    mode: str = "FM"
    wide: bool = False               # FM 25 kHz
    trunk: bool = False              # P25 control channel / DMR Tier III TSCC
    scan_skip: bool = False
    power: str = "high"
    scanlist: int = None             # index into scanlists
    rx_tone: str = None              # "88.5" CTCSS, "D023N" / "D023I" DCS, None
    tx_tone: str = None
    # digital (only the fields of `mode` are encoded)
    cc: int = 1                      # DMR colour code
    slot: int = 1                    # DMR / P25P2 time slot 1..2
    tg: int = 0                      # DMR / P25 talkgroup, NXDN group
    contact: int = None              # index into contacts (TX contact)
    tglist: int = None               # index into tglists (RX group list)
    trunksys: int = None             # index into trunksys
    nac: int = 0x293                 # P25
    wacn: int = 0                    # P25 (Phase 2 scrambling seed with sysid)
    sysid: int = 0
    ran: int = 0                     # NXDN
    ur: str = ""                     # D-STAR
    rpt1: str = ""
    rpt2: str = ""
    dgid: int = 0                    # YSF (RX DG-ID, 0 = all)
    # digital extensions (section CHEXT, only for channels that differ from the defaults)
    talkaround: bool = False         # simplex on the repeater output (TX = RX frequency); = stock "Talk Around(Simplex)"
    vocoder: str = "auto"            # MODE_VOCODERS[mode]
    key: int = None                  # index into keys (encryption), DMR / P25 / P25P2 / NXDN
    nxdn_rate: int = 4800            # NXDN48 / NXDN96
    dgid_tx: int = None              # YSF TX DG-ID (None = same as dgid)
    ysf_mode: str = "DN"             # YSF_MODES
    wiresx: bool = False             # YSF Wires-X
    tdma_direct: bool = False        # DMR: TDMA direct (dual-capacity simplex, TS1/TS2 syncs); off = normal direct
    dstar_rpt: int = None            # index into dstar_rpts (D-STAR repeater / routing entry)
    stock: dict = field(default_factory=dict)       # stock CPS columns cfw does not model (only non-defaults)


MODE_FIELDS = {
    "FM": [],
    "DMR": ["cc", "slot", "tg", "contact", "tglist", "trunksys", "vocoder", "key", "tdma_direct"],
    "P25": ["nac", "tg", "contact", "tglist", "trunksys", "wacn", "sysid", "vocoder", "key"],
    "P25P2": ["nac", "slot", "tg", "contact", "tglist", "trunksys", "wacn", "sysid", "vocoder", "key"],
    "NXDN": ["ran", "tg", "contact", "tglist", "trunksys", "vocoder", "key", "nxdn_rate"],
    "DSTAR": ["ur", "rpt1", "rpt2", "vocoder", "dstar_rpt"],
    "YSF": ["dgid", "dgid_tx", "ysf_mode", "wiresx", "vocoder"],
}
EXT_DEFAULTS = {"talkaround": False, "vocoder": "auto", "key": None, "nxdn_rate": 4800, "dgid_tx": None, "ysf_mode": "DN",
                "wiresx": False, "dstar_rpt": None, "tdma_direct": False}
FM_FIELDS = ["wide", "rx_tone", "tx_tone"]
COMMON_FIELDS = ["name", "rx_hz", "tx_hz", "mode", "trunk", "scan_skip", "power", "scanlist", "talkaround", "stock"]


def channel_defaults_for(mode):
    """Values the encoder writes for fields that do not belong to `mode` (so decode is canonical)."""
    c = Channel(mode=mode)
    c.cc, c.slot, c.tg, c.contact, c.tglist, c.trunksys = 0, 0, 0, None, None, None
    c.nac, c.wacn, c.sysid, c.ran, c.dgid = 0, 0, 0, 0, 0
    c.ur = c.rpt1 = c.rpt2 = ""
    c.wide, c.rx_tone, c.tx_tone = False, None, None
    for k, v in EXT_DEFAULTS.items():
        setattr(c, k, v)
    c.stock = {}
    return c


def normalize_channel(c):
    """Reset the fields `c.mode` does not use, so the model equals what decode() returns."""
    d = channel_defaults_for(c.mode)
    keep = set(COMMON_FIELDS) | set(MODE_FIELDS.get(c.mode, [])) | (set(FM_FIELDS) if c.mode == "FM" else set())
    for f in fields(Channel):
        if f.name not in keep:
            setattr(c, f.name, getattr(d, f.name))
    if c.mode == "DMR" and c.slot not in (1, 2):
        c.slot = 1
    if c.mode == "P25":
        c.slot = 0
    return c


@dataclass
class Zone:
    name: str = ""
    channels: list = field(default_factory=list)
    stock: dict = field(default_factory=dict)       # stock CPS columns cfw does not model (only non-defaults)


@dataclass
class ScanList:
    name: str = ""
    channels: list = field(default_factory=list)
    prio1: int = None
    prio2: int = None
    dwell_100ms: int = 20
    flags: int = 0
    stock: dict = field(default_factory=dict)       # stock CPS columns cfw does not model (only non-defaults)


@dataclass
class Contact:
    name: str = ""
    id: int = 0
    kind: str = "group"
    mode: str = "any"
    stock: dict = field(default_factory=dict)       # stock CPS columns cfw does not model (only non-defaults)


@dataclass
class TgList:
    name: str = ""
    contacts: list = field(default_factory=list)     # order = priority
    stock: dict = field(default_factory=dict)       # stock CPS columns cfw does not model (only non-defaults)


@dataclass
class TrunkSystem:
    name: str = ""
    type: str = "P25"                # P25 / DMR_T3
    nac_cc: int = 0                  # P25 NAC / DMR colour code (0 = take the channel's)
    wacn: int = 0
    sysid: int = 0
    tglist: int = None               # talkgroup priority list (index into tglists)
    control_channels: list = field(default_factory=list)   # Hz, hunted in order
    chan_step_hz: int = 12500        # DMR Tier III channel plan step
    base_hz: int = 0                 # DMR Tier III LPCN 1 frequency (0 = first control channel)
    flags: int = 0
    rfss: int = 0                    # P25 home RFSS / NXDN area
    site: int = 0                    # P25 / DMR T3 / NXDN home site
    registration: bool = False       # register with the system (needs TX; cfw RX-only today)
    phase2: bool = False             # P25: Phase 2 TDMA voice channels
    bandplan: list = field(default_factory=list)   # P25 IDEN_UP entries / NXDN channel plan (BandPlan)


@dataclass
class BandPlan:
    iden: int = 0                    # P25 identifier 0..15
    base_hz: int = 851006250
    spacing_hz: int = 6250
    tx_offset_hz: int = -45000000
    bw_hz: int = 12500
    tdma: bool = False               # Phase 2 TDMA channel
    slots: int = 1                   # TDMA slots per carrier (2 for Phase 2)


@dataclass
class Key:
    name: str = ""
    kind: str = "P25_AES256"         # KEY_KINDS
    key_id: int = 1
    algid: int = 0x84
    hex: str = ""                    # user-entered key (hex), length KEY_KINDS[kind] bytes


@dataclass
class DstarRepeater:
    name: str = ""
    rpt1: str = ""                   # repeater callsign + module ("XX0RPT B")
    rpt2: str = ""                   # gateway ("XX0RPT G")
    rx_hz: int = 0
    tx_hz: int = 0
    gps: bool = False


@dataclass
class DigiSettings:
    dstar_dprs: bool = False         # send GPS position as D-PRS in the slow data
    dstar_gps_interval_s: int = 0    # 0 = with every transmission
    dstar_auto_reply: bool = False
    dprs_symbol: str = "/["
    dprs_comment: str = ""
    dmr_t3_register: bool = False
    p25_register: bool = False
    nxdn_register: bool = False
    ysf_mode: str = "DN"             # default for new YSF channels
    ysf_wiresx_room: int = 0
    ysf_wiresx_auto: bool = False


@dataclass
class Codeplug:
    settings: Settings = field(default_factory=Settings)
    channels: list = field(default_factory=list)
    zones: list = field(default_factory=list)
    scanlists: list = field(default_factory=list)
    contacts: list = field(default_factory=list)
    tglists: list = field(default_factory=list)
    trunksys: list = field(default_factory=list)
    generation: int = 0
    created: int = 0
    stock: dict = field(default_factory=dict)       # stock CPS tables cfw does not model: {table: rows} (cps/stock.py)
    keys: list = field(default_factory=list)
    dstar_rpts: list = field(default_factory=list)
    digi: DigiSettings = field(default_factory=DigiSettings)
    model: str = "D890UV"                           # radio model (MODELS); selects the stock CPS schema

    def normalize(self):
        for c in self.channels:
            normalize_channel(c)
        return self


# ---------------------------------------------------------------- helpers

def _s(b, n):
    b = b.encode("ascii", "replace") if isinstance(b, str) else b
    return b[:n].ljust(n, b"\0")


def _us(b):
    return b.split(b"\0", 1)[0].decode("ascii", "replace")


def _ref16(v):
    return NONE16 if v is None else int(v)


def _unref16(v):
    return None if v == NONE16 else v


def tone_encode(t):
    if t is None or t == "":
        return 0
    t = str(t).strip().upper()
    if t.startswith("D"):
        inv = t.endswith("I")
        code = t[1:].rstrip("NI")
        v = int(code, 8)
        if v > 0o777:
            raise CodeplugError("DCS code %r out of range" % t)
        return 0x8000 | (0x4000 if inv else 0) | v
    v = int(round(float(t) * 10))
    if not 1 <= v <= 0x3FFF:
        raise CodeplugError("CTCSS %r out of range" % t)
    return v


def tone_decode(v):
    if v == 0:
        return None
    if v & 0x8000:
        return "D%03o%s" % (v & 0x1FF, "I" if v & 0x4000 else "N")
    return "%d.%d" % (v // 10, v % 10)


# ---------------------------------------------------------------- binary

def _enc_settings(s):
    flags = ((1 if s.rx_invert else 0) | (2 if s.key_beep else 0) | (4 if s.auto_keylock else 0) | (8 if s.boot_vfo else 0)
             | (16 if s.encryption else 0) | (32 if s.sms_msms else 0))
    keys = bytes(KEY_FUNCS.index(k) if k in KEY_FUNCS else 0 for k in (list(s.keys) + ["none"] * 6)[:6])
    b = (_s(s.callsign, 8) + struct.pack("<IIHHIHHBBBBH", s.dmr_id, s.p25_unit_id, s.nxdn_unit_id, flags, s.step_hz,
                                         s.deemph_us, s.test_tone_hz, s.backlight_level, s.backlight_timeout_s,
                                         MODES.index(s.vfo_mode), s.keylock_timeout_s, _ref16(s.start_channel))
         + keys + struct.pack("<BBHIHBBIIIHH", s.dmr_cc, s.dmr_slot, 0, s.dmr_tg, s.p25_nac, s.nxdn_ran, s.ysf_dgid,
                              s.p25_tg, s.nxdn_group, s.p25_wacn, s.p25_sysid, 0)
         + _s(s.ur, 8) + _s(s.rpt1, 8) + _s(s.rpt2, 8) + _s(s.dstar_msg, 20) + _s(s.radio_name, 16))
    assert len(b) == 128, len(b)
    return b


def _dec_settings(b):
    s = Settings()
    s.callsign = _us(b[0:8])
    (s.dmr_id, s.p25_unit_id, s.nxdn_unit_id, flags, s.step_hz, s.deemph_us, s.test_tone_hz, s.backlight_level,
     s.backlight_timeout_s, vm, s.keylock_timeout_s, sc) = struct.unpack_from("<IIHHIHHBBBBH", b, 8)
    s.rx_invert, s.key_beep, s.auto_keylock, s.boot_vfo = bool(flags & 1), bool(flags & 2), bool(flags & 4), bool(flags & 8)
    s.encryption = bool(flags & 16)
    s.sms_msms = bool(flags & 32)
    s.vfo_mode = MODES[vm] if vm < len(MODES) else "FM"
    s.start_channel = _unref16(sc)
    s.keys = [KEY_FUNCS[k] if k < len(KEY_FUNCS) else "none" for k in b[34:40]]
    (s.dmr_cc, s.dmr_slot, _, s.dmr_tg, s.p25_nac, s.nxdn_ran, s.ysf_dgid, s.p25_tg, s.nxdn_group, s.p25_wacn,
     s.p25_sysid, _) = struct.unpack_from("<BBHIHBBIIIHH", b, 40)
    s.ur, s.rpt1, s.rpt2 = _us(b[68:76]), _us(b[76:84]), _us(b[84:92])
    s.dstar_msg, s.radio_name = _us(b[92:112]), _us(b[112:128])
    return s


def _enc_channel(c):
    m = c.mode
    flags = (1 if (c.wide and m == "FM") else 0) | (2 if c.trunk else 0) | (4 if c.scan_skip else 0)
    head = _s(c.name, 16) + struct.pack("<IIBBBBHH", c.rx_hz, c.tx_hz, MODES.index(m), flags, POWERS.index(c.power),
                                         NONE8 if c.scanlist is None else c.scanlist,
                                         tone_encode(c.rx_tone) if m == "FM" else 0,
                                         tone_encode(c.tx_tone) if m == "FM" else 0)
    if m == "DMR":
        u = struct.pack("<BBBBIHHH", c.cc, c.slot, 0, 0, c.tg, _ref16(c.contact), _ref16(c.tglist), _ref16(c.trunksys))
    elif m in ("P25", "P25P2"):
        u = struct.pack("<HBBIHHHHI", c.nac, c.slot if m == "P25P2" else 0, 0, c.tg, _ref16(c.contact),
                        _ref16(c.tglist), _ref16(c.trunksys), c.sysid, c.wacn)
    elif m == "NXDN":
        u = struct.pack("<B3xIHHH", c.ran, c.tg, _ref16(c.contact), _ref16(c.tglist), _ref16(c.trunksys))
    elif m == "DSTAR":
        u = _s(c.ur, 8) + _s(c.rpt1, 8) + _s(c.rpt2, 8)
    elif m == "YSF":
        u = struct.pack("<B", c.dgid)
    else:
        u = b""
    b = head + u.ljust(32, b"\0")
    assert len(b) == 64
    return b


def _dec_channel(b):
    m_i, flags, pw, sl, rxt, txt = struct.unpack_from("<BBBBHH", b, 24)
    if m_i >= len(MODES):
        raise CodeplugError("channel mode %d unknown" % m_i)
    m = MODES[m_i]
    c = channel_defaults_for(m)
    c.name = _us(b[0:16])
    c.rx_hz, c.tx_hz = struct.unpack_from("<II", b, 16)
    c.wide, c.trunk, c.scan_skip = bool(flags & 1), bool(flags & 2), bool(flags & 4)
    c.power = POWERS[pw & 3]
    c.scanlist = None if sl == NONE8 else sl
    if m == "FM":
        c.rx_tone, c.tx_tone = tone_decode(rxt), tone_decode(txt)
    u = b[32:64]
    if m == "DMR":
        c.cc, c.slot, _, _, c.tg, ct, tl, ts = struct.unpack_from("<BBBBIHHH", u)
        c.contact, c.tglist, c.trunksys = _unref16(ct), _unref16(tl), _unref16(ts)
    elif m in ("P25", "P25P2"):
        c.nac, c.slot, _, c.tg, ct, tl, ts, c.sysid, c.wacn = struct.unpack_from("<HBBIHHHHI", u)
        c.contact, c.tglist, c.trunksys = _unref16(ct), _unref16(tl), _unref16(ts)
    elif m == "NXDN":
        c.ran, c.tg, ct, tl, ts = struct.unpack_from("<B3xIHHH", u)
        c.contact, c.tglist, c.trunksys = _unref16(ct), _unref16(tl), _unref16(ts)
    elif m == "DSTAR":
        c.ur, c.rpt1, c.rpt2 = _us(u[0:8]), _us(u[8:16]), _us(u[16:24])
    elif m == "YSF":
        c.dgid = u[0]
    return c


def _ext_of(c):
    """CHEXT record of a channel, or None when all its digital extensions are default"""
    if all(getattr(c, k) == v for k, v in EXT_DEFAULTS.items()):
        return None
    voc = VOCODERS.index(c.vocoder) if c.vocoder in VOCODERS else 0
    flags = (1 if c.talkaround else 0) | (2 if c.wiresx else 0) | (4 if c.tdma_direct else 0)
    return struct.pack("<BBBBBBH", voc, flags, NONE8 if c.key is None else c.key, 1 if c.nxdn_rate == 9600 else 0,
                       NONE8 if c.dgid_tx is None else c.dgid_tx, YSF_MODES.index(c.ysf_mode), _ref16(c.dstar_rpt))


def _enc_digi(g):
    flags = sum(b << i for i, b in enumerate([g.dstar_dprs, g.dstar_auto_reply, g.dmr_t3_register, g.p25_register,
                                              g.nxdn_register, g.ysf_wiresx_auto]))
    b = struct.pack("<BBHI", flags, YSF_MODES.index(g.ysf_mode), g.dstar_gps_interval_s, g.ysf_wiresx_room) + \
        _s(g.dprs_symbol, 2) + _s(g.dprs_comment, 20)
    return b.ljust(64, b"\0")


def _dec_digi(b):
    g = DigiSettings()
    flags, ym, g.dstar_gps_interval_s, g.ysf_wiresx_room = struct.unpack_from("<BBHI", b, 0)
    (g.dstar_dprs, g.dstar_auto_reply, g.dmr_t3_register, g.p25_register, g.nxdn_register, g.ysf_wiresx_auto) = \
        [bool(flags >> i & 1) for i in range(6)]
    g.ysf_mode = YSF_MODES[ym] if ym < len(YSF_MODES) else "DN"
    g.dprs_symbol, g.dprs_comment = _us(b[8:10]), _us(b[10:30])
    return g


def encode(cp, for_radio=True):
    """Codeplug -> bytes (canonical). for_radio: leave out file-only stock tables (contact databases) and enforce the
    radio region size; files (.d8cp) keep everything."""
    pool16, pool32 = [], []

    def put16(lst):
        first = len(pool16)
        pool16.extend(int(x) for x in lst)
        return first

    recs = {k: [] for k in REC_SIZE}
    recs[SEC_SETTINGS].append(_enc_settings(cp.settings))
    for c in cp.channels:
        recs[SEC_CHANNELS].append(_enc_channel(c))
    for z in cp.zones:
        recs[SEC_ZONES].append(_s(z.name, 16) + struct.pack("<IHH", put16(z.channels), len(z.channels), 0))
    for s in cp.scanlists:
        recs[SEC_SCANLISTS].append(_s(s.name, 16) + struct.pack("<IHHHBB", put16(s.channels), len(s.channels),
                                                                 _ref16(s.prio1), _ref16(s.prio2), s.dwell_100ms, s.flags))
    for c in cp.contacts:
        recs[SEC_CONTACTS].append(_s(c.name, 16) + struct.pack("<IBBH", c.id, CONTACT_KINDS.index(c.kind),
                                                                CONTACT_MODES[c.mode], 0))
    for t in cp.tglists:
        recs[SEC_TGLISTS].append(_s(t.name, 16) + struct.pack("<IHH", put16(t.contacts), len(t.contacts), 0))
    for t in cp.trunksys:
        first = len(pool32)
        pool32.extend(int(f) for f in t.control_channels)
        recs[SEC_TRUNKSYS].append(_s(t.name, 16) + struct.pack("<BBHIHHIHHIII", TRUNK_TYPES[t.type], t.flags, t.nac_cc,
                                                                t.wacn, t.sysid, _ref16(t.tglist), first,
                                                                len(t.control_channels), (t.rfss & 0xFF) << 8 | (t.site & 0xFF),
                                                                t.chan_step_hz, t.base_hz,
                                                                (1 if t.registration else 0) | (2 if t.phase2 else 0)))
    for ti, t in enumerate(cp.trunksys):
        for bp in t.bandplan:
            recs[SEC_BANDPLAN].append(struct.pack("<HBBIIiIB3x", ti, bp.iden, 1 if bp.tdma else 0, bp.base_hz, bp.spacing_hz,
                                                  bp.tx_offset_hz, bp.bw_hz, bp.slots))
    for i, c in enumerate(cp.channels):
        e = _ext_of(c)
        if e is not None:
            recs[SEC_CHEXT].append((struct.pack("<H", i) + e).ljust(32, b"\0"))
    for k in cp.keys:
        kb = bytes.fromhex(k.hex) if k.hex else b""
        recs[SEC_KEYS].append(_s(k.name, 16) + struct.pack("<BBHB3x", list(KEY_KINDS).index(k.kind), k.algid, k.key_id, len(kb))
                              + kb.ljust(32, b"\0")[:32])
    for r in cp.dstar_rpts:
        recs[SEC_DSTAR_RPT].append(_s(r.name, 16) + _s(r.rpt1, 8) + _s(r.rpt2, 8) +
                                   struct.pack("<IIB7x", r.rx_hz, r.tx_hz, 1 if r.gps else 0))
    recs[SEC_DIGISET].append(_enc_digi(cp.digi))
    recs[SEC_POOL16] = [struct.pack("<H", v) for v in pool16]
    recs[SEC_POOL32] = [struct.pack("<I", v) for v in pool32]

    from . import stock as ST
    stock_b = ST.encode_stock(cp, for_radio)
    order = list(REC_SIZE)
    if stock_b:
        order.append(SEC_STOCK)
        recs[SEC_STOCK] = [stock_b]
    off = HEADER_SIZE + 16 * len(order)
    dirent, body = b"", b""
    for sid in order:
        data = b"".join(recs[sid])
        if sid == SEC_STOCK:
            dirent += struct.pack("<HHIII", sid, 1, len(data), off + len(body), 0)
        else:
            dirent += struct.pack("<HHIII", sid, REC_SIZE[sid], len(recs[sid]), off + len(body), 0)
        body += data + b"\0" * (-len(data) % 4)
    total = HEADER_SIZE + len(dirent) + len(body)
    pad = -total % 16                       # whole quad-words (flash programming unit)
    total += pad
    tail = struct.pack("<HHIII", len(order), MODELS[cp.model]["id"], cp.generation, cp.created, 0) + dirent + body + b"\0" * pad
    crc = zlib.crc32(tail) & 0xFFFFFFFF
    out = MAGIC + struct.pack("<HHII", VERSION, HEADER_SIZE, total, crc) + tail
    assert len(out) == total
    region = REGION_SIZE if cp.model == "D890UV" else MODELS[cp.model]["region"]
    if for_radio and total > region:
        raise CodeplugError("codeplug is %d bytes, the radio holds %d" % (total, region))
    return out


def check_header(b):
    """Returns (total_len, crc) or raises CodeplugError."""
    if len(b) < HEADER_SIZE or b[:4] != MAGIC:
        raise CodeplugError("not a cfw codeplug (magic)")
    ver, hs, total, crc = struct.unpack_from("<HHII", b, 4)
    if ver != VERSION:
        raise CodeplugError("codeplug format version %d, this CPS knows %d" % (ver, VERSION))
    if hs != HEADER_SIZE or total < HEADER_SIZE or total > len(b):
        raise CodeplugError("bad header (size %d, length %d of %d)" % (hs, total, len(b)))
    if zlib.crc32(b[16:total]) & 0xFFFFFFFF != crc:
        raise CodeplugError("CRC mismatch")
    return total, crc


def decode(b):
    """bytes -> Codeplug. Raises CodeplugError on any inconsistency."""
    total, _ = check_header(b)
    nsec, mid, gen, created, _ = struct.unpack_from("<HHIII", b, 16)
    if mid not in MODEL_BY_ID:
        raise CodeplugError("codeplug for an unknown radio model (id %d)" % mid)
    cp = Codeplug(generation=gen, created=created, model=MODEL_BY_ID[mid])
    secs = {}
    for i in range(nsec):
        sid, rs, cnt, off, _ = struct.unpack_from("<HHIII", b, HEADER_SIZE + 16 * i)
        if off + rs * cnt > total:
            raise CodeplugError("section %d out of bounds" % sid)
        if sid in REC_SIZE and rs != REC_SIZE[sid]:
            raise CodeplugError("section %d record size %d" % (sid, rs))
        secs[sid] = [b[off + k * rs: off + (k + 1) * rs] for k in range(cnt)] if sid != SEC_STOCK else [b[off:off + cnt]]
    p16 = [struct.unpack("<H", r)[0] for r in secs.get(SEC_POOL16, [])]
    p32 = [struct.unpack("<I", r)[0] for r in secs.get(SEC_POOL32, [])]

    def take16(first, n):
        if first + n > len(p16):
            raise CodeplugError("list out of the pool")
        return p16[first:first + n]

    if secs.get(SEC_SETTINGS):
        cp.settings = _dec_settings(secs[SEC_SETTINGS][0])
    cp.channels = [_dec_channel(r) for r in secs.get(SEC_CHANNELS, [])]
    for r in secs.get(SEC_ZONES, []):
        f, n, _ = struct.unpack_from("<IHH", r, 16)
        cp.zones.append(Zone(_us(r[:16]), take16(f, n)))
    for r in secs.get(SEC_SCANLISTS, []):
        f, n, p1, p2, dw, fl = struct.unpack_from("<IHHHBB", r, 16)
        cp.scanlists.append(ScanList(_us(r[:16]), take16(f, n), _unref16(p1), _unref16(p2), dw, fl))
    for r in secs.get(SEC_CONTACTS, []):
        cid, kind, mode, _ = struct.unpack_from("<IBBH", r, 16)
        modes = {v: k for k, v in CONTACT_MODES.items()}
        cp.contacts.append(Contact(_us(r[:16]), cid, CONTACT_KINDS[kind] if kind < 3 else "group", modes.get(mode, "any")))
    for r in secs.get(SEC_TGLISTS, []):
        f, n, _ = struct.unpack_from("<IHH", r, 16)
        cp.tglists.append(TgList(_us(r[:16]), take16(f, n)))
    types = {v: k for k, v in TRUNK_TYPES.items()}
    for r in secs.get(SEC_TRUNKSYS, []):
        ty, fl, nc, wacn, sysid, tl, f, n, rs, step, base, fl2 = struct.unpack_from("<BBHIHHIHHIII", r, 16)
        if f + n > len(p32):
            raise CodeplugError("control channel list out of the pool")
        cp.trunksys.append(TrunkSystem(_us(r[:16]), types.get(ty, "P25"), nc, wacn, sysid, _unref16(tl),
                                       p32[f:f + n], step, base, fl, rs >> 8, rs & 0xFF, bool(fl2 & 1), bool(fl2 & 2)))
    for r in secs.get(SEC_BANDPLAN, []):
        ti, iden, fl, base, sp, off, bw, slots = struct.unpack_from("<HBBIIiIB", r)
        if ti < len(cp.trunksys):
            cp.trunksys[ti].bandplan.append(BandPlan(iden, base, sp, off, bw, bool(fl & 1), slots))
    for r in secs.get(SEC_CHEXT, []):
        i, voc, flags, key, rate, dtx, ym, rpt = struct.unpack_from("<HBBBBBBH", r)
        if i < len(cp.channels):
            c = cp.channels[i]
            c.vocoder = VOCODERS[voc] if voc < len(VOCODERS) else "auto"
            c.talkaround, c.wiresx, c.tdma_direct = bool(flags & 1), bool(flags & 2), bool(flags & 4)
            c.key = None if key == NONE8 else key
            c.nxdn_rate = 9600 if rate else 4800
            c.dgid_tx = None if dtx == NONE8 else dtx
            c.ysf_mode = YSF_MODES[ym] if ym < len(YSF_MODES) else "DN"
            c.dstar_rpt = _unref16(rpt)
    kinds = list(KEY_KINDS)
    for r in secs.get(SEC_KEYS, []):
        kind, algid, kid, ln = struct.unpack_from("<BBHB", r, 16)
        cp.keys.append(Key(_us(r[:16]), kinds[kind] if kind < len(kinds) else "P25_AES256", kid, algid, r[24:24 + ln].hex().upper()))
    for r in secs.get(SEC_DSTAR_RPT, []):
        rx, tx, fl = struct.unpack_from("<IIB", r, 32)
        cp.dstar_rpts.append(DstarRepeater(_us(r[:16]), _us(r[16:24]), _us(r[24:32]), rx, tx, bool(fl & 1)))
    if secs.get(SEC_DIGISET):
        cp.digi = _dec_digi(secs[SEC_DIGISET][0])
    from . import stock as ST
    ST.use(cp.model)
    if secs.get(SEC_STOCK):
        ST.decode_stock(secs[SEC_STOCK][0], cp)
    return cp


# ---------------------------------------------------------------- JSON / YAML

def to_dict(cp):
    d = {"format": "cfw-codeplug", "version": VERSION, "generation": cp.generation, "created": cp.created,
         "settings": asdict(cp.settings), "channels": []}
    for c in cp.channels:
        keep = COMMON_FIELDS + (FM_FIELDS if c.mode == "FM" else []) + MODE_FIELDS[c.mode]
        cd = {k: getattr(c, k) for k in keep}
        if not cd.get("stock"):
            cd.pop("stock", None)
        d["channels"].append(cd)
    for k in ("zones", "scanlists", "contacts", "tglists", "trunksys", "keys", "dstar_rpts"):
        d[k] = []
        for x in getattr(cp, k):
            xd = asdict(x)
            if not xd.get("stock"):
                xd.pop("stock", None)
            d[k].append(xd)
    d["digi"] = asdict(cp.digi)
    if cp.model != "D890UV":
        d["model"] = cp.model
    if cp.stock:
        d["stock"] = cp.stock
    return d


def _mk(cls, d):
    names = {f.name for f in fields(cls)}
    unknown = set(d) - names
    if unknown:
        raise CodeplugError("%s: unknown field(s) %s" % (cls.__name__, ", ".join(sorted(unknown))))
    return cls(**d)


def from_dict(d):
    if d.get("format") != "cfw-codeplug":
        raise CodeplugError("not a cfw codeplug export (format field)")
    cp = Codeplug(generation=d.get("generation", 0), created=d.get("created", 0), model=d.get("model", "D890UV"))
    if cp.model not in MODELS:
        raise CodeplugError("unknown radio model %r" % cp.model)
    cp.stock = {k: [list(r) for r in v] for k, v in d.get("stock", {}).items()}
    cp.settings = _mk(Settings, d.get("settings", {}))
    for cd in d.get("channels", []):
        c = channel_defaults_for(cd.get("mode", "FM"))
        for k, v in cd.items():
            if not hasattr(c, k):
                raise CodeplugError("channel: unknown field %s" % k)
            setattr(c, k, v)
        cp.channels.append(normalize_channel(c))
    cp.zones = [_mk(Zone, x) for x in d.get("zones", [])]
    cp.scanlists = [_mk(ScanList, x) for x in d.get("scanlists", [])]
    cp.contacts = [_mk(Contact, x) for x in d.get("contacts", [])]
    cp.tglists = [_mk(TgList, x) for x in d.get("tglists", [])]
    cp.trunksys = []
    for x in d.get("trunksys", []):
        x = dict(x)
        x["bandplan"] = [_mk(BandPlan, b) for b in x.get("bandplan", [])]
        cp.trunksys.append(_mk(TrunkSystem, x))
    cp.keys = [_mk(Key, x) for x in d.get("keys", [])]
    cp.dstar_rpts = [_mk(DstarRepeater, x) for x in d.get("dstar_rpts", [])]
    cp.digi = _mk(DigiSettings, d.get("digi", {}))
    from . import stock as ST
    ST.use(cp.model)
    return cp


def dumps_json(cp):
    return json.dumps(to_dict(cp), indent=1, ensure_ascii=False) + "\n"


def dumps_yaml(cp):
    import yaml          # optional dependency
    return yaml.safe_dump(to_dict(cp), sort_keys=False, allow_unicode=True)


def load(path):
    """Load .d8cp (binary), .json or .yaml/.yml."""
    if path.lower().endswith(".lst"):
        from . import stock
        return stock.from_stock(stock.read_csv_set(path))
    if path.lower().endswith(".rdt"):
        from . import rdt
        return rdt.load(path)
    data = open(path, "rb").read()
    if data[:4] == MAGIC:
        return decode(data)
    text = data.decode("utf-8")
    if path.lower().endswith((".yaml", ".yml")):
        import yaml
        return from_dict(yaml.safe_load(text))
    return from_dict(json.loads(text))


def save(cp, path):
    p = path.lower()
    if p.endswith(".rdt"):
        from . import rdt
        lost = rdt.save(cp, path)
        if lost:
            import sys
            print("warning: not written into the .rdt (stock tables kept in the .rdt tail are not decoded yet; use the "
                  "stock CSV set): " + ", ".join(lost), file=sys.stderr)
    elif p.endswith(".lst"):
        from . import stock
        stock.write_csv_set(stock.to_stock(cp), path)
    elif p.endswith(".json"):
        open(path, "w").write(dumps_json(cp))
    elif p.endswith((".yaml", ".yml")):
        open(path, "w").write(dumps_yaml(cp))
    else:
        open(path, "wb").write(encode(cp, for_radio=False))


def new_codeplug(model="D890UV"):
    if model not in MODELS:
        raise CodeplugError("unknown radio model %r" % model)
    cp = Codeplug(created=int(time.time()), model=model)
    cp.settings.radio_name = MODELS[model]["name"]
    cp.channels = [Channel(name="2M CALL", rx_hz=146520000, tx_hz=146520000, mode="FM", wide=True),
                   Channel(name="70CM CALL", rx_hz=446000000, tx_hz=446000000, mode="FM", wide=True)]
    return cp.normalize()
