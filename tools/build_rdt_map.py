#!/usr/bin/env python3
"""Collect the stock .rdt (V1323) field offsets from the import/save/diff experiments (stock/map/*.jsonl, produced by
tools/stock_rdt_experiments/rdtmap.py driving the stock CPS) into schema/rdt_map.json:
  {table: {column: [byte offsets changed by +1 / a new value] | [] (no effect)}}
Offsets of channel columns are relative to the first channel record of the reference file (row 1)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main(src, name="rdt_map.json"):
    """name: rdt_map.json (D890UV V1323) or rdt_map_d168.json (D168UV V1292)"""
    out = {}
    for f in sorted(os.listdir(src)):
        if not f.endswith(".jsonl"):
            continue
        for line in open(os.path.join(src, f)):
            r = json.loads(line)
            if not r.get("ok") or r.get("len_ref") != r.get("len"):
                continue
            out.setdefault(r["table"], {})[r["name"]] = [b[0] for b in r.get("diff", [])]
            out.setdefault("_ref_len", {})[r["table"]] = r["len_ref"]      # file length of the experiment reference
    p = os.path.join(ROOT, "schema", name)
    json.dump(out, open(p, "w"), indent=0, sort_keys=True)
    os.makedirs(os.path.join(ROOT, "web", "schema"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "web", "schema", name), "w"), indent=0, sort_keys=True)
    print("wrote", p, {t: len(v) for t, v in out.items()})


if __name__ == "__main__":
    main(*sys.argv[1:3])
