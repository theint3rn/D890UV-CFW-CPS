// Headless browser test of the web CPS (playwright-core + an installed Chromium; no browser download).
//   node web/test/browser_test.mjs [--url http://localhost:8000/] [--transport demo|ws] [--ws ws://localhost:8765]
//          [--name NAME] [--shots DIR] [--chromium /usr/bin/chromium]
// Needs playwright-core on NODE_PATH (npm i playwright-core). Serves web/ itself when --url is not given.
// Steps: open the synthetic test codeplug (examples/synth.d8cp), check counts, edit a channel in the form, write to the radio
// (diff dialog -> Write), read back, check the page's codeplug equals what was written; screenshots.
import { createServer } from "node:http";
import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");
const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = join(HERE, "..");
const SYNTH = join(WEB, "..", "examples", "synth.d8cp");
// a stock-CPS-saved .rdt is not shipped: $CFW_CPS_PRIVATE/vectors/stock_small_v1323.rdt (tests/conftest.py), else skipped
const PRIV = process.env.CFW_CPS_PRIVATE || join(WEB, "..", "..", "..", "private", "cfw_cps");
const STOCK_RDT = join(PRIV, "vectors", "stock_small_v1323.rdt");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const transport = arg("--transport", "demo");
const name = arg("--name", "WEB CPS TEST");
const shots = arg("--shots", join(WEB, "..", "screens"));
mkdirSync(shots, { recursive: true });

let url = arg("--url"), server = null;
if (!url) {
  const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
  server = createServer((req, res) => {
    const p = join(WEB, decodeURIComponent(req.url.split("?")[0]).replace(/\/$/, "/index.html"));
    if (!p.startsWith(WEB) || !existsSync(p)) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": types[extname(p)] || "application/octet-stream" }); res.end(readFileSync(p));
  }).listen(0, "127.0.0.1");
  await new Promise((r) => server.on("listening", r));
  url = `http://127.0.0.1:${server.address().port}/`;
}
let pass = 0, fail = 0;
const ok = (c, m, extra = "") => { console.log(`${c ? "PASS" : "FAIL"} ${m} ${extra}`); c ? pass++ : fail++; };

const browser = await chromium.launch({ executablePath: arg("--chromium", "/usr/bin/chromium"), headless: true });
const page = await browser.newPage({ viewport: { width: 1360, height: 820 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("dialog", (d) => d.accept());                 // confirm() / alert()
try {
  await page.goto(`${url}?transport=${transport}&ws=${encodeURIComponent(arg("--ws", "ws://localhost:8765"))}`);
  await page.waitForFunction(() => window.cps && document.querySelector("#log").textContent.includes("ready"));
  ok(errors.length === 0, "page loads without errors", errors.join("; "));

  await page.setInputFiles("#fOpen", SYNTH);
  await page.waitForFunction(() => window.cps.st.cp.channels.length > 100, null, { timeout: 20000 });
  const counts = await page.evaluate(() => { const c = window.cps.st.cp; return [c.channels.length, c.zones.length, c.scanlists.length, c.contacts.length, c.tglists.length]; });
  ok(JSON.stringify(counts) === JSON.stringify([179, 12, 6, 22, 3]), "synthetic codeplug opened in the page", JSON.stringify(counts));
  ok(await page.locator("#chTable tbody tr").count() === 179, "channel table shows 179 rows");

  // edit the first DMR channel through the form
  const E = await page.evaluate(() => window.cps.st.cp.channels.findIndex((c) => c.mode === "DMR"));
  await page.click(`#chTable tbody tr:nth-child(${E + 1})`);
  await page.fill("#chForm input[name=name]", name);
  await page.fill("#chForm input[name=tg]", "3100");
  await page.click("#chApply");
  let ch = await page.evaluate((e) => window.cps.st.cp.channels[e], E);
  ok(ch.name === name && ch.tg === 3100 && ch.mode === "DMR", "channel edited through the form", `${ch.name} TG${ch.tg}`);
  // a bad value is reported, not stored
  await page.fill("#chForm input[name=cc]", "99");
  await page.click("#chApply");
  ok((await page.textContent("#chMsg")).includes("colour code"), "validation message for CC 99");
  await page.fill("#chForm input[name=cc]", "1");
  await page.click("#chApply");
  // digital extensions of the channel (talkaround, vocoder)
  await page.check("#chForm input[name=talkaround]");
  await page.selectOption("#chForm select[name=vocoder]", "AMBE+2");
  await page.click("#chApply");
  ch = await page.evaluate((e) => window.cps.st.cp.channels[e], E);
  ok(ch.talkaround === true && ch.vocoder === "AMBE+2", "channel talkaround + vocoder set");
  await page.uncheck("#chForm input[name=talkaround]");
  await page.click("#chApply");
  // move it to the top so the radio's channel 1 shows it
  for (let i = 0; i < E; i++) await page.click("#chUp");
  ch = await page.evaluate(() => window.cps.st.cp.channels[0]);
  ok(ch.name === name, "moved to channel 1");
  await page.screenshot({ path: join(shots, `web_channels_${transport}.png`) });

  // other tabs render
  const nav = (pg, arg) => page.click(arg ? `#nav button[data-page="${pg}"][data-arg="${arg}"]` : `#nav button[data-page="${pg}"]`);
  await page.evaluate(() => document.querySelectorAll("#nav details").forEach((d) => { d.open = true; }));
  for (const t of ["zones", "scanlists", "contacts", "tglists", "trunksys", "settings", "keys", "dstar", "digi"]) await nav(t);
  // stock pages: Optional Settings tabs, a stock list table
  await nav("stock", "OptionalSetting");
  ok((await page.locator("#t-stock .subtabs button").count()) === 18, "Optional Settings shows the 17 stock tabs (+ CSV-only)");
  await page.click('#t-stock .subtabs button:has-text("Other")');
  await page.fill('#t-stock input[name="TOT"]', "4");
  await page.click('#t-stock button[type="submit"]');
  ok(await page.evaluate(() => window.cps.ST.stockSettingsView(window.cps.st.cp, "OptionalSetting").TOT) === "4", "stock Optional Setting edited (TOT)");
  await nav("stock", "RoamingChannel");
  ok((await page.locator("#t-stock tbody tr").count()) >= 1, "stock Roaming Channel table shown");
  await page.screenshot({ path: join(shots, `web_stock_${transport}.png`) });
  {
    const before = await page.evaluate(() => window.cps.C.encode(window.cps.st.cp, false).length);
    ok(before > 0, "codeplug encodes before .rdt test");
  }
  // a cfw encryption key + D-STAR repeater
  await nav("keys");
  const nkeys = await page.evaluate(() => window.cps.st.cp.keys.length);
  await page.click('#t-keys button:has-text("Add")');
  await page.fill('#t-keys input[name="hex"]', "00112233445566778899AABBCCDDEEFF00112233445566778899AABBCCDDEEFF");
  await page.click('#t-keys button[type="submit"]');
  ok(await page.evaluate((n) => window.cps.st.cp.keys.length === n + 1 && window.cps.st.cp.keys[n].hex.length === 64, nkeys), "encryption key added");
  await nav("zones");
  await page.selectOption("#t-zones select[size]", "0");
  ok((await page.locator("#t-zones .c2 option").count()) === 40, "zone 1 members listed (40)");
  await page.screenshot({ path: join(shots, `web_zones_${transport}.png`) });
  await nav("channels");

  // write: diff dialog, then Write
  await page.click("#bWrite");
  await page.waitForSelector("#diffDlg[open]", { timeout: 60000 });
  const diffText = await page.textContent("#diffText");
  ok(diffText.includes(name), "diff dialog lists the edited channel");
  await page.screenshot({ path: join(shots, `web_diff_${transport}.png`) });
  await page.click("#diffOk");
  await page.waitForFunction(() => /write done|write cancelled|\nerror:/.test(document.querySelector("#log").textContent), null, { timeout: 180000 });
  const logText = await page.textContent("#log");
  ok(/verified: read back \d+ bytes, identical/.test(logText), "write + read-back verified", (logText.match(/verified[^\n]*/) || [""])[0]);
  const written = await page.evaluate(() => Array.from(window.cps.C.encode(window.cps.st.cp)));

  // read back into a fresh page state
  await page.evaluate(() => { window.cps.st.dirty = false; });
  await page.click("#bRead");
  await page.waitForFunction(() => /read \d+ bytes/.test(document.querySelector("#log").textContent), null, { timeout: 180000 });
  const back = await page.evaluate(() => Array.from(window.cps.C.encode(window.cps.st.cp)));
  ok(back.length === written.length && back.every((x, i) => x === written[i]), "read back byte for byte", `${back.length} bytes`);
  ok(await page.evaluate(() => window.cps.st.cp.channels[0].name) === name, "read-back channel 1 is the edited one");
  // stock D890UV .rdt (V1323): open, then Save .rdt gives the same bytes back
  if (!existsSync(STOCK_RDT)) console.log("skip (stock CPS file not present): .rdt open + save");
  else {
    const src = STOCK_RDT;
    await page.evaluate(() => { window.cps.st.dirty = false; });
    await page.setInputFiles("#fOpen", src);
    await page.waitForFunction(() => /opened stock D890UV CPS file/.test(document.querySelector("#log").textContent), null, { timeout: 60000 });
    ok(await page.evaluate(() => window.cps.st.cp.channels.length) === 1405, "stock .rdt opened in the page (1405 channels)");
    const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#bSaveRdt")]);
    const got = new Uint8Array(readFileSync(await dl.path())), want = new Uint8Array(readFileSync(src));
    ok(got.length === want.length && got.every((x, i) => x === want[i]), "Save .rdt byte-identical to the opened file", `${got.length} vs ${want.length}`);
  }
  ok(errors.length === 0, "no page errors", errors.join("; "));
  await nav("log");
  await page.screenshot({ path: join(shots, `web_log_${transport}.png`) });
} catch (e) {
  ok(false, "exception", e.message + " | page errors: " + errors.join("; "));
} finally {
  await browser.close();
  if (server) server.close();
}
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
