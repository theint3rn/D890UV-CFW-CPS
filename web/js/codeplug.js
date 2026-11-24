// cfw codeplug core for the web CPS: model (= the JSON schema of cps/codeplug.py to_dict), binary "D8CP" v1
// encoder/decoder, validation, diff. Port of cps/codeplug.py, cps/validate.py, cps/diff.py; tests/vectors/ keep
// both sides byte-identical (web/test/run_tests.mjs). Works in browsers and in node (ES module, no deps).

export const MAGIC = "D8CP";
export const VERSION = 1;
export const HEADER_SIZE = 32;
export const REGION_SIZE = 0x60000;   // max; the radio reports its own region size (info block)
// radio models (cps/codeplug.py MODELS): header id (u16 at 18), radio region size, cfw link ident, default radio name
export const MODELS = { D890UV: { id: 0, region: 0x60000, ident: "D890CFW", name: "D890UV cfw" },
  D168UV: { id: 1, region: 0x60000, ident: "D168CFW", name: "D168UV cfw" } };
export const modelOf = (cp) => (cp && cp.model) || "D890UV";
const regionOf = (cp) => MODELS[modelOf(cp)].region;
export const MAX_CHANNELS = 4000;
export const MODES = ["FM", "DMR", "P25", "P25P2", "DSTAR", "NXDN", "YSF"];
export const POWERS = ["low", "mid", "high", "turbo"];
export const CONTACT_KINDS = ["group", "private", "all"];
export const CONTACT_MODES = { any: 0xff, DMR: 1, P25: 2, NXDN: 5 };
export const TRUNK_TYPES = { P25: 1, DMR_T3: 2, NXDN_C: 3, NXDN_D: 4 };
export const VOCODERS = ["auto", "AMBE+2", "AMBE+2 half-rate", "IMBE", "AMBE (D-STAR)", "AMBE+2 EHR", "AMBE+2 EFR", "YSF V/D", "YSF VW"];
export const MODE_VOCODERS = { DMR: ["auto", "AMBE+2"], P25: ["auto", "IMBE"], P25P2: ["auto", "AMBE+2 half-rate"],
  NXDN: ["auto", "AMBE+2 EHR", "AMBE+2 EFR"], DSTAR: ["auto", "AMBE (D-STAR)"], YSF: ["auto", "YSF V/D", "YSF VW"] };
export const YSF_MODES = ["DN", "VW", "DATA"];
export const KEY_KINDS = { DMR_BP: 2, DMR_ARC4: 5, DMR_AES128: 16, DMR_AES256: 32, P25_DES: 8, P25_AES256: 32, P25_ADP: 5,
  NXDN_SCR: 2, NXDN_DES: 8, NXDN_AES: 32 };
export const KEY_ALGID = { P25_DES: 0x81, P25_AES256: 0x84, P25_ADP: 0xaa, DMR_AES256: 0x24, DMR_AES128: 0x25, DMR_ARC4: 0x21 };
export const KEY_FUNCS = ["none", "mode_next", "mode_picker", "vfo_mem", "key_lock", "monitor", "scan", "test_tone", "zone_next",
  "talkaround", "tx_power", "call_log", "gps_info"];
export const CTCSS = [625, 670, 693, 719, 744, 770, 797, 825, 854, 885, 915, 948, 974, 1000, 1035, 1072, 1109, 1148, 1188, 1230,
  1273, 1318, 1365, 1413, 1462, 1514, 1567, 1598, 1622, 1655, 1679, 1713, 1738, 1773, 1799, 1835, 1862, 1899,
  1928, 1966, 1995, 2035, 2065, 2107, 2181, 2257, 2291, 2336, 2418, 2503, 2541];
const NONE16 = 0xffff, NONE8 = 0xff;
const REC_SIZE = { 1: 128, 2: 64, 3: 24, 4: 28, 5: 24, 6: 24, 7: 48, 8: 4, 9: 2, 11: 32, 12: 56, 13: 24, 14: 48, 15: 64 };
const SEC_STOCK = 10;
let STOCK = null;                 // stock.js module (registered by it: encode/decode of section 10)
let STOCK_SCHEMA = null;
export function registerStock(m, schema) { STOCK = m; STOCK_SCHEMA = schema || STOCK_SCHEMA; }
const useModel = (cp) => { if (STOCK && STOCK.use) STOCK.use(modelOf(cp)); };

export class CodeplugError extends Error {}

export const MODE_FIELDS = {
  FM: [], DMR: ["cc", "slot", "tg", "contact", "tglist", "trunksys", "vocoder", "key", "tdma_direct"],
  P25: ["nac", "tg", "contact", "tglist", "trunksys", "wacn", "sysid", "vocoder", "key"],
  P25P2: ["nac", "slot", "tg", "contact", "tglist", "trunksys", "wacn", "sysid", "vocoder", "key"],
  NXDN: ["ran", "tg", "contact", "tglist", "trunksys", "vocoder", "key", "nxdn_rate"],
  DSTAR: ["ur", "rpt1", "rpt2", "vocoder", "dstar_rpt"], YSF: ["dgid", "dgid_tx", "ysf_mode", "wiresx", "vocoder"],
};
export const EXT_DEFAULTS = { talkaround: false, vocoder: "auto", key: null, nxdn_rate: 4800, dgid_tx: null, ysf_mode: "DN",
  wiresx: false, dstar_rpt: null, tdma_direct: false };
export const FM_FIELDS = ["wide", "rx_tone", "tx_tone"];
export const COMMON_FIELDS = ["name", "rx_hz", "tx_hz", "mode", "trunk", "scan_skip", "power", "scanlist", "talkaround", "stock"];

export function settingsDefaults() {
  return {
    callsign: "N0CALL", dmr_id: 0, p25_unit_id: 0, nxdn_unit_id: 0, rx_invert: false, key_beep: true,
    auto_keylock: false, boot_vfo: false, encryption: false, sms_msms: false, step_hz: 12500, deemph_us: 0, test_tone_hz: 0, backlight_level: 8,
    backlight_timeout_s: 0, vfo_mode: "FM", keylock_timeout_s: 0, start_channel: null,
    keys: ["mode_next", "vfo_mem", "none", "none", "mode_next", "mode_picker"], dmr_cc: 1, dmr_slot: 1, dmr_tg: 91,
    p25_nac: 0x293, nxdn_ran: 1, ysf_dgid: 0, p25_tg: 1, nxdn_group: 1, p25_wacn: 0xbee00, p25_sysid: 0x3c1,
    ur: "CQCQCQ", rpt1: "", rpt2: "", dstar_msg: "", radio_name: "D890UV cfw",
  };
}

const MODE_DEFAULTS = Object.assign({ cc: 0, slot: 0, tg: 0, contact: null, tglist: null, trunksys: null, nac: 0, wacn: 0, sysid: 0,
  ran: 0, ur: "", rpt1: "", rpt2: "", dgid: 0, wide: false, rx_tone: null, tx_tone: null }, EXT_DEFAULTS);

/** canonical channel dict: exactly the keys to_dict() writes for its mode, missing ones defaulted */
export function normalizeChannel(c) {
  const mode = c.mode || "FM";
  if (!MODES.includes(mode)) throw new CodeplugError(`channel: mode ${JSON.stringify(mode)}`);
  const base = { name: "", rx_hz: 446000000, tx_hz: 446000000, mode, trunk: false, scan_skip: false, power: "high", scanlist: null,
    talkaround: false };
  const keys = COMMON_FIELDS.concat(mode === "FM" ? FM_FIELDS : [], MODE_FIELDS[mode]);
  const out = {};
  for (const k of keys) {
    if (k === "stock") { if (c.stock && Object.keys(c.stock).length) out.stock = Object.assign({}, c.stock); continue; }
    out[k] = k in c ? c[k] : (k in base ? base[k] : MODE_DEFAULTS[k]);
  }
  if (mode === "DMR" && out.slot !== 1 && out.slot !== 2) out.slot = 1;
  return out;
}

export function newChannel(over = {}) { return normalizeChannel(Object.assign({ name: "NEW" }, over)); }

export function newCodeplug(model = "D890UV") {
  if (!MODELS[model]) throw new CodeplugError(`unknown radio model '${model}'`);
  const settings = settingsDefaults();
  settings.radio_name = MODELS[model].name;
  return {
    format: "cfw-codeplug", version: VERSION, generation: 0, created: Math.floor(Date.now() / 1000), ...(model !== "D890UV" ? { model } : {}),
    settings,
    channels: [normalizeChannel({ name: "2M CALL", rx_hz: 146520000, tx_hz: 146520000, mode: "FM", wide: true }),
               normalizeChannel({ name: "70CM CALL", rx_hz: 446000000, tx_hz: 446000000, mode: "FM", wide: true })],
    zones: [], scanlists: [], contacts: [], tglists: [], trunksys: [], keys: [], dstar_rpts: [], digi: digiDefaults(),
  };
}

export function digiDefaults() {
  return { dstar_dprs: false, dstar_gps_interval_s: 0, dstar_auto_reply: false, dprs_symbol: "/[", dprs_comment: "",
    dmr_t3_register: false, p25_register: false, nxdn_register: false, ysf_mode: "DN", ysf_wiresx_room: 0, ysf_wiresx_auto: false };
}

const LIST_DEFAULTS = {
  zones: { name: "", channels: [] },
  scanlists: { name: "", channels: [], prio1: null, prio2: null, dwell_100ms: 20, flags: 0 },
  contacts: { name: "", id: 0, kind: "group", mode: "any" },
  tglists: { name: "", contacts: [] },
  trunksys: { name: "", type: "P25", nac_cc: 0, wacn: 0, sysid: 0, tglist: null, control_channels: [], chan_step_hz: 12500, base_hz: 0, flags: 0,
    rfss: 0, site: 0, registration: false, phase2: false, bandplan: [] },
  keys: { name: "", kind: "P25_AES256", key_id: 1, algid: 0x84, hex: "" },
  dstar_rpts: { name: "", rpt1: "", rpt2: "", rx_hz: 0, tx_hz: 0, gps: false },
};
const BANDPLAN_DEFAULTS = { iden: 0, base_hz: 851006250, spacing_hz: 6250, tx_offset_hz: -45000000, bw_hz: 12500, tdma: false, slots: 1 };
const HAS_STOCK = ["zones", "scanlists", "contacts", "tglists"];

/** from_dict(): checks the format, fills defaults, rejects unknown fields (same rules as Python) */
export function fromDict(d) {
  if (!d || d.format !== "cfw-codeplug") throw new CodeplugError("not a cfw codeplug export (format field)");
  const cp = { format: "cfw-codeplug", version: VERSION, generation: d.generation || 0, created: d.created || 0 };
  if (d.model !== undefined && d.model !== "D890UV") {
    if (!MODELS[d.model]) throw new CodeplugError(`unknown radio model '${d.model}'`);
    cp.model = d.model;
  }
  const sd = settingsDefaults();
  for (const k of Object.keys(d.settings || {})) if (!(k in sd)) throw new CodeplugError(`Settings: unknown field(s) ${k}`);
  cp.settings = Object.assign(sd, JSON.parse(JSON.stringify(d.settings || {})));
  cp.channels = (d.channels || []).map((c) => {
    for (const k of Object.keys(c)) if (!(k in MODE_DEFAULTS) && !COMMON_FIELDS.includes(k)) throw new CodeplugError(`channel: unknown field ${k}`);
    return normalizeChannel(c);
  });
  for (const k of Object.keys(LIST_DEFAULTS)) {
    cp[k] = (d[k] || []).map((x) => {
      for (const f of Object.keys(x)) if (!(f in LIST_DEFAULTS[k]) && !(f === "stock" && HAS_STOCK.includes(k))) throw new CodeplugError(`${k}: unknown field(s) ${f}`);
      const o = Object.assign(JSON.parse(JSON.stringify(LIST_DEFAULTS[k])), JSON.parse(JSON.stringify(x)));
      if (k === "trunksys") o.bandplan = o.bandplan.map((b) => Object.assign({}, BANDPLAN_DEFAULTS, b));
      if (o.stock !== undefined && !Object.keys(o.stock).length) delete o.stock;
      return o;
    });
  }
  const dd = digiDefaults();
  for (const k of Object.keys(d.digi || {})) if (!(k in dd)) throw new CodeplugError(`DigiSettings: unknown field(s) ${k}`);
  cp.digi = Object.assign(dd, d.digi || {});
  if (d.stock && Object.keys(d.stock).length) cp.stock = JSON.parse(JSON.stringify(d.stock));
  return cp;
}

// ------------------------------------------------------------------ bytes

export function crc32(b, start = 0, end = b.length) {
  let c = 0xffffffff;
  for (let i = start; i < end; i++) {
    c ^= b[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return (~c) >>> 0;
}

class W {
  constructor() { this.a = []; }
  u8(v) { this.a.push(v & 0xff); return this; }
  u16(v) { this.a.push(v & 0xff, (v >>> 8) & 0xff); return this; }
  u32(v) { v = v >>> 0; this.a.push(v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff); return this; }
  str(s, n) {
    for (let i = 0; i < n; i++) {
      const ch = i < (s || "").length ? s.charCodeAt(i) : 0;
      this.a.push(ch < 0x80 ? ch : 0x3f);
    }
    return this;
  }
  pad(n) { for (let i = 0; i < n; i++) this.a.push(0); return this; }
  bytes() { return Uint8Array.from(this.a); }
  get length() { return this.a.length; }
}

const ref16 = (v) => (v === null || v === undefined ? NONE16 : v);
const unref16 = (v) => (v === NONE16 ? null : v);
const chk = (v, lo, hi, what) => { if (!Number.isInteger(v) || v < lo || v > hi) throw new CodeplugError(`${what} ${v} does not fit`); return v; };

export function toneEncode(t) {
  if (t === null || t === undefined || t === "") return 0;
  t = String(t).trim().toUpperCase();
  if (t.startsWith("D")) {
    const inv = t.endsWith("I");
    const code = t.slice(1).replace(/[NI]+$/, "");
    if (!/^[0-7]+$/.test(code)) throw new CodeplugError(`invalid literal for int() with base 8: '${code}'`);
    const v = parseInt(code, 8);
    if (v > 0o777) throw new CodeplugError(`DCS code '${t}' out of range`);
    return 0x8000 | (inv ? 0x4000 : 0) | v;
  }
  const f = Number(t);
  if (t === "" || Number.isNaN(f)) throw new CodeplugError(`could not convert string to float: '${t}'`);
  const v = Math.round(f * 10);
  if (!(v >= 1 && v <= 0x3fff)) throw new CodeplugError(`CTCSS '${t}' out of range`);
  return v;
}

export function toneDecode(v) {
  if (v === 0) return null;
  if (v & 0x8000) return "D" + (v & 0x1ff).toString(8).padStart(3, "0") + (v & 0x4000 ? "I" : "N");
  return `${Math.floor(v / 10)}.${v % 10}`;
}

function encSettings(s) {
  const w = new W();
  const flags = (s.rx_invert ? 1 : 0) | (s.key_beep ? 2 : 0) | (s.auto_keylock ? 4 : 0) | (s.boot_vfo ? 8 : 0) |
    (s.encryption ? 16 : 0) | (s.sms_msms ? 32 : 0);
  w.str(s.callsign, 8).u32(s.dmr_id).u32(s.p25_unit_id).u16(s.nxdn_unit_id).u16(flags).u32(s.step_hz)
    .u16(s.deemph_us).u16(s.test_tone_hz).u8(s.backlight_level).u8(s.backlight_timeout_s)
    .u8(MODES.indexOf(s.vfo_mode)).u8(s.keylock_timeout_s).u16(ref16(s.start_channel));
  const keys = (s.keys || []).concat(Array(6).fill("none")).slice(0, 6);
  for (const k of keys) w.u8(Math.max(0, KEY_FUNCS.indexOf(k)));
  w.u8(s.dmr_cc).u8(s.dmr_slot).u16(0).u32(s.dmr_tg).u16(s.p25_nac).u8(s.nxdn_ran).u8(s.ysf_dgid)
    .u32(s.p25_tg).u32(s.nxdn_group).u32(s.p25_wacn).u16(s.p25_sysid).u16(0)
    .str(s.ur, 8).str(s.rpt1, 8).str(s.rpt2, 8).str(s.dstar_msg, 20).str(s.radio_name, 16);
  if (w.length !== 128) throw new Error("settings size");
  return w.bytes();
}

function encChannel(c0) {
  const c = normalizeChannel(c0);
  const m = c.mode;
  const w = new W();
  const flags = (m === "FM" && c.wide ? 1 : 0) | (c.trunk ? 2 : 0) | (c.scan_skip ? 4 : 0);
  if (!POWERS.includes(c.power)) throw new CodeplugError(`power ${c.power}`);
  w.str(c.name, 16).u32(chk(c.rx_hz, 0, 0xffffffff, "rx")).u32(chk(c.tx_hz, 0, 0xffffffff, "tx"))
    .u8(MODES.indexOf(m)).u8(flags).u8(POWERS.indexOf(c.power)).u8(c.scanlist === null ? NONE8 : c.scanlist)
    .u16(m === "FM" ? toneEncode(c.rx_tone) : 0).u16(m === "FM" ? toneEncode(c.tx_tone) : 0);
  const u = new W();
  if (m === "DMR") u.u8(c.cc).u8(c.slot).u8(0).u8(0).u32(c.tg).u16(ref16(c.contact)).u16(ref16(c.tglist)).u16(ref16(c.trunksys));
  else if (m === "P25" || m === "P25P2") u.u16(c.nac).u8(m === "P25P2" ? c.slot : 0).u8(0).u32(c.tg).u16(ref16(c.contact))
    .u16(ref16(c.tglist)).u16(ref16(c.trunksys)).u16(c.sysid).u32(c.wacn);
  else if (m === "NXDN") u.u8(c.ran).pad(3).u32(c.tg).u16(ref16(c.contact)).u16(ref16(c.tglist)).u16(ref16(c.trunksys));
  else if (m === "DSTAR") u.str(c.ur, 8).str(c.rpt1, 8).str(c.rpt2, 8);
  else if (m === "YSF") u.u8(c.dgid);
  u.pad(32 - u.length);
  w.a.push(...u.a);
  return w.bytes();
}

function extOf(c) {
  const v = Object.assign({}, EXT_DEFAULTS, c);
  if (Object.keys(EXT_DEFAULTS).every((k) => v[k] === EXT_DEFAULTS[k])) return null;
  const voc = Math.max(0, VOCODERS.indexOf(v.vocoder));
  return new W().u8(voc).u8((v.talkaround ? 1 : 0) | (v.wiresx ? 2 : 0) | (v.tdma_direct ? 4 : 0)).u8(v.key === null ? NONE8 : v.key)
    .u8(v.nxdn_rate === 9600 ? 1 : 0).u8(v.dgid_tx === null ? NONE8 : v.dgid_tx).u8(YSF_MODES.indexOf(v.ysf_mode)).u16(ref16(v.dstar_rpt));
}

function encDigi(g0) {
  const g = Object.assign(digiDefaults(), g0 || {});
  const flags = [g.dstar_dprs, g.dstar_auto_reply, g.dmr_t3_register, g.p25_register, g.nxdn_register, g.ysf_wiresx_auto]
    .reduce((a, b, i) => a | ((b ? 1 : 0) << i), 0);
  const w = new W().u8(flags).u8(YSF_MODES.indexOf(g.ysf_mode)).u16(g.dstar_gps_interval_s).u32(g.ysf_wiresx_room)
    .str(g.dprs_symbol, 2).str(g.dprs_comment, 20);
  w.pad(64 - w.length);
  return w.bytes();
}

function hexBytes(h) {
  h = (h || "").replace(/\s/g, "");
  const out = [];
  for (let i = 0; i + 1 < h.length; i += 2) out.push(parseInt(h.slice(i, i + 2), 16));
  return out;
}

/** codeplug dict -> Uint8Array (canonical, identical to cps.codeplug.encode(cp, for_radio)) */
export function encode(cp, forRadio = true) {
  const pool16 = [], pool32 = [];
  const put16 = (lst) => { const f = pool16.length; for (const x of lst) pool16.push(x); return f; };
  const recs = {}; for (const k of Object.keys(REC_SIZE)) recs[k] = [];
  recs[1].push(encSettings(Object.assign(settingsDefaults(), cp.settings)));
  for (const c of cp.channels) recs[2].push(encChannel(c));
  for (const z of cp.zones || []) recs[3].push(new W().str(z.name, 16).u32(put16(z.channels)).u16(z.channels.length).u16(0).bytes());
  for (const s of cp.scanlists || []) recs[4].push(new W().str(s.name, 16).u32(put16(s.channels)).u16(s.channels.length)
    .u16(ref16(s.prio1)).u16(ref16(s.prio2)).u8(s.dwell_100ms ?? 20).u8(s.flags ?? 0).bytes());
  for (const c of cp.contacts || []) recs[5].push(new W().str(c.name, 16).u32(c.id).u8(CONTACT_KINDS.indexOf(c.kind))
    .u8(CONTACT_MODES[c.mode]).u16(0).bytes());
  for (const t of cp.tglists || []) recs[6].push(new W().str(t.name, 16).u32(put16(t.contacts)).u16(t.contacts.length).u16(0).bytes());
  for (const t of cp.trunksys || []) {
    const first = pool32.length;
    for (const f of t.control_channels) pool32.push(f);
    recs[7].push(new W().str(t.name, 16).u8(TRUNK_TYPES[t.type]).u8(t.flags ?? 0).u16(t.nac_cc).u32(t.wacn).u16(t.sysid)
      .u16(ref16(t.tglist)).u32(first).u16(t.control_channels.length).u16(((t.rfss & 0xff) << 8) | (t.site & 0xff))
      .u32(t.chan_step_hz).u32(t.base_hz).u32((t.registration ? 1 : 0) | (t.phase2 ? 2 : 0)).bytes());
  }
  (cp.trunksys || []).forEach((t, ti) => {
    for (const bp of t.bandplan || []) {
      const w = new W().u16(ti).u8(bp.iden).u8(bp.tdma ? 1 : 0).u32(bp.base_hz).u32(bp.spacing_hz).u32(bp.tx_offset_hz >>> 0)
        .u32(bp.bw_hz).u8(bp.slots).pad(3);
      recs[13].push(w.bytes());
    }
  });
  cp.channels.forEach((c, i) => {
    const e = extOf(c);
    if (e) { const w = new W().u16(i); w.a.push(...e.a); w.pad(32 - w.length); recs[11].push(w.bytes()); }
  });
  const kinds = Object.keys(KEY_KINDS);
  for (const k of cp.keys || []) {
    const kb = hexBytes(k.hex);
    const w = new W().str(k.name, 16).u8(kinds.indexOf(k.kind)).u8(k.algid).u16(k.key_id).u8(kb.length).pad(3);
    for (let i = 0; i < 32; i++) w.u8(i < kb.length ? kb[i] : 0);
    recs[12].push(w.bytes());
  }
  for (const r of cp.dstar_rpts || []) recs[14].push(new W().str(r.name, 16).str(r.rpt1, 8).str(r.rpt2, 8).u32(r.rx_hz).u32(r.tx_hz)
    .u8(r.gps ? 1 : 0).pad(7).bytes());
  recs[15].push(encDigi(cp.digi));
  recs[9] = pool16.map((v) => new W().u16(v).bytes());
  recs[8] = pool32.map((v) => new W().u32(v).bytes());
  const order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15];
  useModel(cp);
  const stockB = STOCK ? STOCK.encodeStock(cp, forRadio) : new Uint8Array(0);
  if (stockB.length) { order.push(SEC_STOCK); recs[SEC_STOCK] = [stockB]; }
  let off = HEADER_SIZE + 16 * order.length;
  const dir = new W(), body = [];
  let blen = 0;
  for (const sid of order) {
    let n = 0; for (const r of recs[sid]) n += r.length;
    if (sid === SEC_STOCK) dir.u16(sid).u16(1).u32(n).u32(off + blen).u32(0);
    else dir.u16(sid).u16(REC_SIZE[sid]).u32(recs[sid].length).u32(off + blen).u32(0);
    for (const r of recs[sid]) body.push(r);
    const p = (4 - (n % 4)) % 4;
    if (p) body.push(new Uint8Array(p));
    blen += n + p;
  }
  let total = HEADER_SIZE + dir.length + blen;
  const pad = (16 - (total % 16)) % 16;
  total += pad;
  if (forRadio && total > regionOf(cp)) throw new CodeplugError(`codeplug is ${total} bytes, the radio holds ${regionOf(cp)}`);
  const out = new Uint8Array(total);
  const hdr = new W().str(MAGIC, 4).u16(VERSION).u16(HEADER_SIZE).u32(total).u32(0)
    .u16(order.length).u16(MODELS[modelOf(cp)].id).u32(cp.generation || 0).u32(cp.created || 0).u32(0).bytes();
  out.set(hdr, 0);
  out.set(dir.bytes(), HEADER_SIZE);
  let p = HEADER_SIZE + dir.length;
  for (const r of body) { out.set(r, p); p += r.length; }
  new DataView(out.buffer).setUint32(12, crc32(out, 16, total), true);
  return out;
}

const dv = (b) => new DataView(b.buffer, b.byteOffset, b.byteLength);
function cstr(b, o, n) {
  let s = "";
  for (let i = 0; i < n && b[o + i]; i++) s += b[o + i] < 0x80 ? String.fromCharCode(b[o + i]) : "�";
  return s;
}

export function checkHeader(b) {
  if (b.length < HEADER_SIZE || cstr(b, 0, 4) !== MAGIC) throw new CodeplugError("not a cfw codeplug (magic)");
  const v = dv(b);
  const ver = v.getUint16(4, true), hs = v.getUint16(6, true), total = v.getUint32(8, true), crc = v.getUint32(12, true);
  if (ver !== VERSION) throw new CodeplugError(`codeplug format version ${ver}, this CPS knows ${VERSION}`);
  if (hs !== HEADER_SIZE || total < HEADER_SIZE || total > b.length)
    throw new CodeplugError(`bad header (size ${hs}, length ${total} of ${b.length})`);
  if (crc32(b, 16, total) !== crc) throw new CodeplugError("CRC mismatch");
  return { total, crc };
}

function decSettings(b) {
  const v = dv(b), s = settingsDefaults();
  s.callsign = cstr(b, 0, 8);
  s.dmr_id = v.getUint32(8, true); s.p25_unit_id = v.getUint32(12, true); s.nxdn_unit_id = v.getUint16(16, true);
  const flags = v.getUint16(18, true);
  s.rx_invert = !!(flags & 1); s.key_beep = !!(flags & 2); s.auto_keylock = !!(flags & 4); s.boot_vfo = !!(flags & 8);
  s.encryption = !!(flags & 16);
  s.sms_msms = !!(flags & 32);
  s.step_hz = v.getUint32(20, true); s.deemph_us = v.getUint16(24, true); s.test_tone_hz = v.getUint16(26, true);
  s.backlight_level = b[28]; s.backlight_timeout_s = b[29]; s.vfo_mode = MODES[b[30]] || "FM"; s.keylock_timeout_s = b[31];
  s.start_channel = unref16(v.getUint16(32, true));
  s.keys = Array.from(b.slice(34, 40)).map((k) => KEY_FUNCS[k] || "none");
  s.dmr_cc = b[40]; s.dmr_slot = b[41]; s.dmr_tg = v.getUint32(44, true); s.p25_nac = v.getUint16(48, true);
  s.nxdn_ran = b[50]; s.ysf_dgid = b[51]; s.p25_tg = v.getUint32(52, true); s.nxdn_group = v.getUint32(56, true);
  s.p25_wacn = v.getUint32(60, true); s.p25_sysid = v.getUint16(64, true);
  s.ur = cstr(b, 68, 8); s.rpt1 = cstr(b, 76, 8); s.rpt2 = cstr(b, 84, 8); s.dstar_msg = cstr(b, 92, 20); s.radio_name = cstr(b, 112, 16);
  return s;
}

function decChannel(b) {
  const v = dv(b);
  const mi = b[24];
  if (mi >= MODES.length) throw new CodeplugError(`channel mode ${mi} unknown`);
  const m = MODES[mi], flags = b[25];
  const c = { name: cstr(b, 0, 16), rx_hz: v.getUint32(16, true), tx_hz: v.getUint32(20, true), mode: m, trunk: !!(flags & 2),
    scan_skip: !!(flags & 4), power: POWERS[b[26] & 3], scanlist: b[27] === NONE8 ? null : b[27] };
  if (m === "FM") { c.wide = !!(flags & 1); c.rx_tone = toneDecode(v.getUint16(28, true)); c.tx_tone = toneDecode(v.getUint16(30, true)); }
  const o = 32;
  if (m === "DMR") {
    Object.assign(c, { cc: b[o], slot: b[o + 1], tg: v.getUint32(o + 4, true), contact: unref16(v.getUint16(o + 8, true)),
      tglist: unref16(v.getUint16(o + 10, true)), trunksys: unref16(v.getUint16(o + 12, true)) });
  } else if (m === "P25" || m === "P25P2") {
    Object.assign(c, { nac: v.getUint16(o, true), tg: v.getUint32(o + 4, true), contact: unref16(v.getUint16(o + 8, true)),
      tglist: unref16(v.getUint16(o + 10, true)), trunksys: unref16(v.getUint16(o + 12, true)),
      wacn: v.getUint32(o + 16, true), sysid: v.getUint16(o + 14, true) });
    if (m === "P25P2") c.slot = b[o + 2];
  } else if (m === "NXDN") {
    Object.assign(c, { ran: b[o], tg: v.getUint32(o + 4, true), contact: unref16(v.getUint16(o + 8, true)), tglist: unref16(v.getUint16(o + 10, true)),
      trunksys: unref16(v.getUint16(o + 12, true)) });
  } else if (m === "DSTAR") {
    Object.assign(c, { ur: cstr(b, o, 8), rpt1: cstr(b, o + 8, 8), rpt2: cstr(b, o + 16, 8) });
  } else if (m === "YSF") c.dgid = b[o];
  return normalizeChannel(c);
}

/** Uint8Array -> codeplug dict (same as Python to_dict(decode(b))) */
export function decode(b) {
  const { total } = checkHeader(b);
  const v = dv(b);
  const nsec = v.getUint16(16, true), mid = v.getUint16(18, true);
  const model = Object.keys(MODELS).find((m) => MODELS[m].id === mid);
  if (!model) throw new CodeplugError(`codeplug for an unknown radio model (id ${mid})`);
  const cp = { format: "cfw-codeplug", version: VERSION, generation: v.getUint32(20, true), created: v.getUint32(24, true),
    ...(model !== "D890UV" ? { model } : {}),
    settings: settingsDefaults(), channels: [], zones: [], scanlists: [], contacts: [], tglists: [], trunksys: [], keys: [],
    dstar_rpts: [], digi: digiDefaults() };
  const secs = {};
  for (let i = 0; i < nsec; i++) {
    const o = HEADER_SIZE + 16 * i;
    const sid = v.getUint16(o, true), rs = v.getUint16(o + 2, true), cnt = v.getUint32(o + 4, true), off = v.getUint32(o + 8, true);
    if (off + rs * cnt > total) throw new CodeplugError(`section ${sid} out of bounds`);
    if (REC_SIZE[sid] && rs !== REC_SIZE[sid]) throw new CodeplugError(`section ${sid} record size ${rs}`);
    if (sid === SEC_STOCK) { secs[sid] = [b.subarray(off, off + cnt)]; continue; }
    secs[sid] = []; for (let k = 0; k < cnt; k++) secs[sid].push(b.subarray(off + k * rs, off + (k + 1) * rs));
  }
  const p16 = (secs[9] || []).map((r) => dv(r).getUint16(0, true));
  const p32 = (secs[8] || []).map((r) => dv(r).getUint32(0, true));
  const take16 = (f, n) => { if (f + n > p16.length) throw new CodeplugError("list out of the pool"); return p16.slice(f, f + n); };
  if (secs[1] && secs[1].length) cp.settings = decSettings(secs[1][0]);
  cp.channels = (secs[2] || []).map(decChannel);
  for (const r of secs[3] || []) { const q = dv(r); cp.zones.push({ name: cstr(r, 0, 16), channels: take16(q.getUint32(16, true), q.getUint16(20, true)) }); }
  for (const r of secs[4] || []) {
    const q = dv(r);
    cp.scanlists.push({ name: cstr(r, 0, 16), channels: take16(q.getUint32(16, true), q.getUint16(20, true)),
      prio1: unref16(q.getUint16(22, true)), prio2: unref16(q.getUint16(24, true)), dwell_100ms: r[26], flags: r[27] });
  }
  const cmodes = Object.fromEntries(Object.entries(CONTACT_MODES).map(([k, x]) => [x, k]));
  for (const r of secs[5] || []) cp.contacts.push({ name: cstr(r, 0, 16), id: dv(r).getUint32(16, true),
    kind: r[20] < 3 ? CONTACT_KINDS[r[20]] : "group", mode: cmodes[r[21]] || "any" });
  for (const r of secs[6] || []) { const q = dv(r); cp.tglists.push({ name: cstr(r, 0, 16), contacts: take16(q.getUint32(16, true), q.getUint16(20, true)) }); }
  const types = { 1: "P25", 2: "DMR_T3", 3: "NXDN_C", 4: "NXDN_D" };
  for (const r of secs[7] || []) {
    const q = dv(r), f = q.getUint32(28, true), n = q.getUint16(32, true), rs = q.getUint16(34, true), f2 = q.getUint32(44, true);
    if (f + n > p32.length) throw new CodeplugError("control channel list out of the pool");
    cp.trunksys.push({ name: cstr(r, 0, 16), type: types[r[16]] || "P25", nac_cc: q.getUint16(18, true), wacn: q.getUint32(20, true),
      sysid: q.getUint16(24, true), tglist: unref16(q.getUint16(26, true)), control_channels: p32.slice(f, f + n),
      chan_step_hz: q.getUint32(36, true), base_hz: q.getUint32(40, true), flags: r[17], rfss: rs >> 8, site: rs & 0xff,
      registration: !!(f2 & 1), phase2: !!(f2 & 2), bandplan: [] });
  }
  for (const r of secs[13] || []) {
    const q = dv(r), ti = q.getUint16(0, true);
    if (ti < cp.trunksys.length) cp.trunksys[ti].bandplan.push({ iden: r[2], base_hz: q.getUint32(4, true), spacing_hz: q.getUint32(8, true),
      tx_offset_hz: q.getInt32(12, true), bw_hz: q.getUint32(16, true), tdma: !!(r[3] & 1), slots: r[20] });
  }
  for (const r of secs[11] || []) {
    const q = dv(r), i = q.getUint16(0, true);
    if (i >= cp.channels.length) continue;
    const c = cp.channels[i];
    const ext = { vocoder: VOCODERS[r[2]] || "auto", talkaround: !!(r[3] & 1), wiresx: !!(r[3] & 2), tdma_direct: !!(r[3] & 4), key: r[4] === NONE8 ? null : r[4],
      nxdn_rate: r[5] ? 9600 : 4800, dgid_tx: r[6] === NONE8 ? null : r[6], ysf_mode: YSF_MODES[r[7]] || "DN", dstar_rpt: unref16(q.getUint16(8, true)) };
    cp.channels[i] = normalizeChannel(Object.assign({}, c, ext));
  }
  const kinds = Object.keys(KEY_KINDS);
  for (const r of secs[12] || []) {
    const q = dv(r), ln = r[20];
    cp.keys.push({ name: cstr(r, 0, 16), kind: kinds[r[16]] || "P25_AES256", key_id: q.getUint16(18, true), algid: r[17],
      hex: Array.from(r.slice(24, 24 + ln)).map((x) => x.toString(16).toUpperCase().padStart(2, "0")).join("") });
  }
  for (const r of secs[14] || []) {
    const q = dv(r);
    cp.dstar_rpts.push({ name: cstr(r, 0, 16), rpt1: cstr(r, 16, 8), rpt2: cstr(r, 24, 8), rx_hz: q.getUint32(32, true),
      tx_hz: q.getUint32(36, true), gps: !!(r[40] & 1) });
  }
  if (secs[15] && secs[15].length) {
    const r = secs[15][0], q = dv(r), fl = r[0];
    cp.digi = { dstar_dprs: !!(fl & 1), dstar_gps_interval_s: q.getUint16(2, true), dstar_auto_reply: !!(fl & 2),
      dprs_symbol: cstr(r, 8, 2), dprs_comment: cstr(r, 10, 20), dmr_t3_register: !!(fl & 4), p25_register: !!(fl & 8),
      nxdn_register: !!(fl & 16), ysf_mode: YSF_MODES[r[1]] || "DN", ysf_wiresx_room: q.getUint32(4, true), ysf_wiresx_auto: !!(fl & 32) };
  }
  useModel(cp);
  if (secs[SEC_STOCK] && STOCK) STOCK.decodeStock(secs[SEC_STOCK][0], cp);
  return cp;
}

export function load(bytesOrText, name = "") {
  const b = typeof bytesOrText === "string" ? new TextEncoder().encode(bytesOrText) : bytesOrText;
  if (b.length >= 4 && cstr(b, 0, 4) === MAGIC) return decode(b);
  return fromDict(JSON.parse(new TextDecoder().decode(b)));
}

export const dumpsJson = (cp) => JSON.stringify(fromDict(cp), null, 1) + "\n";

// ------------------------------------------------------------------ validation (cps/validate.py)

const BANDS = [[136000000, 174000000], [400000000, 480000000]];
export const inBand = (hz) => BANDS.some(([lo, hi]) => lo <= hz && hz <= hi);
const mhz5 = (hz) => (hz / 1e6).toFixed(5);
const hx = (v) => "0x" + v.toString(16).toUpperCase();
const pyr = (s) => (s === null || s === undefined ? "None" : typeof s === "string" ? `'${s}'` : String(s));

export function validate(cp) {
  const out = [];
  const err = (w, m) => out.push({ level: "error", where: w, msg: m });
  const warn = (w, m) => out.push({ level: "warn", where: w, msg: m });
  const s = cp.settings;
  if (!(s.dmr_id >= 0 && s.dmr_id <= 16776415)) err("settings", `DMR ID ${s.dmr_id} out of range (1..16776415)`);
  if (s.dmr_id === 0) warn("settings", "DMR ID is 0 (firmware keeps its default)");
  if (!/^[A-Za-z0-9/ ]{0,8}$/.test(s.callsign || "")) err("settings", `callsign ${pyr(s.callsign)}: up to 8 of A-Z 0-9 /`);
  if (!(s.step_hz >= 1000 && s.step_hz <= 100000)) err("settings", `step ${s.step_hz} Hz (1000..100000)`);
  if (!(s.deemph_us >= 0 && s.deemph_us <= 2000)) err("settings", `de-emphasis ${s.deemph_us} us (0..2000)`);
  if (!(s.test_tone_hz >= 0 && s.test_tone_hz <= 3000)) err("settings", `test tone ${s.test_tone_hz} Hz (0..3000)`);
  if (!(s.backlight_level >= 0 && s.backlight_level <= 10)) err("settings", `backlight level ${s.backlight_level} (0..10)`);
  if (!MODES.includes(s.vfo_mode)) err("settings", `VFO mode ${pyr(s.vfo_mode)}`);
  for (const k of s.keys) if (!KEY_FUNCS.includes(k)) err("settings", `key function ${pyr(k)} (one of ${KEY_FUNCS.join(", ")})`);
  if (s.start_channel !== null && !(s.start_channel >= 0 && s.start_channel < cp.channels.length))
    err("settings", `start channel ${s.start_channel} does not exist`);
  for (const [nm, v, hi] of [["DMR CC", s.dmr_cc, 15], ["P25 NAC", s.p25_nac, 0xfff], ["NXDN RAN", s.nxdn_ran, 63],
    ["YSF DG-ID", s.ysf_dgid, 99], ["P25 WACN", s.p25_wacn, 0xfffff], ["P25 SysID", s.p25_sysid, 0xfff]])
    if (!(v >= 0 && v <= hi)) err("settings", `${nm} default ${v} out of range`);
  const nch = cp.channels.length;
  if (nch === 0) err("channels", "no channels");
  if (nch > MAX_CHANNELS) err("channels", `${nch} channels, firmware limit ${MAX_CHANNELS}`);
  cp.channels.forEach((c, i) => {
    const w = `ch ${i + 1} ${c.name.slice(0, 12)}`;
    if (!MODES.includes(c.mode)) { err(w, `mode ${pyr(c.mode)}`); return; }
    if (c.name.length > 16 || [...c.name].some((ch) => ch.charCodeAt(0) < 0x20 || ch.charCodeAt(0) >= 0x7f))
      err(w, "name: up to 16 printable ASCII characters");
    if (!c.name) warn(w, "empty name");
    if (!inBand(c.rx_hz)) err(w, `RX ${mhz5(c.rx_hz)} MHz outside 136-174 / 400-480 MHz`);
    if (c.tx_hz && !inBand(c.tx_hz)) err(w, `TX ${mhz5(c.tx_hz)} MHz outside 136-174 / 400-480 MHz (use 0 for RX only)`);
    if (c.rx_hz % 50) warn(w, "RX frequency not on a 50 Hz grid");
    if (!POWERS.includes(c.power)) err(w, `power ${pyr(c.power)}`);
    if (c.scanlist !== null && !(c.scanlist >= 0 && c.scanlist < (cp.scanlists || []).length)) err(w, `scan list ${c.scanlist} does not exist`);
    if (c.mode === "FM") {
      for (const nm of ["rx_tone", "tx_tone"]) {
        let v;
        try { v = toneEncode(c[nm]); } catch (e) { err(w, `${nm}: ${e.message}`); continue; }
        if (v && !(v & 0x8000) && !CTCSS.includes(v)) warn(w, `${nm} ${c[nm]} Hz is not a standard CTCSS tone`);
      }
      if (c.trunk) err(w, "trunk flag only for DMR (Tier III) / P25 channels");
    } else {
      if (c.wide) err(w, "25 kHz bandwidth is FM only");
      if (c.rx_tone || c.tx_tone) err(w, "CTCSS/DCS only on FM channels");
    }
    if (c.mode !== "FM") {
      if (!(MODE_VOCODERS[c.mode] || ["auto"]).includes(c.vocoder)) err(w, `vocoder ${pyr(c.vocoder)} not usable in ${c.mode} (${MODE_VOCODERS[c.mode].join(", ")})`);
      if (c.key !== null && c.key !== undefined && !(c.key >= 0 && c.key < (cp.keys || []).length)) err(w, `encryption key ${c.key} does not exist`);
      else if (c.key !== null && c.key !== undefined) {
        const kk = cp.keys[c.key].kind.split("_")[0];
        if (kk !== ({ P25P2: "P25" }[c.mode] || c.mode)) err(w, `key ${pyr(cp.keys[c.key].name)} is a ${kk} key, channel is ${c.mode}`);
      }
    }
    if (c.mode === "NXDN" && c.nxdn_rate !== 4800 && c.nxdn_rate !== 9600) err(w, `NXDN rate ${pyr(c.nxdn_rate)} (4800 / 9600)`);
    if (c.mode === "YSF") {
      if (c.dgid_tx !== null && !(c.dgid_tx >= 0 && c.dgid_tx <= 99)) err(w, `TX DG-ID ${c.dgid_tx} (0..99)`);
      if (!YSF_MODES.includes(c.ysf_mode)) err(w, `YSF mode ${pyr(c.ysf_mode)}`);
    }
    if (c.mode === "DSTAR" && c.dstar_rpt !== null && !(c.dstar_rpt >= 0 && c.dstar_rpt < (cp.dstar_rpts || []).length))
      err(w, `D-STAR repeater ${c.dstar_rpt} does not exist`);
    if (c.talkaround && !c.tx_hz) warn(w, "talkaround on an RX-only channel");
    if (c.mode === "DMR" && c.tdma_direct && c.tx_hz && c.tx_hz !== c.rx_hz && !c.talkaround)
      warn(w, "TDMA direct on a duplex channel (simplex or talkaround only)");
    if (c.trunk && !["DMR", "P25", "P25P2", "NXDN"].includes(c.mode)) err(w, `trunk flag on a ${c.mode} channel`);
    if (c.mode === "DMR") {
      if (!(c.cc >= 0 && c.cc <= 15)) err(w, `colour code ${c.cc} (0..15)`);
      if (c.slot !== 1 && c.slot !== 2) err(w, `time slot ${c.slot} (1/2)`);
      if (!(c.tg >= 0 && c.tg <= 16776415)) err(w, `talkgroup ${c.tg} out of range`);
    }
    if (c.mode === "P25" || c.mode === "P25P2") {
      if (!(c.nac >= 0 && c.nac <= 0xfff)) err(w, `NAC ${hx(c.nac)} (0..FFF)`);
      if (!(c.tg >= 0 && c.tg <= 65535)) err(w, `P25 talkgroup ${c.tg} (0..65535)`);
      if (!(c.wacn >= 0 && c.wacn <= 0xfffff)) err(w, `WACN ${hx(c.wacn)} (20 bit)`);
      if (!(c.sysid >= 0 && c.sysid <= 0xfff)) err(w, `system ID ${hx(c.sysid)} (12 bit)`);
      if (c.mode === "P25P2") {
        if (c.slot !== 1 && c.slot !== 2) err(w, `time slot ${c.slot} (1/2)`);
        if (!c.wacn && c.trunksys === null) warn(w, "Phase 2 needs WACN + system ID for the scrambling seed");
      }
    }
    if (c.mode === "NXDN") {
      if (!(c.ran >= 0 && c.ran <= 63)) err(w, `RAN ${c.ran} (0..63)`);
      if (!(c.tg >= 0 && c.tg <= 65535)) err(w, `NXDN group ${c.tg} (0..65535)`);
    }
    if (c.mode === "DSTAR") for (const nm of ["ur", "rpt1", "rpt2"])
      if (!/^[A-Z0-9/ ]{0,8}$/.test(c[nm] || "")) err(w, `${nm.toUpperCase()} ${pyr(c[nm])}: up to 8 of A-Z 0-9 / space`);
    if (c.mode === "YSF" && !(c.dgid >= 0 && c.dgid <= 99)) err(w, `DG-ID ${c.dgid} (0..99)`);
    if (["DMR", "P25", "P25P2", "NXDN"].includes(c.mode)) {
      if (c.contact !== null && !(c.contact >= 0 && c.contact < cp.contacts.length)) err(w, `contact ${c.contact} does not exist`);
      if (c.tglist !== null && !(c.tglist >= 0 && c.tglist < cp.tglists.length)) err(w, `TG list ${c.tglist} does not exist`);
    }
    if (["DMR", "P25", "P25P2", "NXDN"].includes(c.mode) && c.trunksys !== null) {
      if (!(c.trunksys >= 0 && c.trunksys < cp.trunksys.length)) err(w, `trunk system ${c.trunksys} does not exist`);
      else {
        const t = cp.trunksys[c.trunksys], want = { DMR: ["DMR_T3"], NXDN: ["NXDN_C", "NXDN_D"] }[c.mode] || ["P25"];
        if (!want.includes(t.type)) err(w, `trunk system ${pyr(t.name)} is ${t.type}, channel is ${c.mode}`);
        if (!c.trunk) warn(w, "has a trunk system but the trunk flag is off (firmware sets it)");
      }
    }
  });
  for (const [k, lst] of [["zone", cp.zones], ["scan list", cp.scanlists]]) {
    lst.forEach((z, i) => {
      const w = `${k} ${i + 1} ${z.name.slice(0, 10)}`;
      if (z.name.length > 16) err(w, "name longer than 16");
      for (const m of z.channels) if (!(m >= 0 && m < nch)) err(w, `member channel ${m} does not exist`);
      if (new Set(z.channels).size !== z.channels.length) warn(w, "duplicate members");
      if (k === "scan list") for (const p of [z.prio1, z.prio2]) if (p !== null && !(p >= 0 && p < nch)) err(w, `priority channel ${p} does not exist`);
    });
  }
  if (cp.scanlists.length > 254) err("scanlists", "more than 254 scan lists");
  cp.contacts.forEach((c, i) => {
    const w = `contact ${i + 1} ${c.name.slice(0, 10)}`;
    if (!CONTACT_KINDS.includes(c.kind)) err(w, `kind ${pyr(c.kind)}`);
    if (!(c.mode in CONTACT_MODES)) err(w, `mode ${pyr(c.mode)}`);
    const hi = c.mode === "P25" ? (c.kind === "private" ? 0xffffff : 65535) : c.mode === "NXDN" ? 65535 : 16777215;
    if (!(c.id >= 0 && c.id <= hi)) err(w, `id ${c.id} out of range for ${c.mode}`);
  });
  cp.tglists.forEach((t, i) => {
    const w = `TG list ${i + 1} ${t.name.slice(0, 10)}`;
    for (const m of t.contacts) if (!(m >= 0 && m < cp.contacts.length)) err(w, `member contact ${m} does not exist`);
  });
  cp.trunksys.forEach((t, i) => {
    const w = `trunk ${i + 1} ${t.name.slice(0, 10)}`;
    if (!(t.type in TRUNK_TYPES)) err(w, `type ${pyr(t.type)} (P25 / DMR_T3)`);
    if (!t.control_channels.length) err(w, "no control channel");
    for (const f of t.control_channels) if (!inBand(f)) err(w, `control channel ${mhz5(f)} MHz out of band`);
    if (t.tglist !== null && !(t.tglist >= 0 && t.tglist < cp.tglists.length)) err(w, `TG list ${t.tglist} does not exist`);
    if (t.type === "P25" && !(t.wacn >= 0 && t.wacn <= 0xfffff && t.sysid >= 0 && t.sysid <= 0xfff && t.nac_cc >= 0 && t.nac_cc <= 0xfff))
      err(w, "WACN / system ID / NAC out of range");
    if (t.type === "DMR_T3" && !(t.nac_cc >= 0 && t.nac_cc <= 15)) err(w, "colour code out of range");
    if ((t.type === "NXDN_C" || t.type === "NXDN_D") && !(t.nac_cc >= 0 && t.nac_cc <= 63)) err(w, "RAN out of range (0..63)");
    if (!((t.rfss ?? 0) >= 0 && (t.rfss ?? 0) <= 255) || !((t.site ?? 0) >= 0 && (t.site ?? 0) <= 255)) err(w, "RFSS / site 0..255");
    const bp = t.bandplan || [];
    if (new Set(bp.map((b) => b.iden)).size !== bp.length) err(w, "band plan identifiers repeat");
    for (const b of bp) {
      if (!(b.iden >= 0 && b.iden <= 15)) err(w, `band plan identifier ${b.iden} (0..15)`);
      if (!inBand(b.base_hz) && !(b.base_hz >= 762000000 && b.base_hz <= 970000000))
        warn(w, `band plan ${b.iden} base ${mhz5(b.base_hz)} MHz outside the radio's bands`);
      if (!(b.spacing_hz > 0 && b.spacing_hz <= 125000) || !(b.bw_hz > 0 && b.bw_hz <= 25000)) err(w, `band plan ${b.iden} spacing / bandwidth out of range`);
      if ((b.tdma && ![2, 4].includes(b.slots)) || (!b.tdma && b.slots !== 1)) err(w, `band plan ${b.iden}: TDMA needs 2 (or 4) slots, FDMA 1`);
    }
  });
  (cp.keys || []).forEach((k, i) => {
    const w = `key ${i + 1} ${k.name.slice(0, 10)}`;
    if (!(k.kind in KEY_KINDS)) { err(w, `kind ${pyr(k.kind)}`); return; }
    const h = (k.hex || "").replace(/\s/g, "");
    if (h.length % 2 || !/^[0-9a-fA-F]*$/.test(h)) { err(w, "key is not hex"); return; }
    const n = KEY_KINDS[k.kind];
    if (h.length / 2 !== n) err(w, `${k.kind} key must be ${n} bytes (${2 * n} hex digits), has ${h.length / 2}`);
    if (!(k.key_id >= 0 && k.key_id <= 0xffff) || !(k.algid >= 0 && k.algid <= 0xff)) err(w, "key ID 0..65535, ALGID 0..255");
  });
  (cp.dstar_rpts || []).forEach((r, i) => {
    const w = `D-STAR rpt ${i + 1} ${r.name.slice(0, 10)}`;
    for (const nm of ["rpt1", "rpt2"]) if (!/^[A-Z0-9/ ]{0,8}$/.test(r[nm] || "")) err(w, `${nm.toUpperCase()} ${pyr(r[nm])}: up to 8 of A-Z 0-9 / space`);
    for (const f of [r.rx_hz, r.tx_hz]) if (f && !inBand(f)) err(w, `frequency ${mhz5(f)} MHz out of band`);
  });
  const g = Object.assign(digiDefaults(), cp.digi || {});
  if (!YSF_MODES.includes(g.ysf_mode)) err("digital", `YSF default mode ${pyr(g.ysf_mode)}`);
  if (!(g.ysf_wiresx_room >= 0 && g.ysf_wiresx_room <= 99999)) err("digital", "Wires-X room 0..99999");
  if (!(g.dstar_gps_interval_s >= 0 && g.dstar_gps_interval_s <= 3600)) err("digital", "D-PRS interval 0..3600 s");
  if (g.dmr_t3_register || g.p25_register || g.nxdn_register) warn("digital", "registration needs TX; the cfw is receive-only on trunked systems today");
  useModel(cp);
  if (STOCK_SCHEMA) {
    for (const t of Object.keys(STOCK_SCHEMA.tables)) {
      const tab = STOCK_SCHEMA.tables[t];
      if (tab.kind !== "record" || !(cp.stock || {})[t]) continue;
      const r = cp.stock[t][0];
      for (let i = 0; i < Math.min(tab.columns.length, r.length, tab.defaults.length); i++) {
        const dv0 = tab.defaults[i], v = r[i];
        if (/^-?\d+$/.test(dv0) && v !== "" && !/^-?\d+(\.\d+)?$/.test(v))
          err(`stock ${t}`, `${STOCK_SCHEMA.labels[tab.columns[i]] || tab.columns[i]} = ${pyr(v)} must be a number`);
      }
    }
  }
  try {
    const n = encode(cp).length;
    if (n > regionOf(cp) * 0.9) warn("size", `${n} of ${regionOf(cp)} bytes used`);
  } catch (e) { err("size", e.message); }
  return out;
}

export const errors = (iss) => iss.filter((i) => i.level === "error");
export const issueText = (i) => `${i.level.padEnd(5)} ${i.where.padEnd(22)} ${i.msg}`;

// ------------------------------------------------------------------ diff (cps/diff.py)

function fmtv(k, v) {
  if (Number.isInteger(v) && k.endsWith("_hz") && v > 1000000) return mhz5(v);
  if (["nac", "wacn", "sysid", "p25_nac", "p25_wacn", "p25_sysid"].includes(k) && Number.isInteger(v)) return hx(v);
  if (v === null || v === undefined) return "None";
  if (typeof v === "boolean") return v ? "True" : "False";
  if (typeof v === "string") return `'${v}'`;
  if (Array.isArray(v)) return "[" + v.map((x) => fmtv("", x)).join(", ") + "]";
  return String(v);
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const SECTS = ["channels", "zones", "scanlists", "contacts", "tglists", "trunksys"];

export function diff(old, neu, limit = 400) {
  const a = old ? fromDict(old) : { settings: {}, channels: [], zones: [], scanlists: [], contacts: [], tglists: [], trunksys: [] };
  const b = fromDict(neu);
  const out = [];
  for (const k of Object.keys(b.settings)) if (!same(a.settings[k], b.settings[k])) out.push(`settings.${k}: ${fmtv(k, a.settings[k])} -> ${fmtv(k, b.settings[k])}`);
  for (const sec of SECTS) {
    const la = a[sec] || [], lb = b[sec];
    for (let i = 0; i < Math.max(la.length, lb.length); i++) {
      const x = la[i], y = lb[i];
      if (same(x, y)) continue;
      const label = `${sec === "trunksys" ? "trunksys" : sec.slice(0, -1)} ${i + 1}`;
      if (x === undefined) out.push(`+ ${label} ${fmtv("", y.name || "")}`);
      else if (y === undefined) out.push(`- ${label} ${fmtv("", x.name || "")}`);
      else {
        const ks = [...new Set([...Object.keys(x), ...Object.keys(y)])].sort();
        out.push(`~ ${label} ${fmtv("", y.name || "")}: ` + ks.filter((k) => !same(x[k], y[k])).map((k) => `${k} ${fmtv(k, x[k])}->${fmtv(k, y[k])}`).join(", "));
      }
    }
  }
  if (out.length > limit) { const n = out.length; out.length = limit; out.push(`... ${n - limit} more changes`); }
  return out;
}

export function diffSummary(old, neu) {
  const l = diff(old, neu, 1e9);
  const adds = l.filter((x) => x.startsWith("+")).length, dels = l.filter((x) => x.startsWith("-")).length;
  return `${adds} added, ${dels} removed, ${l.length - adds - dels} changed`;
}
