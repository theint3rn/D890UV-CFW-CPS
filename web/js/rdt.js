// Stock D890UV CPS file (.rdt V1323, model "D890UV") and stock D168UV CPS file (V1292, "D168UV"): lossless reader /
// writer. Port of cps/rdt.py (layouts there, LAYOUT below).
// load(bytes) -> cfw codeplug dict (+ cp._rdt, the parsed file); save(cp) -> {bytes, lost: [tables not written]}.
import * as C from "./codeplug.js";
import * as ST from "./stock.js";

export class RdtError extends Error {}
let DEFAULT = null, OPTMAP = {}, NX = null;
const NX_ALIAS_MAX = 16;
export const LAYOUT = {
  D890UV: { C: 94, chanTail: 50, zoneExtra: ["after", 3], scanHdr: 14, tgPre: 6, userPre: 7, counted: true, fmName: true,
    segs: [[0, 0x81], [0x8a, 0x95], [0x9d, 0xfb]] },
  D168UV: { C: 90, chanTail: 35, zoneExtra: ["inline", 1], scanHdr: 11, tgPre: 4, userPre: 5, counted: false, fmName: false,
    segs: [[0, 0x81], [0x83, 0x8e], [0x8f, 0xe9]], endFrom: 0x400 },     // + tail block addressed from the file end
};
const DEFAULTS = {}, OPTMAPS = {}, CHBS = {};
// power-on texts of the stock new file the rdt_map experiments were made on (cps/rdt.py REF_TEXTS)
const REF_TEXTS = { D890UV: ["WELCOME", "", "ANYTONE"], D168UV: ["", "", ""] };
export const TEMPLATE_FILES = { D890UV: "new_v1323.rdt", D168UV: "new_v1292.rdt" };
/** the user's stock CPS new file (File > New, saved) for writing .rdt files that were not opened from one; cfw_cps
 *  does not ship it (cps/rdt.py template_path) */
export function setTemplate(bytes, model) {
  const m = fileModel(bytes);
  if (!m || (model && m !== model)) throw new Error(`not a stock ${model || "D890UV / D168UV"} CPS file`);
  DEFAULTS[m] = bytes;
  if (m === "D890UV") DEFAULT = bytes;
  return m;
}
export const hasTemplate = (model) => !!DEFAULTS[model];
export function clearTemplate(model) { delete DEFAULTS[model]; if (model === "D890UV") DEFAULT = null; }   // back to the built-in blank
export const templateHelp = (model) => `no stock ${model} .rdt template: cfw_cps does not ship one. In the stock ${model} CPS do `
  + `File > New and save the empty codeplug, then load it here (Load .rdt template). Opening an .rdt and saving it again needs no template.`;
// the template: the user's stock new file when given, else the built-in blank file (cps/rdt.py _default_file)
function defaultFile(model) {
  return DEFAULTS[model] ? parse(DEFAULTS[model]) : blankFile(model);
}
// built-in blank file: layout + cfw_cps's own defaults, no stock bytes (cps/rdt.py BLANK, blank_file)
const u32le = (v) => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
export const BLANK = {
  D890UV: { version: "V1323", tailLen: 22881, hdr: { 23: 1 }, tgPre: {}, userPre: { 4: 1 }, smsPre: [1, 0, 0],
    tail: { 126: "APZCFW", 133: "N0CALL", 140: "WIDE1-1,WIDE2-1", 156: "/[N0CALL", 167: 1, 181: "Roam Chan 01", 194: 1,
      198: "Roam List 1", 210: 1, 22360: 2, 22364: 1, 22365: u32le(11800000), 22369: "AIR 01", 22377: 1,
      22379: u32le(11800000), 22383: "VFO", 22876: "V1323" } },
  D168UV: { version: "V1292", tailLen: 24052, hdr: { 23: 1 }, tgPre: {}, userPre: {}, smsPre: [1, 0, 0],
    tail: { 126: "APZCFW\x01N0CALL", 140: "WIDE1-1WIDE2-1", 155: "/[N0CALL", 166: 1, 180: "Roaming Chan 1", 195: 1,
      199: "Roam List 1", 211: 1, 24047: "V1292" } },
};
const FM_VFO = { idx: 100, flag: 0, freq: 8750, name: "" };
const defaultContact = () => ({ id: 1, idx: 1, type: 0x10, strs: ["Contact 1", "", "", "", "", ""], raw: new Uint8Array(0) });
function blankChannel(model) {
  const x = new Uint8Array(48), ch = ST.schemaOf(model).tables.Channel;
  const v = parseFloat(ch.defaults[ch.columns.indexOf("Custom CTCSS")] ?? "0");
  if (!isNaN(v)) { const n = Math.round(v * 10); x[26] = n & 0xff; x[27] = (n >> 8) & 0xff; }
  x[34] = 0xff;
  return { fixed: x, name: "", tail: new Uint8Array(LAYOUT[model].chanTail) };
}
export function blankFile(model = "D890UV") {
  const L = LAYOUT[model], B = BLANK[model];
  const A = new Uint8Array(0x81);
  A.set(ST.toLatin1(B.version), 0); A.set(ST.toLatin1(model), 9); A.set(ST.toLatin1("V100"), 19);
  for (const [k, v] of Object.entries(B.hdr)) A[k] = v;
  const segs = { A, B: new Uint8Array(L.segs[1][1] - L.segs[1][0]), C: new Uint8Array(L.C), E: new Uint8Array(B.tailLen) };
  for (const [k, v] of Object.entries(B.tail)) {
    if (typeof v === "number") segs.E[k] = v; else segs.E.set(typeof v === "string" ? ST.toLatin1(v) : v, +k);
  }
  const sch = ST.schemaOf(model).tables.OptionalSetting, opt = Object.fromEntries(sch.columns.map((c, i) => [c, sch.defaults[i]]));
  for (const [k, [seg, o]] of Object.entries(optFields(model))) {
    const v = /^\d+$/.test(opt[k] ?? "") ? parseInt(opt[k], 10) : NaN;
    if (!(v >= 0 && v <= 255)) continue;
    if (seg === "E") segs.E[segs.E.length - o] = v; else segs[seg][o] = v;
  }
  const hs = {};
  for (const t of Object.values(ST.dialogDefs())) for (const fd of t.fields) {      // own defaults of the .rdt-only dialogs (cps/rdt.py blank_file)
    const loc = fd[model];
    if (!loc || !["A", "C", "H", "E"].includes(loc.seg)) continue;
    if (loc.seg === "H") { hs[loc.off] = loc.type === "hnum" ? parseInt(loc.default, 10) : loc.default; continue; }
    const v = fldBytes(loc, loc.default);
    if (v && loc.seg !== "E") segs[loc.seg].set(v, loc.off);
  }
  const tgPre = new Uint8Array(L.tgPre), userPre = new Uint8Array(L.userPre);
  for (const [k, v] of Object.entries(B.tgPre)) tgPre[k] = v;
  for (const [k, v] of Object.entries(B.userPre)) userPre[k] = v;
  const f = { version: B.version, model, A: segs.A, line1: "", password: "", B: segs.B, line2: "", C: segs.C, channels: [], ids: [],
    zones: [], scans: [], tg_pre: tgPre, tgs: [defaultContact()], user_pre: userPre, users: [], sms_pre: Uint8Array.from(B.smsPre), sms: [],
    fm: [], rxgroups: [], tail: model === "D168UV" ? segs.E.slice(1) : segs.E, friends: [], enc: [], hs };
  if (!L.fmName) f.fm_vfo = Object.assign({}, FM_VFO);
  return f;
}
export const blankRdt = (model = "D890UV") => serialise(blankFile(model));
/** defaultRdt: the model's template bytes (setTemplate) or null; rdtMap: schema/rdt_map.json / rdt_map_d168.json */
export function setDefaults(defaultRdt, rdtMap, model = "D890UV") {
  if (defaultRdt) DEFAULTS[model] = defaultRdt;
  const om = {};
  for (const [col, offs] of Object.entries((rdtMap || {}).OptionalSetting || {})) {
    if (offs.length !== 1) continue;
    const o = offs[0];
    LAYOUT[model].segs.forEach(([a, b], i) => { if (o >= a && o < b) om[col] = ["ABC"[i], o - a]; });
    const ref = ((rdtMap || {})._ref_len || {}).OptionalSetting;
    if (LAYOUT[model].endFrom && ref && o >= LAYOUT[model].endFrom && o < ref) om[col] = ["E", ref - o];
  }
  OPTMAPS[model] = om;
  CHBS[model] = model === "D890UV" ? CH_BYTES : Object.assign({}, CH_BYTES_D168, mapTailBytes(model, rdtMap));
  if (model !== "D890UV") return;
  if (defaultRdt) DEFAULT = defaultRdt;
  OPTMAP = om;
  // NXSetting in the tail (cps/rdt.py _nx_fields): fields after the TxAliasName cstr from the file end, before it from the alias
  NX = null;
  const nx = (rdtMap || {}).NXSetting || {}, ref = ((rdtMap || {})._ref_len || {}).NXSetting;
  if ((nx.TxAliasEn || []).length === 1 && ref) {
    const alias = nx.TxAliasEn[0] + 1, fields = {};
    const pre = Object.entries(nx).filter(([, o]) => o.length === 1 && o[0] < alias).map(([c, o]) => [o[0], c]).sort((a, b) => a[0] - b[0]);
    pre.forEach(([o, c], i) => { fields[c] = ["pre", alias - o, (i + 1 < pre.length ? pre[i + 1][0] : alias) - o]; });
    for (const [c, o] of Object.entries(nx)) if (o.length === 1 && o[0] > alias) fields[c] = ["post", ref - o[0], 1];
    NX = [ref - alias, fields];
  }
}
const printable = (b) => b >= 0x20 && b < 0x7f;
function nxFind(tail) {
  if (!NX || tail.length < NX[0] + 16) return null;
  const nul = tail.length - NX[0];
  if (tail[nul] !== 0) return null;
  let a = nul;
  while (a > nul - NX_ALIAS_MAX && printable(tail[a - 1])) a--;
  if (tail[a - 1] !== 0 && tail[a - 1] !== 1) return null;
  return [a, nul - a];
}
export function nxRow(tail) {
  const loc = nxFind(tail);
  if (!loc) return null;
  const [a, L] = loc, cols = ST.TABLES.NXSetting.columns, row = ST.defaultRows("NXSetting")[0].slice();
  const byName = Object.fromEntries(cols.map((c) => [c.trim(), c]));
  for (const [c, [kind, d, size]] of Object.entries(NX[1])) {
    const p = kind === "pre" ? a - d : tail.length - d;
    let v = 0; for (let i = size - 1; i >= 0; i--) v = v * 256 + tail[p + i];
    const col = byName[c.trim()]; if (col !== undefined) row[cols.indexOf(col)] = String(v);
  }
  row[cols.indexOf("TxAliasName")] = lat(tail, a, a + L);
  return row;
}
export function nxPatch(tail, row) {
  const loc = nxFind(tail);
  if (!loc) return null;
  const [a, L] = loc, cols = ST.TABLES.NXSetting.columns;
  const r = Object.fromEntries(cols.map((c, i) => [c.trim(), row[i] ?? ""]));
  const alias = Array.from(ST.toLatin1(r.TxAliasName || "")).slice(0, NX_ALIAS_MAX).map((b) => (printable(b) ? b : 0x3f));
  const t = new Uint8Array(tail.length - L + alias.length);
  t.set(tail.subarray(0, a), 0); t.set(alias, a); t.set(tail.subarray(a + L), a + alias.length);
  for (const [c, [kind, d, size]] of Object.entries(NX[1])) {
    const s = r[c.trim()] ?? "";
    if (!/^\d+$/.test(s)) continue;
    let v = parseInt(s, 10);
    if (v >= 2 ** (8 * size)) continue;
    const p = kind === "pre" ? a - d : t.length - d;
    for (let i = 0; i < size; i++) { t[p + i] = v & 0xff; v = Math.floor(v / 256); }
  }
  return t;
}
export const optFields = (model = "D890UV") => OPTMAPS[model] || {};
const fileModel = (d) => { const m = lat(d, 9, 15); return LAYOUT[m] ? m : null; };

const u16 = (d, p) => d[p] | (d[p + 1] << 8);
const u32 = (d, p) => (d[p] | (d[p + 1] << 8) | (d[p + 2] << 16) | (d[p + 3] << 24)) >>> 0;
const lat = (d, a, b) => { let s = ""; for (let i = a; i < b; i++) s += String.fromCharCode(d[i]); return s; };
function cstr(d, p, mx) { let e = p; while (e < p + mx && e < d.length && d[e] !== 0) e++; const s = lat(d, p, e); if (e < p + mx) e++; return [s, e]; }
function wcstr(s, mx) { const b = Array.from(ST.toLatin1(s)).slice(0, mx); if (b.length < mx) b.push(0); return b; }
function s7(d, p, nstr = 6) {
  let bits = 0, n = 0, q = p, cur = "";
  const out = [];
  while (out.length < nstr) {
    while (n < 7) { if (q >= d.length) throw new RdtError("packed string runs past the end"); bits |= d[q] << n; n += 8; q++; }
    const c = bits & 0x7f; bits >>>= 7; n -= 7;
    if (c === 0) { out.push(cur); cur = ""; } else cur += String.fromCharCode(c);
  }
  return [out, q];
}
function w7(strs) {
  let bits = 0, n = 0;
  const out = [];
  for (const s of strs) for (const ch of [...ST.toLatin1(s), 0]) {
    bits |= (ch & 0x7f) << n; n += 7;
    while (n >= 8) { out.push(bits & 0xff); bits >>>= 8; n -= 8; }
  }
  if (n) out.push(bits & 0xff);
  return out;
}
const le = (v, n) => Array.from({ length: n }, (_, i) => (v >>> (8 * i)) & 0xff);

function records(d, p, n, end = null) {
  const out = [];
  while (end === null ? out.length < n : p < end) {
    const id = d[p] | (d[p + 1] << 8) | (d[p + 2] << 16), idx = u16(d, p + 3), type = d[p + 5];
    const [strs, q] = s7(d, p + 6);
    out.push({ id, idx, type, strs, raw: d.slice(p, q) });
    p = q;
  }
  return [out, p];
}

// header segment A holds variable strings: -> [A with them taken out, strings, position after it] (cps/rdt.py _hdr_parse)
function hdrParse(d) {
  const h = {}, a = new Uint8Array(0x81);
  let p;
  a.set(d.subarray(0, 0x1c)); a[0x1a] = 0;
  [h.t5_self, p] = cstr(d, 0x1c, 16);
  a.set(d.subarray(p, p + 11), 0x1d); p += 11;
  const n = d[p++];
  h.info = [];
  for (let i = 0; i < n; i++) {
    const idx = d[p], func = d[p + 1], resp = d[p + 2];
    let id, name;
    [id, p] = cstr(d, p + 4, 16); [name, p] = cstr(d, p, 32);
    h.info.push({ idx, func, resp, id, name });
  }
  for (const key of ["bot", "eot"]) {
    if (d[p++]) { [h["t5_" + key], p] = cstr(d, p, 16); h[`t5_${key}_std`] = d[p]; h[`t5_${key}_time`] = d[p + 1]; p += 2; }
    else { h["t5_" + key] = ""; h[`t5_${key}_std`] = 0; h[`t5_${key}_time`] = 70; }
  }
  if (d[p] || d[p + 3]) throw new RdtError("header byte 0x2B / 0x2E is not zero: unknown string block in the file header");
  a.set(d.subarray(p, p + 4), 0x2b); p += 4;
  for (const key of ["bot", "eot", "kill", "stun"]) { if (d[p++]) [h["dtmf_" + key], p] = cstr(d, p, 16); else h["dtmf_" + key] = ""; }
  a.set(d.subarray(p, p + 0x4e), 0x33);
  return [a, h, p + 0x4e];
}
function hdrWrite(a, h) {
  h = h || {};
  const b = (s) => [...ST.toLatin1(s || ""), 0], out = [...a.subarray(0, 0x1c)];
  out[0x1a] = (h.t5_self || "").length;
  out.push(...b(h.t5_self), ...a.subarray(0x1d, 0x28));
  const info = h.info || [];
  out.push(info.length);
  for (const r of info) out.push(r.idx, r.func, r.resp, r.id.length, ...b(r.id), ...b(r.name));
  for (const key of ["bot", "eot"]) {
    const s = h["t5_" + key] || "";
    out.push(s.length);
    if (s) out.push(...b(s), h[`t5_${key}_std`] ?? 0, h[`t5_${key}_time`] ?? 70);
  }
  out.push(...a.subarray(0x2b, 0x2f));
  for (const key of ["bot", "eot", "kill", "stun"]) { const s = h["dtmf_" + key] || ""; out.push(s.length); if (s) out.push(...b(s)); }
  out.push(...a.subarray(0x33, 0x81));
  return out;
}

export function parse(d) {
  const model = fileModel(d);
  if (!model) throw new RdtError(`not a stock D890UV / D168UV CPS file (model '${lat(d, 9, 15)}')`);
  const L = LAYOUT[model];
  const f = { version: lat(d, 0, 5), model };
  let p;
  [f.A, f.hs, p] = hdrParse(d);
  [f.line1, p] = cstr(d, p, 16);
  [f.password, p] = cstr(d, p, 8);
  f.B = d.slice(p, p + 11); p += 11;
  [f.line2, p] = cstr(d, p, 16);
  f.C = d.slice(p, p + L.C); p += L.C;
  let n = u16(d, p); p += 2;
  f.channels = [];
  for (let i = 0; i < n; i++) {
    const fixed = d.slice(p, p + 48);
    const [name, q] = cstr(d, p + 48, 16);
    f.channels.push({ fixed, name, tail: d.slice(q, q + L.chanTail) });
    p = q + L.chanTail;
  }
  n = d[p++]; f.ids = [];
  for (let i = 0; i < n; i++) { const idx = d[p], id = d[p + 1] | (d[p + 2] << 8) | (d[p + 3] << 16); let name; [name, p] = cstr(d, p + 4, 16); f.ids.push({ idx, id, name }); }
  n = d[p++]; f.zones = [];
  for (let i = 0; i < n; i++) {
    if (d[p] !== i) throw new RdtError(`zone ${i} at 0x${p.toString(16)}`);
    const m = d[p + 1], slots = [];
    for (let k = 0; k < m + 2; k++) slots.push(u16(d, p + 2 + 2 * k));
    let name; [name, p] = cstr(d, p + 2 + 2 * (m + 2), 16);
    f.zones.push({ slots: slots.slice(0, m), a: slots[m], b: slots[m + 1], name });
    if (L.zoneExtra[0] === "inline") { f.zones[i].extra = d.slice(p, p + L.zoneExtra[1]); p += L.zoneExtra[1]; }
  }
  if (L.zoneExtra[0] === "after") for (const z of f.zones) { z.extra = d.slice(p, p + L.zoneExtra[1]); p += L.zoneExtra[1]; }
  n = d[p++]; f.scans = [];
  for (let i = 0; i < n; i++) {
    if (d[p] !== i) throw new RdtError(`scan list ${i} at 0x${p.toString(16)}`);
    let name; [name, p] = cstr(d, p + 1, 16);
    const hdr = d.slice(p, p + L.scanHdr), m = d[p + L.scanHdr]; p += L.scanHdr + 1;
    const members = []; for (let k = 0; k < m; k++) members.push([d[p + 3 * k], u16(d, p + 3 * k + 1)]);
    p += 3 * m;
    f.scans.push({ name, hdr, members });
  }
  f.tg_pre = d.slice(p, p + L.tgPre);
  if (L.counted) { n = u16(d, p + 1); p += L.tgPre; [f.tgs, p] = records(d, p, n); }
  else { const end = p + 3 + u16(d, p + 1); p += L.tgPre; [f.tgs, p] = records(d, p, 0, end); }
  f.user_pre = d.slice(p, p + L.userPre); n = d[p + 1] | (d[p + 2] << 8) | (d[p + 3] << 16);
  if (L.counted) { p += L.userPre; [f.users, p] = records(d, p, n); }
  else { const end = p + 4 + n; p += L.userPre; [f.users, p] = records(d, p, 0, end); }
  f.sms_pre = Uint8Array.from([d[p], 0, 0]);
  n = u16(d, p + 1); p += 3; f.friends = [];                    // Friends List: u16 count, u24 index into the digital contact list
  for (let i = 0; i < n; i++) f.friends.push(d[p + 3 * i] | (d[p + 3 * i + 1] << 8) | (d[p + 3 * i + 2] << 16));
  p += 3 * n;
  n = d[p++]; f.sms = [];
  for (let i = 0; i < n; i++) { if (d[p] !== i) throw new RdtError(`SMS ${i}`); let t; [t, p] = cstr(d, p + 1, 200); f.sms.push(t); }
  n = d[p++]; f.fm = [];
  for (let i = 0; i < n; i++) {
    const idx = d[p], flag = d[p + 1], freq = u16(d, p + 2); let name = "";
    if (L.fmName) [name, p] = cstr(d, p + 4, 16); else p += 4;
    f.fm.push({ idx, flag, freq, name });
  }
  if (!L.fmName) f.fm_vfo = f.fm.length && f.fm[f.fm.length - 1].idx === 100 ? f.fm.pop() : null;      // D168: FM VFO record
  n = d[p++]; f.rxgroups = [];
  for (let i = 0; i < n; i++) {
    if (d[p] !== i) throw new RdtError(`RX group list ${i}`);
    let name; [name, p] = cstr(d, p + 1, 16);
    const m = d[p], members = []; for (let k = 0; k < m; k++) members.push(u16(d, p + 1 + 2 * k));
    p += 1 + 2 * m;
    f.rxgroups.push({ name, members });
  }
  f.tail = d.slice(p);
  f.enc = [];
  if (model === "D168UV") {                  // Encryption Code: u8 count, {u8 row (0-based), u16 key, u16 ID}
    n = f.tail[0];
    for (let i = 0; i < n; i++) f.enc.push([f.tail[1 + 5 * i], [u16(f.tail, 2 + 5 * i), u16(f.tail, 4 + 5 * i)]]);
    f.tail = f.tail.slice(1 + 5 * n);
  }
  return f;
}

function sameRecord(r) {
  if (!r.raw || !r.raw.length) return false;
  try {
    const [strs] = s7(r.raw, 6);
    return (r.raw[0] | (r.raw[1] << 8) | (r.raw[2] << 16)) === r.id && u16(r.raw, 3) === r.idx && r.raw[5] === r.type && JSON.stringify(strs) === JSON.stringify(r.strs);
  } catch (e) { return false; }
}
const wrecords = (recs) => recs.flatMap((r) => (sameRecord(r) ? Array.from(r.raw) : [...le(r.id, 3), ...le(r.idx, 2), r.type, ...w7(r.strs)]));

export function serialise(f) {
  const L = LAYOUT[f.model || "D890UV"];
  const b = [...hdrWrite(f.A, f.hs), ...wcstr(f.line1, 16), ...wcstr(f.password, 8), ...f.B, ...wcstr(f.line2, 16), ...f.C, ...le(f.channels.length, 2)];
  for (const c of f.channels) b.push(...c.fixed, ...wcstr(c.name, 16), ...c.tail);
  b.push(f.ids.length);
  for (const r of f.ids) b.push(r.idx, ...le(r.id, 3), ...wcstr(r.name, 16));
  b.push(f.zones.length);
  const inline = L.zoneExtra[0] === "inline";
  f.zones.forEach((z, i) => { b.push(i, z.slots.length); for (const s of [...z.slots, z.a, z.b]) b.push(...le(s, 2)); b.push(...wcstr(z.name, 16)); if (inline) b.push(...z.extra); });
  if (!inline) for (const z of f.zones) b.push(...z.extra);
  b.push(f.scans.length);
  f.scans.forEach((s, i) => { b.push(i, ...wcstr(s.name, 16), ...s.hdr, s.members.length); for (const [x, slot] of s.members) b.push(x, ...le(slot, 2)); });
  const tr = wrecords(f.tgs), tp = Array.from(f.tg_pre), tn = L.counted ? f.tgs.length : tp.length - 3 + tr.length;
  tp[1] = tn & 0xff; tp[2] = (tn >> 8) & 0xff;
  if (L.counted) { tp[3] = (tr.length + 1) & 0xff; tp[4] = ((tr.length + 1) >> 8) & 0xff; }   // D890: record bytes + 1 (cps/rdt.py)
  for (const x of tp) b.push(x);
  for (let i = 0; i < tr.length; i++) b.push(tr[i]);
  const ur = wrecords(f.users), up = Array.from(f.user_pre), un = L.counted ? f.users.length : up.length - 4 + ur.length;
  up[1] = un & 0xff; up[2] = (un >> 8) & 0xff; up[3] = (un >> 16) & 0xff;
  if (L.counted && (up[4] | (up[5] << 8) | (up[6] << 16)) < ur.length + 1) { const n = ur.length + 1; up[4] = n & 0xff; up[5] = (n >> 8) & 0xff; up[6] = (n >> 16) & 0xff; }
  for (const x of up) b.push(x);
  for (let i = 0; i < ur.length; i++) b.push(ur[i]);
  const sp = Array.from(f.sms_pre);
  if (sp[0] === 0 || sp[0] === 1) sp[0] = f.users.length ? 0 : 1;        // 1 = empty user database (cps/rdt.py)
  const fr = f.friends || [];
  sp[1] = fr.length & 0xff; sp[2] = fr.length >> 8;
  b.push(...sp);
  for (const i of fr) b.push(...le(i, 3));
  b.push(f.sms.length);
  f.sms.forEach((t, i) => b.push(i, ...wcstr(t, 200)));
  const fm = f.fm.concat(f.fm_vfo ? [f.fm_vfo] : []);
  b.push(fm.length);
  for (const r of fm) b.push(r.idx, r.flag, ...le(r.freq, 2), ...(L.fmName ? wcstr(r.name, 16) : []));
  b.push(f.rxgroups.length);
  f.rxgroups.forEach((g, i) => { b.push(i, ...wcstr(g.name, 16), g.members.length); for (const m of g.members) b.push(...le(m, 2)); });
  if (f.model === "D168UV") {
    b.push((f.enc || []).length);
    for (const [row, [key, ident]] of f.enc || []) b.push(row, ...le(key, 2), ...le(ident, 2));
  }
  const out = new Uint8Array(b.length + f.tail.length);
  out.set(b); out.set(f.tail, b.length);
  new DataView(out.buffer).setUint32(5, out.length - 14, true);   // header: file length - 14 (stock CPS checks it)
  return out;
}

// ------------------------------------------------------------------ file <-> stock tables
const POWER = ["Low", "Middle", "High", "Turbo"];
const TYPES = ["A-Analog", "D-Digital", "A+D TX A", "D+A TX D"];
const CALLTYPE = { 0x10: "Group Call", 0x00: "Private Call", 0x20: "All Call" };
const CALLTYPE_R = { "Group Call": 0x10, "Private Call": 0x00, "All Call": 0x20 };
const BUSY = { false: { 0: "Off", 2: "Channel Free" }, true: { 0: "Always", 1: "Channel Free", 2: "Different Color Code" } };
const BUSY_D168 = { false: { 0: "Off", 2: "Busy" }, true: BUSY.true };      // the D168 CPS calls analog busy lock "Busy"
const ONOFF = ["Off", "On"];
const CH_BYTES = { "Squelch Mode": [33, ["Carrier", "CTCSS/DCS"]], "PTT Prohibit": [15, ONOFF], "Talk Around(Simplex)": [17, ONOFF],
  "Digital Duplex": [42, ONOFF], "AES Digital Encryption": [47, ["Normal Encryption", "Enhanced Encryption"]], "2TONE Decode": [48, null], txcc: [97, null],
  // tail bytes from schema/rdt_map.json (value byte = CSV value)
  "Exclude channel from roaming": [59, null], "DMR MODE": [60, null], "DataACK Disable": [65, null], "R5toneBot": [66, null], "R5ToneEot": [67, null], "Auto Scan": [68, null], "Ana APRS Mute": [69, null], "Send Talker Alias DMR/NX": [70, null], "AnaAprsTxPath": [72, null], "ARC4": [73, null], "ex_emg_kind": [74, null], "Rpga_Mdc": [75, null], "DisturEn": [76, null], "DisturFreq": [77, null], "dmr_crc_ignore": [78, null], "compand": [79, null], "dup_call": [80, null], "tx_int": [81, null], "BtRxState": [82, null], "idle_tx": [83, null], "tx_talkalaes": [84, null], "nxdn_wn": [85, null], "NxdnRpga": [86, null], "nxdnSqCon": [87, null], "NxdnTxBusy": [88, null], "NxDnPttId": [89, null], "EnRan": [90, null], "DeRan": [91, null], "NxdnEncry": [92, null], "NxdnGroupId": [93, null], "NxdnIdNum": [94, null], "NxdnStateNum": [96, null] };
const D168_B17 = { false: "Talk Around(Simplex)", true: "Work Alone" };     // byte 17: analog TA, digital Work Alone
const CH_BYTES_D168 = { "Squelch Mode": [33, ["Carrier", "CTCSS/DCS"]], "PTT Prohibit": [15, ONOFF], "Idle TX": [42, ONOFF],
  "AES Digital Encryption": [47, ["Normal Encryption", "Enhanced Encryption"]] };
// D168: channel columns the experiments found in one tail byte (cps/rdt.py _map_tail_bytes)
function mapTailBytes(model, rdtMap) {
  const m = (rdtMap || {}).Channel || {}, L = LAYOUT[model], [l1, pw, l2] = REF_TEXTS[model];
  const first = 0x81 + wcstr(l1, 16).length + wcstr(pw, 8).length + 11 + wcstr(l2, 16).length + L.C + 2;
  const tail0 = first + 48 + wcstr("Channel 1", 16).length;
  const sch = ST.schemaOf(model).tables.Channel, defs = Object.fromEntries(sch.columns.map((c, i) => [c, sch.defaults[i]]));
  const alias = Object.fromEntries((sch.csv_columns || sch.columns).map((c, i) => [c, sch.columns[i]]));
  const out = {};
  for (const [col0, offs0] of Object.entries(m)) {
    const col = alias[col0] ?? col0;
    const offs = offs0.filter((o) => o >= tail0);
    if (offs.length === 1 && offs[0] - tail0 < L.chanTail) {
      if (/^\d+$/.test(defs[col] ?? "x")) out[col] = [48 + offs[0] - tail0, null];
      else if (ONOFF.includes(defs[col])) out[col] = [48 + offs[0] - tail0, ONOFF];
    }
  }
  return out;
}
const SCAN_TIMES = { "Look Back Time A[s]": 7, "Look Back Time B[s]": 8, "Dropout Delay Time[s]": 9, "Dwell Time[s]": 10 };
const rb = (c, pos) => (pos < 48 ? c.fixed[pos] : c.tail[pos - 48]);
const mhz10 = (v) => (v * 10 / 1e6).toFixed(5);
function toneText(sig, idx, dcs, custom) {
  if (sig === 1) { const v = idx < C.CTCSS.length ? C.CTCSS[idx] : custom; return `${Math.floor(v / 10)}.${v % 10}`; }
  if (sig === 2) return "D" + (dcs & 0x1ff).toString(8).padStart(3, "0") + (dcs & 0x200 ? "I" : "N");
  return "Off";
}
function toneBytes(text) {
  if (text === "Off") return [0, null, null];
  if (text.startsWith("D")) { const v = parseInt(text.slice(1, 4), 8); return Number.isNaN(v) ? null : [2, null, v | (text.endsWith("I") ? 0x200 : 0)]; }
  const v = Math.round(parseFloat(text) * 10);
  return C.CTCSS.includes(v) ? [1, C.CTCSS.indexOf(v), null] : null;
}

// ------------------------------------------------------------ .rdt-only dialogs (cps/rdt.py, schema/rdt_dialogs.json)
function ePos(f, dist) {
  const loc = f.model === "D890UV" ? nxFind(f.tail) : null;
  return f.tail.length - dist - (loc ? loc[1] : 0);
}
function fldGet(f, loc) {
  const { type, seg, off } = loc;
  if (seg === "H") return String((f.hs || {})[off] ?? loc.default);
  const b = seg === "E" ? f.tail : f[seg], p = seg === "E" ? ePos(f, off) : off;
  if (p < 0 || p >= b.length) return loc.default;
  if (type === "u8") return String(b[p]);
  const hx = (v, n) => v.toString(16).toUpperCase().padStart(n, "0");
  if (["u16", "chan", "hex3", "hex4"].includes(type)) { const v = b[p] | (b[p + 1] << 8); return type === "chan" ? String(v + 1) : type === "hex3" ? hx(v, 3) : type === "hex4" ? hx(v, 4) : String(v); }
  if (type === "u32") return String((b[p] | (b[p + 1] << 8) | (b[p + 2] << 16) | (b[p + 3] << 24)) >>> 0);
  if (type === "str3") return latin1z(b.subarray(p, p + 3));
  throw new RdtError(`dialog field type ${type}`);
}
const latin1z = (b) => { let s = ""; for (const x of b) { if (!x) break; s += String.fromCharCode(x); } return s; };
function fldBytes(loc, text) {
  const t = String(text ?? "").trim(), typ = loc.type;
  if (typ === "str3") { const x = ST.toLatin1(t).slice(0, 3); return Uint8Array.from([0, 1, 2], (i) => x[i] || 0); }
  let v;
  if (typ === "hex3" || typ === "hex4") v = /^[0-9a-f]+$/i.test(t) ? parseInt(t, 16) : NaN;
  else { v = /^-?\d+$/.test(t) ? parseInt(t, 10) : NaN; if (typ === "chan") v -= 1; }
  if (Number.isNaN(v)) return null;
  if (typ === "u8") return v >= 0 && v <= 255 ? Uint8Array.from([v]) : null;
  if (typ === "u32") return v >= 0 && v < 2 ** 32 ? Uint8Array.from(le(v >>> 0, 4)) : null;
  return v >= 0 && v < 65536 ? Uint8Array.from(le(v, 2)) : null;
}
export function dialogRows(f) {
  const out = {}, hs = f.hs || {};
  for (const [name, t] of Object.entries(ST.DIALOGS)) {
    if (t.kind === "record") out[name] = [t.fields.map((fd) => (fd[f.model] ? fldGet(f, fd[f.model]) : ""))];
  }
  if (ST.DIALOGS.T5InfoCodes) out.T5InfoCodes = (hs.info || []).map((r) => [String(r.idx), String(r.func), String(r.resp), r.id]);
  if (ST.DIALOGS.FriendsList) out.FriendsList = (f.friends || []).filter((k) => k < f.users.length).map((k, i) => [String(i + 1), String(f.users[k].id)]);
  if (ST.DIALOGS.EncryptionCodeRdt) out.EncryptionCodeRdt = (f.enc || []).map(([row, [key, ident]]) => [String(row + 1), key.toString(16).toUpperCase().padStart(4, "0"), String(ident)]);
  return out;
}
function dialogWrite(f, base, cp) {
  const old = dialogRows(Object.assign({}, base, { model: f.model })), hs = JSON.parse(JSON.stringify(base.hs || {})), stock = cp.stock || {};
  for (const [name, t] of Object.entries(ST.DIALOGS)) {
    const rows = stock[name];
    if (!rows || !rows.length || t.kind !== "record") continue;
    t.fields.forEach((fd, i) => {
      const loc = fd[f.model], val = rows[0][i];
      if (!loc || val === undefined || val === old[name][0][i]) return;
      if (loc.seg === "H") {
        if (loc.type === "hnum") { const n = parseInt(val, 10); if (!Number.isNaN(n)) hs[loc.off] = n & 0xff; } else hs[loc.off] = val.slice(0, 16);
        return;
      }
      const b = fldBytes(loc, val);
      if (!b) return;
      const seg = loc.seg === "E" ? "tail" : loc.seg, buf = Uint8Array.from(f[seg]), p = loc.seg === "E" ? ePos(f, loc.off) : loc.off;
      if (p >= 0 && p + b.length <= buf.length) { buf.set(b, p); f[seg] = buf; }
    });
  }
  if (stock.T5InfoCodes && ST.DIALOGS.T5InfoCodes) {
    const names = new Map((hs.info || []).map((r) => [r.idx, r.name])), num = (t) => (/^\d+$/.test(t.trim()) ? parseInt(t, 10) & 255 : 0);
    hs.info = stock.T5InfoCodes.filter((r) => r.length > 3 && /^\d+$/.test(r[0].trim()))           // the string after the ID is not decoded: kept
      .map((r) => ({ idx: num(r[0]), func: num(r[1]), resp: num(r[2]), id: r[3].slice(0, 16), name: names.get(num(r[0])) || "" }));
  }
  f.hs = hs;
  if (stock.EncryptionCodeRdt && ST.DIALOGS.EncryptionCodeRdt) {
    f.enc = stock.EncryptionCodeRdt.filter((r) => /^\d+$/.test((r[0] || "").trim()) && /^[0-9a-f]+$/i.test((r[1] || "").trim()))
      .map((r) => [parseInt(r[0], 10) - 1, [parseInt(r[1], 16) & 0xffff, (parseInt(r[2] || "65535", 10) || 65535) & 0xffff]])
      .sort((a, b) => a[0] - b[0] || a[1][0] - b[1][0]);
  }
}

const sortU = (a) => [...new Set(a)].sort((x, y) => x - y);
export function tablesFromFile(f) {
  const model = f.model || "D890UV";
  ST.use(model);
  const chb = CHBS[model] || {};
  const t = {}, slot2ch = new Map();
  const scanNames = f.scans.map((s) => s.name);
  const rows = f.channels.map((c) => {
    const x = c.fixed, slot = u16(x, 0), rx = u32(x, 2), sh = x[6], off = u32(x, 7);
    const tx = sh === 1 ? rx + off : sh === 2 ? rx - off : rx;
    const custom = u16(x, 26);
    const d = Object.assign({}, ST.CH_DEFAULT_D, { "No.": String(slot + 1), "Channel Name": c.name, "Receive Frequency": mhz10(rx), "Transmit Frequency": mhz10(tx),
      "Channel Type": TYPES[x[11] & 3], "Transmit Power": POWER[x[12] & 3], "Band Width": x[13] === 1 ? "25K" : "12.5K",
      "CTCSS/DCS Decode": toneText(x[18], x[19], u16(x, 20), custom), "CTCSS/DCS Encode": toneText(x[22], x[23], u16(x, 24), custom),
      "Custom CTCSS": (custom / 10).toFixed(1), "RX Color Code": String(x[40]), Slot: String((x[41] & 1) + 1),
      "Scan List": x[34] < scanNames.length ? scanNames[x[34]] : "None" });
    const dig = [1, 3].includes(x[11] & 3);
    d["Busy Lock/TX Permit"] = (model === "D168UV" ? BUSY_D168 : BUSY)[dig][x[32]] ?? d["Busy Lock/TX Permit"];
    for (const [col, [pos, vals]] of Object.entries(chb)) { const v = rb(c, pos); d[col] = vals ? (vals[v] ?? d[col]) : String(v); }
    if (model === "D168UV" && x[17] < 2) d[D168_B17[dig]] = ONOFF[x[17]];
    d["Radio ID"] = x[35] < f.ids.length ? f.ids[x[35]].name : "";
    const ci = u16(x, 28);
    if (ci < f.tgs.length) { const r = f.tgs[ci]; Object.assign(d, { "Contact/Talk Group": r.strs[0], "Contact/Talk Group Call Type": CALLTYPE[r.type & 0x30] || "Group Call", "Contact/Talk Group TG/DMR ID": String(r.id) }); }
    slot2ch.set(slot, [c.name, d["Receive Frequency"], d["Transmit Frequency"]]);
    return d;
  });
  t.Channel = rows.map((r) => ST.CH_COLS.map((k) => r[k] ?? ""));
  t.RadioIDList = f.ids.map((r, i) => [String(i + 1), String(r.id), r.name]);
  const names = (slots) => { const ch = slots.filter((s) => slot2ch.has(s)).map((s) => slot2ch.get(s)); return [0, 1, 2].map((k) => ch.map((c) => c[k]).join("|")); };
  const zc = ST.TABLES.DMRZone.columns;
  t.DMRZone = f.zones.map((z, i) => {
    const a = slot2ch.get(z.a) || ["", "", ""], b = slot2ch.get(z.b) || ["", "", ""], [nm, rx, tx] = names(z.slots);
    const row = Object.fromEntries(zc.map((c) => [c, ""]));
    Object.assign(row, { "No.": String(i + 1), "Zone Name": z.name, "Zone Channel Member": nm, "Zone Channel Member RX Frequency": rx, "Zone Channel Member TX Frequency": tx,
      "A Channel": a[0], "A Channel RX Frequency": a[1], "A Channel TX Frequency": a[2], "B Channel": b[0], "B Channel RX Frequency": b[1], "B Channel TX Frequency": b[2],
      "Zone Hide ": String(z.extra[0]) });
    return zc.map((c) => row[c]);
  });
  const sc = ST.TABLES.ScanList.columns;
  t.ScanList = f.scans.map((s, i) => {
    const [nm, rx, tx] = names(s.members.map((m) => m[1]));
    const row = Object.fromEntries(sc.map((c, k) => [c, (ST.TABLES.ScanList.defaults || [])[k] ?? ""]));
    Object.assign(row, { "No.": String(i + 1), "Scan List Name": s.name, "Scan Channel Member": nm, "Scan Channel Member RX Frequency": rx, "Scan Channel Member TX Frequency": tx });
    for (const [col, pos] of Object.entries(SCAN_TIMES)) row[col] = (s.hdr[pos] / 10).toFixed(1);
    if (!Array.from(s.hdr.slice(0, 7)).some((x) => x)) Object.assign(row, { "Scan Mode": "Off", "Priority Channel Select": "Off", "Priority Channel 1": "Off", "Priority Channel 2": "Off", "Revert Channel": "Selected" });
    return sc.map((c) => row[c] ?? "");
  });
  t.DMRTalkGroups = f.tgs.map((r, i) => [String(i + 1), String(r.id), r.strs[0], CALLTYPE[r.type & 0x30] || "Group Call", "None"]);
  t.DMRDigitalContactList = f.users.map((r, i) => [String(i + 1), String(r.id), r.strs[2], r.strs[0], r.strs[1], r.strs[3], r.strs[4], r.strs[5], CALLTYPE[r.type & 0x30] || "Private Call", "None"]);
  t.PrefabricatedSMS = f.sms.map((s, i) => [String(i + 1), s]);
  const nfm = ST.TABLES.FM.columns.length, nrg = ST.TABLES.DMRReceiveGroupCallList.columns.length;
  t.FM = f.fm.map((r) => [String(r.idx + 1), `${Math.floor(r.freq / 100)}.${String((r.freq % 100) * 10).padStart(3, "0")}`, r.flag ? "Add" : "Del", r.name].slice(0, nfm));
  const tgNames = f.tgs.map((r) => r.strs[0]);
  t.DMRReceiveGroupCallList = f.rxgroups.map((g, i) => [String(i + 1), g.name, g.members.filter((m) => m < tgNames.length).map((m) => tgNames[m]).join("|"),
    g.members.filter((m) => m < f.tgs.length).map((m) => String(f.tgs[m].id)).join("|")].slice(0, nrg));
  const opt = ST.defaultRows("OptionalSetting"), cols = ST.TABLES.OptionalSetting.columns;
  opt[0][cols.indexOf("Start_Char")] = f.line1; opt[0][cols.indexOf("Start_Char2")] = f.line2; opt[0][cols.indexOf("Password_Char")] = f.password;
  for (const [k, [seg, o]] of Object.entries(optFields(model))) {
    if (!cols.includes(k)) continue;
    if (seg === "E") { if (o <= f.tail.length) opt[0][cols.indexOf(k)] = String(f.tail[f.tail.length - o]); }
    else opt[0][cols.indexOf(k)] = String(f[seg][o]);
  }
  t.OptionalSetting = opt;
  for (const [name, rows] of Object.entries(dialogRows(f))) if (JSON.stringify(rows) !== JSON.stringify(ST.defaultRows(name))) t[name] = rows;   // dialogs at their defaults are not stored
  if (model === "D890UV") { const nx = nxRow(f.tail); if (nx) t.NXSetting = [nx]; }
  return t;
}

export const tailTables = () => ST.ORDER.filter((t) => !["Channel", "RadioIDList", "DMRZone", "ScanList", "DMRTalkGroups", "DMRDigitalContactList", "PrefabricatedSMS", "FM", "DMRReceiveGroupCallList", "OptionalSetting", "NXSetting"].includes(t));

export function load(bytes) {
  const f = parse(bytes);
  const cp = ST.fromStock(tablesFromFile(f), f.model);
  Object.defineProperty(cp, "_rdt", { value: f, enumerable: false, writable: true });
  cp.channels.forEach((c, i) => Object.defineProperty(c, "_rdt", { value: f.channels[i], enumerable: false, writable: true }));
  Object.defineProperty(cp, "_rdtStock", { value: JSON.parse(JSON.stringify(Object.fromEntries(tailTables().concat(f.model === "D890UV" ? ["NXSetting"] : []).map((t) => [t, (cp.stock || {})[t] ?? null])))), enumerable: false });
  Object.defineProperty(cp, "_rdtOpt", { value: ST.stockSettingsView(cp, "OptionalSetting"), enumerable: false });
  return cp;
}

function chRecord(row, tpl, tgIndex, scanIndex, chb = CH_BYTES) {
  const x = Uint8Array.from(tpl.fixed), dv = new DataView(x.buffer);
  const slot = parseInt(row["No."], 10) - 1, rx = Math.round(parseFloat(row["Receive Frequency"]) * 1e5), tx = Math.round(parseFloat(row["Transmit Frequency"]) * 1e5);
  const shOld = x[6], offOld = dv.getUint32(7, true);
  let sh, off;
  if (tx === rx && shOld === 0) [sh, off] = [0, offOld];
  else if (tx === rx) [sh, off] = [0, rx];
  else if (tx > rx) [sh, off] = [1, tx - rx];
  else [sh, off] = [2, rx - tx];
  dv.setUint16(0, slot, true); dv.setUint32(2, rx, true); x[6] = sh; dv.setUint32(7, off, true);
  if (TYPES.includes(row["Channel Type"])) x[11] = TYPES.indexOf(row["Channel Type"]);
  if (POWER.includes(row["Transmit Power"])) x[12] = POWER.indexOf(row["Transmit Power"]);
  x[13] = row["Band Width"] === "25K" ? 1 : 0;
  const custom = dv.getUint16(26, true);
  for (const [col, so] of [["CTCSS/DCS Decode", 18], ["CTCSS/DCS Encode", 22]]) {
    if (toneText(x[so], x[so + 1], dv.getUint16(so + 2, true), custom) === row[col]) continue;
    const tb = toneBytes(row[col]);
    if (!tb) continue;
    x[so] = tb[0]; if (tb[1] !== null) x[so + 1] = tb[1]; if (tb[2] !== null) dv.setUint16(so + 2, tb[2], true);
  }
  const cc = parseInt(row["RX Color Code"], 10);
  if (!Number.isNaN(cc)) { x[40] = cc & 15; x[41] = (x[41] & ~1) | (row.Slot === "2" ? 1 : 0); }
  const ci = tgIndex.get(`${row["Contact/Talk Group"]}\u0000${row["Contact/Talk Group TG/DMR ID"] ?? "\u0001"}`);
  if (ci !== undefined) dv.setUint16(28, ci, true);
  x[34] = scanIndex.has(row["Scan List"]) ? scanIndex.get(row["Scan List"]) : 0xff;
  const tail = Uint8Array.from(tpl.tail);
  const dig = [1, 3].includes(x[11] & 3);
  const inv = Object.fromEntries(Object.entries((tpl.tail.length === LAYOUT.D168UV.chanTail ? BUSY_D168 : BUSY)[dig]).map(([k, v]) => [v, Number(k)]));
  if (row["Busy Lock/TX Permit"] in inv) x[32] = inv[row["Busy Lock/TX Permit"]];
  if (tpl.tail.length === LAYOUT.D168UV.chanTail && ONOFF.includes(row[D168_B17[dig]] ?? "")) x[17] = ONOFF.indexOf(row[D168_B17[dig]]);
  for (const [col, [pos, vals]] of Object.entries(chb)) {
    let v = row[col] ?? "";
    if (vals) { if (!vals.includes(v)) continue; v = vals.indexOf(v); } else { v = parseInt(v, 10); if (Number.isNaN(v)) continue; }
    if (pos < 48) x[pos] = v & 0xff; else tail[pos - 48] = v & 0xff;
  }
  return { fixed: x, name: row["Channel Name"], tail };
}

export function buildFile(cp) {
  const model = C.modelOf(cp), L = LAYOUT[model];
  let base = cp._rdt;
  if (!base || (base.model || "D890UV") !== model) base = defaultFile(model);   // new / imported / converted: the template
  const f = Object.assign({}, base);
  const t = ST.toStock(cp);
  const opt = Object.fromEntries(ST.TABLES.OptionalSetting.columns.map((c, i) => [c, t.OptionalSetting[0][i]]));
  f.line1 = opt.Start_Char; f.line2 = opt.Start_Char2; f.password = opt.Password_Char;
  const segs = { A: Uint8Array.from(f.A), B: Uint8Array.from(f.B), C: Uint8Array.from(f.C) }, tail = Uint8Array.from(f.tail);
  // write only settings that differ from the template file's (as loaded, or the stock defaults): cps/rdt.py build_file
  const oc = ST.TABLES.OptionalSetting;
  const ref = (base === cp._rdt && cp._rdtOpt) || Object.fromEntries(oc.columns.map((c, i) => [c, oc.defaults[i]]));
  for (const [k, [seg, o]] of Object.entries(optFields(model))) {
    if (opt[k] === ref[k]) continue;
    const v = /^\d+$/.test(opt[k] ?? "") ? parseInt(opt[k], 10) : NaN;
    if (!(v >= 0 && v <= 255)) continue;
    if (seg === "E") { if (o <= tail.length) tail[tail.length - o] = v; } else segs[seg][o] = v;
  }
  Object.assign(f, segs); f.tail = tail;
  if (t.NXSetting && t.NXSetting.length) { const nt = nxPatch(f.tail, t.NXSetting[0]); if (nt) f.tail = nt; }
  const oldTg = new Map(base.tgs.map((r) => [`${r.strs[0]}\u0000${r.id}`, r]));
  f.tgs = t.DMRTalkGroups.map((row, i) => {
    const id = parseInt(row[1] || "0", 10), name = row[2];
    const o = oldTg.get(`${name}\u0000${id}`) || { strs: [name, "", "", "", "", ""], raw: new Uint8Array(0), type: 0 };
    return { id, idx: i + 1, type: (o.type & ~0x30) | (CALLTYPE_R[row[3]] ?? 0x10), strs: [name, ...o.strs.slice(1)], raw: o.raw };
  });
  if (!f.tgs.length) f.tgs = [defaultContact()];                    // the stock CPS refuses a file with no contact
  const tgIndex = new Map(f.tgs.map((r, i) => [`${r.strs[0]}\u0000${r.id}`, i]));
  if (!ST.hasCol("Channel", "Contact/Talk Group TG/DMR ID")) f.tgs.forEach((r, i) => { const k = `${r.strs[0]}\u0000\u0001`; if (!tgIndex.has(k)) tgIndex.set(k, i); });
  const scanIndex = new Map(t.ScanList.map((row, i) => [row[1], i]));
  // record for channels that never were in an .rdt: the template's channel 1, else the built-in blank record (cps/rdt.py)
  let dflt = base.channels.length ? base.channels[0] : null;
  if (cp.channels.some((c) => !c._rdt)) {
    const tf = DEFAULTS[model] ? parse(DEFAULTS[model]) : null;
    dflt = tf && tf.channels.length ? tf.channels[0] : blankChannel(model);
  }
  const chb = CHBS[model] || {};
  f.channels = cp.channels.map((c, i) => chRecord(Object.fromEntries(ST.CH_COLS.map((k, j) => [k, t.Channel[i][j]])),
    c._rdt && (!dflt || c._rdt.tail.length === dflt.tail.length) ? c._rdt : dflt, tgIndex, scanIndex, chb));
  f.channels.sort((p, q) => u16(p.fixed, 0) - u16(q.fixed, 0));       // the stock CPS keeps records in number order
  const key2slot = new Map();
  for (const rc of f.channels) {
    const x = rc.fixed, slot = u16(x, 0), rx = u32(x, 2), sh = x[6], off = u32(x, 7), tx = sh === 1 ? rx + off : sh === 2 ? rx - off : rx;
    const k = `${rc.name}\u0000${mhz10(rx)}\u0000${mhz10(tx)}`; if (!key2slot.has(k)) key2slot.set(k, slot);
  }
  const sp = (s) => (s ? s.split("|") : []);
  const name2slot = new Map();
  for (const [k, v] of key2slot) { const n = k.split("\u0000")[0]; if (!name2slot.has(n)) name2slot.set(n, v); }
  const slots = (n, r, x) => {
    if (r === undefined) return sp(n).filter((k) => name2slot.has(k)).map((k) => name2slot.get(k));       // D168: by name
    const a = sp(n), b = sp(r), c = sp(x), o = []; for (let i = 0; i < Math.min(a.length, b.length, c.length); i++) { const k = `${a[i]}\u0000${b[i]}\u0000${c[i]}`; if (key2slot.has(k)) o.push(key2slot.get(k)); } return o; };
  const zc = ST.TABLES.DMRZone.columns;
  f.zones = t.DMRZone.map((row, i) => {
    const r = Object.fromEntries(zc.map((c, j) => [c, row[j]]));
    const old = base.zones[i] || { extra: new Uint8Array(L.zoneExtra[1]), a: 0, b: 0 };
    const a = slots(r["A Channel"], r["A Channel RX Frequency"], r["A Channel TX Frequency"]), b = slots(r["B Channel"], r["B Channel RX Frequency"], r["B Channel TX Frequency"]);
    const extra = Uint8Array.from(old.extra); if ("Zone Hide " in r) { const zh = parseInt(r["Zone Hide "] || "0", 10); if (!Number.isNaN(zh)) extra[0] = zh & 0xff; }
    return { slots: slots(r["Zone Channel Member"], r["Zone Channel Member RX Frequency"], r["Zone Channel Member TX Frequency"]), a: a.length ? a[0] : old.a, b: b.length ? b[0] : old.b, name: r["Zone Name"], extra };
  });
  const sc = ST.TABLES.ScanList.columns;
  f.scans = t.ScanList.map((row, i) => {
    const r = Object.fromEntries(sc.map((c, j) => [c, row[j]]));
    const old = base.scans[i] || { hdr: Uint8Array.from([0, 0, 0, 0, 0, 0, 0, 5, 5, 1, 1, 0, 0, 0].slice(0, L.scanHdr)), members: [] };
    const xs = new Map(old.members.map(([x, s]) => [s, x]));
    const hdr = Uint8Array.from(old.hdr);
    for (const [col, pos] of Object.entries(SCAN_TIMES)) { const v = Math.round(parseFloat(r[col]) * 10); if (!Number.isNaN(v)) hdr[pos] = v & 0xff; }
    return { name: r["Scan List Name"], hdr, members: slots(r["Scan Channel Member"], r["Scan Channel Member RX Frequency"], r["Scan Channel Member TX Frequency"]).map((s) => [xs.get(s) ?? 0, s]) };
  });
  f.ids = t.RadioIDList.map((row, i) => ({ idx: i, id: parseInt(row[1] || "0", 10), name: row[2] }));
  f.sms = t.PrefabricatedSMS.map((row) => row[1]);
  f.fm = t.FM.map((row) => ({ idx: parseInt(row[0], 10) - 1, flag: row[2] === "Add" ? 1 : 0, freq: Math.round(parseFloat(row[1]) * 100), name: row[3] ?? "" }));
  const firstTg = new Map(); f.tgs.forEach((r, i) => { if (!firstTg.has(r.strs[0])) firstTg.set(r.strs[0], i); });
  f.rxgroups = t.DMRReceiveGroupCallList.map((row) => {
    const nm = sp(row[2]), m = [];
    if (row.length > 3) {
      const ids = sp(row[3]);
      for (let i = 0; i < Math.min(nm.length, ids.length); i++) { const k = `${nm[i]}\u0000${ids[i]}`; if (tgIndex.has(k)) m.push(tgIndex.get(k)); }
    } else for (const n of nm) if (firstTg.has(n)) m.push(firstTg.get(n));      // D168: by name
    return { name: row[1], members: m };
  });
  const oldU = new Map(base.users.map((r) => [`${r.id}\u0000${r.strs[0]}`, r]));
  f.users = t.DMRDigitalContactList.map((row, i) => {
    const id = parseInt(row[1] || "0", 10), o = oldU.get(`${id}\u0000${row[3]}`) || { raw: new Uint8Array(0), type: 0 };
    return { id, idx: (i + 1) & 0xffff, strs: [row[3], row[4], row[2], row[5], row[6], row[7]], type: (o.type & ~0x30) | (CALLTYPE_R[row[8]] ?? 0), raw: o.raw };
  });
  dialogWrite(f, base, cp);
  const idx = new Map(); f.users.forEach((r, i) => { if (!idx.has(r.id)) idx.set(r.id, i); });
  const fr = (cp.stock || {}).FriendsList;
  if (!fr) f.friends = sortU((base.friends || []).filter((k) => k < base.users.length && idx.has(base.users[k].id)).map((k) => idx.get(base.users[k].id)));
  else if (ST.DIALOGS.FriendsList) {
    const want = fr.filter((r) => /^\d+$/.test((r[1] || "").trim())).map((r) => parseInt(r[1], 10));
    f.friends = sortU(want.filter((x) => idx.has(x)).map((x) => idx.get(x)));        // the stock CPS keeps them in list order
    f.lostFriends = want.filter((x) => !idx.has(x));
  }
  return f;
}

export function unsavedTailEdits(cp) {
  const model = C.modelOf(cp);
  ST.use(model);
  const out = [], snap = cp._rdtStock;
  const opt = ST.stockSettingsView(cp, "OptionalSetting");
  const ref = cp._rdtOpt || Object.fromEntries(ST.TABLES.OptionalSetting.columns.map((c, i) => [c, ST.TABLES.OptionalSetting.defaults[i]]));
  const lost = Object.keys(opt).filter((k) => opt[k] !== ref[k] && !(k in optFields(model)) && !["Start_Char", "Start_Char2", "Password_Char"].includes(k));
  if (lost.length) out.push(`OptionalSetting (${lost.slice(0, 8).join(", ")}${lost.length > 8 ? " ..." : ""})`);
  const tabs = tailTables();
  if (model === "D890UV" && !nxFind((cp._rdt || defaultFile("D890UV")).tail)) tabs.push("NXSetting");   // NX block not found: its edits cannot be written
  for (const t of tabs) {
    const cur = (cp.stock || {})[t] ?? null;
    if (snap) { if (JSON.stringify(cur) !== JSON.stringify(snap[t] ?? null)) out.push(t); }
    else if (cur !== null && JSON.stringify(cur) !== JSON.stringify(ST.defaultRows(t))) out.push(t);
  }
  return out;
}

export function save(cp) {
  const f = buildFile(cp), bytes = serialise(f), lost = unsavedTailEdits(cp);
  if (f.lostFriends && f.lostFriends.length) lost.push(`FriendsList (not in the digital contact list: ${f.lostFriends.slice(0, 8).join(", ")})`);
  return { bytes, lost };
}
