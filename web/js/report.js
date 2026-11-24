// Printable codeplug report (stock CPS "Print"): same tables as cps/report.py.
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mhz = (hz) => (hz / 1e6).toFixed(5);
function detail(c) {
  if (c.mode === "FM") return (c.wide ? "25k" : "12.5k") + (c.tx_tone ? " T" + c.tx_tone : "") + (c.rx_tone ? " R" + c.rx_tone : "");
  if (c.mode === "DMR") return `CC${c.cc} TS${c.slot} TG${c.tg}${c.trunk ? " T3" : ""}`;
  if (c.mode === "P25" || c.mode === "P25P2") return `NAC ${c.nac.toString(16).toUpperCase().padStart(3, "0")} TG${c.tg}${c.trunk ? " TRUNK" : ""}`;
  if (c.mode === "NXDN") return `RAN${c.ran} G${c.tg} ${c.nxdn_rate}`;
  if (c.mode === "DSTAR") return `UR ${c.ur} RPT1 ${c.rpt1} RPT2 ${c.rpt2}`;
  return `DG-ID ${c.dgid}/${c.dgid_tx ?? c.dgid} ${c.ysf_mode}`;
}
export function reportHtml(cp, ST) {
  const s = cp.settings;
  const T = [["Radio", ["Item", "Value"], [["Callsign", s.callsign], ["DMR ID", s.dmr_id], ["Radio name", s.radio_name], ["Channels", cp.channels.length], ["Zones", cp.zones.length]]],
    ["Channels", ["#", "Name", "RX MHz", "TX MHz", "Mode", "Details", "Power", "Talkaround"],
      cp.channels.map((c, i) => [i + 1, c.name, mhz(c.rx_hz), mhz(c.tx_hz), c.mode, detail(c), c.power, c.talkaround ? "on" : ""])],
    ["Zones", ["#", "Name", "Channels"], cp.zones.map((z, i) => [i + 1, z.name, z.channels.map((m) => m + 1).join(", ")])],
    ["Scan lists", ["#", "Name", "Channels"], cp.scanlists.map((z, i) => [i + 1, z.name, z.channels.map((m) => m + 1).join(", ")])],
    ["Contacts / talkgroups", ["#", "Name", "ID", "Kind", "Mode"], cp.contacts.map((c, i) => [i + 1, c.name, c.id, c.kind, c.mode])],
    ["Trunk systems", ["#", "Name", "Type", "Control channels"], cp.trunksys.map((t, i) => [i + 1, t.name, t.type, t.control_channels.map(mhz).join(" ")])],
    ["Encryption keys", ["#", "Name", "Kind", "Key ID"], (cp.keys || []).map((k, i) => [i + 1, k.name, k.kind, k.key_id])],
    ["Optional settings (stock)", ["Setting", "Value"], Object.entries(ST.stockSettingsView(cp, "OptionalSetting")).map(([k, v]) => [ST.LABELS[k] || k, v])]];
  return "<!doctype html><meta charset=utf-8><title>cfw codeplug</title><style>body{font:12px sans-serif}table{border-collapse:collapse;margin-bottom:14px}td,th{border:1px solid #999;padding:1px 5px}</style>" +
    T.map(([t, h, rows]) => `<h2>${esc(t)}</h2><table><tr>${h.map((x) => `<th>${esc(x)}</th>`).join("")}</tr>` +
      rows.map((r) => `<tr>${r.map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("") + "</table>").join("");
}
