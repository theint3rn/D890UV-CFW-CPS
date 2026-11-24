"""Radio link: the cfw programming protocol (cfw/app/prog.c) over TCP (emulator) or a serial port.

Ports:  tcp:HOST:PORT   emulator USART1 socket (Renode CreateServerSocketTerminal)
        /dev/ttyXXX     programming cable (115200 8N1, raw termios; no pyserial needed)
        COM3            Windows (kernel32 via ctypes, also in the .exe)
Safety: this module only speaks the codeplug protocol. It refuses radios that do not identify as the cfw
("D890CFW" on the D890UV, "D168CFW" on the D168UV; codeplug.MODELS), so a stock radio is never written, and it has no firmware / bootloader / NAND commands.
Serial (real hardware) writes additionally need allow_hardware=True (CLI: --allow-hardware), which is only to
be used once the owner has approved hardware writes (CLAUDE.md).
"""
import os
import select
import socket
import struct
import time

from . import codeplug as C

ACK, NAK = 0x06, 0x15
INFO_ADDR = 0x00F00000
CHUNK = 128


class LinkError(IOError):
    pass


class TcpPort:
    hardware = False

    def __init__(self, host, port, timeout=5.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.timeout = timeout

    def write(self, b):
        self.s.sendall(b)

    def read(self, n, timeout=None):
        out = b""
        end = time.time() + (timeout or self.timeout)
        while len(out) < n:
            left = end - time.time()
            if left <= 0:
                break
            r, _, _ = select.select([self.s], [], [], left)
            if not r:
                break
            chunk = self.s.recv(n - len(out))
            if not chunk:
                raise LinkError("connection closed")
            out += chunk
        return out

    def drain(self):
        while True:
            r, _, _ = select.select([self.s], [], [], 0.05)
            if not r or not self.s.recv(4096):
                return

    def close(self):
        self.s.close()


class SerialPort:
    hardware = True

    def __init__(self, path, baud=115200, timeout=5.0):
        import termios
        import tty
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(self.fd)
        a = termios.tcgetattr(self.fd)
        sp = getattr(termios, "B%d" % baud)
        a[4] = a[5] = sp
        a[2] |= termios.CLOCAL | termios.CREAD
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        self.timeout = timeout
        self.hardware = not os.path.realpath(path).startswith("/dev/pts/")   # a pty = emulator / test double

    def write(self, b):
        while b:
            try:
                n = os.write(self.fd, b)
                b = b[n:]
            except BlockingIOError:
                select.select([], [self.fd], [], 1)

    def read(self, n, timeout=None):
        out = b""
        end = time.time() + (timeout or self.timeout)
        while len(out) < n:
            left = end - time.time()
            if left <= 0:
                break
            r, _, _ = select.select([self.fd], [], [], left)
            if r:
                try:
                    out += os.read(self.fd, n - len(out))
                except BlockingIOError:
                    pass
        return out

    def drain(self):
        while True:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if not r:
                return
            try:
                os.read(self.fd, 4096)
            except BlockingIOError:
                return

    def close(self):
        os.close(self.fd)


class WinSerialPort:
    """Windows COM port (COM3, \\\\.\\COM12) through kernel32 with ctypes: no pyserial needed in the .exe."""
    hardware = True

    def __init__(self, name, baud=115200, timeout=5.0):
        import ctypes
        from ctypes import wintypes as W
        self.k = k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ct, self.W = ctypes, W
        path = name if name.startswith("\\\\.\\") else "\\\\.\\" + name
        k.CreateFileW.restype = W.HANDLE
        self.h = k.CreateFileW(path, 0xC0000000, 0, None, 3, 0, None)       # GENERIC_READ|WRITE, OPEN_EXISTING
        if self.h in (None, W.HANDLE(-1).value):
            raise LinkError("cannot open %s (error %d)" % (name, ctypes.get_last_error()))

        class DCB(ctypes.Structure):
            _fields_ = [("DCBlength", W.DWORD), ("BaudRate", W.DWORD), ("flags", W.DWORD), ("wReserved", W.WORD),
                        ("XonLim", W.WORD), ("XoffLim", W.WORD), ("ByteSize", ctypes.c_ubyte), ("Parity", ctypes.c_ubyte),
                        ("StopBits", ctypes.c_ubyte), ("XonChar", ctypes.c_char), ("XoffChar", ctypes.c_char),
                        ("ErrorChar", ctypes.c_char), ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
                        ("wReserved1", W.WORD)]

        class TIMEOUTS(ctypes.Structure):
            _fields_ = [(n, W.DWORD) for n in ("ReadIntervalTimeout", "ReadTotalTimeoutMultiplier", "ReadTotalTimeoutConstant",
                                               "WriteTotalTimeoutMultiplier", "WriteTotalTimeoutConstant")]
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        k.GetCommState(self.h, ctypes.byref(dcb))
        dcb.BaudRate, dcb.ByteSize, dcb.Parity, dcb.StopBits = baud, 8, 0, 0
        dcb.flags = 1                                    # fBinary, no flow control
        if not k.SetCommState(self.h, ctypes.byref(dcb)):
            raise LinkError("SetCommState %s failed (error %d)" % (name, ctypes.get_last_error()))
        to = TIMEOUTS(0xFFFFFFFF, 0xFFFFFFFF, 50, 0, 2000)  # ReadFile returns after <= 50 ms with what is there
        k.SetCommTimeouts(self.h, ctypes.byref(to))
        self.timeout = timeout

    def write(self, b):
        n = self.W.DWORD()
        if not self.k.WriteFile(self.h, b, len(b), self.ct.byref(n), None) or n.value != len(b):
            raise LinkError("serial write failed")

    def read(self, n, timeout=None):
        out = b""
        end = time.time() + (timeout or self.timeout)
        buf = self.ct.create_string_buffer(4096)
        got = self.W.DWORD()
        while len(out) < n and time.time() < end:
            if self.k.ReadFile(self.h, buf, min(4096, n - len(out)), self.ct.byref(got), None) and got.value:
                out += buf.raw[:got.value]
        return out

    def drain(self):
        time.sleep(0.05)
        self.k.PurgeComm(self.h, 0x0008)                 # PURGE_RXCLEAR

    def close(self):
        self.k.CloseHandle(self.h)


def open_port(spec, timeout=5.0):
    if spec.startswith("tcp:"):
        _, host, port = spec.split(":")
        return TcpPort(host or "localhost", int(port), timeout)
    if os.name == "nt":
        return WinSerialPort(spec, timeout=timeout)
    return SerialPort(spec, timeout=timeout)


class Radio:
    def __init__(self, port, log=None):
        self.p = port
        self.log = log or (lambda s: None)
        self.ident = None

    # ---- framing
    def _expect(self, n, what, timeout=None):
        b = self.p.read(n, timeout)
        if len(b) != n:
            raise LinkError("%s: got %d of %d bytes (%s)" % (what, len(b), n, b.hex()))
        return b

    def enter(self):
        self.p.drain()
        for attempt in range(3):
            self.p.write(b"PROGRAM")
            b = self.p.read(3, 2.0)
            if b == b"QX\x06":
                break
            self.p.drain()
        else:
            raise LinkError("no answer to PROGRAM (is the cfw running and the port right?)")
        self.p.write(b"\x02")
        r = self._expect(16, "identify")
        if r[0:1] != b"I" or r[-1] != ACK:
            raise LinkError("bad identify reply %s" % r.hex())
        idents = {v["ident"].encode(): m for m, v in C.MODELS.items()}
        if r[1:8] not in idents:
            raise LinkError("radio identifies as %r, not the cfw: refusing (this CPS is for the custom firmware "
                            "only; use the stock CPS for stock firmware)" % r[1:8].split(b"\0")[0])
        self.ident = {"fw": "%d.%d" % (r[9], r[10]), "cp_version": r[11], "caps": r[12],
                      "write_protected": bool(r[12] & 4), "max_kb": r[13] << 8 | r[14], "model": idents[r[1:8]]}
        if self.ident["cp_version"] != C.VERSION:
            raise LinkError("radio codeplug format v%d, this CPS writes v%d" % (self.ident["cp_version"], C.VERSION))
        self.log("radio: %s cfw %s, codeplug v%d, %d KB%s" % (self.ident["model"], self.ident["fw"], self.ident["cp_version"],
                                                          self.ident["max_kb"],
                                                          ", WRITE-PROTECTED build" if self.ident["write_protected"] else ""))
        return self.ident

    def read_block(self, addr, n):
        for attempt in range(3):
            self.p.write(b"R" + struct.pack(">IB", addr, n))
            r = self.p.read(8 + n)
            if len(r) == 8 + n and r[0:1] == b"W" and struct.unpack(">IB", r[1:6]) == (addr, n) and r[-1] == ACK \
                    and sum(r[1:6 + n]) & 0xFF == r[6 + n]:
                return r[6:6 + n]
            self.p.drain()
        raise LinkError("read 0x%08X+%d failed" % (addr, n))

    def write_block(self, addr, data):
        assert len(data) % 16 == 0 and addr % 16 == 0 and 0 < len(data) <= 240
        f = struct.pack(">IB", addr, len(data)) + data
        self.p.write(b"W" + f + bytes([sum(f) & 0xFF, ACK]))
        r = self._expect(1, "write ack")
        if r[0] != ACK:
            raise LinkError("radio refused write at 0x%X (%s)" % (addr, "write-protected build"
                                                                  if self.ident and self.ident["write_protected"] else
                                                                  "checksum / range / flash verify"))

    def end(self):
        self.p.write(b"END")
        r = self._expect(1, "END", 10)
        return r[0] == ACK

    def info(self):
        b = self.read_block(INFO_ADDR, 64)
        if b[:4] != b"CFWI":
            raise LinkError("bad info block")
        v = struct.unpack_from("<8I", b, 4)
        return {"link": v[0] & 0xFFFF, "cp_version": v[0] >> 16, "base": v[1], "size": v[2], "len": v[3],
                "crc": v[4], "generation": v[5], "cp_channels": v[6], "channels": v[7], "valid": bool(b[36]),
                "write_protected": bool(b[37]), "fw": b[40:64].split(b"\0")[0].decode("ascii", "replace")}

    # ---- whole codeplug
    def read_codeplug(self, progress=None):
        """Returns the raw codeplug bytes (b'' if the radio holds none)."""
        inf = self.info()
        if not inf["valid"]:
            return b""
        n = inf["len"]
        out = b""
        for a in range(0, n, CHUNK):
            out += self.read_block(a, min(CHUNK, n - a))
            if progress:
                progress(len(out), n)
        return out

    def write_codeplug(self, data, progress=None):
        if len(data) % 16:
            data += b"\0" * (-len(data) % 16)
        blocks = list(range(0, len(data), CHUNK))
        blocks = blocks[1:] + blocks[:1]          # header block last: an aborted write leaves no valid codeplug
        for k, a in enumerate(blocks):
            self.write_block(a, data[a:a + CHUNK])
            if progress:
                progress(k + 1, len(blocks))


def with_radio(spec, fn, log=print, allow_hardware=False, writing=False, timeout=5.0):
    port = open_port(spec, timeout)
    try:
        if writing and port.hardware and not allow_hardware:
            raise LinkError("refusing to write to a hardware serial port without --allow-hardware "
                            "(real-radio writes need the owner's OK, see README)")
        r = Radio(port, log)
        r.enter()
        return fn(r)          # fn ends program mode with r.end()
    finally:
        port.close()
