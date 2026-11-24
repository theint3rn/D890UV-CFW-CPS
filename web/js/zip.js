// Minimal ZIP writer (stored, no compression) for the stock CSV set download.
import { crc32 } from "./codeplug.js";

export function zip(entries) {               // entries: [[name, Uint8Array]] -> Uint8Array
  const parts = [], central = [];
  let off = 0;
  const u16 = (v) => [v & 0xff, (v >> 8) & 0xff];
  const u32 = (v) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >>> 24) & 0xff];
  for (const [name, data] of entries) {
    const nm = new TextEncoder().encode(name), crc = crc32(data);
    const local = Uint8Array.from([...u32(0x04034b50), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc),
      ...u32(data.length), ...u32(data.length), ...u16(nm.length), ...u16(0), ...nm]);
    central.push(Uint8Array.from([...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc),
      ...u32(data.length), ...u32(data.length), ...u16(nm.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(off), ...nm]));
    parts.push(local, data);
    off += local.length + data.length;
  }
  const cdLen = central.reduce((a, b) => a + b.length, 0);
  const end = Uint8Array.from([...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(entries.length), ...u16(entries.length), ...u32(cdLen), ...u32(off), ...u16(0)]);
  const all = [...parts, ...central, end];
  const out = new Uint8Array(all.reduce((a, b) => a + b.length, 0));
  let p = 0;
  for (const a of all) { out.set(a, p); p += a.length; }
  return out;
}
