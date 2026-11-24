"""Radio edits journal (cfw/app/cfwcp.c cfwcp_journal_write): the firmware writes radio-menu settings into the spare
zero bytes at the end of codeplug section 10 and keeps the header CRC valid with a 4-byte CRC fix entry. This test
does the same in Python (same algorithm as the C code) and checks that the CPS decodes the edits."""
import struct
import zlib

from cps import codeplug as C, stock as ST
from conftest import SYNTH

POLY = 0xEDB88320


def crc_step(c, b):
    c ^= b
    for _ in range(8):
        c = (c >> 1) ^ (POLY if c & 1 else 0)
    return c


def crc_unshift(c):
    return (((c ^ POLY) << 1) | 1) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF


def crc_unstep(c, b):
    for _ in range(8):
        c = crc_unshift(c)
    return c ^ b


def section(data, sid):
    n = struct.unpack_from("<H", data, 16)[0]
    for i in range(n):
        s, rs, cnt, off, _ = struct.unpack_from("<HHIII", data, 32 + 16 * i)
        if s == sid:
            return off, rs * cnt
    raise KeyError(sid)


def journal_start(sec):
    p = 0
    end = 0
    while p + 6 <= len(sec):
        t, c, r, ln = struct.unpack_from("<BBHH", sec, p)
        if t == 0xEE:
            return p
        if t == 0 and c == 0 and r == 0 and ln == 0:
            break
        p += 6 + ln
        end = p
    return (end + 3) & ~3


def firmware_journal(data, edits):
    """edits: [(table, col, row, text)] -> new codeplug bytes, as the firmware writes them"""
    b = bytearray(data)
    off, n = section(b, C.SEC_STOCK)
    js = journal_start(bytes(b[off:off + n]))
    jabs, jlen = off + js, n - js
    jb = bytearray(jlen)
    q = 0
    jb[q] = 0xEE
    q += 6
    for t, c, r, txt in edits:
        tb = txt.encode()
        jb[q:q + 6] = struct.pack("<BBHH", t, c, r, len(tb))
        jb[q + 6:q + 6 + len(tb)] = tb
        q += 6 + len(tb)
    jb[q] = 0xEF
    jb[q + 4] = 4
    fix = q + 6
    total, crc = struct.unpack_from("<II", b, 8)
    c = 0xFFFFFFFF
    for x in b[16:jabs]:
        c = crc_step(c, x)
    for x in jb[:fix]:
        c = crc_step(c, x)
    r = ~crc & 0xFFFFFFFF
    for i in range(total, jabs + jlen, -1):
        r = crc_unstep(r, b[i - 1])
    for i in range(jlen, fix + 4, -1):
        r = crc_unstep(r, jb[i - 1])
    for _ in range(32):
        r = crc_unshift(r)
    jb[fix:fix + 4] = struct.pack("<I", c ^ r)
    b[jabs:jabs + jlen] = jb
    return bytes(b)


def synth(model="D890UV"):
    cp = C.load(SYNTH)
    if cp.model != model:
        ST.convert_model(cp, model)
    return cp


def test_spare_only_for_radio():
    cp = synth()
    radio = C.encode(cp, for_radio=True)
    off, n = section(radio, C.SEC_STOCK)
    sec = radio[off:off + n]
    assert n - journal_start(sec) >= ST.STOCK_SPARE
    assert C.decode(radio).settings == cp.settings


def test_journal_decoded():
    for model in ("D890UV", "D168UV"):
        cp = synth(model)
        data = C.encode(cp, for_radio=True)
        opt = ST.TABLES["OptionalSetting"]["columns"]
        edits = [(21, opt.index("TOT"), 0, "4"), (21, opt.index("SQL1"), 0, "3"), (0xE0, 2, 0, "5"), (0xE2, 0, 3, "1"),
                 (21, opt.index("TOT"), 0, "2")]          # a later entry wins
        new = firmware_journal(data, edits)
        total, crc = struct.unpack_from("<II", new, 8)
        assert zlib.crc32(new[16:total]) & 0xFFFFFFFF == crc       # header untouched, CRC still valid
        off, n = section(data, C.SEC_STOCK)
        jabs = off + journal_start(data[off:off + n])
        assert new[:jabs] == data[:jabs] and len(new) == len(data)  # only the journal bytes changed
        cp2 = C.decode(new)
        o = cp2.stock["OptionalSetting"][0]
        assert o[opt.index("TOT")] == "2" and o[opt.index("SQL1")] == "3"
        assert cp2.settings.keys[2] == "monitor"
        assert cp2.channels[3].power == "mid"
        # the next CPS write folds the edits into the normal entries; the journal is empty again
        again = C.encode(cp2, for_radio=True)
        cp3 = C.decode(again)
        assert cp3.stock["OptionalSetting"] == cp2.stock["OptionalSetting"] and cp3.settings == cp2.settings
        off, n = section(again, C.SEC_STOCK)
        assert b"\xEE" not in again[off + journal_start(again[off:off + n]):off + n]


def test_new_key_functions_round_trip():
    cp = synth()
    cp.settings.keys = ["talkaround", "tx_power", "call_log", "gps_info", "scan", "monitor"]
    assert C.decode(C.encode(cp)).settings.keys == cp.settings.keys


def test_cfw_flags_from_journal():
    """Settings > Encryption (0xE0 col 6) and SMS format (col 7) edited on the radio read back into the settings
    flags (b4 / b5), and survive the next CPS write"""
    for model in ("D890UV", "D168UV"):
        cp = synth(model)
        assert not cp.settings.encryption and not cp.settings.sms_msms
        new = firmware_journal(C.encode(cp, for_radio=True), [(0xE0, 6, 0, "1"), (0xE0, 7, 0, "1")])
        cp2 = C.decode(new)
        assert cp2.settings.encryption and cp2.settings.sms_msms
        cp3 = C.decode(C.encode(cp2, for_radio=True))
        assert cp3.settings.encryption and cp3.settings.sms_msms
        flags = struct.unpack_from("<H", C.encode(cp2), section(C.encode(cp2), C.SEC_SETTINGS)[0] + 18)[0]
        assert flags & 0x30 == 0x30
