// Which stock CPS data the cfw firmware uses, per radio model: port of cps/support.py (schema/cfw_support.json).
// States: "used" (shown plainly), "stored" (in the cfw codeplug, firmware ignores it: note + *), "n/a" (hidden).
export const STATES = ["used", "stored", "n/a"];
export const NOTE = "Stock CPS data: stored in the cfw codeplug and kept in stock .rdt / CSV files, not used by cfw yet.";
export const STAR_NOTE = "* = stored in the cfw codeplug, not used by cfw yet.";
let DATA = { sections: {}, keys: {} };

export function setData(d) { DATA = d; }
export const data = () => DATA;

export const section = (node, model) => (DATA.sections[node] || {})[model] || "stored";
export const tableOf = (node, tables) => {
  const t = node.split("#")[0];
  return t in tables ? t : Object.keys(tables).find((n) => tables[n].node && tables[n].node === node) || null;
};

export function key(table, k, model, node) {
  const v = ((DATA.keys[table] || {})[k] || {})[model];
  return v || section(node || table, model);
}

/** [visible keys, show the note, keys marked *] for a page showing `keys` of `table` */
export function pageMarks(model, node, keys, table) {
  table = table || node.split("#")[0];
  const st = Object.fromEntries(keys.map((k) => [k, key(table, k, model, node)]));
  const vis = keys.filter((k) => st[k] !== "n/a");
  const stored = vis.filter((k) => st[k] === "stored");
  return [vis, stored.length > 0, stored.length < vis.length ? stored : []];
}

export function nodeState(model, node, tables, pages = {}) {
  const s = section(node, model);
  if (s === "n/a") return s;
  const t = tableOf(node, tables);
  if (t && (pages[node] || tables[t].kind === "record")) {
    const keys = pages[node] ? pages[node].keys : tables[t].columns;
    return pageMarks(model, node, keys, t)[1] ? "stored" : "used";
  }
  return s;
}

export const channelMarks = (model, cols) => pageMarks(model, "Channel", cols, "Channel");

/** everything the GUIs decide from the map for one model (== cps/support.py view, tests/vectors/cfw_support_view.json) */
export function view(model, schema) {
  const tabs = schema.tables, pages = schema.pages || {};
  const out = { nodes: {}, pages: {} };
  for (const [, nodes] of schema.tree) {
    for (const [, n] of nodes) {
      out.nodes[n] = nodeState(model, n, tabs, pages);
      const t = tableOf(n, tabs);
      if (t && (pages[n] || tabs[t].kind === "record")) {
        const keys = pages[n] ? pages[n].keys : tabs[t].columns;
        const [vis, note, star] = pageMarks(model, n, keys, t);
        out.pages[n] = { hidden: keys.filter((k) => !vis.includes(k)), note, star };
      }
    }
  }
  const ch = tabs.Channel, cols = ch.columns.filter((c) => !ch.cfw_mapped.includes(c));
  const [vis, note, star] = channelMarks(model, cols);
  out.channel = { hidden: cols.filter((c) => !vis.includes(c)), note, star };
  return out;
}
