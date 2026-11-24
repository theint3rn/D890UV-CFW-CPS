# cfw Web CPS

The web CPS is a static HTML/JS app (no build step and no dependencies) for the D890UV and D168UV custom-firmware
codeplugs. It works offline. The "Radio" selector (header, next to New) picks the radio model: New makes a codeplug for
it, changing it converts the open codeplug (stock tree, stock tables and the `.rdt` format follow the model; see the
main README "D168UV"). `index.html?model=D168UV` starts with a D168UV codeplug. Stock D168 `.rdt` files and D168 CSV
sets open as D168UV codeplugs; the demo radio identifies as the selected model's cfw.

```sh
cd D890UV_src/cfw_cps/web && python3 -m http.server 8000 --bind 127.0.0.1     # then open http://localhost:8000/
```

ES modules do not load from `file://`, so a local server is needed. Any static server works.

| File | What |
|---|---|
| `js/codeplug.js` | Model (the JSON schema of `cps/codeplug.py`), binary "D8CP" v1 encoder/decoder, validation, diff |
| `js/importers.js` | AnyTone `.rdt` import, CHIRP / cfw CSV import, CSV export |
| `js/stock.js`, `js/rdt.js` | Stock CPS tables per model (`schema/stock_d890uv.json`, `stock_d168uv.json`), stock `.rdt` V1323 / V1292 |
| `js/link.js` | Radio protocol (as `cps/link.py`), Web Serial, WebSocket bridge, in-page demo radio |
| `js/app.js`, `index.html`, `css/cps.css` | UI |
| `test/run_tests.mjs` | JS core vs the Python vectors in `../tests/vectors` (`node web/test/run_tests.mjs`; also run by `make test`) |
| `test/browser_test.mjs` | Headless Chromium test (playwright-core) |

**Features:**
* Open and save `.d8cp` / `.json`.
* Import `.rdt` / `.csv`, export `.csv`.
* Channel table with per-mode fields.
* Zones, scan lists and TG lists with ordered members.
* Contacts, trunk systems and settings.
* Validation, with the same rules and messages as Python.
* Write to the radio: validate, read the radio, show the diff dialog, write, then read back and compare.

**Radio links:**
* **Web Serial** (Chrome / Edge): the programming cable, or USB CDC once the cfw has one. Writing over Web Serial needs the "allow hardware write" switch. That is only for after the owner has approved real-radio writes.
* **WebSocket bridge:** `python3 ../tools/ws_bridge.py --target tcp:localhost:3471` (emulator USART1) or `--target /dev/pts/N`. Add `--http 8000` to also serve this folder. Browsers cannot open a pty or a raw TCP socket, so the bridge passes bytes through unchanged.
* **Demo radio:** a JS model of the firmware side, kept in the page.

Same safety rules as the desktop CPS: the app speaks the codeplug protocol only, refuses radios that do not identify as `D890CFW`, and has no firmware commands.

The JS and Python sides produce **identical bytes**. `tests/make_vectors.py` writes the shared vectors: sample, minimal, invalid, `synth` (the synthetic test codeplug, `tools/make_synth.py`), a diff case, two CSV cases, `digital` (every digital section) and `synthstock` (stock CSV set); with the private stock CPS files (`$CFW_CPS_PRIVATE`, README "Stock CPS files") also a real D878UV import, the stock CSV exports and the decoded stock `.rdt` files. `run_tests.mjs` (85 checks with them, 52 without, 2026-11-23) checks that the JS side produces the same results for each:
* decode and encode;
* validation issues;
* diff lines;
* the `.rdt` import of a real D878UV codeplug (same 96 592 bytes; private file);
* CSV import and export;
* the stock CSV set (all 38 tables) byte for byte;
* the stock D890UV `.rdt` (V1323):
  * reader = Python;
  * open + save byte-identical;
  * edits = Python bytes;
  * NX Setting written exactly as the stock CPS writes it (`nx_stock_v1323.rdt`).
