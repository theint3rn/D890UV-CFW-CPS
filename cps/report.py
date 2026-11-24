"""Printable codeplug report (the stock CPS "Print" / "Print to File"): HTML or plain text."""
import html as H

from . import codeplug as C, stock as ST


def _detail(c):
    if c.mode == "FM":
        return "%s%s%s" % ("25k" if c.wide else "12.5k", " T" + c.tx_tone if c.tx_tone else "", " R" + c.rx_tone if c.rx_tone else "")
    if c.mode == "DMR":
        return "CC%d TS%d TG%d%s" % (c.cc, c.slot, c.tg, " T3" if c.trunk else "")
    if c.mode in ("P25", "P25P2"):
        return "NAC %03X TG%d%s" % (c.nac, c.tg, " TRUNK" if c.trunk else "")
    if c.mode == "NXDN":
        return "RAN%d G%d %d" % (c.ran, c.tg, c.nxdn_rate)
    if c.mode == "DSTAR":
        return "UR %s RPT1 %s RPT2 %s" % (c.ur, c.rpt1, c.rpt2)
    return "DG-ID %d/%s %s" % (c.dgid, c.dgid if c.dgid_tx is None else c.dgid_tx, c.ysf_mode)


def tables(cp):
    s = cp.settings
    out = [("Radio", ["Item", "Value"], [["Callsign", s.callsign], ["DMR ID", s.dmr_id], ["Radio name", s.radio_name],
                                         ["Channels", len(cp.channels)], ["Zones", len(cp.zones)]])]
    out.append(("Channels", ["#", "Name", "RX MHz", "TX MHz", "Mode", "Details", "Power", "Talkaround"],
                [[i + 1, c.name, "%.5f" % (c.rx_hz / 1e6), "%.5f" % (c.tx_hz / 1e6), c.mode, _detail(c), c.power,
                  "on" if c.talkaround else ""] for i, c in enumerate(cp.channels)]))
    out.append(("Zones", ["#", "Name", "Channels"], [[i + 1, z.name, ", ".join(str(m + 1) for m in z.channels)]
                                                     for i, z in enumerate(cp.zones)]))
    out.append(("Scan lists", ["#", "Name", "Channels"], [[i + 1, z.name, ", ".join(str(m + 1) for m in z.channels)]
                                                          for i, z in enumerate(cp.scanlists)]))
    out.append(("Contacts / talkgroups", ["#", "Name", "ID", "Kind", "Mode"],
                [[i + 1, c.name, c.id, c.kind, c.mode] for i, c in enumerate(cp.contacts)]))
    out.append(("Trunk systems", ["#", "Name", "Type", "NAC/CC/RAN", "WACN", "SysID", "Control channels"],
                [[i + 1, t.name, t.type, "%X" % t.nac_cc, "%X" % t.wacn, "%X" % t.sysid,
                  " ".join("%.5f" % (f / 1e6) for f in t.control_channels)] for i, t in enumerate(cp.trunksys)]))
    out.append(("Encryption keys", ["#", "Name", "Kind", "Key ID"], [[i + 1, k.name, k.kind, k.key_id] for i, k in enumerate(cp.keys)]))
    opt = ST.stock_settings_view(cp, "OptionalSetting")
    out.append(("Optional settings (stock)", ["Setting", "Value"], [[ST.LABELS.get(k, k), v] for k, v in opt.items()]))
    return out


def html(cp):
    parts = ["<!doctype html><meta charset=utf-8><title>cfw codeplug</title><style>body{font:12px sans-serif}"
             "table{border-collapse:collapse;margin-bottom:14px}td,th{border:1px solid #999;padding:1px 5px}</style>"]
    for title, head, rows in tables(cp):
        parts.append("<h2>%s</h2><table><tr>%s</tr>" % (H.escape(title), "".join("<th>%s</th>" % H.escape(h) for h in head)))
        for r in rows:
            parts.append("<tr>%s</tr>" % "".join("<td>%s</td>" % H.escape(str(x)) for x in r))
        parts.append("</table>")
    return "".join(parts)


def text(cp):
    out = []
    for title, head, rows in tables(cp):
        out.append("== " + title)
        w = [max(len(str(x)) for x in [h] + [r[i] for r in rows]) for i, h in enumerate(head)]
        out.append("  ".join(str(h).ljust(w[i]) for i, h in enumerate(head)))
        for r in rows:
            out.append("  ".join(str(x).ljust(w[i]) for i, x in enumerate(r)))
        out.append("")
    return "\n".join(out)
