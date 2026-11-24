"""Runs the JS core tests (web/test/run_tests.mjs): JS encoder/decoder/validation/diff/importers == Python."""
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_core_matches_python():
    r = subprocess.run(["node", os.path.join(HERE, "..", "web", "test", "run_tests.mjs")], capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
