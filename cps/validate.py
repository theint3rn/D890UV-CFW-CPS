"""Codeplug validation: frequency ranges, mode/field consistency, references, size.

validate(cp) -> list of Issue(level, where, msg); level "error" blocks a write, "warn" does not.
"""
import re
from dataclasses import dataclass

from . import codeplug as C

BANDS = [(136000000, 174000000), (400000000, 480000000)]     # cfw freq_in_band() (channels.c)
DSTAR_CALL = re.compile(r"^[A-Z0-9/ ]{0,8}$")


@dataclass
class Issue:
    level: str
    where: str
    msg: str

    def __str__(self):
        return "%-5s %-22s %s" % (self.level, self.where, self.msg)


def in_band(hz):
    return any(lo <= hz <= hi for lo, hi in BANDS)


def validate(cp):
    out = []

    def err(w, m):
        out.append(Issue("error", w, m))

    def warn(w, m):
        out.append(Issue("warn", w, m))

    s = cp.settings
    if not 0 <= s.dmr_id <= 16776415:
        err("settings", "DMR ID %d out of range (1..16776415)" % s.dmr_id)
    if s.dmr_id == 0:
        warn("settings", "DMR ID is 0 (firmware keeps its default)")
    if not re.match(r"^[A-Za-z0-9/ ]{0,8}$", s.callsign or ""):
        err("settings", "callsign %r: up to 8 of A-Z 0-9 /" % s.callsign)
    if not 1000 <= s.step_hz <= 100000:
        err("settings", "step %d Hz (1000..100000)" % s.step_hz)
    if not 0 <= s.deemph_us <= 2000:
        err("settings", "de-emphasis %d us (0..2000)" % s.deemph_us)
    if not 0 <= s.test_tone_hz <= 3000:
        err("settings", "test tone %d Hz (0..3000)" % s.test_tone_hz)
    if not 0 <= s.backlight_level <= 10:
        err("settings", "backlight level %d (0..10)" % s.backlight_level)
    if s.vfo_mode not in C.MODES:
        err("settings", "VFO mode %r" % s.vfo_mode)
    for k in s.keys:
        if k not in C.KEY_FUNCS:
            err("settings", "key function %r (one of %s)" % (k, ", ".join(C.KEY_FUNCS)))
    if s.start_channel is not None and not 0 <= s.start_channel < len(cp.channels):
        err("settings", "start channel %d does not exist" % s.start_channel)
    for nm, v, hi in (("DMR CC", s.dmr_cc, 15), ("P25 NAC", s.p25_nac, 0xFFF), ("NXDN RAN", s.nxdn_ran, 63),
                      ("YSF DG-ID", s.ysf_dgid, 99), ("P25 WACN", s.p25_wacn, 0xFFFFF), ("P25 SysID", s.p25_sysid, 0xFFF)):
        if not 0 <= v <= hi:
            err("settings", "%s default %d out of range" % (nm, v))

    nch = len(cp.channels)
    if nch == 0:
        err("channels", "no channels")
    if nch > C.MAX_CHANNELS:
        err("channels", "%d channels, firmware limit %d" % (nch, C.MAX_CHANNELS))
    for i, c in enumerate(cp.channels):
        w = "ch %d %s" % (i + 1, c.name[:12])
        if c.mode not in C.MODES:
            err(w, "mode %r" % c.mode)
            continue
        if len(c.name) > 16 or any(not 0x20 <= ord(ch) < 0x7F for ch in c.name):
            err(w, "name: up to 16 printable ASCII characters")
        if not c.name:
            warn(w, "empty name")
        if not in_band(c.rx_hz):
            err(w, "RX %.5f MHz outside 136-174 / 400-480 MHz" % (c.rx_hz / 1e6))
        if c.tx_hz and not in_band(c.tx_hz):
            err(w, "TX %.5f MHz outside 136-174 / 400-480 MHz (use 0 for RX only)" % (c.tx_hz / 1e6))
        if c.rx_hz % 50:
            warn(w, "RX frequency not on a 50 Hz grid")
        if c.power not in C.POWERS:
            err(w, "power %r" % c.power)
        if c.scanlist is not None and not 0 <= c.scanlist < len(cp.scanlists):
            err(w, "scan list %d does not exist" % c.scanlist)
        if c.mode == "FM":
            for nm in ("rx_tone", "tx_tone"):
                try:
                    v = C.tone_encode(getattr(c, nm))
                except (ValueError, C.CodeplugError) as e:
                    err(w, "%s: %s" % (nm, e))
                    continue
                if v and not v & 0x8000 and v not in C.CTCSS:
                    warn(w, "%s %s Hz is not a standard CTCSS tone" % (nm, getattr(c, nm)))
            if c.trunk:
                err(w, "trunk flag only for DMR (Tier III) / P25 channels")
        else:
            if c.wide:
                err(w, "25 kHz bandwidth is FM only")
            if c.rx_tone or c.tx_tone:
                err(w, "CTCSS/DCS only on FM channels")
        if c.mode != "FM":
            if c.vocoder not in C.MODE_VOCODERS.get(c.mode, ["auto"]):
                err(w, "vocoder %r not usable in %s (%s)" % (c.vocoder, c.mode, ", ".join(C.MODE_VOCODERS[c.mode])))
            if c.key is not None and not 0 <= c.key < len(cp.keys):
                err(w, "encryption key %d does not exist" % c.key)
            elif c.key is not None:
                kk = cp.keys[c.key].kind.split("_")[0]
                if kk != {"P25P2": "P25"}.get(c.mode, c.mode):
                    err(w, "key %r is a %s key, channel is %s" % (cp.keys[c.key].name, kk, c.mode))
        if c.mode == "NXDN" and c.nxdn_rate not in (4800, 9600):
            err(w, "NXDN rate %r (4800 / 9600)" % c.nxdn_rate)
        if c.mode == "YSF":
            if c.dgid_tx is not None and not 0 <= c.dgid_tx <= 99:
                err(w, "TX DG-ID %d (0..99)" % c.dgid_tx)
            if c.ysf_mode not in C.YSF_MODES:
                err(w, "YSF mode %r" % c.ysf_mode)
        if c.mode == "DSTAR" and c.dstar_rpt is not None and not 0 <= c.dstar_rpt < len(cp.dstar_rpts):
            err(w, "D-STAR repeater %d does not exist" % c.dstar_rpt)
        if c.talkaround and not c.tx_hz:
            warn(w, "talkaround on an RX-only channel")
        if c.mode == "DMR" and c.tdma_direct and c.tx_hz and c.tx_hz != c.rx_hz and not c.talkaround:
            warn(w, "TDMA direct on a duplex channel (simplex or talkaround only)")
        if c.trunk and c.mode not in ("DMR", "P25", "P25P2", "NXDN"):
            err(w, "trunk flag on a %s channel" % c.mode)
        if c.mode == "DMR":
            if not 0 <= c.cc <= 15:
                err(w, "colour code %d (0..15)" % c.cc)
            if c.slot not in (1, 2):
                err(w, "time slot %d (1/2)" % c.slot)
            if not 0 <= c.tg <= 16776415:
                err(w, "talkgroup %d out of range" % c.tg)
        if c.mode in ("P25", "P25P2"):
            if not 0 <= c.nac <= 0xFFF:
                err(w, "NAC 0x%X (0..FFF)" % c.nac)
            if not 0 <= c.tg <= 65535:
                err(w, "P25 talkgroup %d (0..65535)" % c.tg)
            if not 0 <= c.wacn <= 0xFFFFF:
                err(w, "WACN 0x%X (20 bit)" % c.wacn)
            if not 0 <= c.sysid <= 0xFFF:
                err(w, "system ID 0x%X (12 bit)" % c.sysid)
            if c.mode == "P25P2":
                if c.slot not in (1, 2):
                    err(w, "time slot %d (1/2)" % c.slot)
                if not c.wacn and c.trunksys is None:
                    warn(w, "Phase 2 needs WACN + system ID for the scrambling seed")
        if c.mode == "NXDN":
            if not 0 <= c.ran <= 63:
                err(w, "RAN %d (0..63)" % c.ran)
            if not 0 <= c.tg <= 65535:
                err(w, "NXDN group %d (0..65535)" % c.tg)
        if c.mode == "DSTAR":
            for nm in ("ur", "rpt1", "rpt2"):
                if not DSTAR_CALL.match(getattr(c, nm) or ""):
                    err(w, "%s %r: up to 8 of A-Z 0-9 / space" % (nm.upper(), getattr(c, nm)))
        if c.mode == "YSF" and not 0 <= c.dgid <= 99:
            err(w, "DG-ID %d (0..99)" % c.dgid)
        if c.mode in ("DMR", "P25", "P25P2", "NXDN"):
            if c.contact is not None and not 0 <= c.contact < len(cp.contacts):
                err(w, "contact %d does not exist" % c.contact)
            if c.tglist is not None and not 0 <= c.tglist < len(cp.tglists):
                err(w, "TG list %d does not exist" % c.tglist)
        if c.mode in ("DMR", "P25", "P25P2", "NXDN") and c.trunksys is not None:
            if not 0 <= c.trunksys < len(cp.trunksys):
                err(w, "trunk system %d does not exist" % c.trunksys)
            else:
                t = cp.trunksys[c.trunksys]
                want = {"DMR": ("DMR_T3",), "NXDN": ("NXDN_C", "NXDN_D")}.get(c.mode, ("P25",))
                if t.type not in want:
                    err(w, "trunk system %r is %s, channel is %s" % (t.name, t.type, c.mode))
                if not c.trunk:
                    warn(w, "has a trunk system but the trunk flag is off (firmware sets it)")

    for k, lst in (("zone", cp.zones), ("scan list", cp.scanlists)):
        for i, z in enumerate(lst):
            w = "%s %d %s" % (k, i + 1, z.name[:10])
            if len(z.name) > 16:
                err(w, "name longer than 16")
            for m in z.channels:
                if not 0 <= m < nch:
                    err(w, "member channel %d does not exist" % m)
            if len(set(z.channels)) != len(z.channels):
                warn(w, "duplicate members")
            if k == "scan list":
                for p in (z.prio1, z.prio2):
                    if p is not None and not 0 <= p < nch:
                        err(w, "priority channel %d does not exist" % p)
    if len(cp.scanlists) > 254:
        err("scanlists", "more than 254 scan lists")
    for i, c in enumerate(cp.contacts):
        w = "contact %d %s" % (i + 1, c.name[:10])
        if c.kind not in C.CONTACT_KINDS:
            err(w, "kind %r" % c.kind)
        if c.mode not in C.CONTACT_MODES:
            err(w, "mode %r" % c.mode)
        hi = {"P25": 0xFFFFFF if c.kind == "private" else 65535, "NXDN": 65535}.get(c.mode, 16777215)
        if not 0 <= c.id <= hi:
            err(w, "id %d out of range for %s" % (c.id, c.mode))
    for i, t in enumerate(cp.tglists):
        w = "TG list %d %s" % (i + 1, t.name[:10])
        for m in t.contacts:
            if not 0 <= m < len(cp.contacts):
                err(w, "member contact %d does not exist" % m)
    for i, t in enumerate(cp.trunksys):
        w = "trunk %d %s" % (i + 1, t.name[:10])
        if t.type not in C.TRUNK_TYPES:
            err(w, "type %r (P25 / DMR_T3)" % t.type)
        if not t.control_channels:
            err(w, "no control channel")
        for f in t.control_channels:
            if not in_band(f):
                err(w, "control channel %.5f MHz out of band" % (f / 1e6))
        if t.tglist is not None and not 0 <= t.tglist < len(cp.tglists):
            err(w, "TG list %d does not exist" % t.tglist)
        if t.type == "P25" and (not 0 <= t.wacn <= 0xFFFFF or not 0 <= t.sysid <= 0xFFF or not 0 <= t.nac_cc <= 0xFFF):
            err(w, "WACN / system ID / NAC out of range")
        if t.type == "DMR_T3" and not 0 <= t.nac_cc <= 15:
            err(w, "colour code out of range")
        if t.type in ("NXDN_C", "NXDN_D") and not 0 <= t.nac_cc <= 63:
            err(w, "RAN out of range (0..63)")
        if not 0 <= t.rfss <= 255 or not 0 <= t.site <= 255:
            err(w, "RFSS / site 0..255")
        idens = [b.iden for b in t.bandplan]
        if len(set(idens)) != len(idens):
            err(w, "band plan identifiers repeat")
        for b in t.bandplan:
            if not 0 <= b.iden <= 15:
                err(w, "band plan identifier %d (0..15)" % b.iden)
            if not in_band(b.base_hz) and not 762000000 <= b.base_hz <= 870000000 + 100000000:
                warn(w, "band plan %d base %.5f MHz outside the radio's bands" % (b.iden, b.base_hz / 1e6))
            if not 0 < b.spacing_hz <= 125000 or not 0 < b.bw_hz <= 25000:
                err(w, "band plan %d spacing / bandwidth out of range" % b.iden)
            if b.tdma and b.slots not in (2, 4) or not b.tdma and b.slots != 1:
                err(w, "band plan %d: TDMA needs 2 (or 4) slots, FDMA 1" % b.iden)
    for i, k in enumerate(cp.keys):
        w = "key %d %s" % (i + 1, k.name[:10])
        if k.kind not in C.KEY_KINDS:
            err(w, "kind %r" % k.kind)
            continue
        try:
            kb = bytes.fromhex(k.hex)
        except ValueError:
            err(w, "key is not hex")
            continue
        if len(kb) != C.KEY_KINDS[k.kind]:
            err(w, "%s key must be %d bytes (%d hex digits), has %d" % (k.kind, C.KEY_KINDS[k.kind], 2 * C.KEY_KINDS[k.kind], len(kb)))
        if not 0 <= k.key_id <= 0xFFFF or not 0 <= k.algid <= 0xFF:
            err(w, "key ID 0..65535, ALGID 0..255")
    for i, r in enumerate(cp.dstar_rpts):
        w = "D-STAR rpt %d %s" % (i + 1, r.name[:10])
        for nm in ("rpt1", "rpt2"):
            if not DSTAR_CALL.match(getattr(r, nm) or ""):
                err(w, "%s %r: up to 8 of A-Z 0-9 / space" % (nm.upper(), getattr(r, nm)))
        for f in (r.rx_hz, r.tx_hz):
            if f and not in_band(f):
                err(w, "frequency %.5f MHz out of band" % (f / 1e6))
    g = cp.digi
    if g.ysf_mode not in C.YSF_MODES:
        err("digital", "YSF default mode %r" % g.ysf_mode)
    if not 0 <= g.ysf_wiresx_room <= 99999:
        err("digital", "Wires-X room 0..99999")
    if not 0 <= g.dstar_gps_interval_s <= 3600:
        err("digital", "D-PRS interval 0..3600 s")
    if g.dmr_t3_register or g.p25_register or g.nxdn_register:
        warn("digital", "registration needs TX; the cfw is receive-only on trunked systems today")
    from . import stock as ST
    ST.use(cp.model)
    for t in ST.RECORD:
        if t in cp.stock:
            for col, v, dv in zip(ST.TABLES[t]["columns"], cp.stock[t][0], ST.TABLES[t]["defaults"]):
                if dv.lstrip("-").isdigit() and v != "" and not re.match(r"^-?\d+(\.\d+)?$", v):
                    err("stock %s" % t, "%s = %r must be a number" % (ST.LABELS.get(col, col), v))
    try:
        n = len(C.encode(cp))
        region = C.REGION_SIZE if cp.model == "D890UV" else C.MODELS[cp.model]["region"]
        if n > region * 0.9:
            warn("size", "%d of %d bytes used" % (n, region))
    except Exception as e:                      # noqa: BLE001  (size / encoding problems)
        err("size", str(e))
    return out


def errors(issues):
    return [i for i in issues if i.level == "error"]
