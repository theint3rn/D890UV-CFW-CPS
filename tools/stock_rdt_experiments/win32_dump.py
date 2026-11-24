# Dump the controls of a visible top-level window (by title substring) of the stock CPS: class, text, rect,
# combo items + selection, checkbox state. Usage: python dump.py "<title substring>" out.json
import ctypes, json, sys
from ctypes import wintypes as W
u = ctypes.WinDLL("user32", use_last_error=True)
u.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, ctypes.POINTER(ctypes.c_size_t)]
def SM(h, m, w, l):
    r = ctypes.c_size_t(0)
    if not u.SendMessageTimeoutW(h, m, w, l, 2, 500, ctypes.byref(r)): return -1
    return ctypes.c_ssize_t(r.value).value
class _U: pass
CB_GETCOUNT, CB_GETLBTEXT, CB_GETLBTEXTLEN, CB_GETCURSEL = 0x146, 0x148, 0x149, 0x147
LB_GETCOUNT, LB_GETTEXT, LB_GETTEXTLEN, LB_GETCURSEL = 0x18B, 0x189, 0x18A, 0x188
BM_GETCHECK, WM_GETTEXT, WM_GETTEXTLENGTH = 0xF0, 0xD, 0xE
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

def text(h):
    n = SM(h, WM_GETTEXTLENGTH, 0, 0)
    b = ctypes.create_unicode_buffer(n + 1); SM(h, WM_GETTEXT, n + 1, ctypes.cast(b, ctypes.c_void_p).value); return b.value
def cls(h):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256); return b.value
def rect(h, top):
    r = W.RECT(); u.GetWindowRect(h, ctypes.byref(r)); p = W.POINT(r.left, r.top); u.ScreenToClient(top, ctypes.byref(p))
    return [p.x, p.y, r.right - r.left, r.bottom - r.top]
def items(h, cnt, ln, get):
    out = []
    n0 = SM(h, cnt, 0, 0)
    if n0 > 600: return ['<%d items>' % n0]
    for i in range(max(0, n0)):
        n = SM(h, ln, i, 0); b = ctypes.create_unicode_buffer(max(n, 0) + 2)
        SM(h, get, i, ctypes.cast(b, ctypes.c_void_p).value); out.append(b.value)
    return out

tops = []
def top_cb(h, l):
    if u.IsWindowVisible(h) and sys.argv[1] in text(h): tops.append(h)
    return True
u.EnumWindows(EnumProc(top_cb), 0)
if not tops: print("no window"); sys.exit(1)
top = tops[0]
ctl = []
def ch_cb(h, l):
    c = cls(h); d = {"cls": c, "text": text(h), "rect": rect(h, top), "visible": bool(u.IsWindowVisible(h)),
                     "enabled": bool(u.IsWindowEnabled(h)), "id": u.GetDlgCtrlID(h), "parent": cls(u.GetParent(h))}
    lc = c.lower()
    if "combo" in lc:
        d["items"] = items(h, CB_GETCOUNT, CB_GETLBTEXTLEN, CB_GETLBTEXT); d["sel"] = SM(h, CB_GETCURSEL, 0, 0)
    elif "listbox" in lc:
        d["items"] = items(h, LB_GETCOUNT, LB_GETTEXTLEN, LB_GETTEXT); d["sel"] = SM(h, LB_GETCURSEL, 0, 0)
    elif "check" in lc or "option" in lc:
        d["checked"] = SM(h, BM_GETCHECK, 0, 0)
    ctl.append(d); return True
u.EnumChildWindows(top, EnumProc(ch_cb), 0)
json.dump({"title": text(top), "controls": ctl}, open(sys.argv[2], "w"), indent=1)
print(text(top), len(ctl), "controls")
