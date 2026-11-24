# Stock CPS .rdt mapping experiments

How `schema/rdt_map.json` and `docs/STOCK_CPS_MAP.md` were produced. Needs the stock D890UV CPS V1.05 installed in a
**scratch** Wine prefix (never `~/.wine`), with every COM port pointed at `/dev/null`:

```sh
export WINEPREFIX=$SCRATCH/wine_cps
wine D890UV_Setup_1.05.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR='C:\D890CPS'
for i in $(seq 1 16); do wine reg add 'HKLM\Software\Wine\Ports' /v COM$i /d /dev/null /f; ln -sfn /dev/null $WINEPREFIX/dosdevices/com$i; done
```

1. Start the CPS, File > New, Save As `C:\work\base.rdt`; Tool > Export > Export All into `C:\work\bexp\` (the defaults,
   kept as `$CFW_CPS_PRIVATE/schema/stock_defaults/`; not shipped).
2. `rdtmap.py TABLE [first] [last]` (env `BATCH=n` groups columns): for each column writes the table's CSV with that value
   changed (+1, or another value seen in a real codeplug's export), a one-line `.LST`, runs Tool > Import > Import From File
   List, File > Save As, and diffs the saved `.rdt` against the reference save of the unchanged CSV. A group whose diff
   is one +1 byte per column (in column order) is accepted at once, otherwise it is bisected. Results:
   `map/<TABLE>.jsonl`.
3. `tools/build_rdt_map.py map/` -> `schema/rdt_map.json`; `tools/make_stock_map_doc.py` -> `docs/STOCK_CPS_MAP.md`.

The CPS is driven with xdotool on the desktop (keyboard + mouse); it never talks to a radio. `win32_dump.py` (run with a
Windows Python inside the same prefix) lists the Win32 controls of a CPS window; it showed that the Optional Setting
combo boxes are windowless, so their option lists come from screenshots.

`nxverify.py`: imports one NXSetting row with several non-default values (u16 IDs, the TxAliasName string, flags) into
the stock CPS and saves `x/nxv.rdt`. That file is `tests/vectors/nx_stock_v1323.rdt`; its reference is
`nx_ref_v1323.rdt`. `tests/test_rdt.py` and `web/test/run_tests.mjs` check that cfw writes the same bytes.
Mapping status (2026-11-21): OptionalSetting 196, Channel 75 and NXSetting 42 columns (`tools/build_rdt_map.py`).
`import -window` screenshots run under `timeout 10`, because one hung for 6 h on a vanished message box.
