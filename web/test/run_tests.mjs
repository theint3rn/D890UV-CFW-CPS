// node web/test/run_tests.mjs : JS codeplug core vs the Python reference (tests/vectors from tests/make_vectors.py).
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as C from "../js/codeplug.js";
import { importRdt, importCsv, exportCsv } from "../js/importers.js";
import { FakeRadio, Radio } from "../js/link.js";
import * as ST from "../js/stock.js";
import * as R3 from "../js/rdt.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const VEC = join(HERE, "..", "..", "tests", "vectors");
// files made by the stock CPS are not shipped: $CFW_CPS_PRIVATE (tests/conftest.py); their checks are skipped without them
const PRIV = process.env.CFW_CPS_PRIVATE || join(HERE, "..", "..", "..", "..", "private", "cfw_cps");
const PVEC = join(PRIV, "vectors"), TPL = (n) => join(process.env.CFW_CPS_RDT_DIR || join(PRIV, "templates"), n);
const RDT = process.env.CFW_CPS_D878_RDT || join(PRIV, "d878.rdt");
const SCH = (n) => join(HERE, "..", "schema", n);
const readIf = (p) => existsSync(p) ? new Uint8Array(readFileSync(p)) : null;
ST.setSchema(JSON.parse(readFileSync(SCH("stock_d168uv.json"), "utf8")));
ST.setSchema(JSON.parse(readFileSync(SCH("stock_d890uv.json"), "utf8")));          // the last one set is selected
R3.setDefaults(readIf(TPL("new_v1323.rdt")), JSON.parse(readFileSync(SCH("rdt_map.json"), "utf8")));
R3.setDefaults(readIf(TPL("new_v1292.rdt")), existsSync(SCH("rdt_map_d168.json")) ? JSON.parse(readFileSync(SCH("rdt_map_d168.json"), "utf8")) : {}, "D168UV");
let pass = 0, fail = 0, skipped = 0;
const skip = (what) => { skipped++; console.log("skip (no stock CPS file):", what); };
const ok = (cond, name) => { if (cond) pass++; else { fail++; console.log("FAIL", name); } };
const eqBytes = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const firstDiff = (a, b) => { for (let i = 0; i < Math.max(a.length, b.length); i++) if (a[i] !== b[i]) return i; return -1; };
const deep = (a, b) => JSON.stringify(sortKeys(a)) === JSON.stringify(sortKeys(b));
function sortKeys(x) {
  if (Array.isArray(x)) return x.map(sortKeys);
  if (x && typeof x === "object") return Object.fromEntries(Object.keys(x).sort().map((k) => [k, sortKeys(x[k])]));
  return x;
}

for (const [dir, name] of [[VEC, "sample"], [VEC, "minimal"], [VEC, "bad"], [VEC, "synth"], [PVEC, "d878"], [VEC, "digital"], [VEC, "digital_d168"]]) {
  if (!existsSync(join(dir, name + ".d8cp"))) { skip(name); continue; }
  const bin = new Uint8Array(readFileSync(join(dir, name + ".d8cp")));
  const js = JSON.parse(readFileSync(join(dir, name + ".json"), "utf8"));
  const dec = C.decode(bin);
  const pydec = JSON.parse(readFileSync(join(dir, name + ".decoded.json"), "utf8"));
  ok(deep(dec, pydec), `${name}: decode(.d8cp) == Python decode`);
  if (name !== "bad") ok(deep(dec, js), `${name}: decode(.d8cp) == source JSON`);
  const enc = C.encode(C.fromDict(js));
  ok(eqBytes(enc, bin), `${name}: encode(JSON) == Python bytes (first diff at ${firstDiff(enc, bin)})`);
  ok(eqBytes(C.encode(dec), bin), `${name}: encode(decode(b)) == b`);
  const iss = C.validate(C.fromDict(js));
  const want = JSON.parse(readFileSync(join(dir, name + ".issues.json"), "utf8"));
  ok(deep(iss, want), `${name}: validation issues identical (${iss.length} vs ${want.length})`);
  if (!deep(iss, want)) { console.log(" js:", iss.slice(0, 5)); console.log(" py:", want.slice(0, 5)); }
}

// stock CPS CSV set (synthetic, and the stock CPS's own export when present): read -> cfw -> same bytes as Python;
// written back byte for byte
const { readdirSync } = await import("node:fs");
for (const [dir, vdir, vec] of [[join(VEC, "stock_synth"), VEC, "synthstock"], [join(PVEC, "stock_csv_d890"), PVEC, "stockcsv"]]) {
  if (!existsSync(dir)) { skip(dir); continue; }
  const files = Object.fromEntries(readdirSync(dir).map((n) => [n, new Uint8Array(readFileSync(join(dir, n)))]));
  const tables = ST.readCsvSet(files);
  const cp = ST.fromStock(tables);
  const want = new Uint8Array(readFileSync(join(vdir, vec + ".d8cp")));
  const enc = C.encode(cp, false);
  ok(eqBytes(enc, want), `${vec}: stock CSV set -> cfw codeplug == Python bytes (first diff ${firstDiff(enc, want)}, ${enc.length} vs ${want.length})`);
  ok(deep(cp, JSON.parse(readFileSync(join(vdir, vec + ".json"), "utf8"))), `${vec}: stock import JSON == Python JSON`);
  const out = ST.writeCsvSet(ST.toStock(C.decode(enc)), "x.LST");
  const badf = Object.keys(out).filter((n) => n.endsWith(".CSV") && ST.latin1(files[n] || new Uint8Array()) !== out[n]);
  ok(badf.length === 0, `${vec}: stock CSV set written back byte for byte (all 38 files)`, badf.join(","));
}

// D168UV: stock D168 CSV sets, conversion, stock D168 .rdt (V1292)
for (const [dir, vdir, vec] of [[join(VEC, "stock_synth_d168"), VEC, "synthstock_d168"], [join(PVEC, "stock_csv_d168"), PVEC, "stockcsv_d168"]]) {
  if (!existsSync(dir)) { skip(dir); continue; }
  const files = Object.fromEntries(readdirSync(dir).map((n) => [n, new Uint8Array(readFileSync(join(dir, n)))]));
  const tables = ST.readCsvSet(files);
  ok(ST.MODEL === "D168UV", "D168 CSV set detected as D168UV");
  const cp = ST.fromStock(tables);
  const want = new Uint8Array(readFileSync(join(vdir, vec + ".d8cp")));
  const enc = C.encode(cp, false);
  ok(eqBytes(enc, want), `${vec}: D168 stock CSV set -> cfw codeplug == Python bytes (first diff ${firstDiff(enc, want)}, ${enc.length} vs ${want.length})`);
  ok(deep(cp, JSON.parse(readFileSync(join(vdir, vec + ".json"), "utf8"))), `${vec}: D168 stock import JSON == Python JSON`);
  const dec = C.decode(enc);
  ok(dec.model === "D168UV", "D168 model kept in the binary header");
  const out = ST.writeCsvSet(ST.toStock(dec), "x.LST");
  const badf = Object.keys(out).filter((n) => n.endsWith(".CSV") && ST.latin1(files[n] || new Uint8Array()) !== out[n]);
  ok(badf.length === 0 && Object.keys(out).length === 29, "D168 stock CSV set written back byte for byte (all 28 files)", badf.join(","));
  const dig = C.fromDict(JSON.parse(readFileSync(join(VEC, "digital.json"), "utf8")));
  ST.convertModel(dig, "D168UV");
  const w2 = new Uint8Array(readFileSync(join(VEC, "digital_d168.d8cp")));
  ok(eqBytes(C.encode(dig), w2), `convert D890UV -> D168UV == Python bytes (first diff ${firstDiff(C.encode(dig), w2)})`);
  ST.convertModel(dig, "D890UV");
  ok(dig.model === undefined && dig.settings.radio_name === "D890UV cfw", "convert back to D890UV");
  ST.use("D890UV");
}
{ // D168 stock .rdt files (V1292): private
  const files = Object.fromEntries(existsSync(join(PVEC, "stock_csv_d168"))
    ? readdirSync(join(PVEC, "stock_csv_d168")).map((n) => [n, new Uint8Array(readFileSync(join(PVEC, "stock_csv_d168", n)))]) : []);
  ST.use("D168UV");
  for (const [path, json] of [[TPL("new_v1292.rdt"), "new_v1292.json"], [join(PVEC, "stock_small_v1292.rdt"), "stock_small_v1292.json"]]) {
    if (!existsSync(path) || !existsSync(join(PVEC, json))) { skip(path); continue; }
    const raw = new Uint8Array(readFileSync(path));
    const r = R3.load(raw);
    ok(deep(r, JSON.parse(readFileSync(join(PVEC, json), "utf8"))), `${json}: JS .rdt reader == Python`);
    const o = R3.save(r).bytes;
    ok(eqBytes(o, raw), `${json}: open + save byte-identical (first diff ${firstDiff(o, raw)})`);
  }
  if (!files["export.LST"] || !existsSync(join(PVEC, "csvset_stock_v1292.rdt")) || !R3.hasTemplate("D168UV")) skip("csvset_stock_v1292.rdt");
  else {   // cfw-built .rdt that the stock D168 CPS re-saved byte for byte (tests/test_d168.py)
    const cp2 = ST.fromStock(ST.readCsvSet(files));
    cp2.stock = Object.fromEntries(Object.entries(cp2.stock).filter(([k]) => ["PrefabricatedSMS", "FM", "RadioIDList"].includes(k)));
    cp2.channels.push(C.normalizeChannel({ name: "CFW P25", rx_hz: 446100000, tx_hz: 446100000, mode: "P25", nac: 0x293, tg: 1 }));
    ST.setStockValue(cp2, "OptionalSetting", "TOT", "3");
    const o = R3.save(cp2), want2 = new Uint8Array(readFileSync(join(PVEC, "csvset_stock_v1292.rdt")));
    ok(eqBytes(o.bytes, want2) && o.lost.length === 0, `cfw-built D168 .rdt == stock CPS save (first diff ${firstDiff(o.bytes, want2)})`);
  }
  {   // Bluetooth page (radio Settings > BT): value lists + .rdt bytes == Python (tests/test_d168.py test_bluetooth_*)
    const BT = { BlueToothOn: "BT On", BhtHoldTime: "infinite", BhtHoldDelay: "2.5S", SpkInBlueTooth: "On",
      BhtMicGain: "Level 5", BhtSpkGain: "Level 3", BhtPttHold: "1", MicInBlueTooth: "1" };
    const pg = ST.PAGES["OptionalSetting#Bluetooth"];
    ok(pg && pg.keys.length === 8 && ST.CHOICES.BhtHoldTime.length === 34 && ST.choiceText("BhtHoldTime", "10") === "10S"
      && ST.choiceValue("BhtHoldDelay", "5.5S") === "10" && ST.choiceText("BhtMicGain", "9") === "9", "D168 Bluetooth page + value lists");
    const small = readIf(join(PVEC, "stock_small_v1292.rdt")), want3 = readIf(join(PVEC, "bt_v1292.rdt"));
    if (!small || !want3) skip("bt_v1292.rdt");
    else {
      const b = R3.load(small);
      for (const [k, v] of Object.entries(BT)) ST.setStockValue(b, "OptionalSetting", k, ST.choiceValue(k, v));
      const o = R3.save(b);
      ok(eqBytes(o.bytes, want3) && o.lost.length === 0, `D168 Bluetooth settings -> .rdt == Python bytes (first diff ${firstDiff(o.bytes, want3)})`);
      const v = ST.stockSettingsView(R3.load(want3), "OptionalSetting");
      ok(Object.entries(BT).every(([k, t]) => ST.choiceText(k, v[k]) === t), "D168 Bluetooth values read back from the .rdt");
    }
  }
  ST.use("D890UV");
}

// stock .rdt (V1323): JS reader == Python reader, open + save byte-identical, edits == Python bytes
for (const [path, json] of [[TPL("new_v1323.rdt"), "new_v1323.json"], [join(PVEC, "stock_small_v1323.rdt"), "stock_small_v1323.json"]]) {
  if (!existsSync(path) || !existsSync(join(PVEC, json))) { skip(path); continue; }
  const raw = new Uint8Array(readFileSync(path));
  const cp = R3.load(raw);
  ok(deep(cp, JSON.parse(readFileSync(join(PVEC, json), "utf8"))), `${json}: JS .rdt reader == Python`);
  const out = R3.save(cp).bytes;
  ok(eqBytes(out, raw), `${json}: open + save byte-identical (first diff ${firstDiff(out, raw)})`);
}
if (!existsSync(join(PVEC, "stock_small_v1323.rdt")) || !existsSync(join(PVEC, "stock_small_v1323_edit.rdt"))) skip("stock_small_v1323_edit.rdt");
else {
  const e = R3.load(new Uint8Array(readFileSync(join(PVEC, "stock_small_v1323.rdt"))));
  const old = ST.channelKey(e.channels[0]);
  e.channels[0] = C.normalizeChannel(Object.assign({}, e.channels[0], { name: "CFW EDIT" })); Object.defineProperty(e.channels[0], "_rdt", { value: R3.parse(new Uint8Array(readFileSync(join(PVEC, "stock_small_v1323.rdt")))).channels[0], enumerable: false });
  ST.clearMappedOverrides(e.channels[0], "Channel"); ST.renameChannelRefs(e, old, ST.channelKey(e.channels[0]));
  const c1 = e.channels[1]; c1.rx_hz = 446600000; ST.clearMappedOverrides(c1, "Channel");
  e.zones[0].channels = e.zones[0].channels.slice(0, 5);
  e.stock.PrefabricatedSMS.push(["15", "cfw test"]);
  ST.setStockValue(e, "OptionalSetting", "Start_Char", "CFW CPS"); ST.setStockValue(e, "OptionalSetting", "Beep", "1");
  const out = R3.save(e).bytes, want = new Uint8Array(readFileSync(join(PVEC, "stock_small_v1323_edit.rdt")));
  ok(eqBytes(out, want), `edited .rdt == Python bytes (first diff ${firstDiff(out, want)}, ${out.length} vs ${want.length})`);
}

// corrupt input is refused
{
  const bin = new Uint8Array(readFileSync(join(VEC, "sample.d8cp")));
  const bad = bin.slice(); bad[200] ^= 1;
  let threw = false; try { C.decode(bad); } catch (e) { threw = e instanceof C.CodeplugError; }
  ok(threw, "CRC error detected");
}

// diff lines identical to Python
for (const [dir, nm] of [[VEC, "synth"], [PVEC, "d878"]]) {
  if (!existsSync(join(dir, `diff_${nm}.json`))) { skip(`diff_${nm}.json`); continue; }
  const d = JSON.parse(readFileSync(join(dir, `diff_${nm}.json`), "utf8"));
  const old = JSON.parse(readFileSync(join(dir, nm + ".json"), "utf8"));
  const lines = C.diff(old, d.new);
  ok(deep(lines, d.lines), `${nm}: diff lines identical to Python`);
  if (!deep(lines, d.lines)) { console.log(lines.slice(0, 5), d.lines.slice(0, 5)); }
  ok(C.diffSummary(old, d.new) === d.summary, `${nm}: diff summary identical`);
}

// D878UV .rdt import -> same bytes as the Python importer (private)
if (!existsSync(RDT) || !existsSync(join(PVEC, "d878.d8cp"))) skip("d878.rdt");
else {
  const t0 = Date.now();
  const { cp, report } = importRdt(new Uint8Array(readFileSync(RDT)));
  const enc = C.encode(cp);
  const want = new Uint8Array(readFileSync(join(PVEC, "d878.d8cp")));
  ok(eqBytes(enc, want), `D878UV .rdt import (JS) == Python import bytes (first diff ${firstDiff(enc, want)})`);
  ok(/\d/.test(report[1]), "user DB counted");
  console.log(`  rdt import ${Date.now() - t0} ms: ${report[0]}`);
}

// CSV import -> same bytes as Python; CSV export identical text
for (const nm of ["chirp", "sample"]) {
  const { cp } = importCsv(readFileSync(join(VEC, nm + ".csv"), "utf8"));
  cp.created = 1763600000;
  const want = new Uint8Array(readFileSync(join(VEC, nm + ".csv.d8cp")));
  const enc = C.encode(cp);
  ok(eqBytes(enc, want), `${nm}.csv import == Python bytes (first diff ${firstDiff(enc, want)})`);
}
{
  const js = JSON.parse(readFileSync(join(VEC, "sample.json"), "utf8"));
  ok(exportCsv(C.fromDict(js)) === readFileSync(join(VEC, "sample.csv"), "utf8"), "CSV export identical to Python");
}

// link protocol against a JS model of prog.c (same behaviour as tests/fake_radio.py)
{
  const fake = new FakeRadio();
  const r = new Radio(fake.port());
  const cp = C.fromDict(JSON.parse(readFileSync(join(VEC, "sample.json"), "utf8")));
  await r.enter();
  ok(r.ident.fw === "1.0" && !r.ident.write_protected, "identify");
  const data = C.encode(cp);
  await r.writeCodeplug(data);
  ok(await r.end(), "END ack after write");
  ok(fake.order[fake.order.length - 1] === 0, "header block written last");
  await r.enter();
  const back = await r.readCodeplug();
  await r.end();
  ok(eqBytes(back, data), "read back byte for byte");
  const stock = new FakeRadio({ ident: "D890UV\0" });
  let refused = false; try { await new Radio(stock.port()).enter(); } catch (e) { refused = /not the cfw/.test(e.message); }
  ok(refused && stock.writes === 0, "stock radio refused");
}

// NXSetting inside the .rdt tail: same bytes as the stock CPS's own save (tests/test_rdt.py)
if (!existsSync(join(PVEC, "nx_stock_v1323.rdt"))) skip("nx_stock_v1323.rdt");
else {
  const stock = new Uint8Array(readFileSync(join(PVEC, "nx_stock_v1323.rdt")));
  const s = R3.load(stock), nx = ST.stockSettingsView(s, "NXSetting");
  ok(nx.OwnId === "1234" && nx.OwnIdAbleMax === "4000" && nx.TxAliasName === "CFW7" && nx.NxdnMoniId === "7", "NXSetting decoded from the stock CPS file");
  const e = R3.load(new Uint8Array(readFileSync(join(PVEC, "nx_ref_v1323.rdt"))));
  for (const k of ["OwnId", "StationId ", "OwnIdAbleMax", "TxAliasEn", "TxAliasName", "ResetTime", "StateMsg2", "NxdnMoni", "NxdnMoniId", "PriCallBeep"])
    ST.setStockValue(e, "NXSetting", k, nx[k]);
  const r = R3.save(e);
  ok(r.lost.length === 0 && r.bytes.length === stock.length && eqBytes(r.bytes.subarray(9), stock.subarray(9)), `NXSetting written like the stock CPS (lost ${r.lost}, first diff ${firstDiff(r.bytes, stock)})`);
}
// built-in blank .rdt (no stock template): blank file + the synthetic codeplug written on it == Python (tests/test_rdt.py)
for (const [model, ver, syn] of [["D890UV", "v1323", "synth"], ["D168UV", "v1292", "synth_d168"]]) {
  R3.clearTemplate(model);
  ST.use(model);
  const want = new Uint8Array(readFileSync(join(VEC, `blank_${ver}.rdt`))), got = R3.blankRdt(model);
  ok(eqBytes(got, want), `${model} built-in blank .rdt == Python (first diff ${firstDiff(got, want)}, ${got.length} vs ${want.length})`);
  const cp = C.decode(new Uint8Array(readFileSync(join(HERE, "..", "..", "examples", syn + ".d8cp"))));
  const o = R3.save(cp).bytes, w2 = new Uint8Array(readFileSync(join(VEC, `synth_${ver}.rdt`)));
  ok(eqBytes(o, w2), `${model} synthetic codeplug -> .rdt on the blank == Python (first diff ${firstDiff(o, w2)}, ${o.length} vs ${w2.length})`);
  const back = R3.load(o);
  ok(back.channels.length === cp.channels.length && back.zones.length === cp.zones.length, `${model} .rdt on the blank reads back`);
  const tpl = readIf(TPL(model === "D890UV" ? "new_v1323.rdt" : "new_v1292.rdt"));
  if (tpl) R3.setTemplate(tpl, model);
}
ST.use("D890UV");
console.log(`${pass} passed, ${fail} failed${skipped ? `, ${skipped} skipped (stock CPS files not present)` : ""}`);
process.exit(fail ? 1 : 0);
