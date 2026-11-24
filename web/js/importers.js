// Importers for the web CPS: AnyTone .rdt (port of cps/import_rdt.py) and CSV (port of cps/import_csv.py).
// Results are codeplug dicts (same schema as codeplug.js); tests check they encode to the same bytes as Python.
import { CTCSS, normalizeChannel, newCodeplug, settingsDefaults, digiDefaults, VERSION, MODES } from "./codeplug.js";

export class ImportError extends Error {}

const u16 = (d, p) => d[p] | (d[p + 1] << 8);
const u32 = (d, p) => (d[p] | (d[p + 1] << 8) | (d[p + 2] << 16) | (d[p + 3] << 24)) >>> 0;
const latin1 = (d, a, b) => { let s = ""; for (let i = a; i < b; i++) s += String.fromCharCode(d[i]); return s; };

function cstr(d, p, mx = 16) {
  let e = p;
  while (e < p + mx && e < d.length && d[e] !== 0) e++;
  const s = latin1(d, p, e);
  if (e < p + mx) e++;
  return [s, e];
}

function s7(d, p, nstr = 6) {
  let bits = 0, n = 0, q = p, cur = "";
  const out = [];
  while (out.length < nstr) {
    while (n < 7) {
      if (q >= d.length) throw new ImportError("packed string runs past the end");
      bits |= d[q] << n; n += 8; q++;
    }
    const c = bits & 0x7f; bits >>>= 7; n -= 7;
    if (c === 0) { out.push(cur); cur = ""; } else { cur += String.fromCharCode(c); if (cur.length > 200) throw new ImportError("packed string too long"); }
  }
  return [out, q];
}

const ascii = (s, n = 16) => [...s].map((ch) => (ch.charCodeAt(0) >= 0x20 && ch.charCodeAt(0) < 0x7f ? ch : "?")).join("").slice(0, n);
const printable = (s) => [...s].every((c) => c.charCodeAt(0) >= 0x20 && c.charCodeAt(0) < 0x7f);

function chanOk(d, p) {
  if (p + 48 > d.length) return false;
  const rx = u32(d, p + 2), sh = d[p + 6], ty = d[p + 11];
  return rx >= 1000000 && rx <= 100000000 && sh <= 2 && ty <= 3;
}

function findChannels(d) {
  const cands = [0xf4]; for (let p = 0x40; p < 0x400; p++) cands.push(p);
  for (const p of cands) {
    const n = u16(d, p);
    if (!(n >= 1 && n <= 4000)) continue;
    let q = p + 2, ok = true, last = -1;
    for (let k = 0; k < Math.min(n, 8); k++) {
      if (!chanOk(d, q) || u16(d, q) <= last) { ok = false; break; }
      last = u16(d, q);
      let name; [name, q] = cstr(d, q + 48);
      if (!name || !printable(name)) { ok = false; break; }
      q += 12;
    }
    if (ok) return p;
  }
  throw new ImportError("channel table not found");
}

export function parseRdt(d) {
  const model = latin1(d, 9, 15);
  if (!["D878UV", "D890UV", "D868UV", "D578UV"].includes(model)) throw new ImportError(`not an AnyTone CPS .rdt file (model '${model}')`);
  const res = { model, cps_version: latin1(d, 0, 5), warnings: [] };
  res.power_on_text = latin1(d, 0, 5) === "V1270" ? cstr(d, 0x7f)[0] : "";
  let p = findChannels(d);
  const n = u16(d, p); p += 2;
  res.channels = [];
  for (let i = 0; i < n; i++) {
    if (!chanOk(d, p)) throw new ImportError(`channel record at 0x${p.toString(16)} unreadable`);
    const f = d.subarray(p, p + 48);
    let name; [name, p] = cstr(d, p + 48); p += 12;
    res.channels.push({ slot: u16(f, 0), rx: u32(f, 2) * 10, shift: f[6], offset: u32(f, 7) * 10, type: f[11], power: f[12] & 3,
      wide: f[13] === 1, rx_sig: f[18], rx_ctcss: f[19], rx_dcs: u16(f, 20), tx_sig: f[22], tx_ctcss: f[23], tx_dcs: u16(f, 24),
      custom_ctcss: u16(f, 26), contact: u16(f, 28), scanlist: f[34], cc: f[40], slot2: f[41] & 1, name });
  }
  res.radio_ids = [];
  const nid = d[p++];
  for (let i = 0; i < nid; i++) {
    const idx = d[p], id = d[p + 1] | (d[p + 2] << 8) | (d[p + 3] << 16);
    let name; [name, p] = cstr(d, p + 4);
    res.radio_ids.push({ idx, id, name });
  }
  res.zones = [];
  const nz = d[p++];
  for (let i = 0; i < nz; i++) {
    const idx = d[p], m = d[p + 1];
    if (idx !== i) throw new ImportError(`zone ${i}: index ${idx} at 0x${p.toString(16)}`);
    const mem = []; for (let k = 0; k < m + 2; k++) mem.push(u16(d, p + 2 + 2 * k));
    let name; [name, p] = cstr(d, p + 2 + 2 * (m + 2));
    res.zones.push({ name, members: mem.slice(0, m) });
  }
  res.scanlists = [];
  const ns = d[p++];
  for (let i = 0; i < ns; i++) {
    if (d[p] !== i) throw new ImportError(`scan list ${i}: index ${d[p]} at 0x${p.toString(16)}`);
    let name; [name, p] = cstr(d, p + 1);
    const m = d[p + 11]; p += 12;
    const mem = []; for (let k = 0; k < m; k++) mem.push(u16(d, p + 3 * k + 1));
    p += 3 * m;
    res.scanlists.push({ name, members: mem });
  }
  p += 4;
  res.talkgroups = [];
  for (;;) {
    try {
      if (p + 6 > d.length) break;
      const id = d[p] | (d[p + 1] << 8) | (d[p + 2] << 16), idx = u16(d, p + 3), ty = d[p + 5];
      if (idx !== res.talkgroups.length + 1) break;
      const [strs, q] = s7(d, p + 6);
      res.talkgroups.push({ id, type: ty, name: strs[0] });
      p = q;
    } catch (e) { if (e instanceof ImportError) break; throw e; }
  }
  p += 4;
  let nusers = 0;
  while (p + 6 < d.length) {
    try {
      if (u16(d, p + 3) !== ((nusers + 1) & 0xffff)) break;
      p = s7(d, p + 6)[1];
    } catch (e) { if (e instanceof ImportError) break; throw e; }
    nusers++;
  }
  res.user_db_entries = nusers;
  res.rx_group_lists = rxGroupLists(d, p, res.talkgroups.length, res.warnings);
  return res;
}

function rxGroupLists(d, p, ntg, warnings) {
  try {
    const at = (i) => { if (i >= d.length) throw new ImportError("index out of range"); return d[i]; };
    while (at(p) === 0 && at(p + 1) === 0) p++;
    const nsms = at(p) === 0 ? at(p + 1) : at(p);
    let q = at(p) === 0 ? p + 2 : p + 1;
    for (let i = 0; i < nsms; i++) { if (at(q) !== i) throw new ImportError("sms"); q = cstr(d, q + 1, 200)[1]; }
    q += 1;
    let i = 0;
    while (at(q) === i && at(q + 1) === 1) { q += 4; i++; }
    q += 4;
    const n = at(q); q++;
    const out = [];
    for (let k = 0; k < n; k++) {
      if (at(q) !== k) throw new ImportError("rx group list index");
      let name; [name, q] = cstr(d, q + 1);
      const m = at(q);
      const mem = []; for (let j = 0; j < m; j++) mem.push(u16(d, q + 1 + 2 * j));
      q += 1 + 2 * m;
      if (mem.some((x) => x >= ntg)) throw new ImportError("rx group list member out of range");
      out.push({ name, members: mem });
    }
    return out;
  } catch (e) {
    if (!(e instanceof ImportError)) throw e;
    warnings.push(`RX group lists not read (${e.message})`);
    return [];
  }
}

function tone(sig, idx, dcs, custom) {
  if (sig === 1) {
    const v = idx < CTCSS.length ? CTCSS[idx] : custom;
    return v ? `${Math.floor(v / 10)}.${v % 10}` : null;
  }
  if (sig === 2) return "D" + (dcs & 0x1ff).toString(8).padStart(3, "0") + (dcs & 0x200 ? "I" : "N");
  return null;
}

const POWER = ["low", "mid", "high", "turbo"];

export function rdtToCodeplug(res, digitalAs = "DMR") {
  const cp = { format: "cfw-codeplug", version: VERSION, generation: 0, created: 0, settings: settingsDefaults(),
    channels: [], zones: [], scanlists: [], contacts: [], tglists: [], trunksys: [], keys: [], dstar_rpts: [], digi: digiDefaults() };
  if (res.radio_ids.length) cp.settings.dmr_id = res.radio_ids[0].id;
  cp.settings.radio_name = ascii(res.power_on_text || "D890UV cfw");
  cp.settings.callsign = "N0CALL";
  for (const t of res.talkgroups) {
    const kind = { 0x10: "group", 0: "private", 0x20: "all" }[t.type] || "group";
    cp.contacts.push({ name: ascii(t.name), id: t.id, kind, mode: "DMR" });
  }
  const slot2idx = new Map();
  [...res.channels].sort((a, b) => a.slot - b.slot).forEach((ch, i) => {
    slot2idx.set(ch.slot, i);
    const c = { name: ascii(ch.name), rx_hz: ch.rx, power: POWER[ch.power] };
    c.tx_hz = ch.shift === 1 ? ch.rx + ch.offset : ch.shift === 2 ? ch.rx - ch.offset : ch.rx;
    if (ch.type === 1 || ch.type === 3) {
      c.mode = digitalAs; c.cc = ch.cc & 15; c.slot = ch.slot2 ? 2 : 1;
      if (ch.contact < cp.contacts.length) { c.contact = ch.contact; c.tg = cp.contacts[ch.contact].id; }
    } else {
      c.mode = "FM"; c.wide = ch.wide;
      c.rx_tone = tone(ch.rx_sig, ch.rx_ctcss, ch.rx_dcs, ch.custom_ctcss);
      c.tx_tone = tone(ch.tx_sig, ch.tx_ctcss, ch.tx_dcs, ch.custom_ctcss);
    }
    c.scanlist = ch.scanlist < res.scanlists.length ? ch.scanlist : null;
    cp.channels.push(normalizeChannel(c));
  });
  for (const z of res.zones) cp.zones.push({ name: ascii(z.name), channels: z.members.filter((m) => slot2idx.has(m)).map((m) => slot2idx.get(m)) });
  for (const s of res.scanlists) cp.scanlists.push({ name: ascii(s.name), channels: s.members.filter((m) => slot2idx.has(m)).map((m) => slot2idx.get(m)),
    prio1: null, prio2: null, dwell_100ms: 20, flags: 0 });
  for (const g of res.rx_group_lists) cp.tglists.push({ name: ascii(g.name), contacts: [...g.members] });
  return cp;
}

export function importRdt(bytes, digitalAs = "DMR") {
  const res = parseRdt(bytes);
  const cp = rdtToCodeplug(res, digitalAs);
  const rep = [`${res.model} CPS ${res.cps_version} file: ${res.channels.length} channels, ${res.zones.length} zones, ` +
    `${res.scanlists.length} scan lists, ${res.talkgroups.length} talkgroups/contacts, ${res.rx_group_lists.length} RX group lists, ` +
    `${res.radio_ids.length} radio IDs`, `user database: ${res.user_db_entries} entries (not imported: cfw has no contact database)`];
  return { cp, report: rep.concat(res.warnings) };
}

// ------------------------------------------------------------------ CSV

export const CFW_COLUMNS = ["name", "rx_mhz", "tx_mhz", "mode", "bw", "power", "rx_tone", "tx_tone", "cc", "slot", "tg", "contact",
  "nac", "wacn", "sysid", "ran", "dgid", "ur", "rpt1", "rpt2", "trunk", "scanlist", "zone"];

export function parseCsv(text) {
  text = text.replace(/^﻿/, "");
  const rows = [];
  let row = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(f); f = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(f); f = ""; if (row.length > 1 || row[0] !== "") rows.push(row); row = [];
    } else f += ch;
  }
  if (f !== "" || row.length) { row.push(f); rows.push(row); }
  if (!rows.length) return [];
  const head = rows[0];
  return rows.slice(1).map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

const mhz = (s) => { s = (s || "").trim(); return s ? Math.round(parseFloat(s) * 1e6) : 0; };
const pint = (s, def = 0) => {
  s = (s || "").trim();
  if (!s) return def;
  const v = /^0x/i.test(s) ? parseInt(s, 16) : /^0o/i.test(s) ? parseInt(s.slice(2), 8) : /^-?\d+$/.test(s) ? parseInt(s, 10) : NaN;
  if (Number.isNaN(v)) throw new ImportError(`invalid number '${s}'`);
  return v;
};

export function sniffCsv(text) {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/);
  const head = text.trim() ? lines[0].toLowerCase() : "";
  if (head.includes("location") && head.includes("frequency") && head.includes("duplex")) return "chirp";
  if (head.includes("rx_mhz") && head.includes("mode")) return "cfw";
  throw new ImportError("unknown CSV format (want CHIRP or cfw columns)");
}

export function readChirp(text) {
  const out = [];
  parseCsv(text).forEach((r, i) => {
    const mode = (r.Mode || "FM").trim();
    if (mode !== "FM" && mode !== "NFM") return;
    const rx = mhz(r.Frequency), dup = (r.Duplex || "").trim(), off = mhz(r.Offset);
    const tx = ({ "+": rx + off, "-": rx - off, split: off, off: 0 })[dup] ?? rx;
    const c = { name: (r.Name || `CH${i + 1}`).trim().slice(0, 16), rx_hz: rx, tx_hz: tx, mode: "FM", wide: mode === "FM" };
    const t = (r.Tone || "").trim(), rt = (r.rToneFreq || "88.5").trim(), ct = (r.cToneFreq || "88.5").trim();
    const pol = (r.DtcsPolarity || "NN").trim().toUpperCase() + "NN";
    const code = String(parseInt(r.DtcsCode || "23", 10)).padStart(3, "0");
    if (t === "Tone") c.tx_tone = rt;
    else if (t === "TSQL") c.tx_tone = c.rx_tone = ct;
    else if (t === "DTCS") { c.tx_tone = `D${code}${pol[0] === "R" ? "I" : "N"}`; c.rx_tone = `D${code}${pol[1] === "R" ? "I" : "N"}`; }
    else if (t === "Cross") {
      const [a, b] = ((r.CrossMode || "Tone->Tone").trim()).split("->");
      c.tx_tone = a === "Tone" ? rt : a === "DTCS" ? `D${code}N` : null;
      c.rx_tone = b === "Tone" ? ct : b === "DTCS" ? `D${code}N` : null;
    }
    if ((r.Skip || "").trim() === "S") c.scan_skip = true;
    out.push(normalizeChannel(c));
  });
  return out;
}

export function readCfwCsv(text) {
  const chans = [], zones = new Map();
  parseCsv(text).forEach((r, i) => {
    try {
      let mode = (r.mode || "FM").trim().toUpperCase();
      mode = { P25P1: "P25", "D-STAR": "DSTAR", C4FM: "YSF" }[mode] || mode;
      if (!MODES.includes(mode)) throw new ImportError(`mode '${mode}'`);
      const c = { name: (r.name || "").trim().slice(0, 16), rx_hz: mhz(r.rx_mhz), mode };
      c.tx_hz = (r.tx_mhz || "").trim() ? mhz(r.tx_mhz) : c.rx_hz;
      c.wide = ["25", "25k", "wide"].includes((r.bw || "").trim());
      c.power = (r.power || "high").trim().toLowerCase() || "high";
      c.rx_tone = (r.rx_tone || "").trim() || null; c.tx_tone = (r.tx_tone || "").trim() || null;
      c.cc = pint(r.cc, 1); c.slot = pint(r.slot, 1); c.tg = pint(r.tg, 0);
      const ct = (r.contact || "").trim(); c.contact = ct ? parseInt(ct, 10) - 1 : null;
      c.nac = pint(r.nac, 0x293); c.wacn = pint(r.wacn, 0); c.sysid = pint(r.sysid, 0); c.ran = pint(r.ran, 0); c.dgid = pint(r.dgid, 0);
      for (const k of ["ur", "rpt1", "rpt2"]) c[k] = (r[k] || "").trim().toUpperCase().slice(0, 8);
      c.trunk = ["1", "y", "yes", "true"].includes((r.trunk || "").trim().toLowerCase());
      const sl = (r.scanlist || "").trim(); c.scanlist = sl ? parseInt(sl, 10) - 1 : null;
      if (mode === "P25") c.slot = 0;
      for (const z of (r.zone || "").split("|")) if (z.trim()) { if (!zones.has(z.trim())) zones.set(z.trim(), []); zones.get(z.trim()).push(chans.length); }
      chans.push(normalizeChannel(Object.fromEntries(Object.entries(c).filter(([k]) =>
        ["name", "rx_hz", "tx_hz", "mode", "trunk", "scan_skip", "power", "scanlist"].includes(k) ||
        (mode === "FM" && ["wide", "rx_tone", "tx_tone"].includes(k)) || modeKeys(mode).includes(k)))));
    } catch (e) { throw new ImportError(`row ${i + 2}: ${e.message}`); }
  });
  return { chans, zones };
}

const modeKeys = (m) => ({ FM: [], DMR: ["cc", "slot", "tg", "contact", "tglist", "trunksys"],
  P25: ["nac", "tg", "contact", "tglist", "trunksys", "wacn", "sysid"], P25P2: ["nac", "slot", "tg", "contact", "tglist", "trunksys", "wacn", "sysid"],
  NXDN: ["ran", "tg", "contact", "tglist"], DSTAR: ["ur", "rpt1", "rpt2"], YSF: ["dgid"] })[m];

export function importCsv(text, cp = null) {
  const kind = sniffCsv(text);
  if (!cp) { cp = newCodeplug(); cp.channels = []; }
  const base = cp.channels.length;
  const { chans, zones } = kind === "chirp" ? { chans: readChirp(text), zones: new Map() } : readCfwCsv(text);
  cp.channels.push(...chans);
  for (const [name, mem] of zones) {
    let z = cp.zones.find((x) => x.name === name);
    if (!z) { z = { name: name.slice(0, 16), channels: [] }; cp.zones.push(z); }
    z.channels.push(...mem.map((m) => base + m));
  }
  return { cp, report: [`${kind} CSV: ${chans.length} channels, ${zones.size} zones`] };
}

const csvq = (v) => { v = String(v); return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; };

export function exportCsv(cp) {
  const inzone = new Map();
  for (const z of cp.zones) for (const m of z.channels) { if (!inzone.has(m)) inzone.set(m, []); inzone.get(m).push(z.name); }
  const lines = [CFW_COLUMNS.join(",")];
  cp.channels.forEach((c, i) => {
    const d = ["DMR", "P25", "P25P2", "NXDN"].includes(c.mode), p25 = c.mode === "P25" || c.mode === "P25P2";
    lines.push([c.name, (c.rx_hz / 1e6).toFixed(5), c.tx_hz ? (c.tx_hz / 1e6).toFixed(5) : "0", c.mode,
      c.mode === "FM" ? (c.wide ? "25" : "12.5") : "", c.power, c.rx_tone || "", c.tx_tone || "",
      c.mode === "DMR" ? c.cc : "", ["DMR", "P25P2"].includes(c.mode) ? c.slot : "", d ? c.tg : "",
      d && c.contact !== null ? c.contact + 1 : "", p25 ? "0x" + c.nac.toString(16).toUpperCase() : "",
      p25 && c.wacn ? "0x" + c.wacn.toString(16).toUpperCase() : "", p25 && c.sysid ? "0x" + c.sysid.toString(16).toUpperCase() : "",
      c.mode === "NXDN" ? c.ran : "", c.mode === "YSF" ? c.dgid : "", c.mode === "DSTAR" ? c.ur : "", c.mode === "DSTAR" ? c.rpt1 : "",
      c.mode === "DSTAR" ? c.rpt2 : "", c.trunk ? "1" : "", c.scanlist !== null ? c.scanlist + 1 : "", (inzone.get(i) || []).join("|")]
      .map(csvq).join(","));
  });
  return lines.join("\n") + "\n";
}
