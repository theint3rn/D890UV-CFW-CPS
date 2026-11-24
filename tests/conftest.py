import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
VEC = os.path.join(HERE, "vectors")
# Synthetic test codeplug (tools/make_synth.py): made-up data, always present
SYNTH = os.path.join(ROOT, "examples", "synth.d8cp")
SYNTH_CSV = os.path.join(VEC, "stock_synth", "synth.LST")
SYNTH_CSV_D168 = os.path.join(VEC, "stock_synth_d168", "synth.LST")
# Files made by the stock CPS (its new-file templates, real codeplugs it saved or exported) are not shipped with cfw_cps.
# Tests that need them look in $CFW_CPS_PRIVATE (layout: README "Stock CPS files") and are skipped when it is missing:
#   templates/new_v1323.rdt, templates/new_v1292.rdt     stock CPS File > New, saved (D890UV V1.05 / D168UV V1.07)
#   d878.rdt                                             a D878UV CPS codeplug (V1270) for the D878 importer
#   vectors/...                                          stock-saved .rdt files and stock CSV exports (make vectors)
PRIV = os.environ.get("CFW_CPS_PRIVATE") or os.path.join(ROOT, "..", "..", "private", "cfw_cps")
PVEC = os.path.join(PRIV, "vectors")
TEMPLATES = os.path.join(PRIV, "templates")
RDT = os.environ.get("CFW_CPS_D878_RDT") or os.path.join(PRIV, "d878.rdt")
WRITES = os.path.join(ROOT, "..", "emu", "out", "codeplug_capture", "writes.bin")
if not os.environ.get("CFW_CPS_RDT_DIR") and os.path.isdir(TEMPLATES):
    os.environ["CFW_CPS_RDT_DIR"] = TEMPLATES        # .rdt templates for the cfw_cps code under test


def pvec(*p):
    return os.path.join(PVEC, *p)


def need(*paths):
    """skip unless these (private) files exist"""
    miss = [p for p in paths if not os.path.exists(p)]
    return pytest.mark.skipif(bool(miss), reason="stock CPS file not present: %s" % ", ".join(
        os.path.relpath(p, PRIV) if p.startswith(PRIV) else p for p in miss))


def template(model="D890UV"):
    from cps import rdt
    return rdt.template_path(model)


def need_template(model="D890UV"):
    return pytest.mark.skipif(template(model) is None, reason="no stock %s .rdt template ($CFW_CPS_RDT_DIR)" % model)
