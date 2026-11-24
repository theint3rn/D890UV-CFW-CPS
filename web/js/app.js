// cfw Web CPS: UI. Codeplug core in codeplug.js (byte-identical with the Python CPS), importers.js, link.js.
import * as C from "./codeplug.js";
import { importRdt, importCsv, exportCsv } from "./importers.js";
import { WebSerialPort, WebSocketPort, FakeRadio, readRadio, writeRadio } from "./link.js";
import * as ST from "./stock.js";
import { zip } from "./zip.js";
import { reportHtml } from "./report.js";

import * as RDT from "./rdt.js";
import * as SU from "./support.js";

const getJson = async (u, dflt) => { const r = await fetch(u); return r.ok ? r.json() : dflt; };
ST.setDialogs(await getJson("schema/rdt_dialogs.json", { tables: {} }));     // dialogs kept only in the .rdt
ST.setSchema(await (await fetch("schema/stock_d168uv.json")).json());
ST.setSchema(await (await fetch("schema/stock_d890uv.json")).json());              // selected by default
SU.setData(await getJson("schema/cfw_support.json", { sections: {}, keys: {} }));   // what the cfw firmware uses, per model
// .rdt templates (the user's stock CPS new files) are not shipped: "Load .rdt template" (kept in this browser)
const savedTemplate = (m) => { try { const v = localStorage.getItem("cfwcps.rdtTemplate." + m); return v ? Uint8Array.from(atob(v), (c) => c.charCodeAt(0)) : null; } catch { return null; } };
RDT.setDefaults(savedTemplate("D890UV"), await (await fetch("schema/rdt_map.json")).json());
RDT.setDefaults(savedTemplate("D168UV"), await getJson("schema/rdt_map_d168.json", {}), "D168UV");

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "on") for (const [ev, f] of Object.entries(v)) e.addEventListener(ev, f);
    else if (k === "dataset") Object.assign(e.dataset, v);
    else if (k in e && k !== "list") e[k] = v; else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) e.append(k);
  return e;
};
const MODE_LABEL = { FM: "FM", DMR: "DMR", P25: "P25 Ph1", P25P2: "P25 Ph2", NXDN: "NXDN", DSTAR: "D-STAR", YSF: "YSF" };
const mhz = (hz) => (hz ? (hz / 1e6).toFixed(5) : "0");
const parseMhz = (s) => { s = String(s).trim(); if (!s || s === "0") return 0; const v = Number(s); if (Number.isNaN(v)) throw new Error(`'${s}' is not a frequency`); return Math.round(v * 1e6); };
const int = (s, base = 10, what = "number") => {
  s = String(s).trim();
  const v = base === 16 ? (/^(0x)?[0-9a-f]+$/i.test(s) ? parseInt(s, 16) : NaN) : (/^-?\d+$/.test(s) ? parseInt(s, 10) : NaN);
  if (Number.isNaN(v)) throw new Error(`${what}: '${s}' is not a ${base === 16 ? "hex " : ""}number`);
  return v;
};
const optRef = (s) => (String(s).trim() === "" ? null : int(s, 10, "reference") - 1);
const showRef = (v) => (v === null || v === undefined ? "" : String(v + 1));
const hex = (v) => v.toString(16).toUpperCase();

// Default radio: ?model=..., else the site path (the D168UV-CFW-CPS GitHub Pages site opens as a D168UV), else D890UV.
const defaultModel = () => C.modelFromUrl(location.search, location.pathname);
const st = { cp: C.newCodeplug(defaultModel()), fname: "untitled", dirty: false, sel: null, demo: null, busy: false };
window.cps = { st, C, ST };       // for tests / the console

function log(s, cls) {
  const l = $("#log");
  const line = el("span", { className: cls || "" }, s + "\n");
  l.append(line);
  $("#status").textContent = s.slice(0, 100);
}
function setDirty(d = true) { st.dirty = d; $("#fname").textContent = st.fname + (d ? " *" : ""); }
function confirmDiscard() { return !st.dirty || confirm("Discard unsaved changes?"); }
function download(name, data, type) {
  const a = el("a", { href: URL.createObjectURL(new Blob([data], { type })), download: name });
  document.body.append(a); a.click(); a.remove();
}

// ------------------------------------------------------------ navigation (stock CPS tree + cfw sections)
const PAGES = ["channels", "zones", "scanlists", "contacts", "tglists", "trunksys", "settings", "keys", "dstar", "digi", "stock", "info", "log"];
const CFW_NODE = { Channel: "channels", DMRZone: "zones", ScanList: "scanlists", DMRTalkGroups: "contacts",
  DMRReceiveGroupCallList: "tglists", "@masterid": "settings" };
let curNav = null;
function showTab(id, arg) {
  for (const t of PAGES) $(`#t-${t}`).classList.toggle("on", t === id);
  st.page = id; st.pageArg = arg;
  if (RENDER[id]) RENDER[id](arg);
}
function navButton(label, page, arg, stock) {
  const b = el("button", { className: stock ? "stock" : "", dataset: { page, arg: arg || "" }, title: stock ? "stock CPS data, stored, not used by cfw yet" : "",
    on: { click: () => { if (curNav) curNav.classList.remove("on"); curNav = b; b.classList.add("on"); showTab(page, arg); } } }, label);
  return b;
}
let navModel = null;
function buildNav() {
  const nav = $("#nav");
  nav.replaceChildren();
  navModel = C.modelOf(st.cp);
  ST.use(navModel);
  ST.SCHEMA.tree.forEach(([sec, nodes], si) => {
    const d = el("details", { open: si === 0 }, el("summary", {}, sec));
    for (const [label, target] of nodes) {
      const state = SU.nodeState(navModel, target, ST.TABLES, ST.PAGES);     // schema/cfw_support.json
      if (state === "n/a") continue;
      const page = CFW_NODE[target] || (target.startsWith("@") && !ST.NODE_TABLE[target] ? "info" : "stock");
      d.append(navButton(label, page, page === "stock" || page === "info" ? target : "", state === "stored" && !CFW_NODE[target]));
    }
    if (sec === "DMR" || sec === "Digital") d.append(navButton("Tier III Systems (cfw)", "trunksys"));
    if (sec === "NXDN") d.append(navButton("Type-C / Type-D Systems (cfw)", "trunksys"));
    nav.append(d);
  });
  const cf = el("details", { open: true }, el("summary", {}, "cfw Digital Modes"));
  for (const [label, page] of [["Radio Settings (cfw)", "settings"], ["Trunk Systems: P25 / DMR T3 / NXDN", "trunksys"],
    ["Encryption Keys", "keys"], ["D-STAR Repeaters / Routing", "dstar"], ["D-STAR / YSF / Registration", "digi"]]) cf.append(navButton(label, page));
  nav.append(cf, navButton("Log", "log"));
  curNav = nav.querySelector('button[data-page="channels"]'); curNav.classList.add("on");
}
buildNav();

// ------------------------------------------------------------ channels
function detail(c) {
  switch (c.mode) {
    case "FM": return (c.wide ? "25k" : "12.5k") + (c.tx_tone ? " T" + c.tx_tone : "") + (c.rx_tone ? " R" + c.rx_tone : "");
    case "DMR": return `CC${c.cc} TS${c.slot} TG${c.tg}${c.trunk ? " T3" : ""}`;
    case "P25": case "P25P2": return `NAC ${hex(c.nac).padStart(3, "0")} TG${c.tg}${c.mode === "P25P2" ? " S" + c.slot : ""}${c.trunk ? " TRUNK" : ""}`;
    case "NXDN": return `RAN${c.ran} G${c.tg}`;
    case "DSTAR": return `UR ${c.ur}`;
    case "YSF": return `DG-ID ${c.dgid}`;
  }
  return "";
}
function chRow(c, i) {
  return el("tr", { dataset: { i }, className: i === st.sel ? "sel" : "" },
    el("td", {}, String(i + 1)), el("td", {}, c.name), el("td", {}, mhz(c.rx_hz)), el("td", {}, mhz(c.tx_hz)),
    el("td", {}, MODE_LABEL[c.mode]), el("td", {}, detail(c)), el("td", {}, c.power));
}
function renderChannels() {
  const f = $("#chFilter").value.trim().toLowerCase();
  const tb = $("#chTable tbody");
  const rows = [];
  st.cp.channels.forEach((c, i) => {
    if (f && !(`${c.name} ${mhz(c.rx_hz)} ${c.mode}`.toLowerCase().includes(f))) return;
    rows.push(chRow(c, i));
  });
  tb.replaceChildren(...rows);
  const selRow = tb.querySelector("tr.sel");
  if (selRow) selRow.scrollIntoView({ block: "nearest" });
  $("#chCount").textContent = `${st.cp.channels.length} channels`;
  renderEditor();
}
$("#chTable tbody").addEventListener("click", (e) => {
  const tr = e.target.closest("tr"); if (!tr) return;
  st.sel = Number(tr.dataset.i);
  for (const r of $("#chTable tbody").children) r.classList.toggle("sel", r === tr);
  renderEditor();
});
$("#chFilter").addEventListener("input", renderChannels);

const voc = (m) => ["vocoder", "Vocoder", "sel", C.MODE_VOCODERS[m]];
const FIELDS = {
  FM: [["wide", "25 kHz", "check"], ["rx_tone", "RX tone (88.5 / D023N)", "tone"], ["tx_tone", "TX tone", "tone"]],
  DMR: [["cc", "Colour code", "int"], ["slot", "Time slot", "sel", ["1", "2"]], ["tg", "Talkgroup", "int"], ["contact", "Contact #", "ref"],
    ["tglist", "TG list #", "ref"], ["trunksys", "Tier III system #", "ref"], voc("DMR"), ["key", "Encryption key #", "ref"],
    ["tdma_direct", "TDMA direct (dual-capacity simplex)", "check"]],
  P25: [["nac", "NAC (hex)", "hex"], ["tg", "Talkgroup", "int"], ["wacn", "WACN (hex)", "hex"], ["sysid", "System ID (hex)", "hex"],
    ["contact", "Contact #", "ref"], ["tglist", "TG list #", "ref"], ["trunksys", "Trunk system #", "ref"], voc("P25"), ["key", "Encryption key #", "ref"]],
  NXDN: [["ran", "RAN", "int"], ["tg", "Group", "int"], ["contact", "Contact #", "ref"], ["tglist", "TG list #", "ref"],
    ["trunksys", "Type-C/D system #", "ref"], ["nxdn_rate", "Rate", "sel", ["4800", "9600"]], voc("NXDN"), ["key", "Encryption key #", "ref"]],
  DSTAR: [["ur", "UR", "call"], ["rpt1", "RPT1", "call"], ["rpt2", "RPT2", "call"], ["dstar_rpt", "Repeater list #", "ref"], voc("DSTAR")],
  YSF: [["dgid", "RX DG-ID (0 = all)", "int"], ["dgid_tx", "TX DG-ID (empty = RX)", "optint"], ["ysf_mode", "Mode", "sel", C.YSF_MODES],
    ["wiresx", "Wires-X", "check"], voc("YSF")],
};
FIELDS.P25P2 = [FIELDS.P25[0], ["slot", "Time slot", "sel", ["1", "2"]], ...FIELDS.P25.slice(1, 7), voc("P25P2"), FIELDS.P25[8]];

function input(name, kind, val, choices) {
  if (kind === "check") return el("input", { type: "checkbox", name, checked: !!val });
  if (kind === "sel") return el("select", { name }, choices.map((c) => el("option", { value: c, selected: String(val) === c }, c)));
  const v = kind === "hex" ? hex(val) : kind === "ref" ? showRef(val) : kind === "mhz" ? mhz(val) : kind === "optint" ? (val ?? "") : val ?? "";
  return el("input", { type: "text", name, value: String(v) });
}
function readInput(form, name, kind) {
  const e = form.elements[name];
  if (kind === "check") return e.checked;
  const s = e.value;
  switch (kind) {
    case "int": return int(s, 10, name);
    case "hex": return int(s || "0", 16, name);
    case "ref": return optRef(s);
    case "optint": return s.trim() === "" ? null : int(s, 10, name);
    case "mhz": return parseMhz(s);
    case "tone": return s.trim() || null;
    case "call": return s.toUpperCase().slice(0, 8);
    default: return s;
  }
}
function renderEditor(modeOverride) {
  const form = $("#chForm");
  const i = st.sel;
  if (i === null || i >= st.cp.channels.length) { form.replaceChildren(el("p", { className: "muted" }, "Select a channel.")); return; }
  const c = st.cp.channels[i];
  const mode = modeOverride || c.mode;
  const row = (label, inp) => el("label", { className: "row" }, el("span", {}, label), inp);
  const modeSel = input("mode", "sel", mode, C.MODES);
  modeSel.addEventListener("change", () => { readCommon(); renderEditor(modeSel.value); });
  const md = Object.assign(C.normalizeChannel(Object.assign({}, c, { mode })), {});
  form.replaceChildren(
    el("fieldset", {}, el("legend", {}, `Channel ${i + 1}`),
      row("Name", input("name", "text", st.draft?.name ?? c.name)), row("Mode", modeSel),
      row("RX MHz", input("rx_hz", "mhz", st.draft?.rx_hz ?? c.rx_hz)), row("TX MHz (0 = RX only)", input("tx_hz", "mhz", st.draft?.tx_hz ?? c.tx_hz)),
      row("Power", input("power", "sel", c.power, C.POWERS)), row("Scan list #", input("scanlist", "ref", c.scanlist)),
      row("Scan skip", input("scan_skip", "check", c.scan_skip)), row("Trunk CC / Tier III", input("trunk", "check", c.trunk)),
      row("Talkaround (simplex)", input("talkaround", "check", c.talkaround))),
    el("fieldset", {}, el("legend", {}, `${MODE_LABEL[mode]} settings`),
      FIELDS[mode].length ? FIELDS[mode].map(([k, label, kind, ch]) => row(label, input(k, kind, md[k], ch))) : el("p", { className: "muted" }, "Analog FM")),
    el("div", { className: "right" }, el("button", { type: "button", id: "chStock", on: { click: () => editChannelStock(i) } }, "Stock settings..."), " ",
      el("button", { type: "submit", className: "primary", id: "chApply" }, "Apply")),
    el("div", { className: "msg", id: "chMsg" }));
  st.draft = null;
}
function readCommon() {
  const f = $("#chForm");
  try { st.draft = { name: f.elements.name.value, rx_hz: parseMhz(f.elements.rx_hz.value), tx_hz: parseMhz(f.elements.tx_hz.value) }; } catch (e) { st.draft = null; }
}
$("#chForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = $("#chForm"), i = st.sel;
  const mode = f.elements.mode.value;
  try {
    const c = { name: f.elements.name.value.slice(0, 16), mode, rx_hz: parseMhz(f.elements.rx_hz.value), tx_hz: parseMhz(f.elements.tx_hz.value),
      power: f.elements.power.value, scanlist: optRef(f.elements.scanlist.value), scan_skip: f.elements.scan_skip.checked, trunk: f.elements.trunk.checked,
      talkaround: f.elements.talkaround.checked };
    for (const [k, , kind] of FIELDS[mode]) {
      if (kind === "sel") c[k] = ["slot", "nxdn_rate"].includes(k) ? Number(f.elements[k].value) : f.elements[k].value;
      else c[k] = readInput(f, k, kind);
    }
    if (st.cp.channels[i].stock) c.stock = Object.assign({}, st.cp.channels[i].stock);
    ST.clearMappedOverrides(c, "Channel");
    const ch = C.normalizeChannel(c);
    ST.renameChannelRefs(st.cp, ST.channelKey(st.cp.channels[i]), ST.channelKey(ch));
    const tmp = Object.assign({}, st.cp, { channels: [ch], zones: [], stock: undefined, settings: Object.assign({}, st.cp.settings, { start_channel: null }) });
    const errs = C.errors(C.validate(tmp)).filter((x) => x.where.startsWith("ch ")).map((x) => x.msg);
    st.cp.channels[i] = ch;
    setDirty();
    renderChannels();
    $("#chMsg").textContent = errs.join("; ");
  } catch (err) { $("#chMsg").textContent = `invalid value: ${err.message}`; }
});

function shiftChannelRefs(f) {
  for (const l of st.cp.zones.concat(st.cp.scanlists)) l.channels = l.channels.map(f).filter((x) => x !== null);
  for (const s of st.cp.scanlists) { if (s.prio1 !== null) s.prio1 = f(s.prio1); if (s.prio2 !== null) s.prio2 = f(s.prio2); }
  if (st.cp.settings.start_channel !== null) st.cp.settings.start_channel = f(st.cp.settings.start_channel);
}
function insertChannel(i, c) {
  st.cp.channels.splice(i, 0, c);
  shiftChannelRefs((k) => (k >= i ? k + 1 : k));
  st.sel = i; setDirty(); renderChannels();
}
$("#chNew").onclick = () => insertChannel(st.sel === null ? st.cp.channels.length : st.sel + 1, C.newChannel({ name: `NEW ${st.cp.channels.length + 1}` }));
$("#chDup").onclick = () => { if (st.sel !== null) insertChannel(st.sel + 1, structuredClone(st.cp.channels[st.sel])); };
$("#chDel").onclick = () => {
  const i = st.sel; if (i === null || !confirm(`Delete channel ${i + 1} '${st.cp.channels[i].name}'?`)) return;
  st.cp.channels.splice(i, 1);
  shiftChannelRefs((k) => (k === i ? null : k > i ? k - 1 : k));
  st.sel = null; setDirty(); renderChannels();
};
function moveCh(d) {
  const i = st.sel, ch = st.cp.channels;
  if (i === null || i + d < 0 || i + d >= ch.length) return;
  [ch[i], ch[i + d]] = [ch[i + d], ch[i]];
  shiftChannelRefs((k) => (k === i ? i + d : k === i + d ? i : k));
  st.sel = i + d; setDirty(); renderChannels();
}
$("#chUp").onclick = () => moveCh(-1);
$("#chDown").onclick = () => moveCh(1);

// ------------------------------------------------------------ list editors (zones, scan lists, TG lists)
function fixRefsAfterDelete(attr, i) {
  const g = (v) => (v === null || v === i ? null : v > i ? v - 1 : v);
  const key = { scanlists: "scanlist", tglists: "tglist", contacts: "contact", trunksys: "trunksys", keys: "key", dstar_rpts: "dstar_rpt" }[attr];
  if (key) st.cp.channels.forEach((c) => { if (key in c) c[key] = g(c[key]); });
  if (attr === "contacts") st.cp.tglists.forEach((t) => { t.contacts = t.contacts.map(g).filter((x) => x !== null); });
  if (attr === "tglists") st.cp.trunksys.forEach((t) => { t.tglist = g(t.tglist); });
}
function listEditor(attr, memberKey, names, blank) {
  const root = $(`#t-${attr}`);
  let cur = null;
  const lists = el("select", { size: 20 }), mem = el("select", { multiple: true }), avail = el("select", { multiple: true });
  const name = el("input", { type: "text", placeholder: "name" }), filt = el("input", { type: "text", placeholder: "filter" });
  const items = () => st.cp[attr];
  function fill() {
    lists.replaceChildren(...items().map((z, i) => el("option", { value: i, selected: i === cur }, `${i + 1} ${z.name}`)));
    const nm = names();
    const f = filt.value.toLowerCase();
    avail.replaceChildren(...nm.map((n, i) => [n, i]).filter(([n]) => n.toLowerCase().includes(f)).slice(0, 5000)
      .map(([n, i]) => el("option", { value: i }, `${i + 1} ${n}`)));
    if (cur !== null && items()[cur]) {
      name.value = items()[cur].name;
      mem.replaceChildren(...items()[cur][memberKey].map((m, k) => el("option", { value: k }, `${m + 1} ${nm[m] ?? "?"}`)));
    } else mem.replaceChildren();
  }
  lists.onchange = () => { cur = Number(lists.value); fill(); };
  filt.oninput = fill;
  const act = (f) => () => { f(); setDirty(); fill(); };
  const sel = (s) => [...s.selectedOptions].map((o) => Number(o.value));
  root.replaceChildren(el("div", { className: "lists" },
    el("div", { className: "c1" }, lists, name, el("div", { className: "tools" },
      el("button", { on: { click: act(() => { items().push(Object.assign(blank(), { name: name.value.slice(0, 16) || "NEW" })); cur = items().length - 1; }) } }, "Add"),
      el("button", { on: { click: act(() => { if (cur !== null) items()[cur].name = name.value.slice(0, 16); }) } }, "Rename"),
      el("button", { on: { click: act(() => { if (cur !== null && confirm(`Delete '${items()[cur].name}'?`)) { items().splice(cur, 1); fixRefsAfterDelete(attr, cur); cur = null; } }) } }, "Delete"))),
    el("div", { className: "c2" }, el("span", { className: "muted" }, "Members (order = priority)"), mem, el("div", { className: "tools" },
      el("button", { on: { click: act(() => { const m = items()[cur]?.[memberKey]; const s = sel(mem); if (m && s.length === 1 && s[0] > 0) [m[s[0] - 1], m[s[0]]] = [m[s[0]], m[s[0] - 1]]; }) } }, "Up"),
      el("button", { on: { click: act(() => { const m = items()[cur]?.[memberKey]; const s = sel(mem); if (m && s.length === 1 && s[0] < m.length - 1) [m[s[0] + 1], m[s[0]]] = [m[s[0]], m[s[0] + 1]]; }) } }, "Down"),
      el("button", { on: { click: act(() => { const m = items()[cur]?.[memberKey]; if (m) for (const k of sel(mem).reverse()) m.splice(k, 1); }) } }, "Remove"))),
    el("div", { className: "c3" }, el("span", { className: "muted" }, "Available (double-click or Add)"), filt, avail,
      el("button", { on: { click: act(() => { if (cur !== null) items()[cur][memberKey].push(...sel(avail)); }) } }, "<< Add"))));
  avail.ondblclick = act(() => { if (cur !== null) items()[cur][memberKey].push(...sel(avail)); });
  return () => { if (cur !== null && cur >= items().length) cur = null; fill(); };
}

// ------------------------------------------------------------ table + form editors (contacts, trunk systems)
function tableEditor(page, cols, spec, toForm, fromForm, blank, attr = page) {
  const root = $(`#t-${page}`);
  let cur = null;
  const tb = el("tbody"), form = el("form", { className: "editor", autocomplete: "off" }), msg = el("div", { className: "msg" });
  function fill() {
    tb.replaceChildren(...st.cp[attr].map((x, i) => el("tr", { dataset: { i }, className: i === cur ? "sel" : "" },
      el("td", {}, String(i + 1)), ...Object.values(toForm(x)).slice(0, cols.length - 1).map((v) => el("td", {}, String(v))))));
    form.replaceChildren(...spec.map(([k, label, kind, ch]) => el("label", { className: "row" }, el("span", {}, label),
      kind === "sel" ? el("select", { name: k }, ch.map((c) => el("option", { value: c }, c)))
        : kind === "check" ? el("input", { type: "checkbox", name: k }) : el("input", { type: "text", name: k }))),
      el("div", { className: "right" }, el("button", { type: "submit", className: "primary" }, "Apply")), msg);
    if (cur !== null && st.cp[attr][cur]) for (const [k, v] of Object.entries(toForm(st.cp[attr][cur]))) {
      const e = form.elements[k];
      if (e) { if (e.type === "checkbox") e.checked = !!v; else e.value = v; }
    }
  }
  tb.onclick = (e) => { const tr = e.target.closest("tr"); if (tr) { cur = Number(tr.dataset.i); fill(); } };
  form.onsubmit = (e) => {
    e.preventDefault();
    if (cur === null) return;
    try { st.cp[attr][cur] = fromForm(form.elements); msg.textContent = ""; setDirty(); fill(); } catch (err) { msg.textContent = `invalid: ${err.message}`; }
  };
  root.replaceChildren(el("div", { className: "split" }, el("div", { className: "left" },
    el("div", { className: "tools" },
      el("button", { on: { click: () => { st.cp[attr].push(blank()); cur = st.cp[attr].length - 1; setDirty(); fill(); } } }, "Add"),
      el("button", { on: { click: () => { if (cur !== null && confirm(`Delete entry ${cur + 1}?`)) { st.cp[attr].splice(cur, 1); fixRefsAfterDelete(attr, cur); cur = null; setDirty(); fill(); } } } }, "Delete")),
    el("div", { className: "tablewrap" }, el("table", {}, el("thead", {}, el("tr", {}, cols.map((c) => el("th", {}, c)))), tb))), form));
  return () => { if (cur !== null && cur >= st.cp[attr].length) cur = null; fill(); };
}

const contactsRender = tableEditor("contacts", ["#", "Name", "ID", "Kind", "Mode"],
  [["name", "Name", "text"], ["id", "ID", "text"], ["kind", "Kind", "sel", C.CONTACT_KINDS], ["mode", "Mode", "sel", Object.keys(C.CONTACT_MODES)]],
  (x) => ({ name: x.name, id: x.id, kind: x.kind, mode: x.mode }),
  (f) => ({ name: f.name.value.slice(0, 16), id: int(f.id.value, 10, "id"), kind: f.kind.value, mode: f.mode.value }),
  () => ({ name: "NEW", id: 0, kind: "group", mode: "any" }));

const trunkRender = tableEditor("trunksys", ["#", "Name", "Type", "NAC/CC", "WACN", "SysID", "Control channels MHz"],
  [["name", "Name", "text"], ["type", "Type", "sel", Object.keys(C.TRUNK_TYPES)], ["nac_cc", "NAC / CC (hex)", "text"],
    ["wacn", "WACN (hex)", "text"], ["sysid", "System ID (hex)", "text"], ["ccs", "Control channels (MHz)", "text"],
    ["tglist", "TG priority list #", "text"], ["step", "T3 channel step Hz", "text"], ["base", "T3 LPCN1 MHz (0 = CC)", "text"],
    ["rfss", "RFSS / area", "text"], ["site", "Site", "text"], ["registration", "Register (needs TX)", "check"], ["phase2", "P25 Phase 2 TDMA", "check"],
    ["bandplan", "Band plan iden:MHz:spacing:offset:bw:slots;...", "text"]],
  (t) => ({ name: t.name, type: t.type, nac_cc: hex(t.nac_cc), wacn: hex(t.wacn), sysid: hex(t.sysid),
    ccs: t.control_channels.map(mhz).join(" "), tglist: showRef(t.tglist), step: t.chan_step_hz, base: mhz(t.base_hz),
    rfss: t.rfss ?? 0, site: t.site ?? 0, registration: !!t.registration, phase2: !!t.phase2,
    bandplan: (t.bandplan || []).map((b) => `${b.iden}:${mhz(b.base_hz)}:${b.spacing_hz}:${b.tx_offset_hz}:${b.bw_hz}:${b.slots}`).join("; ") }),
  (f) => ({ name: f.name.value.slice(0, 16), type: f.type.value, nac_cc: int(f.nac_cc.value || "0", 16, "NAC"), wacn: int(f.wacn.value || "0", 16, "WACN"),
    sysid: int(f.sysid.value || "0", 16, "system ID"), tglist: optRef(f.tglist.value),
    control_channels: f.ccs.value.replace(/,/g, " ").split(/\s+/).filter(Boolean).map(parseMhz),
    chan_step_hz: int(f.step.value || "12500", 10, "step"), base_hz: parseMhz(f.base.value), flags: 0,
    rfss: int(f.rfss.value || "0", 10, "RFSS"), site: int(f.site.value || "0", 10, "site"), registration: f.registration.checked,
    phase2: f.phase2.checked, bandplan: parseBandplan(f.bandplan.value) }),
  () => ({ name: "NEW", type: "P25", nac_cc: 0, wacn: 0, sysid: 0, tglist: null, control_channels: [], chan_step_hz: 12500, base_hz: 0, flags: 0,
    rfss: 0, site: 0, registration: false, phase2: false, bandplan: [] }));

function parseBandplan(text) {
  return (text || "").replace(/,/g, ";").split(";").map((x) => x.trim()).filter(Boolean).map((part) => {
    const f = part.split(":");
    if (f.length !== 6) throw new Error(`band plan entry '${part}' needs iden:MHz:spacing:offset:bw:slots`);
    const slots = int(f[5], 10, "slots");
    return { iden: int(f[0], 10, "iden"), base_hz: parseMhz(f[1]), spacing_hz: int(f[2], 10, "spacing"), tx_offset_hz: int(f[3], 10, "offset"),
      bw_hz: int(f[4], 10, "bw"), tdma: slots > 1, slots };
  });
}

const keysRender = tableEditor("keys", ["#", "Name", "Kind", "Key ID", "ALGID"],
  [["name", "Name", "text"], ["kind", "Kind", "sel", Object.keys(C.KEY_KINDS)], ["key_id", "Key ID", "text"], ["algid", "ALGID (hex)", "text"],
    ["hex", "Key (hex, user-entered)", "text"]],
  (k) => ({ name: k.name, kind: k.kind, key_id: k.key_id, algid: hex(k.algid).padStart(2, "0"), hex: k.hex }),
  (f) => ({ name: f.name.value.slice(0, 16), kind: f.kind.value, key_id: int(f.key_id.value || "0", 10, "key ID"),
    algid: int(f.algid.value || "0", 16, "ALGID"), hex: f.hex.value.replace(/\s/g, "").toUpperCase() }),
  () => ({ name: "NEW", kind: "P25_AES256", key_id: 1, algid: 0x84, hex: "" }));

const dstarRender = tableEditor("dstar", ["#", "Name", "RPT1", "RPT2", "RX MHz", "TX MHz"],
  [["name", "Name", "text"], ["rpt1", "RPT1 (repeater + module)", "text"], ["rpt2", "RPT2 (gateway)", "text"], ["rx", "RX MHz", "text"],
    ["tx", "TX MHz", "text"], ["gps", "GPS / D-PRS", "check"]],
  (r) => ({ name: r.name, rpt1: r.rpt1, rpt2: r.rpt2, rx: mhz(r.rx_hz), tx: mhz(r.tx_hz), gps: r.gps }),
  (f) => ({ name: f.name.value.slice(0, 16), rpt1: f.rpt1.value.toUpperCase().slice(0, 8), rpt2: f.rpt2.value.toUpperCase().slice(0, 8),
    rx_hz: parseMhz(f.rx.value), tx_hz: parseMhz(f.tx.value), gps: f.gps.checked }),
  () => ({ name: "NEW", rpt1: "", rpt2: "", rx_hz: 0, tx_hz: 0, gps: false }), "dstar_rpts");

const DIGI = [["dstar_dprs", "D-STAR: send GPS as D-PRS", "check"], ["dstar_gps_interval_s", "D-PRS interval s (0 = each TX)", "int"],
  ["dstar_auto_reply", "D-STAR auto reply", "check"], ["dprs_symbol", "D-PRS symbol"], ["dprs_comment", "D-PRS comment"],
  ["ysf_mode", "YSF default mode", "sel", C.YSF_MODES], ["ysf_wiresx_room", "Wires-X room", "int"], ["ysf_wiresx_auto", "Wires-X auto connect", "check"],
  ["dmr_t3_register", "DMR Tier III registration (needs TX)", "check"], ["p25_register", "P25 registration (needs TX)", "check"],
  ["nxdn_register", "NXDN registration (needs TX)", "check"]];
function renderDigi() {
  const g = Object.assign(C.digiDefaults(), st.cp.digi || {}), f = $("#digiForm");
  f.replaceChildren(el("p", { className: "muted" }, "Digital-mode settings (cfw). D-STAR MY / UR / RPT, slow-data message, P25 / NXDN unit IDs: Radio Settings."),
    ...DIGI.map(([k, label, kind, ch]) => el("label", { className: "row" }, el("span", {}, label), input(k, kind || "text", g[k], ch))),
    el("div", {}, el("button", { type: "submit", className: "primary" }, "Apply"), el("span", { className: "msg", id: "digiMsg" })));
}
$("#digiForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = $("#digiForm"), g = Object.assign(C.digiDefaults(), st.cp.digi || {});
  try {
    for (const [k, , kind] of DIGI) g[k] = kind === "sel" ? f.elements[k].value : readInput(f, k, kind || "text");
    st.cp.digi = g; setDirty(); $("#digiMsg").textContent = "";
  } catch (err) { $("#digiMsg").textContent = ` invalid value: ${err.message}`; }
});

// ------------------------------------------------------------ stock CPS tables (verbatim; cfw use per model: schema/cfw_support.json)
const NOT_USED = SU.NOTE;
function renderStock(table) {
  const root = $("#t-stock");
  if (!table) return;
  if (ST.PAGES[table]) return renderStockRecord(ST.PAGES[table].table, root, ST.PAGES[table]);
  const node = table;
  table = ST.NODE_TABLE[table] || table;          // an .rdt-only dialog (schema/rdt_dialogs.json) behind an "@..." node
  const tab = ST.TABLES[table];
  if (tab.kind === "record") return renderStockRecord(table, root, null, node);
  const [, stored, star] = SU.pageMarks(C.modelOf(st.cp), node, tab.columns, table);
  const head = (c) => (ST.LABELS[c] || c) + (star.includes(c) ? " *" : "");
  const rows = () => { st.cp.stock = st.cp.stock || {}; return st.cp.stock[table] || (st.cp.stock[table] = ST.defaultRows(table)); };
  let cur = null;
  const tb = el("tbody"), form = el("form", { className: "grid3", autocomplete: "off" });
  const fill = () => {
    tb.replaceChildren(...rows().slice(0, 2000).map((r, i) => el("tr", { dataset: { i }, className: i === cur ? "sel" : "" }, ...r.map((v) => el("td", {}, v)))));
    form.replaceChildren(...tab.columns.map((c, i) => el("label", { className: "row" }, el("span", {}, head(c)),
      el("input", { type: "text", name: "c" + i, value: cur !== null ? (rows()[cur][i] ?? "") : "" }))),
      el("div", {}, el("button", { type: "submit", className: "primary" }, "Apply row")));
  };
  tb.onclick = (e) => { const tr = e.target.closest("tr"); if (tr) { cur = Number(tr.dataset.i); fill(); } };
  form.onsubmit = (e) => {
    e.preventDefault();
    if (cur === null) return;
    tab.columns.forEach((c, i) => { const r = rows()[cur]; while (r.length <= i) r.push(""); r[i] = form.elements["c" + i].value; });
    setDirty(); fill();
  };
  root.replaceChildren(el("p", { className: "note" }, stored ? `${(ST.DIALOGS[table] || {}).title || table}: ${star.length ? SU.STAR_NOTE : NOT_USED}` : (ST.DIALOGS[table] || {}).title || table),
    el("div", { className: "tools" },
      el("button", { on: { click: () => { const d = (tab.defaults.length ? tab.defaults : tab.columns.map(() => "")).slice();
        if (/^No\.?$/i.test(tab.columns[0])) d[0] = String(rows().length + 1); rows().push(d); cur = rows().length - 1; setDirty(); fill(); } } }, "Add row"),
      el("button", { on: { click: () => { if (cur !== null && confirm(`Delete row ${cur + 1}?`)) { rows().splice(cur, 1); cur = null; setDirty(); fill(); } } } }, "Delete row"),
      el("span", { className: "muted" }, `${rows().length} rows`)),
    el("div", { className: "tablewrap", style: "max-height:45vh" }, el("table", {}, el("thead", {}, el("tr", {}, tab.columns.map((c) => el("th", {}, head(c))))), tb)), form);
  fill();
}

function renderStockRecord(table, root, page, node0) {
  // page: a schema "pages" entry (e.g. D168 Bluetooth) = one group of the record's keys with its own note
  const tab = ST.TABLES[table];
  const node = page ? Object.keys(ST.PAGES).find((k) => ST.PAGES[k] === page) : node0 || table, model = C.modelOf(st.cp);
  const dlg = ST.DIALOGS[table];
  const allKeys = page ? page.keys : tab.columns;
  const [vis, anyStored, star] = SU.pageMarks(model, node, allKeys, table);     // n/a keys hidden, * when mixed
  const groups = (dlg && dlg.groups ? dlg.groups : page ? [[page.title, page.keys]] : table === "OptionalSetting" ? ST.SCHEMA.optional_tabs
    : Array.from({ length: Math.ceil(tab.columns.length / 40) }, (_, i) => [`${table} ${i + 1}`, tab.columns.slice(i * 40, i * 40 + 40)]))
    .map(([g, ks]) => [g, ks.filter((k) => vis.includes(k))]).filter(([, ks]) => ks.length);
  let gi = 0;
  const form = el("form", { className: "grid3", autocomplete: "off" }), sub = el("div", { className: "subtabs" });
  const field = (k, v) => {
    const c = ST.CHOICES[k];
    if (!c) return el("input", { type: "text", name: k, value: v });
    const t = ST.choiceText(k, v), opts = c.includes(t) ? c : c.concat([t]);   // a raw value outside the list is kept
    return el("select", { name: k }, ...opts.map((o) => el("option", { value: o, selected: o === t }, o)));
  };
  const fill = () => {
    const view = ST.stockSettingsView(st.cp, table);
    sub.replaceChildren(...(page ? [] : groups.map(([g], i) => el("button", { type: "button", className: i === gi ? "on" : "", on: { click: () => { gi = i; fill(); } } }, g))));
    form.replaceChildren(...groups[gi][1].map((k) => el("label", { className: "row" }, el("span", {}, (ST.LABELS[k] || k) + (star.includes(k) ? " *" : "")), field(k, view[k] ?? ""))),
      el("div", {}, el("button", { type: "submit", className: "primary" }, "Apply"), " ",
        el("button", { type: "button", on: { click: () => { st.cp.stock = st.cp.stock || {}; st.cp.stock[table] = ST.defaultRows(table); setDirty(); fill(); } } }, "Defaults")));
  };
  form.onsubmit = (e) => {
    e.preventDefault();
    for (const k of groups[gi][1]) ST.setStockValue(st.cp, table, k, ST.choiceValue(k, form.elements[k].value));
    setDirty();
  };
  const lists = groups[gi][1].some((k) => ST.CHOICES[k]);
  const use = !anyStored ? "" : star.length ? SU.STAR_NOTE : NOT_USED;
  const note = dlg ? `${dlg.title}${use ? ": " + use : ""} ${dlg.note || ""}`
    : page ? `${page.note} ${use}${lists ? " Lists show the radio's values." : " Values are the stock CSV values."}`
      : `${table}: ${use} Values are the stock CSV values.`;
  root.replaceChildren(el("p", { className: "note" }, note), sub, form);
  fill();
}

const INFO = { "@device": "Device Information (stock: model, bands, version). cfw: {model}, UHF 400-480 MHz, VHF 136-174 MHz; identify the radio with Read radio.",
  "@enccode": "Encryption Code (DMR basic privacy keys): kept verbatim inside stock .rdt files (no CSV in the stock CPS). cfw keys: cfw Digital Modes > Encryption Keys.",
  "@friends": "Friends List: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
  "@talkalias": "Talk Alias: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
  "@alarm": "Alarm Setting: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
  "@local": "Local Information: the stock CPS reads it live from the radio over the COM port; nothing of it is in the .rdt or the codeplug.",
  "@masterid": "Master ID: see Radio Settings (DMR / radio ID, callsign)." };
const renderInfo = (k) => { $("#infoText").textContent = (INFO[k] || k).replace("{model}", C.modelOf(st.cp))
  + (!CFW_NODE[k] && SU.section(k, C.modelOf(st.cp)) === "stored" ? " Not used by cfw yet." : ""); };

function editChannelStock(i) {
  const c = st.cp.channels[i], gen = ST.row("Channel", c, st.cp);
  const [cols, anyStored, star] = SU.channelMarks(C.modelOf(st.cp), ST.CH_COLS.filter((k) => !ST.TABLES.Channel.cfw_mapped.includes(k)));
  $("#stockDlgTitle").textContent = `Channel ${i + 1}: stock CPS settings` + (!anyStored ? "" : star.length ? ` (${SU.STAR_NOTE})` : " (stored, not used by cfw yet)");
  const f = $("#stockDlgForm");
  f.replaceChildren(...cols.map((k) => el("label", { className: "row" }, el("span", {}, k + (star.includes(k) ? " *" : "")),
    el("input", { type: "text", name: k, value: (c.stock || {})[k] ?? gen[k] ?? "" }))));
  const d = $("#stockDlg");
  $("#stockDlgCancel").onclick = (e) => { e.preventDefault(); d.close(); };
  $("#stockDlgOk").onclick = (e) => {
    e.preventDefault();
    const s0 = Object.assign({}, c.stock || {});
    for (const k of cols) { const v = f.elements[k].value; if (v === (gen[k] ?? "")) delete s0[k]; else s0[k] = v; }
    if (Object.keys(s0).length) c.stock = s0; else delete c.stock;
    setDirty(); d.close();
  };
  d.showModal();
}

const zonesRender = listEditor("zones", "channels", () => st.cp.channels.map((c) => c.name), () => ({ name: "", channels: [] }));
const scanRender = listEditor("scanlists", "channels", () => st.cp.channels.map((c) => c.name),
  () => ({ name: "", channels: [], prio1: null, prio2: null, dwell_100ms: 20, flags: 0 }));
const tglRender = listEditor("tglists", "contacts", () => st.cp.contacts.map((c) => `${c.name} (${c.id})`), () => ({ name: "", contacts: [] }));

// ------------------------------------------------------------ settings
const SET = [["callsign", "Callsign"], ["dmr_id", "DMR / radio ID", "int"], ["p25_unit_id", "P25 unit ID (0 = DMR ID)", "int"],
  ["nxdn_unit_id", "NXDN unit ID (0 = DMR ID)", "int"], ["radio_name", "Radio name"], ["step_hz", "VFO step Hz", "int"],
  ["vfo_mode", "VFO mode", "sel", C.MODES], ["start_channel", "Start channel # (empty = last)", "ref"], ["boot_vfo", "Boot in VFO", "check"],
  ["rx_invert", "RX polarity inverted", "check"], ["deemph_us", "De-emphasis comp us", "int"], ["test_tone_hz", "Test tone Hz (0 = off)", "int"],
  ["backlight_level", "Backlight 0..10", "int"], ["backlight_timeout_s", "Backlight timeout s", "int"], ["batt_percent", "Battery as percent", "check"], ["key_beep", "Key beep", "check"],
  ["auto_keylock", "Auto key lock", "check"], ["keylock_timeout_s", "Key lock timeout s", "int"],
  ...["P1", "P2", "PF1", "PF2", "PF3", "PF3 long"].map((k, i) => [`key${i}`, `Key ${k}`, "sel", C.KEY_FUNCS]),
  ["dmr_cc", "Default DMR CC", "int"], ["dmr_slot", "Default DMR slot", "int"], ["dmr_tg", "Default DMR TG", "int"],
  ["p25_nac", "Default P25 NAC (hex)", "hex"], ["p25_tg", "Default P25 TG", "int"], ["p25_wacn", "Default WACN (hex)", "hex"],
  ["p25_sysid", "Default SysID (hex)", "hex"], ["nxdn_ran", "Default NXDN RAN", "int"], ["nxdn_group", "Default NXDN group", "int"],
  ["ysf_dgid", "Default YSF DG-ID", "int"], ["ur", "D-STAR UR"], ["rpt1", "D-STAR RPT1"], ["rpt2", "D-STAR RPT2"], ["dstar_msg", "D-STAR message"]];
function renderSettings() {
  const s = st.cp.settings, f = $("#setForm");
  f.replaceChildren(...SET.map(([k, label, kind, ch]) => {
    const v = /^key\d$/.test(k) ? s.keys[Number(k[3])] : s[k];
    return el("label", { className: "row" }, el("span", {}, label), input(k, kind || "text", v, ch));
  }), el("div", {}, el("button", { type: "submit", className: "primary" }, "Apply settings"), el("span", { className: "msg", id: "setMsg" })));
}
$("#setForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = $("#setForm"), s = structuredClone(st.cp.settings);
  try {
    for (const [k, , kind] of SET) {
      if (/^key\d$/.test(k)) s.keys[Number(k[3])] = f.elements[k].value;
      else if (kind === "sel") s[k] = f.elements[k].value;
      else s[k] = readInput(f, k, kind || "text");
    }
    st.cp.settings = s; setDirty(); $("#setMsg").textContent = "";
  } catch (err) { $("#setMsg").textContent = ` invalid value: ${err.message}`; }
});

const RENDER = { channels: renderChannels, zones: zonesRender, scanlists: scanRender, contacts: contactsRender, tglists: tglRender,
  trunksys: trunkRender, settings: renderSettings, keys: keysRender, dstar: dstarRender, digi: renderDigi, stock: renderStock, info: renderInfo };
function renderAll() {
  st.sel = null;
  ST.use(C.modelOf(st.cp));
  $("#model").value = C.modelOf(st.cp);
  $("#bSaveRdt").title = `stock ${C.modelOf(st.cp)} CPS file (${C.modelOf(st.cp) === "D168UV" ? "V1292" : "V1323"})`;
  document.title = `cfw Web CPS [${C.modelOf(st.cp)}]`;
  if (navModel !== C.modelOf(st.cp)) { buildNav(); if (st.page === "stock" || st.page === "info") showTab("channels"); }
  for (const [k, f] of Object.entries(RENDER)) if (k !== "stock" && k !== "info") f();
  if (st.page === "stock") renderStock(st.pageArg);
  setDirty(st.dirty);
}

// ------------------------------------------------------------ files
function setCodeplug(cp, name, dirty) { st.cp = cp; st.fname = name; st.dirty = dirty; renderAll(); }
async function fileBytes(input) { const f = input.files[0]; input.value = ""; return f ? { name: f.name, bytes: new Uint8Array(await f.arrayBuffer()) } : null; }
$("#bNew").onclick = () => { if (confirmDiscard()) setCodeplug(C.newCodeplug($("#model").value), "untitled", false); };
$("#model").onchange = () => {
  const m = $("#model").value, from = C.modelOf(st.cp);
  if (m === from) return;
  if (st.cp.channels.length && !confirm(`Convert this codeplug from ${from} to ${m}?\n\ncfw channels, zones, contacts and digital-mode settings are kept. Stock CPS settings are mapped by name; those the ${m} CPS does not have are dropped.`)) { $("#model").value = from; return; }
  ST.convertModel(st.cp, m);
  log(`converted to the ${m}`);
  st.dirty = true; renderAll();
};
$("#fOpen").onchange = async (e) => {
  const f = await fileBytes(e.target); if (!f || !confirmDiscard()) return;
  try {
    if (/\.rdt$/i.test(f.name)) {
      const mdl = ST.latin1(f.bytes.slice(9, 15));
      if (mdl === "D890UV" || mdl === "D168UV") {        // stock D890UV (V1323) / D168UV (V1292) CPS file: lossless
        setCodeplug(RDT.load(f.bytes), f.name, false);
        log(`opened stock ${mdl} CPS file ${f.name} (${ST.latin1(f.bytes.slice(0, 5))}): ${st.cp.channels.length} channels`);
        return;
      }
      const r = importRdt(f.bytes); setCodeplug(r.cp, f.name, true); r.report.forEach((l) => log(l)); return;
    }
    setCodeplug(C.load(f.bytes), f.name, false); log(`opened ${f.name}: ${st.cp.channels.length} channels`);
  }
  catch (err) { alert(`Open: ${err.message}`); }
};
$("#fImport").onchange = async (e) => {
  const f = await fileBytes(e.target); if (!f || !confirmDiscard()) return;
  try {
    const mdl = ST.latin1(f.bytes.slice(9, 15));
    const r = f.name.toLowerCase().endsWith(".csv") ? importCsv(new TextDecoder().decode(f.bytes))
      : (mdl === "D890UV" || mdl === "D168UV") ? { cp: RDT.load(f.bytes), report: [`stock ${mdl} CPS file`] } : importRdt(f.bytes);
    const stockRdt = /\.rdt$/i.test(f.name) && (mdl === "D890UV" || mdl === "D168UV");     // keeps its own model
    if (!stockRdt && C.modelOf(r.cp) !== $("#model").value) {
      ST.convertModel(r.cp, $("#model").value); r.report.push(`converted to the ${$("#model").value}`);
    }
    setCodeplug(r.cp, f.name.replace(/\.[^.]+$/, ""), true);
    r.report.forEach((l) => log(l));
    validateUi(false);
  } catch (err) { alert(`Import: ${err.message}`); }
};
$("#fStock").onchange = async (e) => {
  const fl = [...e.target.files]; e.target.value = "";
  if (!fl.length || !confirmDiscard()) return;
  try {
    const files = {};
    for (const f of fl) files[f.name] = new Uint8Array(await f.arrayBuffer());
    const cp = ST.fromStock(ST.readCsvSet(files));
    setCodeplug(cp, (fl.find((f) => /\.lst$/i.test(f.name)) || fl[0]).name.replace(/\.[^.]+$/, ""), true);
    log(`stock CSV set: ${fl.length} files, ${cp.channels.length} channels, ${cp.zones.length} zones`);
    validateUi(false);
  } catch (err) { alert(`Import: ${err.message}`); }
};
$("#bStockZip").onclick = () => {
  const files = ST.writeCsvSet(ST.toStock(st.cp), base() + ".LST");
  download(base() + "_stock_csv.zip", zip(Object.entries(files).map(([n, t]) => [n, ST.toLatin1(t)])), "application/zip");
};
$("#bPrint").onclick = () => {
  const w = window.open("", "_blank");
  if (!w) { download(base() + "_report.html", reportHtml(st.cp, ST), "text/html"); return; }
  w.document.write(reportHtml(st.cp, ST)); w.document.close(); w.focus(); w.print();
};
$("#bSaveRdt").onclick = () => {
  try {
    const r = RDT.save(st.cp);
    download(base() + ".rdt", r.bytes, "application/octet-stream");
    if (r.lost.length) { log(`not written into the .rdt (stock tables in the undecoded .rdt tail; use the stock CSV set): ${r.lost.join(", ")}`, "warn"); alert(`Saved. Not written into the .rdt: ${r.lost.join(", ")} (use Export stock CSV set).`); }
    else log(`saved ${base()}.rdt (stock ${C.modelOf(st.cp)} CPS file)`);
  } catch (err) { alert(err.message); }
};
$("#fTemplate").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try {
    const b = new Uint8Array(await f.arrayBuffer()), m = RDT.setTemplate(b);
    try { localStorage.setItem("cfwcps.rdtTemplate." + m, btoa(String.fromCharCode(...b))); } catch { /* kept for this page only */ }
    log(`.rdt template for the ${m}: ${f.name}`);
  } catch (err) { alert(err.message); }
};
const base = () => st.fname.replace(/\.(d8cp|json|rdt)$/i, "");
$("#bSave").onclick = () => { try { download(base() + ".d8cp", C.encode(st.cp, false), "application/octet-stream"); st.fname = base() + ".d8cp"; setDirty(false); } catch (err) { alert(err.message); } };
$("#bSaveJson").onclick = () => { download(base() + ".json", C.dumpsJson(st.cp), "application/json"); st.fname = base() + ".json"; setDirty(false); };
$("#bCsv").onclick = () => download(base() + ".csv", exportCsv(st.cp), "text/csv");
window.addEventListener("beforeunload", (e) => { if (st.dirty) e.preventDefault(); });

function validateUi(jump = true) {
  const iss = C.validate(st.cp), errs = C.errors(iss);
  log(`validate: ${errs.length} error(s), ${iss.length - errs.length} warning(s)`, errs.length ? "err" : "");
  iss.slice(0, 300).forEach((i) => log("  " + C.issueText(i), i.level === "error" ? "err" : "warn"));
  if (errs.length && jump) showTab("log");
  return !errs.length;
}
$("#bValidate").onclick = () => validateUi(true);

// ------------------------------------------------------------ radio
async function openPort() {
  const t = $("#transport").value;
  if (t === "serial") return WebSerialPort.request(115200);
  if (t === "ws") return WebSocketPort.open($("#wsUrl").value.trim());
  const ident = C.MODELS[C.modelOf(st.cp)].ident;          // the demo radio is a cfw radio of the selected model
  if (!st.demo || st.demo.ident !== ident) st.demo = new FakeRadio({ ident });
  return st.demo.port();
}
const progress = (a, b) => { $("#prog").value = (100 * a) / Math.max(1, b); };
function busy(on) { st.busy = on; for (const b of ["#bRead", "#bWrite"]) $(b).disabled = on; }
function askDiff(lines, summary) {
  return new Promise((res) => {
    $("#diffText").textContent = lines.length ? lines.join("\n") : "(no changes: the radio already holds this codeplug)";
    $("#diffSum").textContent = summary;
    const d = $("#diffDlg");
    const done = (v) => { d.close(); $("#diffOk").onclick = $("#diffCancel").onclick = null; res(v); };
    $("#diffOk").onclick = () => done(true);
    $("#diffCancel").onclick = () => done(false);
    d.showModal();
  });
}
window.cps.askDiff = askDiff;
$("#bRead").onclick = async () => {
  if (st.busy || !confirmDiscard()) return;
  busy(true);
  let port;
  try {
    port = await openPort();
    log("reading ...");
    const r = await readRadio(port, (s) => log(s), progress);
    if (!r.cp) alert("The radio holds no cfw codeplug (it runs on NAND / built-in channels).");
    else { setCodeplug(r.cp, "radio", false); log(`read ${r.raw.length} bytes, ${r.cp.channels.length} channels`); }
  } catch (err) { log(`error: ${err.message}`, "err"); alert(err.message); } finally { if (port) await port.close(); busy(false); }
};
$("#bWrite").onclick = async () => {
  if (st.busy) return;
  if (!validateUi(true)) { alert("Fix the validation errors first (see Log)."); return; }
  busy(true);
  let port;
  try {
    port = await openPort();
    log("writing ...");
    const r = await writeRadio(port, st.cp, { log: (s) => log(s), progress, allowHardware: $("#allowHw").checked,
      confirm: (lines, sum) => window.cps.askDiff(lines, sum) });
    log(r ? "write done" : "write cancelled");
  } catch (err) { log(`error: ${err.message}`, "err"); alert(err.message); } finally { if (port) await port.close(); busy(false); }
};
$("#transport").onchange = () => { $("#wsUrl").style.display = $("#transport").value === "ws" ? "" : "none"; };
const q = new URLSearchParams(location.search);
if (q.get("transport")) $("#transport").value = q.get("transport");
if (q.get("ws")) $("#wsUrl").value = q.get("ws");
$("#transport").onchange();
if (!("serial" in navigator)) $("#transport").options[0].textContent += " (not in this browser)";

showTab("channels");
renderAll();
log("ready. Codeplug only: this CPS cannot flash firmware.");
