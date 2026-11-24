#!/usr/bin/env python3
"""Web CPS against the cfw in Renode: emulator USART1 -> TCP -> tools/ws_bridge.py -> headless Chromium page
(web/test/browser_test.mjs, transport "ws"). Then checks the radio screen shows the channel the page wrote, power-cycles
and reads back with the Python CPS (must equal what the page wrote).

  NODE_PATH=<dir with playwright-core> python3 tools/web_emu_test.py [--elf ../cfw/build/cfw.elf]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EMU = os.path.join(ROOT, "..", "emu")
sys.path[:0] = [ROOT, EMU, HERE]
from cps import codeplug as C, ops  # noqa: E402
from ctl import talk  # noqa: E402
from emu_roundtrip import wait_port, sym  # noqa: E402

NAME = "WEB CPS EMU"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", default=os.path.join(ROOT, "..", "cfw", "build", "cfw.elf"))
    ap.add_argument("--monitor", type=int, default=1281)
    ap.add_argument("--uart", type=int, default=3472)
    ap.add_argument("--ws", type=int, default=8766)
    a = ap.parse_args()
    out = os.path.join(EMU, "out", "cps_web")
    txt = os.path.join(out, "text.txt")
    subprocess.check_call([sys.executable, os.path.join(EMU, "run.py"), "--elf", a.elf, "--seconds", "4", "--name", "cps_web",
                           "--serve", str(a.monitor),
                           "--extra", 'emulation CreateServerSocketTerminal %d "progterm" false' % a.uart,
                           "--extra", "connector Connect sysbus.usart1 progterm"])
    if not wait_port(a.monitor + 1):
        print("FAIL: emulator did not come up")
        return 1
    hook = ("cpu AddHook 0x%08X \"import System; p = self.GetRegister(2).RawValue; "
            "s = ''.join([chr(self.Bus.ReadByte(p + i)) for i in range(40)]).split(chr(0))[0]; "
            "System.IO.File.AppendAllText('%s', s + chr(10))\"") % (sym(a.elf, "gfx_text") & ~1, txt)
    bridge = subprocess.Popen([sys.executable, os.path.join(HERE, "ws_bridge.py"), "--target", "tcp:127.0.0.1:%d" % a.uart,
                               "--port", str(a.ws)])
    ok = True
    res = []

    def step(n, c, d=""):
        nonlocal ok
        ok &= bool(c)
        res.append("%s %s %s" % ("PASS" if c else "FAIL", n, d))
        print(res[-1], flush=True)

    def screen(secs=1.5):
        if os.path.exists(txt):
            os.remove(txt)
        time.sleep(secs)
        return open(txt).read() if os.path.exists(txt) else ""

    def shot(name):
        p = os.path.join(out, name + ".ppm")
        talk(a.monitor, ["lcd Screenshot @%s" % p])
        subprocess.call([sys.executable, "-I", os.path.join(EMU, "ppm2png.py"), p, os.path.join(ROOT, "screens", name + ".png")])

    try:
        talk(a.monitor, [hook, "start"])
        time.sleep(2)
        r = subprocess.run(["node", os.path.join(ROOT, "web", "test", "browser_test.mjs"), "--transport", "ws",
                            "--ws", "ws://localhost:%d" % a.ws, "--name", NAME], capture_output=True, text=True, timeout=900)
        print(r.stdout)
        step("browser test over the WebSocket bridge (write, diff, verify, read back)", r.returncode == 0,
             r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
        t = ""
        for _ in range(10):
            t = screen()
            if NAME in t:
                break
        shot("web_emu_after_write")
        step("radio screen shows the channel the page wrote", NAME in t)
        _, raw, inf = ops.read_radio("tcp:127.0.0.1:%d" % a.uart, log=lambda s: None, timeout=10)
        talk(a.monitor, ["pause", "board PowerOff", 'emulation RunFor "00:00:02.000000"', "machine Reset", "board PowerOn", "start"])
        t2 = ""
        for _ in range(20):
            t2 = screen()
            if NAME in t2:
                break
        step("after power cycle the channel is still there", NAME in t2)
        _, raw2, inf2 = ops.read_radio("tcp:127.0.0.1:%d" % a.uart, log=lambda s: None, timeout=10)
        cp = C.decode(raw2)
        step("Python CLI reads back the same bytes after power cycle", raw2 == raw and inf2["valid"] and cp.channels[0].name == NAME,
             "%d bytes CRC %08X" % (len(raw2), inf2["crc"]))
    except Exception as e:  # noqa: BLE001
        step("exception", False, repr(e))
    finally:
        bridge.terminate()
        try:
            talk(a.monitor, ["quit"], timeout=20)
        except Exception:  # noqa: BLE001
            pass
    open(os.path.join(out, "result.txt"), "w").write("\n".join(res) + "\n")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
