// Radio link for the web CPS: the cfw programming protocol (cfw/app/prog.c), same as cps/link.py.
// Transports: Web Serial (Chrome/Edge: programming cable / USB CDC), WebSocket bridge (tools/ws_bridge.py ->
// emulator TCP or a serial device), and an in-page FakeRadio (demo + tests).
// Safety: codeplug protocol only; radios that do not identify as the cfw ("D890CFW" / "D168CFW") are refused (no stock-radio writes);
// there are no firmware / bootloader / NAND commands.
import * as C from "./codeplug.js";

export const ACK = 0x06, NAK = 0x15, INFO_ADDR = 0x00f00000, CHUNK = 128;
export class LinkError extends Error {}
const enc = (s) => Uint8Array.from([...s].map((c) => c.charCodeAt(0)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** byte queue with timed reads; transports push received data with feed() */
class BufferedPort {
  constructor() { this.buf = []; this.waiters = []; this.closed = false; }
  feed(bytes) { for (const b of bytes) this.buf.push(b); const w = this.waiters; this.waiters = []; w.forEach((f) => f()); }
  async read(n, timeout = 5000) {
    const end = Date.now() + timeout;
    while (this.buf.length < n && !this.closed) {
      const left = end - Date.now();
      if (left <= 0) break;
      await new Promise((res) => { const t = setTimeout(res, left); this.waiters.push(() => { clearTimeout(t); res(); }); });
    }
    return Uint8Array.from(this.buf.splice(0, Math.min(n, this.buf.length)));
  }
  async drain() { await sleep(50); this.buf = []; }
}

export class WebSerialPort extends BufferedPort {
  static async request(baudRate = 115200) {
    if (!("serial" in navigator)) throw new LinkError("Web Serial is not available in this browser (use Chrome / Edge, or the WebSocket bridge)");
    const sp = await navigator.serial.requestPort();
    await sp.open({ baudRate, dataBits: 8, stopBits: 1, parity: "none", flowControl: "none" });
    const p = new WebSerialPort(); p.sp = sp; p.hardware = true; p.writer = sp.writable.getWriter(); p.pump();
    return p;
  }
  async pump() {
    this.reader = this.sp.readable.getReader();
    try { for (;;) { const { value, done } = await this.reader.read(); if (done) break; this.feed(value); } } catch (e) { /* closed */ }
    this.closed = true;
  }
  async write(b) { await this.writer.write(b); }
  async close() {
    try { await this.reader.cancel(); } catch (e) { /* ignore */ }
    try { this.writer.releaseLock(); } catch (e) { /* ignore */ }
    try { await this.sp.close(); } catch (e) { /* ignore */ }
  }
}

export class WebSocketPort extends BufferedPort {
  static open(url) {
    return new Promise((resolve, reject) => {
      const p = new WebSocketPort();
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      p.ws = ws; p.hardware = false;
      ws.onopen = () => resolve(p);
      ws.onerror = () => reject(new LinkError(`cannot connect to ${url} (is tools/ws_bridge.py running?)`));
      ws.onmessage = (ev) => p.feed(new Uint8Array(ev.data));
      ws.onclose = () => { p.closed = true; p.feed([]); };
    });
  }
  async write(b) { this.ws.send(b); }
  async close() { this.ws.close(); }
}

/** JS model of cfw/app/prog.c + cfwcp.c (same as tests/fake_radio.py) */
export class FakeRadio {
  constructor({ writeProtected = false, ident = "D890CFW" } = {}) {
    this.flash = new Uint8Array(0x20000); this.wp = writeProtected; this.ident = ident;
    this.erased = new Set(); this.writes = 0; this.order = []; this.active = false; this.rx = [];
  }
  valid() {
    try { C.checkHeader(this.flash); return true; } catch (e) { return false; }
  }
  port() {
    const fr = this, p = new BufferedPort();
    p.hardware = false;
    p.write = async (b) => { for (const x of b) fr.rx.push(x); fr.process((out) => setTimeout(() => p.feed(out), 1)); };
    p.close = async () => {};
    return p;
  }
  process(send) {
    const rx = this.rx;
    for (;;) {
      if (!rx.length) return;
      const c = rx[0];
      const need = c === 0x50 ? 7 : c === 0x02 ? 1 : c === 0x52 ? 6 : c === 0x45 ? 3 : c === 0x57 ? (rx.length >= 6 ? 8 + rx[5] : 6) : 1;
      if (c === 0x57 && rx.length < 6) return;
      if (rx.length < need) return;
      const cmd = rx.splice(0, need);
      const s = String.fromCharCode(...cmd);
      if (c === 0x50) { if (s === "PROGRAM") { this.active = true; this.erased = new Set(); send(enc("QX\x06")); } continue; }
      if (!this.active) continue;
      if (c === 0x02) {
        const caps = 1 | (this.wp ? 4 : 2);
        send(Uint8Array.from([0x49, ...enc(this.ident.padEnd(7, "\0").slice(0, 7)), 0, 1, 0, 1, caps, 0, 128, ACK]));
      } else if (c === 0x52) {
        const a = ((cmd[1] << 24) | (cmd[2] << 16) | (cmd[3] << 8) | cmd[4]) >>> 0, n = cmd[5];
        let data;
        if (a >= INFO_ADDR) {
          const info = new Uint8Array(64); const v = new DataView(info.buffer);
          info.set(enc("CFWI"));
          const valid = this.valid(), fv = new DataView(this.flash.buffer);
          [1 | (1 << 16), 0x081c0000, 0x20000, valid ? fv.getUint32(8, true) : 0, valid ? fv.getUint32(12, true) : 0,
            valid ? fv.getUint32(20, true) : 0, 0, 0].forEach((x, i) => v.setUint32(4 + 4 * i, x, true));
          info[36] = valid ? 1 : 0; info[37] = this.wp ? 1 : 0; info[38] = 1; info.set(enc("fake (web)"), 40);
          data = info.slice(a - INFO_ADDR, a - INFO_ADDR + n);
        } else data = this.flash.slice(a, a + n);
        const f = [...cmd.slice(1, 6), ...data];
        send(Uint8Array.from([0x57, ...f, f.reduce((x, y) => x + y, 0) & 0xff, ACK]));
      } else if (c === 0x57) {
        const a = ((cmd[1] << 24) | (cmd[2] << 16) | (cmd[3] << 8) | cmd[4]) >>> 0, n = cmd[5];
        const cs = cmd.slice(1, 6 + n).reduce((x, y) => x + y, 0) & 0xff;
        const ok = cs === cmd[6 + n] && cmd[7 + n] === ACK && !this.wp && a % 16 === 0 && n % 16 === 0 && a + n <= 0x20000;
        if (ok) {
          for (let pg = Math.floor(a / 0x2000); pg <= Math.floor((a + n - 1) / 0x2000); pg++)
            if (!this.erased.has(pg)) { this.flash.fill(0xff, pg * 0x2000, (pg + 1) * 0x2000); this.erased.add(pg); }
          this.flash.set(cmd.slice(6, 6 + n), a); this.writes++; this.order.push(a);
        }
        send(Uint8Array.from([ok ? ACK : NAK]));
      } else if (c === 0x45) {
        this.active = false;
        send(Uint8Array.from([!this.erased.size || this.valid() ? ACK : NAK]));
      }
    }
  }
}

export class Radio {
  constructor(port, log = () => {}) { this.p = port; this.log = log; this.ident = null; }

  async expect(n, what, timeout) {
    const b = await this.p.read(n, timeout);
    if (b.length !== n) throw new LinkError(`${what}: got ${b.length} of ${n} bytes`);
    return b;
  }

  async enter() {
    await this.p.drain();
    let ok = false;
    for (let i = 0; i < 3 && !ok; i++) {
      await this.p.write(enc("PROGRAM"));
      const b = await this.p.read(3, 2000);
      ok = b.length === 3 && b[0] === 0x51 && b[1] === 0x58 && b[2] === ACK;
      if (!ok) await this.p.drain();
    }
    if (!ok) throw new LinkError("no answer to PROGRAM (is the cfw running and the port right?)");
    await this.p.write(Uint8Array.from([0x02]));
    const r = await this.expect(16, "identify");
    if (r[0] !== 0x49 || r[15] !== ACK) throw new LinkError("bad identify reply");
    const id = String.fromCharCode(...r.slice(1, 8));
    const model = Object.keys(C.MODELS).find((m) => C.MODELS[m].ident === id);
    if (!model) throw new LinkError(`radio identifies as '${id.split("\0")[0]}', not the cfw: refusing (this CPS is for the custom firmware only)`);
    this.ident = { fw: `${r[9]}.${r[10]}`, cp_version: r[11], caps: r[12], write_protected: !!(r[12] & 4), max_kb: (r[13] << 8) | r[14], model };
    if (this.ident.cp_version !== C.VERSION) throw new LinkError(`radio codeplug format v${this.ident.cp_version}, this CPS writes v${C.VERSION}`);
    this.log(`radio: ${model} cfw ${this.ident.fw}, codeplug v${this.ident.cp_version}, ${this.ident.max_kb} KB${this.ident.write_protected ? ", WRITE-PROTECTED build" : ""}`);
    return this.ident;
  }

  async readBlock(addr, n) {
    for (let i = 0; i < 3; i++) {
      await this.p.write(Uint8Array.from([0x52, addr >>> 24, (addr >>> 16) & 0xff, (addr >>> 8) & 0xff, addr & 0xff, n]));
      const r = await this.p.read(8 + n);
      const a = ((r[1] << 24) | (r[2] << 16) | (r[3] << 8) | r[4]) >>> 0;
      if (r.length === 8 + n && r[0] === 0x57 && a === addr && r[5] === n && r[7 + n] === ACK &&
          (r.slice(1, 6 + n).reduce((x, y) => x + y, 0) & 0xff) === r[6 + n]) return r.slice(6, 6 + n);
      await this.p.drain();
    }
    throw new LinkError(`read 0x${addr.toString(16)}+${n} failed`);
  }

  async writeBlock(addr, data) {
    const f = [addr >>> 24, (addr >>> 16) & 0xff, (addr >>> 8) & 0xff, addr & 0xff, data.length, ...data];
    await this.p.write(Uint8Array.from([0x57, ...f, f.reduce((x, y) => x + y, 0) & 0xff, ACK]));
    const r = await this.expect(1, "write ack");
    if (r[0] !== ACK) throw new LinkError(`radio refused write at 0x${addr.toString(16)} (${this.ident && this.ident.write_protected ? "write-protected build" : "checksum / range / flash verify"})`);
  }

  async end() { await this.p.write(enc("END")); return (await this.expect(1, "END", 10000))[0] === ACK; }

  async info() {
    const b = await this.readBlock(INFO_ADDR, 64);
    if (String.fromCharCode(...b.slice(0, 4)) !== "CFWI") throw new LinkError("bad info block");
    const v = new DataView(b.buffer, b.byteOffset);
    const u = (i) => v.getUint32(4 + 4 * i, true);
    return { link: u(0) & 0xffff, cp_version: u(0) >>> 16, base: u(1), size: u(2), len: u(3), crc: u(4), generation: u(5),
      cp_channels: u(6), channels: u(7), valid: !!b[36], write_protected: !!b[37],
      fw: String.fromCharCode(...b.slice(40, 64)).split("\0")[0] };
  }

  async readCodeplug(progress) {
    const inf = await this.info();
    if (!inf.valid) return new Uint8Array(0);
    const out = new Uint8Array(inf.len);
    for (let a = 0; a < inf.len; a += CHUNK) {
      out.set(await this.readBlock(a, Math.min(CHUNK, inf.len - a)), a);
      if (progress) progress(Math.min(a + CHUNK, inf.len), inf.len);
    }
    return out;
  }

  async writeCodeplug(data, progress) {
    if (data.length % 16) { const d = new Uint8Array(data.length + 16 - (data.length % 16)); d.set(data); data = d; }
    const blocks = []; for (let a = 0; a < data.length; a += CHUNK) blocks.push(a);
    blocks.push(blocks.shift());                       // header block last: an aborted write leaves no valid codeplug
    for (let k = 0; k < blocks.length; k++) {
      const a = blocks[k];
      await this.writeBlock(a, data.slice(a, a + CHUNK));
      if (progress) progress(k + 1, blocks.length);
    }
  }
}

/** read the radio: {cp|null, raw, info} */
export async function readRadio(port, log = () => {}, progress) {
  const r = new Radio(port, log);
  await r.enter();
  const inf = await r.info();
  log(inf.valid ? `radio holds a valid codeplug, ${inf.len} bytes, generation ${inf.generation}, ${inf.cp_channels} channels`
    : `radio holds no cfw codeplug (NAND / built-in channels, ${inf.channels})`);
  const raw = await r.readCodeplug(progress);
  await r.end();
  inf.model = r.ident.model;
  return { cp: raw.length ? C.decode(raw) : null, raw, info: inf };
}

/** validate, diff against the radio, confirm(lines) -> bool, write, END, read back + compare (as cps/ops.py) */
export async function writeRadio(port, cp, { log = () => {}, confirm = null, progress = null, allowHardware = false } = {}) {
  const errs = C.errors(C.validate(cp));
  if (errs.length) throw new C.CodeplugError(`codeplug has ${errs.length} error(s): ` + errs.slice(0, 5).map(C.issueText).join("; "));
  if (port.hardware && !allowHardware) throw new LinkError("refusing to write to a hardware serial port without the 'allow hardware' switch (real-radio writes need the owner's OK)");
  const r = new Radio(port, log);
  await r.enter();
  if (r.ident.model !== C.modelOf(cp)) { await r.end(); throw new LinkError(`the radio is a ${r.ident.model}, this codeplug is for the ${C.modelOf(cp)} (convert it first: Radio model)`); }
  if (r.ident.write_protected) { await r.end(); throw new LinkError("radio firmware is a write-protected (HW=1) build; nothing written"); }
  const inf = await r.info();
  let old = null;
  if (inf.valid) { try { old = C.decode(await r.readCodeplug()); } catch (e) { old = null; } }
  const neu = C.fromDict(cp);
  neu.generation = (old ? old.generation : inf.generation) + 1;
  neu.created = Math.floor(Date.now() / 1000);
  const data = C.encode(neu);
  if (data.length > inf.size) { await r.end(); throw new C.CodeplugError(`codeplug is ${data.length} bytes, this radio's codeplug region holds ${inf.size} (update the cfw)`); }
  const lines = C.diff(old, neu);
  log(`diff against the radio (${C.diffSummary(old, neu)})`);
  if (confirm && !(await confirm(lines, C.diffSummary(old, neu)))) { await r.end(); log("cancelled, nothing written"); return null; }
  log(`writing ${data.length} bytes ...`);
  await r.writeCodeplug(data, progress);
  if (!(await r.end())) throw new LinkError("radio says the written codeplug is invalid (END -> NAK)");
  const back = await readRadio(port, () => {});
  if (back.raw.length !== data.length || back.raw.some((x, i) => x !== data[i])) throw new LinkError("read-back differs from what was written");
  log(`verified: read back ${back.raw.length} bytes, identical (CRC ${back.info.crc.toString(16).toUpperCase().padStart(8, "0")})`);
  cp.generation = neu.generation; cp.created = neu.created;
  return data;
}
