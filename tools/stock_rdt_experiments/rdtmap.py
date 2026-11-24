#!/usr/bin/env python3
"""Map the stock D890UV CPS .rdt (V1323) layout field by field: for each CSV column, import a CSV whose only change
is that column, Save As a new .rdt, diff against the reference save. Drives the stock CPS (in the scratch Wine prefix)
with xdotool; never touches a radio.
usage: rdtmap.py TABLE [first_col] [last_col]      TABLE = CSV base name, e.g. OptionalSetting
results: stock/map/<TABLE>.jsonl  (column, old, new, changed byte offsets + values)"""
import csv, io, json, os, subprocess, sys, time

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# MODEL=D168UV: stock D168UV CPS V1.07 (prefix in WINEPREFIX, else <S>/wine_cps); WORK = C:\work of that prefix
MODEL = os.environ.get("MODEL", "D890UV")
CLS = MODEL.lower() + ".exe"
# Import dialog: "Import From File List" button, "Import" button (window coordinates)
IMP_LIST, IMP_GO = {"D168UV": ((507, 31), (456, 694))}.get(MODEL, ((470, 39), (472, 710)))
PREFIX = os.environ.get("WINEPREFIX") or os.path.join(S, "wine_cps")
WORK = os.path.join(PREFIX, "drive_c", "work")
S = os.environ.get("MAPDIR", S)
BEXP = os.path.join(WORK, "bexp")
OUTD = os.path.join(S, "stock", "map")
os.makedirs(OUTD, exist_ok=True)
LST_INDEX = {}
for line in open(os.path.join(BEXP, "base.LST"), encoding="latin1"):
    line = line.strip()
    if line:
        if "," not in line:
            continue
        i, f = line.split(",", 1)
        LST_INDEX[f.strip('"')[:-4]] = int(i)


def xd(*a, check=False):
    return subprocess.run(["xdotool"] + list(a), capture_output=True, text=True, check=check).stdout.strip()


def wins():
    out = []
    for w in xd("search", "--onlyvisible", "--class", CLS).split():
        out.append((w, xd("getwindowname", w)))
    return out


def main_win():
    for _ in range(60):                       # the title can be briefly unreadable while a dialog closes
        for w, n in wins():
            if n.startswith(MODEL + "["):
                return w
        time.sleep(0.25)
    raise SystemExit("main window gone")


def wait(pred, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        for w, n in wins():
            if pred(w, n):
                return w
        time.sleep(0.25)
    return None


def activate(w):
    xd("windowactivate", w)
    time.sleep(0.3)


def dismiss_msgs(timeout=4.0, log=None):
    """press Return on message boxes (name 'D890UV' or '', not the 1x1 hidden one); returns screenshots taken"""
    end = time.time() + timeout
    seen = 0
    while time.time() < end:
        found = False
        for w, n in wins():
            if n in (MODEL, "") and w != HIDDEN:
                geo = xd("getwindowgeometry", w)
                if "1x1" in geo:
                    continue
                if log is not None:
                    p = os.path.join(OUTD, "msg_%d.png" % int(time.time() * 1000))
                    subprocess.run(["timeout", "10", "import", "-window", w, p], capture_output=True)
                    log.append(p)
                activate(w)
                xd("key", "Return")
                time.sleep(0.6)
                found = True
                seen += 1
                end = time.time() + timeout
        if not found:
            time.sleep(0.3)
    return seen


HIDDEN = None


def do_import(lst_path, log):
    W = main_win()
    activate(W)
    xd("key", "alt+t"); time.sleep(0.6); xd("key", "i"); time.sleep(1.2)
    dismiss_msgs(1.2)                                   # "new version CPS ... csv" notice
    imp = wait(lambda w, n: n == "Import", 10)
    if not imp:
        raise RuntimeError("no Import dialog")
    activate(imp)
    xd("mousemove", "--window", imp, str(IMP_LIST[0]), str(IMP_LIST[1])); time.sleep(0.2); xd("click", "1"); time.sleep(1.5)
    dlg = wait(lambda w, n: n == "" and "420x" in xd("getwindowgeometry", w), 8)
    if dlg:
        activate(dlg)
    xd("key", "alt+n"); time.sleep(0.3)
    xd("type", "--delay", "20", lst_path); xd("key", "Return")
    time.sleep(2.0)
    dismiss_msgs(1.6, log)
    imp = wait(lambda w, n: n == "Import", 5)
    if imp:
        activate(imp)
        xd("mousemove", "--window", imp, str(IMP_GO[0]), str(IMP_GO[1])); time.sleep(0.2); xd("click", "1"); time.sleep(1.0)
    dismiss_msgs(1.5, log)


def do_save(path, log):
    W = main_win()
    activate(W)
    if os.path.exists(path):
        os.remove(path)
    xd("key", "alt+f"); time.sleep(0.6); xd("key", "a"); time.sleep(1.5)
    dlg = wait(lambda w, n: n.startswith("Save"), 8)
    if dlg:
        activate(dlg)
    win = "C:\\work\\" + os.path.relpath(path, WORK).replace("/", "\\")
    xd("type", "--delay", "20", win); xd("key", "Return")
    for _ in range(40):
        time.sleep(0.5)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            break
    time.sleep(1.0)
    dismiss_msgs(1.0, log)
    return os.path.exists(path)


def do_export_all(lst_win, log):
    """Tool > Export > Export All (Default CSV FileName) into the folder of lst_win (Windows path of the .LST)"""
    W = main_win()
    activate(W)
    xd("key", "alt+t"); time.sleep(0.6); xd("key", "e"); time.sleep(1.2)
    ex = wait(lambda w, n: n == "Export", 8)
    if not ex:
        raise RuntimeError("no Export dialog")
    activate(ex)
    xd("mousemove", "--window", ex, "500", "21"); time.sleep(0.2); xd("click", "1"); time.sleep(1.5)
    dlg = wait(lambda w, n: n == "" and "420x" in xd("getwindowgeometry", w), 8)
    if dlg:
        activate(dlg)
    xd("key", "alt+n"); time.sleep(0.3)
    xd("type", "--delay", "20", lst_win); xd("key", "Return")
    wait(lambda w, n: n == MODEL and w != HIDDEN and "1x1" not in xd("getwindowgeometry", w), 300)   # "Export Complete!"
    dismiss_msgs(2.0, log)
    ex = wait(lambda w, n: n == "Export", 3)
    if ex:
        activate(ex)
        xd("mousemove", "--window", ex, "540", "696"); time.sleep(0.2); xd("click", "1"); time.sleep(0.8)


def diff(a, b):
    ch = []
    for i in range(min(len(a), len(b))):
        if i < 9:
            continue                     # "V1323" + per-save byte(s) in the file header
        if a[i] != b[i]:
            ch.append([i, a[i], b[i]])
    return ch, len(a), len(b)


def alt_value(v, col):
    try:
        x = int(v)
        return str(x + 1)
    except ValueError:
        pass
    try:
        f = float(v)
        return "%.5f" % (f + 0.0125) if "." in v and len(v.split(".")[1]) >= 4 else str(round(f + 1, 1))
    except ValueError:
        pass
    return (v.strip() + "Q")[:16] if v.strip() else "QZ"


def init_hidden():
    global HIDDEN
    for w, n in wins():
        if "1x1" in xd("getwindowgeometry", w):
            HIDDEN = w


def main():
    global HIDDEN
    for w, n in wins():
        if "1x1" in xd("getwindowgeometry", w):
            HIDDEN = w
    table = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    last = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 6
    row = int(os.environ.get("ROW", "1"))
    rows = list(csv.reader(open(os.path.join(BEXP, table + ".CSV"), encoding="latin1", newline="")))
    head = rows[0]
    ALT = {}
    kp = os.path.join(WORK, "exp", table + ".CSV")
    if os.path.exists(kp):
        kr = list(csv.reader(open(kp, encoding="latin1", newline="")))
        if len(kr) > 1 and kr[0] == head:
            for ci, h in enumerate(head):
                for r in kr[1:]:
                    if ci < len(r) and r[ci] != rows[row][ci] and r[ci].strip() != "":
                        ALT[h] = r[ci]
                        break
    xdir = os.path.join(WORK, "x")
    os.makedirs(xdir, exist_ok=True)
    lst = os.path.join(xdir, "x.LST")
    open(lst, "w", newline="").write('1\r\n%d,"%s.CSV"\r\n' % (LST_INDEX[table], table))
    lst_w = "C:\\work\\x\\x.LST"

    def write_csv(rws):
        buf = io.StringIO()
        wr = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        for r in rws:
            wr.writerow(r)
        open(os.path.join(xdir, table + ".CSV"), "w", encoding="latin1", newline="").write(buf.getvalue())

    out = open(os.path.join(OUTD, table + ".jsonl"), "a")
    ref = os.path.join(xdir, "ref_%s.rdt" % table)
    if not os.path.exists(ref) or first == 0:
        log = []
        write_csv(rows)
        for _ in range(2):              # the first import after New also sets a few unrelated bytes: reference = 2nd save
            do_import(lst_w, log)
            do_save(ref, log)
        print("reference saved", os.path.getsize(ref), log, flush=True)
    refb = open(ref, "rb").read()
    def run(cols):
        log = []
        new = [r[:] for r in rows]
        vals = {}
        for c in cols:
            old = new[row][c] if c < len(new[row]) else ""
            nv = os.environ.get("VALUE") or ALT.get(head[c]) or alt_value(old, head[c])
            if nv == old:
                nv = alt_value(old, head[c])
            new[row][c] = nv
            vals[c] = (old, nv)
        write_csv(new)
        p = os.path.join(xdir, "t.rdt")
        try:
            do_import(lst_w, log)
            ok = do_save(p, log)
        except Exception as e:  # noqa: BLE001
            ok, log = False, log + [repr(e)]
        d = diff(refb, open(p, "rb").read()) if ok else ([], 0, 0)
        return ok, vals, d, log

    def emit(c, vals, ok, d, log):
        rec = {"table": table, "col": c, "name": head[c], "row": row, "old": vals[c][0], "new": vals[c][1], "ok": ok,
               "msgs": log, "diff": d[0][:64], "len_ref": d[1], "len": d[2]}
        out.write(json.dumps(rec) + "\n"); out.flush()
        print(c, head[c], vals[c][0], "->", vals[c][1], ok, d[0][:6], flush=True)

    batch = int(os.environ.get("BATCH", "1"))

    def solve(group):
        """map a group of columns: one import if the diff is unambiguous, else bisect"""
        if len(group) == 1:
            ok, vals, d, log = run(group)
            emit(group[0], vals, ok, d, log)
            return
        ok, vals, d, log = run(group)
        ch = d[0]
        if ok and d[1] == d[2] and all((b[2] - b[1]) % 256 == 1 for b in ch):
            if len(ch) == len(group):
                for c, b in zip(group, ch):
                    emit(c, vals, ok, ([b], d[1], d[2]), ["batch"])
                return
            if len(ch) == 0:
                for c in group:
                    emit(c, vals, ok, ([], d[1], d[2]), ["batch: no change"])
                return
        print("bisect", group, ch[:12], flush=True)
        h = len(group) // 2
        solve(group[:h])
        solve(group[h:])

    cols_all = list(range(first, min(last + 1, len(head))))
    for i in range(0, len(cols_all), batch):
        solve(cols_all[i:i + batch])

if __name__ == "__main__":
    main()
