// Stock D890UV CPS (V1.05) / D168UV CPS (V1.07) data for the web CPS: port of cps/stock.py (same schema files, same bytes).
// setSchema(json) for each model first (schema/stock_d890uv.json, stock_d168uv.json; the last one set is selected);
// use(model) selects one. Tables / columns carry the D890UV names for both models (csv_name / csv_columns: D168 names).
import * as C from "./codeplug.js";

export let SCHEMA = null, TABLES = null, ORDER = null, LABELS = null, CH_COLS = null, CH_DEFAULT_D = null, CH_DEFAULT_A = null;
export let RECORD = [], FILE_ONLY = [], CHOICES = {}, PAGES = {};
export const MAPPED = ["Channel", "DMRZone", "ScanList", "DMRTalkGroups", "DMRReceiveGroupCallList"];
const OBJ_ID = { Channel: 0xf0, DMRZone: 0xf1, ScanList: 0xf2, DMRTalkGroups: 0xf3, DMRReceiveGroupCallList: 0xf4 };
export const OBJ_ATTR = { Channel: "channels", DMRZone: "zones", ScanList: "scanlists", DMRTalkGroups: "contacts", DMRReceiveGroupCallList: "tglists" };
const ROWS = 0xff;

export let MODEL = "D890UV";
export const MODELS = ["D890UV", "D168UV"];
const SCHEMAS = {};
export const schemaOf = (m) => SCHEMAS[m];

export function setSchema(s) {
  SCHEMAS[s.model || "D890UV"] = s;
  return use(s.model || "D890UV");
}

/** select the radio model whose schema the exported names describe (cps/stock.py use) */
export function use(model = "D890UV") {
  const s = SCHEMAS[model];
  if (!s) throw new Error(`no stock schema loaded for ${model}`);
  if (s === SCHEMA) return s;
  MODEL = model;
  SCHEMA = s; TABLES = s.tables; ORDER = s.lst_order; LABELS = s.labels;
  CHOICES = s.choices || {}; PAGES = s.pages || {};
  RECORD = Object.keys(TABLES).filter((t) => TABLES[t].kind === "record");
  FILE_ONLY = Object.keys(TABLES).filter((t) => TABLES[t].file_only);
  CH_COLS = TABLES.Channel.columns;
  CH_DEFAULT_D = Object.fromEntries(CH_COLS.map((c, i) => [c, TABLES.Channel.defaults[i]]));
  CH_DEFAULT_A = Object.assign({}, CH_DEFAULT_D, { "Busy Lock/TX Permit": "Off", "Squelch Mode": "CTCSS/DCS", "Custom CTCSS": "0.0",
    "2TONE Decode": "1", txcc: "1", "Contact/Talk Group Call Type": "Private Call" });
  C.registerStock({ encodeStock, decodeStock, use }, s);
  return s;
}
export const csvName = (t) => TABLES[t].csv_name || t;
/** stock CSV value -> label in the radio's value list (raw value when there is no list or it is out of range) */
export function choiceText(key, value) {
  const c = CHOICES[key], v = String(value ?? "").trim();
  return c && /^\d+$/.test(v) && Number(v) < c.length ? c[Number(v)] : v;
}
/** label (or raw value) -> stock CSV value */
export function choiceValue(key, text) {
  const c = CHOICES[key], t = String(text ?? "").trim();
  return c && c.includes(t) ? String(c.indexOf(t)) : t;
}
export const hasCol = (t, c) => TABLES[t].columns.includes(c);

/** stock CSV base names of an "Export All" set -> model (D890UV unless a name only another model has) */
export function detectModel(names) {
  const own = (m) => new Set(Object.entries(SCHEMAS[m].tables).map(([t, v]) => v.csv_name || t));
  const base = SCHEMAS.D890UV ? own("D890UV") : new Set();
  for (const m of MODELS) {
    if (m === "D890UV" || !SCHEMAS[m]) continue;
    const o = own(m);
    if (names.some((n) => o.has(n) && !base.has(n))) return m;
  }
  return "D890UV";
}

export class StockError extends Error {}

// ------------------------------------------------------------------ CSV (stock dialect)
export function parseCsv(text) {
  const rows = [], trails = [];
  for (const line of text.split("\r\n")) {
    if (line === "") continue;
    const f = []; let i = 0, trail = false;
    for (;;) {
      if (i < line.length && line[i] === '"' && rows.length) {
        // data row: a field ends at '",' or at the line's closing quote (quotes inside values are not escaped by the stock CPS)
        let k = line.indexOf('",', i + 1);
        if (k < 0) k = line.endsWith('"') && line.length - 1 > i ? line.length - 1 : line.length;
        f.push(line.slice(i + 1, k)); i = k + 1;
      } else if (i < line.length && line[i] === '"') {
        const j = line.indexOf('"', i + 1); let k = line.indexOf(",", j); if (k < 0) k = line.length;
        f.push(line.slice(i + 1, j) + line.slice(j + 1, k)); i = k;      // header: text after a closing quote is appended (APRS)
      }
      else { let j = line.indexOf(",", i); if (j < 0) j = line.length; f.push(line.slice(i, j)); i = j; }
      if (i < line.length && line[i] === ",") { i++; if (i === line.length) { trail = true; break; } } else break;
    }
    rows.push(f); trails.push(trail);
  }
  return [rows, trails];
}

export function formatCsv(table, rows) {
  const t = TABLES[table];
  const out = [t.header_raw];
  for (const r of rows) out.push('"' + r.join('","') + '"' + (t.row_trail ? "," : ""));
  return out.join("\r\n") + "\r\n";
}

export const latin1 = (bytes) => { let s = ""; for (const b of bytes) s += String.fromCharCode(b); return s; };
export const toLatin1 = (s) => Uint8Array.from([...s].map((c) => (c.charCodeAt(0) < 256 ? c.charCodeAt(0) : 0x3f)));

/** files: {"Channel.CSV": text|bytes, ..., "x.LST": text} -> {table: rows}; selects the detected (or given) model */
export function readCsvSet(files, model = null) {
  const lstName = Object.keys(files).find((n) => n.toLowerCase().endsWith(".lst"));
  const asText = (v) => (typeof v === "string" ? v : latin1(v));
  const names = lstName ? asText(files[lstName]).split(/\r?\n/).filter((l) => l.includes(",")).map((l) => l.split(",")[1].trim().replace(/"/g, ""))
    : Object.keys(files).filter((n) => n.toUpperCase().endsWith(".CSV"));
  const byLower = Object.fromEntries(Object.keys(files).map((n) => [n.toLowerCase(), n]));
  use(model || detectModel(names.map((n) => n.slice(0, -4))));
  const byCsv = Object.fromEntries(Object.keys(TABLES).map((t) => [csvName(t), t]));
  const res = {};
  for (const name of names) {
    const table = byCsv[name.slice(0, -4)];
    const real = byLower[name.toLowerCase()];
    if (!table || !real) continue;
    const [rows] = parseCsv(asText(files[real]));
    if (rows.length && JSON.stringify(rows[0]) !== JSON.stringify(TABLES[table].csv_columns || TABLES[table].columns))
      throw new StockError(`${name}: columns differ from the stock ${SCHEMA.stock_cps} export (other CPS version?)`);
    res[table] = rows.slice(1);
  }
  return res;
}

/** -> {filename: text}: the stock "Export All" set (name.LST + one CSV per table) */
export function writeCsvSet(tables, lstName = "codeplug.LST") {
  const out = {}, lines = [String(ORDER.length)];
  for (const t of ORDER) {
    lines.push(`${TABLES[t].lst_index},"${csvName(t)}.CSV"`);
    out[csvName(t) + ".CSV"] = formatCsv(t, tables[t] || defaultRows(t));
  }
  out[lstName] = lines.join("\r\n") + "\r\n";
  return out;
}

export function defaultRows(table) {
  const t = TABLES[table];
  return t.kind === "record" ? [t.defaults.slice()] : t.default_rows.map((r) => r.slice());
}

// ------------------------------------------------------------------ conversions
const POWER = { Low: "low", Middle: "mid", High: "high", Turbo: "turbo" };
const POWER_R = Object.fromEntries(Object.entries(POWER).map(([k, v]) => [v, k]));
const CALLTYPE = { "Group Call": "group", "Private Call": "private", "All Call": "all" };
const CALLTYPE_R = Object.fromEntries(Object.entries(CALLTYPE).map(([k, v]) => [v, k]));
const mhzToHz = (s) => (s.trim() ? Math.round(parseFloat(s) * 1e6) : 0);
export const hzToMhz = (hz) => (hz / 1e6).toFixed(5);
const toneFrom = (s) => { s = s.trim(); if (s === "Off" || s === "") return null; return "Dd".includes(s[0]) ? s.toUpperCase() : s; };
const toneTo = (t) => (t ? t : "Off");
const split = (s) => (s !== "" ? s.split("|") : []);
const int = (s) => parseInt(s || "0", 10) || 0;

export function fromStock(tables, model = null) {
  if (model) use(model);
  const cp = C.newCodeplug(MODEL);
  cp.channels = []; cp.created = 0;
  const raw = new Map();
  const tgCols = TABLES.DMRTalkGroups.columns;
  for (const r of tables.DMRTalkGroups || defaultRows("DMRTalkGroups")) {
    const d = Object.fromEntries(tgCols.map((c, i) => [c, r[i]]));
    const c = { name: d.Name.slice(0, 16), id: int(d["Radio ID"]), kind: CALLTYPE[d["Call Type"]] || "group", mode: "DMR" };
    raw.set(c, d); cp.contacts.push(c);
  }
  const contactBy = new Map(cp.contacts.map((c, i) => [`${c.name}\u0000${c.id}`, i]));
  const contactName = new Map();
  cp.contacts.forEach((c, i) => { if (!contactName.has(c.name)) contactName.set(c.name, i); });
  const rgCols = TABLES.DMRReceiveGroupCallList.columns;
  for (const r of tables.DMRReceiveGroupCallList || []) {
    const d = Object.fromEntries(rgCols.map((c, i) => [c, r[i]]));
    const names = split(d.Contact), mem = [];
    if ("Contact TG/DMR ID" in d) {
      const ids = split(d["Contact TG/DMR ID"]);
      names.forEach((n, i) => { if (i < ids.length) { const k = `${n}\u0000${int(ids[i])}`; if (contactBy.has(k)) mem.push(contactBy.get(k)); } });
    } else for (const n of names) if (contactName.has(n)) mem.push(contactName.get(n));       // D168: by name
    const t = { name: d["Group Name"].slice(0, 16), contacts: mem };
    raw.set(t, d); cp.tglists.push(t);
  }
  const tglBy = new Map(cp.tglists.map((t, i) => [t.name, i]));
  const slCols = TABLES.ScanList.columns;
  const slNames = (tables.ScanList || []).map((r) => Object.fromEntries(slCols.map((c, i) => [c, r[i]]))["Scan List Name"]);
  for (const r of tables.Channel || defaultRows("Channel")) {
    const d = Object.fromEntries(CH_COLS.map((c, i) => [c, r[i]]));
    const mode = d["Channel Type"].startsWith("A") ? "FM" : "DMR";
    const c = { name: d["Channel Name"].slice(0, 16), rx_hz: mhzToHz(d["Receive Frequency"]), tx_hz: mhzToHz(d["Transmit Frequency"]),
      mode, power: POWER[d["Transmit Power"]] || "high" };
    if (mode === "FM") {
      c.wide = d["Band Width"] === "25K"; c.rx_tone = toneFrom(d["CTCSS/DCS Decode"]); c.tx_tone = toneFrom(d["CTCSS/DCS Encode"]);
    } else {
      c.cc = int(d["RX Color Code"]); c.slot = d.Slot === "2" ? 2 : 1;
      if ("Contact/Talk Group TG/DMR ID" in d) {
        c.tg = int(d["Contact/Talk Group TG/DMR ID"]);
        const k = `${d["Contact/Talk Group"]}\u0000${c.tg}`; c.contact = contactBy.has(k) ? contactBy.get(k) : null;
      } else {                                              // D168: the contact by name gives the TG
        c.contact = contactName.has(d["Contact/Talk Group"]) ? contactName.get(d["Contact/Talk Group"]) : null;
        c.tg = c.contact !== null ? cp.contacts[c.contact].id : 0;
      }
      c.tglist = tglBy.has(d["Receive Group List"]) ? tglBy.get(d["Receive Group List"]) : null;
    }
    c.scanlist = slNames.includes(d["Scan List"]) ? slNames.indexOf(d["Scan List"]) : null;
    c.talkaround = d["Talk Around(Simplex)"] === "On";
    const nc = C.normalizeChannel(c);
    raw.set(nc, d); cp.channels.push(nc);
  }
  const byKey = new Map(), byName = new Map();
  cp.channels.forEach((c, i) => { const k = `${c.name}\u0000${hzToMhz(c.rx_hz)}\u0000${hzToMhz(c.tx_hz)}`; if (!byKey.has(k)) byKey.set(k, i);
    if (!byName.has(c.name)) byName.set(c.name, i); });
  for (const [table, attr, nameCol, pre] of [["DMRZone", "zones", "Zone Name", "Zone Channel Member"], ["ScanList", "scanlists", "Scan List Name", "Scan Channel Member"]]) {
    const cols = TABLES[table].columns;
    for (const r of tables[table] || []) {
      const d = Object.fromEntries(cols.map((c, i) => [c, r[i]]));
      const names = split(d[pre]), mem = [];
      if ((pre + " RX Frequency") in d) {
        const rxs = split(d[pre + " RX Frequency"]), txs = split(d[pre + " TX Frequency"]);
        for (let i = 0; i < Math.min(names.length, rxs.length, txs.length); i++) {
          const k = `${names[i]}\u0000${rxs[i]}\u0000${txs[i]}`;
          if (byKey.has(k)) mem.push(byKey.get(k));
        }
      } else for (const n of names) if (byName.has(n)) mem.push(byName.get(n));           // D168: by name
      const z = table === "DMRZone" ? { name: d[nameCol].slice(0, 16), channels: mem }
        : { name: d[nameCol].slice(0, 16), channels: mem, prio1: null, prio2: null, dwell_100ms: 20, flags: 0 };
      raw.set(z, d); cp[attr].push(z);
    }
  }
  const rid = tables.RadioIDList || [];
  if (rid.length) cp.settings.dmr_id = int(Object.fromEntries(TABLES.RadioIDList.columns.map((c, i) => [c, rid[0][i]]))["Radio ID"]);
  cp.stock = {};
  for (const [t, rows] of Object.entries(tables)) if (!MAPPED.includes(t)) cp.stock[t] = rows.map((x) => x.slice());
  for (const t of MAPPED) {
    cp[OBJ_ATTR[t]].forEach((o, i) => {
      const ex = extras(t, raw.get(o), o, cp, i);
      if (Object.keys(ex).length) o.stock = ex; else delete o.stock;
    });
  }
  if (!Object.keys(cp.stock).length) delete cp.stock;
  return cp;
}

function extras(table, d, o, cp, index) {
  const gen = row(table, o, cp);
  gen["No."] = String(index + 1);
  const ex = {};
  for (const [k, v] of Object.entries(d)) if (gen[k] !== v) ex[k] = v;
  return ex;
}

export function row(table, o, cp) {
  if (table === "Channel") {
    const base = Object.assign({}, o.mode === "FM" ? CH_DEFAULT_A : CH_DEFAULT_D);
    Object.assign(base, { "Channel Name": o.name, "Receive Frequency": hzToMhz(o.rx_hz), "Transmit Frequency": hzToMhz(o.tx_hz),
      "Channel Type": o.mode === "FM" ? "A-Analog" : "D-Digital", "Transmit Power": POWER_R[o.power] || "High",
      "Talk Around(Simplex)": o.talkaround ? "On" : "Off",
      "Scan List": o.scanlist !== null && o.scanlist !== undefined && o.scanlist < cp.scanlists.length ? cp.scanlists[o.scanlist].name : "None" });
    if (o.mode === "FM") {
      Object.assign(base, { "Band Width": o.wide ? "25K" : "12.5K", "CTCSS/DCS Decode": toneTo(o.rx_tone), "CTCSS/DCS Encode": toneTo(o.tx_tone) });
    } else {
      // modes other than DMR have no cc (Python keeps 0 there); P25 / NXDN / D-STAR / YSF are D-Digital rows
      Object.assign(base, { "Band Width": "12.5K", "RX Color Code": String(o.cc ?? 0), Slot: String(o.slot || 1), "Contact/Talk Group TG/DMR ID": String(o.tg ?? 0) });
      if (o.contact !== null && o.contact !== undefined && o.contact < cp.contacts.length) {
        const ct = cp.contacts[o.contact];
        Object.assign(base, { "Contact/Talk Group": ct.name, "Contact/Talk Group Call Type": CALLTYPE_R[ct.kind] || "Group Call" });
      }
      if (o.tglist !== null && o.tglist !== undefined && o.tglist < cp.tglists.length) base["Receive Group List"] = cp.tglists[o.tglist].name;
    }
    return base;
  }
  if (table === "DMRZone" || table === "ScanList") {
    const pre = table === "DMRZone" ? "Zone Channel Member" : "Scan Channel Member";
    const chans = o.channels.filter((i) => i < cp.channels.length).map((i) => cp.channels[i]);
    const cols = TABLES[table].columns;
    const base = Object.fromEntries(cols.map((c, i) => [c, TABLES[table].defaults[i]]));
    Object.assign(base, { [cols[1]]: o.name, [pre]: chans.map((c) => c.name).join("|"),
      [pre + " RX Frequency"]: chans.map((c) => hzToMhz(c.rx_hz)).join("|"), [pre + " TX Frequency"]: chans.map((c) => hzToMhz(c.tx_hz)).join("|") });
    return base;
  }
  if (table === "DMRTalkGroups") return { "Radio ID": String(o.id), Name: o.name, "Call Type": CALLTYPE_R[o.kind] || "Group Call", "Call Alert": "None" };
  if (table === "DMRReceiveGroupCallList") {
    const m = o.contacts.filter((i) => i < cp.contacts.length);
    return { "Group Name": o.name, Contact: m.map((i) => cp.contacts[i].name).join("|"), "Contact TG/DMR ID": m.map((i) => String(cp.contacts[i].id)).join("|") };
  }
  throw new Error(table);
}

export function toStock(cp) {
  use(C.modelOf(cp));
  const out = {};
  for (const t of ORDER) if (!MAPPED.includes(t)) out[t] = ((cp.stock || {})[t] || defaultRows(t)).map((r) => r.slice());
  for (const t of MAPPED) {
    const cols = TABLES[t].columns;
    // channel numbers (= .rdt slots) must be unique: kept stock numbers can have gaps (cps/stock.py to_stock)
    const objs = cp[OBJ_ATTR[t]];
    const kept = new Set(t === "Channel" ? objs.map((o) => (o.stock || {})["No."]).filter((x) => x !== undefined) : []);
    const taken = new Set([...kept, ...objs.map((o, i) => (!("No." in (o.stock || {})) ? String(i + 1) : null)).filter((x) => x !== null)]);
    // next number after the highest one below the VFO numbers (4001/4002), so an added channel stays last
    let free = Math.max(0, ...[...taken].filter((x) => /^\d+$/.test(x) && Number(x) <= 4000).map(Number)) + 1;
    out[t] = objs.map((o, i) => {
      const d = row(t, o, cp);
      d["No."] = String(i + 1);
      if (t === "Channel" && kept.has(d["No."]) && !("No." in (o.stock || {}))) {
        while (taken.has(String(free))) free = free < 4000 ? free + 1 : 1;
        taken.add(String(free)); d["No."] = String(free);
      }
      Object.assign(d, o.stock || {});
      return cols.map((c) => (c in d ? d[c] : ""));
    });
  }
  const rid = out.RadioIDList;
  if (rid && rid.length && cp.settings.dmr_id) rid[0][TABLES.RadioIDList.columns.indexOf("Radio ID")] = String(cp.settings.dmr_id);
  return out;
}

const CH_DIGITAL_ONLY = ["Contact/Talk Group", "Contact/Talk Group Call Type", "Contact/Talk Group TG/DMR ID", "RX Color Code", "Slot", "Receive Group List"];
const CH_FM_ONLY = ["CTCSS/DCS Decode", "CTCSS/DCS Encode"];
export function clearMappedOverrides(o, table) {
  if (!o.stock) return;
  const skip = table === "Channel" ? (o.mode === "FM" ? CH_DIGITAL_ONLY : CH_FM_ONLY) : [];
  for (const k of TABLES[table].cfw_mapped) if (!skip.includes(k)) delete o.stock[k];
  if (!Object.keys(o.stock).length) delete o.stock;
}

export const channelKey = (c) => [c.name, hzToMhz(c.rx_hz), hzToMhz(c.tx_hz)];
export function renameChannelRefs(cp, old, neu) {
  for (const [table, attr, cols] of [["DMRZone", "zones", ["A Channel", "B Channel"]], ["ScanList", "scanlists", ["Priority Channel 1", "Priority Channel 2"]]])
    for (const o of cp[attr] || []) {
      const st = o.stock; if (!st) continue;
      for (const c of cols) {
        if (!hasCol(table, c + " RX Frequency")) { if (c in st && st[c] === old[0]) st[c] = neu[0]; }        // D168: by name
        else if (st[c] === old[0] && st[c + " RX Frequency"] === old[1] && st[c + " TX Frequency"] === old[2])
          [st[c], st[c + " RX Frequency"], st[c + " TX Frequency"]] = neu;
      }
    }
}

export function stockSettingsView(cp, table) {
  use(C.modelOf(cp));
  const r = ((cp.stock || {})[table] || defaultRows(table))[0];
  return Object.fromEntries(TABLES[table].columns.map((c, i) => [c, r[i] ?? ""]));
}

export function setStockValue(cp, table, column, value, rowi = 0) {
  use(C.modelOf(cp));
  cp.stock = cp.stock || {};
  const rows = cp.stock[table] || (cp.stock[table] = defaultRows(table));
  while (rows.length <= rowi) rows.push(TABLES[table].defaults.slice());
  put(rows[rowi], TABLES[table].columns.indexOf(column), String(value));
}

function put(r, col, v) { while (r.length <= col) r.push(""); r[col] = v; }

// ------------------------------------------------------------------ binary (codeplug section 10)
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function encodeStock(cp, forRadio = false) {
  use(C.modelOf(cp));
  const b = [];
  const putE = (tid, col, rowi, s) => {
    const d = toLatin1(s);
    b.push(tid, col, rowi & 0xff, rowi >> 8, d.length & 0xff, d.length >> 8, ...d);
  };
  const st = cp.stock || {};
  ORDER.forEach((t, tid) => {
    if (MAPPED.includes(t) || !(t in st) || (forRadio && FILE_ONLY.includes(t))) return;
    const tab = TABLES[t], rows = st[t];
    if (tab.kind === "record") {
      const n = Math.min(rows[0].length, tab.defaults.length);
      for (let ci = 0; ci < n; ci++) if (rows[0][ci] !== tab.defaults[ci]) putE(tid, ci, 0, rows[0][ci]);
    } else {
      if (same(rows, defaultRows(t))) return;
      putE(tid, ROWS, 0, String(rows.length));
      rows.forEach((r, ri) => r.forEach((v, ci) => { if (v !== "") putE(tid, ci, ri, v); }));
    }
  });
  for (const [t, tid] of Object.entries(OBJ_ID)) {
    const cols = TABLES[t].columns;
    (cp[OBJ_ATTR[t]] || []).forEach((o, ri) => {
      const ent = Object.entries(o.stock || {}).filter(([k]) => cols.includes(k)).sort((a, b2) => cols.indexOf(a[0]) - cols.indexOf(b2[0]));
      for (const [k, v] of ent) putE(tid, cols.indexOf(k), ri, v);
    });
  }
  while (b.length % 4) b.push(0);
  if (forRadio) for (let i = 0; i < STOCK_SPARE; i++) b.push(0);   // radio edits journal room (cps/stock.py)
  return Uint8Array.from(b);
}

// radio edits journal (cps/stock.py): 0xE0 settings keys, 0xE2 channel power, 0xEE marker, 0xEF CRC fix
export const STOCK_SPARE = 1024;
function journalEdit(cp, tid, col, rowi, v) {
  if (!/^\d+$/.test(v)) return;
  const n = parseInt(v, 10);
  if (tid === 0xe0 && col === 6) {          // cfw: encryption (privacy keys) on / off
    cp.settings.encryption = n === 1;
  } else if (tid === 0xe0 && col === 7) {   // cfw: SMS format (1 = M-SMS)
    cp.settings.sms_msms = n === 1;
  } else if (tid === 0xe0 && col < 6 && n < C.KEY_FUNCS.length) {
    const keys = [...(cp.settings.keys || []), ...Array(6).fill("none")].slice(0, 6);
    keys[col] = C.KEY_FUNCS[n];
    cp.settings.keys = keys;
  } else if (tid === 0xe2 && col === 0 && rowi < cp.channels.length && n < C.POWERS.length) {
    cp.channels[rowi].power = C.POWERS[n];
  }
}

export function decodeStock(data, cp) {
  use(C.modelOf(cp));
  let p = 0;
  const lists = {};
  cp.stock = cp.stock || {};
  while (p + 6 <= data.length) {
    const al = (p + 3) & ~3;
    if (p % 4 && al < data.length && data[al] >= 0xe0 && data[al] < 0xf0 && data.subarray(p, al).every((x) => x === 0)) { p = al; continue; }   // journal: 4-aligned (cps/stock.py)
    const tid = data[p], col = data[p + 1], rowi = data[p + 2] | (data[p + 3] << 8), ln = data[p + 4] | (data[p + 5] << 8);
    if (tid === 0 && col === 0 && rowi === 0 && ln === 0 && data.subarray(p).every((x) => x === 0)) break;
    const v = latin1(data.subarray(p + 6, p + 6 + ln));
    p += 6 + ln;
    if (tid >= 0xe0 && tid < 0xf0) { journalEdit(cp, tid, col, rowi, v); continue; }
    if (tid >= 0xf0) {
      const t = Object.keys(OBJ_ID).find((k) => OBJ_ID[k] === tid);
      const objs = cp[OBJ_ATTR[t]];
      if (rowi < objs.length) { objs[rowi].stock = objs[rowi].stock || {}; objs[rowi].stock[TABLES[t].columns[col]] = v; }
      continue;
    }
    const t = ORDER[tid], tab = TABLES[t];
    if (tab.kind === "record") { const rows = cp.stock[t] || (cp.stock[t] = defaultRows(t)); put(rows[0], col, v); }
    else if (col === ROWS) { lists[t] = Array.from({ length: parseInt(v, 10) }, () => Array(tab.columns.length).fill("")); cp.stock[t] = lists[t]; }
    else put(lists[t][rowi], col, v);
  }
  if (!Object.keys(cp.stock).length) delete cp.stock;
  return cp;
}

// ------------------------------------------------------------------ radio model conversion (cps/stock.py convert_model)
export function convertModel(cp, model) {
  if (!C.MODELS[model]) throw new Error(`unknown radio model '${model}'`);
  const from = C.modelOf(cp);
  if (from === model) return cp;
  const oldT = SCHEMAS[from].tables, newT = SCHEMAS[model].tables;
  const stock = {};
  for (const [t, rows] of Object.entries(cp.stock || {})) {
    if (!newT[t]) continue;
    const oc = oldT[t].columns, nt = newT[t];
    const nd = nt.defaults.length ? Object.fromEntries(nt.columns.map((c, i) => [c, nt.defaults[i]])) : {};
    stock[t] = rows.map((r) => { const d = Object.fromEntries(oc.map((c, i) => [c, r[i]])); return nt.columns.map((c) => (c in d && d[c] !== undefined ? d[c] : (nd[c] ?? ""))); });
  }
  if (Object.keys(stock).length) cp.stock = stock; else delete cp.stock;
  for (const [t, attr] of Object.entries(OBJ_ATTR)) {
    const cols = new Set(newT[t].columns);
    for (const o of cp[attr] || []) if (o.stock) {
      o.stock = Object.fromEntries(Object.entries(o.stock).filter(([k]) => cols.has(k)));
      if (!Object.keys(o.stock).length) delete o.stock;
    }
  }
  if (cp.settings.radio_name === C.MODELS[from].name) cp.settings.radio_name = C.MODELS[model].name;
  if (model === "D890UV") delete cp.model; else cp.model = model;
  for (const k of ["_rdt", "_rdtStock", "_rdtOpt"]) delete cp[k];
  for (const c of cp.channels) delete c._rdt;
  use(model);
  return cp;
}
