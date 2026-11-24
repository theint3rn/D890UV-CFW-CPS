#!/usr/bin/env python3
"""WebSocket <-> radio byte bridge for the web CPS (browsers cannot open a pty or a TCP socket).

  python3 tools/ws_bridge.py --target tcp:localhost:3471          # emulator USART1 (emu_roundtrip / run.py --extra)
  python3 tools/ws_bridge.py --target /dev/pts/5                  # a pty
  python3 tools/ws_bridge.py --target tcp:localhost:3471 --http 8000   # also serve web/ at http://localhost:8000/

Then pick "WebSocket bridge" (ws://localhost:8765) in the web CPS. Bytes are passed through unchanged; the codeplug
protocol and its safety checks are in the page (web/js/link.js). Only localhost is bound. Standard library only.
"""
import argparse
import base64
import functools
import hashlib
import http.server
import os
import select
import socket
import struct
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), "web")
GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def open_target(spec):
    if spec.startswith("tcp:"):
        _, host, port = spec.split(":")
        s = socket.create_connection((host or "localhost", int(port)))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return s.fileno(), (lambda b: s.sendall(b)), s.close, s
    import termios
    import tty
    fd = os.open(spec, os.O_RDWR | os.O_NOCTTY)
    tty.setraw(fd)
    a = termios.tcgetattr(fd)
    a[4] = a[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, a)
    return fd, (lambda b: os.write(fd, b)), (lambda: os.close(fd)), None


def ws_handshake(c):
    req = b""
    while b"\r\n\r\n" not in req:
        d = c.recv(4096)
        if not d:
            return False
        req += d
    key = None
    for line in req.split(b"\r\n"):
        if line.lower().startswith(b"sec-websocket-key:"):
            key = line.split(b":", 1)[1].strip()
    if not key:
        c.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        return False
    acc = base64.b64encode(hashlib.sha1(key + GUID).digest())
    c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
              b"Sec-WebSocket-Accept: " + acc + b"\r\n\r\n")
    return True


def ws_send(c, data, op=2):
    n = len(data)
    hdr = bytes([0x80 | op]) + (bytes([n]) if n < 126 else bytes([126]) + struct.pack(">H", n) if n < 65536
                                else bytes([127]) + struct.pack(">Q", n))
    c.sendall(hdr + data)


class WsReader:
    def __init__(self, c):
        self.c, self.buf = c, b""

    def frames(self, data):
        """feed raw bytes, yield (opcode, payload)"""
        self.buf += data
        while True:
            b = self.buf
            if len(b) < 2:
                return
            op, ln, masked = b[0] & 0x0F, b[1] & 0x7F, b[1] & 0x80
            p = 2
            if ln == 126:
                if len(b) < 4:
                    return
                ln, p = struct.unpack(">H", b[2:4])[0], 4
            elif ln == 127:
                if len(b) < 10:
                    return
                ln, p = struct.unpack(">Q", b[2:10])[0], 10
            mask = b[p:p + 4] if masked else b"\0\0\0\0"
            p += 4 if masked else 0
            if len(b) < p + ln:
                return
            pay = bytes(x ^ mask[i % 4] for i, x in enumerate(b[p:p + ln]))
            self.buf = b[p + ln:]
            yield op, pay


def serve_client(c, target, verbose):
    if not ws_handshake(c):
        c.close()
        return
    try:
        fd, write, close, keep = open_target(target)
    except OSError as e:
        print("target %s: %s" % (target, e), flush=True)
        ws_send(c, b"", 8)
        c.close()
        return
    print("client connected, bridged to %s" % target, flush=True)
    rd = WsReader(c)
    try:
        while True:
            r, _, _ = select.select([c, fd], [], [])
            if c in r:
                d = c.recv(65536)
                if not d:
                    break
                for op, pay in rd.frames(d):
                    if op == 8:
                        raise EOFError
                    if op == 9:
                        ws_send(c, pay, 10)
                    elif op in (1, 2) and pay:
                        if verbose:
                            print(">", pay[:32].hex(), flush=True)
                        write(pay)
            if fd in r:
                d = os.read(fd, 65536) if keep is None else keep.recv(65536)
                if not d:
                    break
                if verbose:
                    print("<", d[:32].hex(), flush=True)
                ws_send(c, d)
    except (EOFError, OSError):
        pass
    finally:
        close()
        c.close()
        print("client closed", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="tcp:HOST:PORT or a pty / serial device")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--http", type=int, default=0, help="also serve web/ on this port")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if a.http:
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=WEB)
        h.log_message = lambda *x: None
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.http), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("web CPS on http://localhost:%d/" % a.http, flush=True)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", a.port))
    s.listen(4)
    print("bridge ws://localhost:%d -> %s" % (a.port, a.target), flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=serve_client, args=(c, a.target, a.verbose), daemon=True).start()


if __name__ == "__main__":
    sys.exit(main())
