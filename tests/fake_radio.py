"""Python model of cfw/app/prog.c + cfwcp.c (flash region, program mode, R/W/END) for link tests."""
import socket
import struct
import threading
import zlib

REGION = 0x20000


class FakeCfwRadio:
    def __init__(self, write_protected=False, ident=b"D890CFW"):
        self.flash = bytearray(b"\0" * REGION)
        self.wp = write_protected
        self.ident = ident
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.erased = set()
        self.writes = 0
        self.order = []
        threading.Thread(target=self._serve, daemon=True).start()

    def valid(self):
        f = self.flash
        if f[:4] != b"D8CP":
            return False
        total, crc = struct.unpack_from("<II", f, 8)
        return 32 <= total <= REGION and zlib.crc32(bytes(f[16:total])) & 0xFFFFFFFF == crc

    def _serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._conn, args=(c,), daemon=True).start()

    def _conn(self, c):
        buf = b""
        active = False

        def need(n):
            nonlocal buf
            while len(buf) < n:
                d = c.recv(4096)
                if not d:
                    raise EOFError
                buf += d
            out, buf = buf[:n], buf[n:]
            return out
        try:
            while True:
                b = need(1)
                if b == b"P":
                    if need(6) == b"ROGRAM":
                        active = True
                        self.erased = set()
                        c.sendall(b"QX\x06")
                elif not active:
                    continue
                elif b == b"\x02":
                    caps = 1 | (4 if self.wp else 2)
                    c.sendall(b"I" + self.ident + b"\0" + bytes([1, 0, 1, caps, 0, 128, 6]))
                elif b == b"R":
                    a, n = struct.unpack(">IB", need(5))
                    if a >= 0xF00000:
                        total = struct.unpack_from("<I", self.flash, 8)[0] if self.valid() else 0
                        crc = struct.unpack_from("<I", self.flash, 12)[0] if self.valid() else 0
                        info = b"CFWI" + struct.pack("<8I", 1 | 1 << 16, 0x081C0000, REGION, total, crc, 0, 0, 0)
                        info += bytes([self.valid(), self.wp, 1, 0]) + b"fake".ljust(24, b"\0")
                        data = info[a - 0xF00000:a - 0xF00000 + n]
                    else:
                        data = bytes(self.flash[a:a + n])
                    f = struct.pack(">IB", a, n) + data
                    c.sendall(b"W" + f + bytes([sum(f) & 0xFF, 6]))
                elif b == b"W":
                    h = need(5)
                    a, n = struct.unpack(">IB", h)
                    data = need(n)
                    cs, end = need(2)
                    ok = (sum(h + data) & 0xFF) == cs and end == 6 and not self.wp and a % 16 == 0 and n % 16 == 0 \
                        and a + n <= REGION
                    if ok:
                        for pg in range(a // 0x2000, (a + n - 1) // 0x2000 + 1):
                            if pg not in self.erased:
                                self.flash[pg * 0x2000:(pg + 1) * 0x2000] = b"\xff" * 0x2000
                                self.erased.add(pg)
                        self.flash[a:a + n] = data
                        self.writes += 1
                        self.order.append(a)
                    c.sendall(b"\x06" if ok else b"\x15")
                elif b == b"E":
                    need(2)
                    active = False
                    c.sendall(b"\x06" if (not self.erased or self.valid()) else b"\x15")
        except (EOFError, OSError):
            c.close()

    def close(self):
        self.srv.close()
