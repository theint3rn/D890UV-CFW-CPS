# cfw_cps
#   make test          unit tests (pytest; includes the JS core vs Python vectors when node is installed)
#   make vectors       regenerate tests/vectors (shared Python <-> JS test vectors)
#   make examples      regenerate the synthetic test codeplug (examples/synth*, tests/vectors/stock_synth*)
# Files made by the stock CPS are not shipped; tests that need them read $CFW_CPS_PRIVATE and skip without it (README).
#   make emu-test      Python core round trip against the cfw in Renode
#   make emu-test-d168 the same against the D168UV cfw (D168UV/cfw/build/cfw168.elf in D168UV/emu)
#   make web           serve the web CPS on http://localhost:8000/
#   make web-test      headless browser test, in-page demo radio (needs playwright-core on NODE_PATH + chromium)
#   make web-emu-test  web CPS -> ws_bridge.py -> Renode round trip
PY ?= python3
test:
	$(PY) -m pytest -q tests
vectors:
	$(PY) tests/make_vectors.py
emu-test:
	$(PY) tools/emu_roundtrip.py
emu-test-d168:
	$(PY) tools/emu_roundtrip.py --model D168UV --monitor 1371 --uart 3491
web:
	cd web && $(PY) -m http.server 8000 --bind 127.0.0.1
web-test:
	node web/test/browser_test.mjs
web-emu-test:
	$(PY) tools/web_emu_test.py
examples:
	$(PY) tools/make_synth.py
.PHONY: test vectors emu-test emu-test-d168 web web-test web-emu-test examples
