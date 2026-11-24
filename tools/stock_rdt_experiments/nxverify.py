"""Import one NXSetting row with several non-default values (incl. the alias) into the stock CPS, Save As, print path."""
import csv, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdtmap as R
VALS = {"OwnId": "1234", "StationId ": "300", "OwnIdAbleMax": "4000", "TxAliasEn": "1", "TxAliasName": "CFW7",
        "ResetTime": "3", "StateMsg2": "2", "NxdnMoni": "1", "NxdnMoniId": "7", "PriCallBeep": "1"}
for w, n in R.wins():
    if "1x1" in R.xd("getwindowgeometry", w):
        R.HIDDEN = w
rows = list(csv.reader(open(os.path.join(R.BEXP, "NXSetting.CSV"), encoding="latin1", newline="")))
head = rows[0]
for k, v in VALS.items():
    rows[1][head.index(k)] = v
xdir = os.path.join(R.WORK, "x")
buf = io.StringIO()
csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(rows)
open(os.path.join(xdir, "NXSetting.CSV"), "w", encoding="latin1", newline="").write(buf.getvalue())
open(os.path.join(xdir, "x.LST"), "w", newline="").write('1\r\n%d,"NXSetting.CSV"\r\n' % R.LST_INDEX["NXSetting"])
log = []
R.do_import("C:\\work\\x\\x.LST", log)
p = os.path.join(xdir, "nxv.rdt")
print(R.do_save(p, log), p, log)
