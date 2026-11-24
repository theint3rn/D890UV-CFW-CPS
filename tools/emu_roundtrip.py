#!/usr/bin/env python3
"""Emulator round trip: write a codeplug into the cfw running in Renode over the emulated USART1, check the
screen shows the new channels, read it back (byte for byte), power-cycle, check it persists, read again.

  python3 tools/emu_roundtrip.py [--elf ../cfw/build/cfw.elf] [--codeplug examples/synth.d8cp]
  python3 tools/emu_roundtrip.py --model D168UV     # D168UV cfw (D168UV/cfw/build/cfw168.elf) in D168UV/emu;
                                                     # the codeplug is converted to the D168UV first

USART1 is exposed as TCP localhost:--uart (Renode CreateServerSocketTerminal, passed to emu/run.py --extra;
no emulator files changed). Screens go to cfw_cps/screens/, strings the firmware drew to emu/out/cps_rt/text.txt.
"""
import argparse
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EMU = os.path.join(ROOT, "..", "emu")
EMU168 = os.path.join(ROOT, "..", "..", "..", "D168UV", "emu")
if "D168UV" in sys.argv:                        # the D168 emulator has its own ctl.py / run.py
    EMU = EMU168
sys.path.insert(0, ROOT)
sys.path.insert(0, EMU)
from cps import codeplug as C, ops, stock as ST  # noqa: E402
from ctl import talk  # noqa: E402


def wait_port(port, t=60):
    end = time.time() + t
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def sym(elf, name):
    out = subprocess.check_output(["arm-none-eabi-nm", elf], text=True)
    return next(int(l.split()[0], 16) for l in out.splitlines() if l.split()[-1] == name)


def radio_edit(a, mon, port, cp, step, screen_text, shot, d168):
    """Radio menu Settings -> codeplug journal -> CPS read-back: TX timeout 120 s, squelch 3, key PF1 = Monitor, TX power
    of channel 1 = Mid, then the CPS decode must show them; written back by the CPS, the radio must keep them."""
    def keys(*codes, wait=0.45):
        """key presses in virtual time (paused emulator), then free running again"""
        L = ["pause"]
        for c in codes:
            L += ["lcd Press %d 150" % c, 'emulation RunFor "00:00:%09.6f"' % wait]
        talk(mon, L + ["start"])
    opt = ST.TABLES["OptionalSetting"]["columns"]
    tot0 = cp.stock.get("OptionalSetting", [ST.TABLES["OptionalSetting"]["defaults"]])[0][opt.index("TOT")]
    keys(14, 14, 14)                             # main screen
    keys(13, 10)                                 # Menu, row 9 = Settings
    keys(3, wait=0.6)                            # row 2 = TX timeout -> option list (opens on the current value)
    keys(*([16] * ((4 - int(tot0 or 0)) % 9)), 13)   # -> 120s
    keys(2, wait=0.6)                            # row 1 = Squelch
    sq0 = int(cp.stock.get("OptionalSetting", [ST.TABLES["OptionalSetting"]["defaults"]])[0][opt.index("SQL1")] or 0)
    keys(*([16] * ((3 - sq0) % 6)), 13)
    # TX power (row 12) and the PF1 key (D890UV: row 15 "Key PF1", D168UV: row 13 "Key PF1" = slot P1)
    keys(*([16] * 11), 13, wait=0.3)             # rows 1 -> 12, open TX power
    pw0 = C.POWERS.index(cp.channels[0].power)
    keys(*([16] * ((1 - pw0) % 4)), 13)          # -> Mid
    slot = 0 if d168 else 2
    keys(*([16] * (1 + slot)), 13, wait=0.3)  # TX power row -> key row of PF1
    k0 = C.KEY_FUNCS.index(cp.settings.keys[slot])
    keys(*([16] * ((5 - k0) % len(C.KEY_FUNCS))), 13)   # -> Monitor
    shot("radio_settings")
    keys(14, wait=1.5)                           # leave Settings: journal written to the codeplug
    t = screen_text(1.0)
    step("radio: settings saved to the codeplug", "SAVED" in t or "codeplug" in t, repr([l for l in t.split("\n") if "SAV" in l][:2]))
    keys(14, 14)
    _, raw3, inf3 = ops.read_radio(port, log=lambda s: None, timeout=10)
    cp3 = C.decode(raw3)
    o3 = cp3.stock.get("OptionalSetting", [[]])[0]
    step("CPS reads the radio's edits back (CRC valid)", inf3["valid"],
         "TOT=%s SQL1=%s key=%s power=%s" % (o3[opt.index("TOT")] if o3 else "?", o3[opt.index("SQL1")] if o3 else "?",
                                              cp3.settings.keys[slot], cp3.channels[0].power))
    step("  TX timeout 120 s (TOT 4)", o3 and o3[opt.index("TOT")] == "4")
    step("  squelch 3 (SQL1 3)", o3 and o3[opt.index("SQL1")] == "3")
    step("  key PF1 = monitor", cp3.settings.keys[slot] == "monitor")
    step("  channel 1 TX power mid", cp3.channels[0].power == "mid")
    # CPS writes it back (journal folded into the normal entries); the radio must still have the values
    data = ops.write_radio(port, cp3, log=lambda s: None, timeout=10)
    step("CPS writes the edited codeplug back", data is not None)
    _, raw4, _ = ops.read_radio(port, log=lambda s: None, timeout=10)
    cp4 = C.decode(raw4)
    step("  read back = written, values kept", raw4 == data and cp4.settings.keys == cp3.settings.keys
         and cp4.stock.get("OptionalSetting") == cp3.stock.get("OptionalSetting") and cp4.channels[0].power == "mid")
    keys(14, 14, 13, 10)
    t = screen_text(1.5)
    shot("radio_settings_after_cps_write")
    step("  radio Settings shows TX timeout 120s", "120s" in t)
    keys(14, 14)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="D890UV", choices=list(C.MODELS))
    ap.add_argument("--elf", default=None, help="default: ../cfw/build/cfw.elf (D890UV), D168UV/cfw/build/cfw168.elf (D168UV)")
    ap.add_argument("--codeplug", default=os.path.join(ROOT, "examples", "synth.d8cp"))
    ap.add_argument("--monitor", type=int, default=1271)
    ap.add_argument("--uart", type=int, default=3471)
    ap.add_argument("--keep", action="store_true", help="leave Renode running at the end")
    ap.add_argument("--no-radio-edit", action="store_true", help="skip the radio menu settings -> CPS read-back phase")
    a = ap.parse_args()
    d168 = a.model == "D168UV"
    if a.elf is None:
        a.elf = os.path.join(EMU168, "..", "cfw", "build", "cfw168.elf") if d168 else os.path.join(ROOT, "..", "cfw", "build", "cfw.elf")
    out = os.path.join(EMU, "out", "cps_rt")
    os.makedirs(out, exist_ok=True)
    tag = "d168_" if d168 else ""
    screens = os.path.join(ROOT, "screens")
    os.makedirs(screens, exist_ok=True)
    txt = os.path.join(out, "text.txt")
    mon = a.monitor

    if d168:
        subprocess.check_call([sys.executable, os.path.join(EMU, "run.py"), "--cfw", "--elf", a.elf, "--seconds", "0.2",
                               "--name", "cps_rt", "--serve", str(mon), "--uart-socket", "usart1:%d" % a.uart])
    else:
        subprocess.check_call([sys.executable, os.path.join(EMU, "run.py"), "--elf", a.elf, "--seconds", "4",
                               "--name", "cps_rt", "--serve", str(mon),
                               "--extra", 'emulation CreateServerSocketTerminal %d "progterm" false' % a.uart,
                               "--extra", "connector Connect sysbus.usart1 progterm"])
    if not wait_port(mon + 1, 30) and wait_port(mon, 30):    # broker raced Renode's start: start another one
        subprocess.Popen([sys.executable, os.path.join(EMU, "ctl.py"), "--port", str(mon), "broker"], cwd=EMU,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True)
    if not wait_port(mon + 1):
        print("FAIL: emulator monitor did not come up")
        return 1
    ok = True
    log = []

    def step(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        line = "%-4s %s %s" % ("PASS" if cond else "FAIL", name, detail)
        log.append(line)
        print(line, flush=True)

    gfx = sym(a.elf, "gfx_text")
    hook = ("cpu AddHook 0x%08X \"import System; p = self.GetRegister(2).RawValue; "
            "s = ''.join([chr(self.Bus.ReadByte(p + i)) for i in range(40)]).split(chr(0))[0]; "
            "System.IO.File.AppendAllText('%s', s + chr(10))\"") % (gfx & ~1, txt)

    def screen_text(secs=1.5):
        if os.path.exists(txt):
            os.remove(txt)
        time.sleep(secs)
        return open(txt).read() if os.path.exists(txt) else ""

    def shot(name):
        p = os.path.join(out, name + ".ppm")
        talk(mon, ["lcd Screenshot @%s" % p])
        subprocess.call([sys.executable, "-I", os.path.join(EMU, "ppm2png.py"), p, os.path.join(screens, tag + name + ".png")])

    try:
        talk(mon, [hook, "start"])
        port = "tcp:127.0.0.1:%d" % a.uart
        time.sleep(2)
        before = screen_text()
        cp = C.load(a.codeplug)
        if cp.model != a.model:
            ST.convert_model(cp, a.model)
        cp.channels[0].name = "CPS ROUNDTRIP 1"
        cp.settings.callsign = "N0CPS"
        cp.settings.start_channel = 0
        _, raw0, inf0 = ops.read_radio(port, log=print, timeout=10)
        step("identify + info (no codeplug yet)", not inf0["valid"] or raw0, "channels %d" % inf0["channels"])
        data = ops.write_radio(port, cp, log=lambda s: print(s) if not s.startswith("  ") else None, timeout=10)
        step("write %d bytes + END ack + read-back identical" % len(data), data is not None)
        t = screen_text()
        shot("after_write")
        step("screen shows the new channel", "CPS ROUNDTRIP 1" in t, "(before: %r)" % [l for l in before.split("\n") if l][:3])
        _, raw, inf = ops.read_radio(port, log=lambda s: None, timeout=10)
        step("read back byte for byte", raw == data, "%d bytes, CRC %08X, %d channels" % (len(raw), inf["crc"],
                                                                                         inf["cp_channels"]))
        # power cycle: knob off -> firmware saves, drops the latch, resets; then power on again
        # (D168UV: power on = reset with PA0 low; PA0 held high at boot is the charge-only loop there)
        # D168 emulator: no bootloader at 0x08000000, so the reset needs the cfw vector table again
        on = ['cpu VectorTableOffset 0x%08X' % sym(a.elf, "g_vectors"), 'cpu SP `sysbus ReadDoubleWord 0x%08X`' % sym(a.elf, "g_vectors"),
              'cpu PC `sysbus ReadDoubleWord 0x%08X`' % (sym(a.elf, "g_vectors") + 4), 'board Set "A0" false'] if d168 else ["board PowerOn"]
        talk(mon, ["pause", "board PowerOff", 'emulation RunFor "00:00:02.000000"', "machine Reset"] + on + ["start"])
        t2 = ""
        for _ in range(20):                      # boot screen first, main screen once the power key is armed
            t2 = screen_text(1.5)
            if "CPS ROUNDTRIP 1" in t2:
                break
        shot("after_power_cycle")
        step("after power cycle the channel is still there", "CPS ROUNDTRIP 1" in t2)
        _, raw2, inf2 = ops.read_radio(port, log=lambda s: None, timeout=10)
        step("after power cycle read back byte for byte", raw2 == data and inf2["valid"], "generation %d" % inf2["generation"])
        cp2 = C.decode(raw2)
        step("decoded codeplug equals what was written", cp2.channels == cp.channels and cp2.zones == cp.zones
             and cp2.settings == cp.settings)
        if not a.no_radio_edit:
            radio_edit(a, mon, port, cp2, step, screen_text, shot, d168)
    except Exception as e:                       # noqa: BLE001
        step("exception", False, repr(e))
    finally:
        if not a.keep:
            try:
                talk(mon, ["quit"], timeout=20)
            except Exception:                    # noqa: BLE001
                pass
    open(os.path.join(out, "result.txt"), "w").write("\n".join(log) + "\n")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
