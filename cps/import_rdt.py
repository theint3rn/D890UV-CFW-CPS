"""Import an AnyTone D878UV / D890UV CPS codeplug file (.rdt, "V1270 ... D878UV ... V100" header).

The .rdt is not a memory image: the CPS serialises its tables field by field, little endian, strings
NUL-terminated (max 16, no NUL when full). Layout decoded from a real D878UV codeplug file and
cross-checked against the D890UV memory image the stock D890UV CPS wrote for it (all 1405 channel names and
the frequency / tone / colour-code / slot / contact / scan-list fields agree); see docs/CODEPLUG.md "RDT".

  general settings (0x00-0xF3 in V1270 files; power-on text at 0x7F)
  channels   u16 count, then per channel:
             u16 slot, u32 rx (10 Hz), u8 shift (0 none, 1 +, 2 -), u32 offset (10 Hz),
             u8 type (0 A, 1 D, 2 A+D, 3 D+A), u8 power (0..3), u8 bw (1 = 25 kHz), u8, u8 ?, u8, u8 ?,
             u8 rx sig (0 off, 1 CTCSS, 2 DCS), u8 rx CTCSS idx, u16 rx DCS, u8 tx sig, u8 tx CTCSS idx, u16 tx DCS,
             u16 custom CTCSS (0.1 Hz), u16 contact (0-based TG list index), u16 ?, u8 ?, u8 ?, u8 scan list (FF none),
             5 x u8, u8 colour code, u8 slot (0 = TS1), 5 x u8, name, 12 x u8
  radio IDs  u8 count, {u8 idx, u24 id, name}
  zones      u8 count, {u8 idx, u8 n, n+2 x u16 (members, then A / B channel), name}
  scan lists u8 count, {u8 idx, name, 11 x u8, u8 n, n x (u8, u16 channel slot)}
  TG list    u8, u16, u8, then {u24 id, u16 idx (1-based), u8 type (0x10 group, 0 private, 0x20 all),
             six 7-bit packed NUL-terminated strings (name, city, call, state, country, remark), byte padded}
             until the idx sequence breaks
  user DB    4 bytes, then the same record format (RadioID.net users; counted, not imported)
  SMS, FM broadcast list, then RX group lists: u8 count, {u8 idx, name, u8 n, n x u16 TG list index (0-based)}
Unknown bytes are ignored; the parser checks every count/sequence and reports what it could not read.
"""
import struct

from . import codeplug as C

POWER = ["low", "mid", "high", "turbo"]


class RdtError(ValueError):
    pass


class _R:
    def __init__(self, d):
        self.d = d

    def cstr(self, p, mx=16):
        e = p
        while e < p + mx and e < len(self.d) and self.d[e] != 0:
            e += 1
        s = self.d[p:e].decode("latin1")
        if e < p + mx:
            e += 1
        return s, e

    def s7(self, p, nstr=6):
        """nstr 7-bit packed NUL-terminated strings; returns (list, end offset)."""
        d = self.d
        bits = n = 0
        out, cur, q = [], [], p
        while len(out) < nstr:
            while n < 7:
                if q >= len(d):
                    raise RdtError("packed string runs past the end")
                bits |= d[q] << n
                n += 8
                q += 1
            c = bits & 0x7F
            bits >>= 7
            n -= 7
            if c == 0:
                out.append("".join(cur))
                cur = []
            else:
                cur.append(chr(c))
                if len(cur) > 200:
                    raise RdtError("packed string too long")
        return out, q


def _ascii(s, n=16):
    s = "".join(ch if 0x20 <= ord(ch) < 0x7F else "?" for ch in s)
    return s[:n]


def _chan_ok(d, p):
    if p + 48 > len(d):
        return False
    slot, rx, sh, off, ty = struct.unpack_from("<HIBIB", d, p)
    return 1000000 <= rx <= 100000000 and sh <= 2 and ty <= 3


def _find_channels(d):
    """Offset of the channel count (0xF4 in V1270 files; searched otherwise)."""
    cands = [0xF4] + list(range(0x40, 0x400))
    for p in cands:
        n = struct.unpack_from("<H", d, p)[0]
        if not 1 <= n <= 4000:
            continue
        q, ok, last = p + 2, True, -1
        for _ in range(min(n, 8)):
            if not _chan_ok(d, q) or struct.unpack_from("<H", d, q)[0] <= last:
                ok = False
                break
            last = struct.unpack_from("<H", d, q)[0]
            name, q = _R(d).cstr(q + 48)
            if not name or any(not 0x20 <= ord(c) < 0x7F for c in name):
                ok = False
                break
            q += 12
        if ok:
            return p
    raise RdtError("channel table not found")


def parse(d):
    """Parse .rdt bytes -> dict with the raw tables (slot numbers as in the file)."""
    if d[9:15] not in (b"D878UV", b"D890UV", b"D868UV", b"D578UV"):
        raise RdtError("not an AnyTone CPS .rdt file (model %r)" % d[9:15])
    r = _R(d)
    res = {"model": d[9:15].decode(), "cps_version": d[0:5].decode("latin1"), "warnings": []}
    res["power_on_text"] = r.cstr(0x7F)[0] if d[:5] == b"V1270" else ""
    p = _find_channels(d)
    n = struct.unpack_from("<H", d, p)[0]
    p += 2
    chans = []
    for _ in range(n):
        if not _chan_ok(d, p):
            raise RdtError("channel record at 0x%X unreadable" % p)
        f = d[p:p + 48]
        name, p = r.cstr(p + 48)
        tail = d[p:p + 12]
        p += 12
        slot, rx, sh, off = struct.unpack_from("<HIBI", f)
        chans.append({
            "slot": slot, "rx": rx * 10, "shift": sh, "offset": off * 10, "type": f[11], "power": f[12] & 3,
            "wide": f[13] == 1, "rx_sig": f[18], "rx_ctcss": f[19], "rx_dcs": struct.unpack_from("<H", f, 20)[0],
            "tx_sig": f[22], "tx_ctcss": f[23], "tx_dcs": struct.unpack_from("<H", f, 24)[0],
            "custom_ctcss": struct.unpack_from("<H", f, 26)[0], "contact": struct.unpack_from("<H", f, 28)[0],
            "scanlist": f[34], "cc": f[40], "slot2": f[41] & 1, "name": name, "raw": f + tail})
    res["channels"] = chans
    # radio IDs
    ids = []
    nid = d[p]
    p += 1
    for _ in range(nid):
        idx = d[p]
        rid = d[p + 1] | d[p + 2] << 8 | d[p + 3] << 16
        name, p = r.cstr(p + 4)
        ids.append({"idx": idx, "id": rid, "name": name})
    res["radio_ids"] = ids
    # zones
    zones = []
    nz = d[p]
    p += 1
    for i in range(nz):
        idx, m = d[p], d[p + 1]
        if idx != i:
            raise RdtError("zone %d: index %d at 0x%X" % (i, idx, p))
        mem = list(struct.unpack_from("<%dH" % (m + 2), d, p + 2))
        name, p = r.cstr(p + 2 + 2 * (m + 2))
        zones.append({"name": name, "members": mem[:m], "a": mem[m], "b": mem[m + 1]})
    res["zones"] = zones
    # scan lists
    sls = []
    ns = d[p]
    p += 1
    for i in range(ns):
        if d[p] != i:
            raise RdtError("scan list %d: index %d at 0x%X" % (i, d[p], p))
        name, p = r.cstr(p + 1)
        hdr = d[p:p + 11]
        m = d[p + 11]
        p += 12
        mem = [struct.unpack_from("<H", d, p + 3 * k + 1)[0] for k in range(m)]
        p += 3 * m
        sls.append({"name": name, "members": mem, "hdr": hdr})
    res["scanlists"] = sls
    # talkgroup / digital contact list
    p += 4
    tgs = []
    while True:
        try:
            cid = d[p] | d[p + 1] << 8 | d[p + 2] << 16
            idx, ty = struct.unpack_from("<HB", d, p + 3)
            if idx != len(tgs) + 1:
                break
            strs, q = r.s7(p + 6)
        except (RdtError, IndexError, struct.error):
            break
        tgs.append({"id": cid, "type": ty, "name": strs[0]})
        p = q
    res["talkgroups"] = tgs
    # user database (same record format, after a 4-byte header): counted only
    p += 4
    nusers = 0
    while p + 6 < len(d):
        try:
            idx = struct.unpack_from("<H", d, p + 3)[0]
            if idx != (nusers + 1) & 0xFFFF:
                break
            _, p = r.s7(p + 6)
        except (RdtError, IndexError, struct.error):
            break
        nusers += 1
    res["user_db_entries"] = nusers
    res["rx_group_lists"] = _rx_group_lists(d, r, p, len(tgs), res["warnings"])
    return res


def _rx_group_lists(d, r, p, ntg, warnings):
    """SMS (u8 count?, {u8 idx, string}), FM list ({u8 idx, 01, u16}), u32 FM VFO, then the RX group lists."""
    try:
        while d[p] == 0 and d[p + 1] == 0:      # padding before the SMS list
            p += 1
        # SMS: u8 count, {u8 idx, NUL-terminated text}
        nsms = d[p + 1] if d[p] == 0 else d[p]
        q = p + 2 if d[p] == 0 else p + 1
        for i in range(nsms):
            if d[q] != i:
                raise RdtError("sms")
            _, q = r.cstr(q + 1, 200)
        # FM broadcast memory: u8 count, {u8 idx, u8 flag, u16 freq/10 kHz}
        q += 1
        i = 0
        while d[q] == i and d[q + 1] == 1:
            q += 4
            i += 1
        q += 4                                   # FM VFO
        n = d[q]
        q += 1
        out = []
        for k in range(n):
            if d[q] != k:
                raise RdtError("rx group list index")
            name, q = r.cstr(q + 1)
            m = d[q]
            mem = list(struct.unpack_from("<%dH" % m, d, q + 1))
            q += 1 + 2 * m
            if any(x >= ntg for x in mem):
                raise RdtError("rx group list member out of range")
            out.append({"name": name, "members": mem})
        return out
    except (RdtError, IndexError, struct.error) as e:
        warnings.append("RX group lists not read (%s)" % e)
        return []


def _tone(sig, idx, dcs, custom):
    if sig == 1:
        if idx < len(C.CTCSS):
            v = C.CTCSS[idx]
        else:
            v = custom
        return "%d.%d" % (v // 10, v % 10) if v else None
    if sig == 2:
        return "D%03o%s" % (dcs & 0x1FF, "I" if dcs & 0x200 else "N")
    return None


def to_codeplug(res, digital_as="DMR"):
    """Raw tables -> cfw Codeplug. Channel order = slot order; zones/scan lists are remapped to it."""
    cp = C.Codeplug()
    s = cp.settings
    if res["radio_ids"]:
        s.dmr_id = res["radio_ids"][0]["id"]
    s.radio_name = _ascii(res.get("power_on_text", "") or "D890UV cfw")
    s.callsign = "N0CALL"
    for t in res["talkgroups"]:
        kind = {0x10: "group", 0x00: "private", 0x20: "all"}.get(t["type"], "group")
        cp.contacts.append(C.Contact(name=_ascii(t["name"]), id=t["id"], kind=kind, mode="DMR"))
    slot2idx = {}
    for i, ch in enumerate(sorted(res["channels"], key=lambda c: c["slot"])):
        slot2idx[ch["slot"]] = i
        c = C.Channel(name=_ascii(ch["name"]), rx_hz=ch["rx"], power=POWER[ch["power"]])
        c.tx_hz = ch["rx"] + ch["offset"] if ch["shift"] == 1 else ch["rx"] - ch["offset"] if ch["shift"] == 2 else ch["rx"]
        digital = ch["type"] in (1, 3)
        if digital:
            c.mode = digital_as
            c.cc = ch["cc"] & 15
            c.slot = 2 if ch["slot2"] else 1
            if ch["contact"] < len(cp.contacts):
                c.contact = ch["contact"]
                c.tg = cp.contacts[ch["contact"]].id
        else:
            c.mode = "FM"
            c.wide = ch["wide"]
            c.rx_tone = _tone(ch["rx_sig"], ch["rx_ctcss"], ch["rx_dcs"], ch["custom_ctcss"])
            c.tx_tone = _tone(ch["tx_sig"], ch["tx_ctcss"], ch["tx_dcs"], ch["custom_ctcss"])
        c.scanlist = ch["scanlist"] if ch["scanlist"] < len(res["scanlists"]) else None
        cp.channels.append(C.normalize_channel(c))
    for z in res["zones"]:
        cp.zones.append(C.Zone(_ascii(z["name"]), [slot2idx[m] for m in z["members"] if m in slot2idx]))
    for sl in res["scanlists"]:
        cp.scanlists.append(C.ScanList(_ascii(sl["name"]), [slot2idx[m] for m in sl["members"] if m in slot2idx]))
    for g in res["rx_group_lists"]:
        cp.tglists.append(C.TgList(_ascii(g["name"]), list(g["members"])))
    return cp


def import_rdt(path, digital_as="DMR"):
    """Returns (Codeplug, report lines)."""
    res = parse(open(path, "rb").read())
    cp = to_codeplug(res, digital_as)
    rep = ["%s CPS %s file: %d channels, %d zones, %d scan lists, %d talkgroups/contacts, %d RX group lists, "
           "%d radio IDs" % (res["model"], res["cps_version"], len(res["channels"]), len(res["zones"]),
                             len(res["scanlists"]), len(res["talkgroups"]), len(res["rx_group_lists"]),
                             len(res["radio_ids"])),
           "user database: %d entries (not imported: cfw has no contact database)" % res["user_db_entries"]]
    rep += res["warnings"]
    return cp, rep
