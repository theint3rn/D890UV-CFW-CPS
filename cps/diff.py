"""Human-readable diff between two codeplugs (shown before writing to the radio)."""
from . import codeplug as C


def _fmt(k, v):
    if isinstance(v, int) and not isinstance(v, bool) and k.endswith("_hz") and v > 1000000:
        return "%.5f" % (v / 1e6)
    if k in ("nac", "wacn", "sysid", "p25_nac", "p25_wacn", "p25_sysid") and isinstance(v, int):
        return "0x%X" % v
    return repr(v)


def _items(d):
    return {k: v for k, v in d.items()}


def diff(old, new, limit=400):
    """old/new: Codeplug (old may be None = empty radio). Returns a list of text lines."""
    a = C.to_dict(old) if old is not None else {"settings": {}, "channels": [], "zones": [], "scanlists": [],
                                                 "contacts": [], "tglists": [], "trunksys": []}
    b = C.to_dict(new)
    out = []
    sa, sb = a.get("settings", {}), b["settings"]
    for k in sb:
        if sa.get(k) != sb[k]:
            out.append("settings.%s: %s -> %s" % (k, _fmt(k, sa.get(k)), _fmt(k, sb[k])))
    for sec in ("channels", "zones", "scanlists", "contacts", "tglists", "trunksys"):
        la, lb = a.get(sec, []), b[sec]
        for i in range(max(len(la), len(lb))):
            x = la[i] if i < len(la) else None
            y = lb[i] if i < len(lb) else None
            if x == y:
                continue
            label = "%s %d" % (sec[:-1] if sec != "trunksys" else "trunksys", i + 1)
            if x is None:
                out.append("+ %s %r" % (label, y.get("name", "")))
            elif y is None:
                out.append("- %s %r" % (label, x.get("name", "")))
            else:
                ch = ["%s %s->%s" % (k, _fmt(k, x.get(k)), _fmt(k, y.get(k)))
                      for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)]
                out.append("~ %s %r: %s" % (label, y.get("name", ""), ", ".join(ch)))
    if len(out) > limit:
        n = len(out)
        out = out[:limit] + ["... %d more changes" % (n - limit)]
    return out


def summary(old, new):
    lines = diff(old, new, limit=10 ** 9)
    adds = sum(1 for l in lines if l.startswith("+"))
    dels = sum(1 for l in lines if l.startswith("-"))
    mods = len(lines) - adds - dels
    return "%d added, %d removed, %d changed" % (adds, dels, mods)
