"""Import channels from a stock D890UV memory image (what the stock CPS writes; CPS address == NAND address).

Inputs: a raw NAND dump starting at address 0 (e.g. emu/images/extflash_low16M.bin) or the fake-radio capture
`writes.bin` (records: u32 addr LE, u16 len LE, data) from emu/fake_radio_cps.py.
Channel record layout = cfw/app/channels.c: 128 bytes, 128 per bank, bank b at 0x01000000 + b * 0x80000:
  +0 RX BCD BE 10 Hz, +4 offset BCD, +8 type/power/bw/shift, +9 tone flags, +A TX tone idx, +B RX tone idx,
  +0x14 contact index LE, +0x20 colour code, +0x21 bit0 slot 2, +0x44 name UTF-16LE (16).
Only channels are decoded (zones / TG table of the D890UV image are not mapped yet; use the .rdt importer).
"""
import struct

from . import codeplug as C

CP_BASE, CP_BANK, CP_BANKS, CP_PER, CP_REC = 0x01000000, 0x80000, 32, 128, 128


def _bcd(b):
    v = 0
    for x in b:
        hi, lo = x >> 4, x & 15
        if hi > 9 or lo > 9:
            return None
        v = v * 100 + hi * 10 + lo
    return v * 10


def load_image(path):
    data = open(path, "rb").read()
    if path.endswith("writes.bin") or (len(data) > 6 and struct.unpack_from("<I", data)[0] >= CP_BASE
                                       and struct.unpack_from("<I", data)[0] < 0x20000000):
        mem = {}
        i = 0
        while i + 6 <= len(data):
            a, n = struct.unpack_from("<IH", data, i)
            mem[a] = data[i + 6:i + 6 + n]
            i += 6 + n

        def read(addr, n):
            out = bytearray(b"\xff" * n)
            base = addr & ~0xF
            for a in range(base, addr + n, 16):
                blk = mem.get(a)
                if blk:
                    for k, x in enumerate(blk):
                        if addr <= a + k < addr + n:
                            out[a + k - addr] = x
            return bytes(out)
        return read

    def read(addr, n):
        return data[addr:addr + n].ljust(n, b"\xff")
    return read


def import_nand(path):
    read = load_image(path)
    cp = C.Codeplug()
    for bank in range(CP_BANKS):
        blk = read(CP_BASE + bank * CP_BANK, CP_PER * CP_REC)
        found = 0
        for k in range(CP_PER):
            r = blk[k * CP_REC:(k + 1) * CP_REC]
            rx = _bcd(r[0:4])
            if not rx or not (136000000 <= rx <= 174000000 or 400000000 <= rx <= 480000000):
                continue
            found += 1
            off = _bcd(r[4:8]) or 0
            sh = r[8] >> 6
            c = C.Channel(rx_hz=rx, tx_hz=rx + off if sh == 1 else rx - off if sh == 2 else rx)
            c.name = r[0x44:0x64].decode("utf-16le", "replace").split("\0")[0][:16]
            c.name = "".join(ch if 0x20 <= ord(ch) < 0x7F else "?" for ch in c.name)
            if r[8] & 3:
                c.mode = "DMR"
                c.cc = r[0x20] & 15
                c.slot = (r[0x21] & 1) + 1
                c.tg = 91
            else:
                c.mode = "FM"
                c.wide = bool(r[8] & 0x10)
                if r[9] & 4 and r[10] < len(C.CTCSS):
                    v = C.CTCSS[r[10]]
                    c.tx_tone = "%d.%d" % (v // 10, v % 10)
                if r[9] & 1 and r[11] < len(C.CTCSS):
                    v = C.CTCSS[r[11]]
                    c.rx_tone = "%d.%d" % (v // 10, v % 10)
            cp.channels.append(C.normalize_channel(c))
    return cp, ["D890UV memory image: %d channels (zones / talkgroups not decoded from this format)" % len(cp.channels)]
