"""Tkinter GUI for cfw_cps (standard library only).

Tabs: Channels (table + per-mode editor), Zones, Scan lists, Contacts, TG lists, Trunk systems, Settings, Log.
Radio menu: read / write (validation + diff dialog before anything is written, read-back verify after).
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import codeplug as C, validate as V, diff as D, ops, stock as ST, support as SU

MODE_LABEL = {"FM": "FM", "DMR": "DMR", "P25": "P25 Ph1", "P25P2": "P25 Ph2", "NXDN": "NXDN", "DSTAR": "D-STAR", "YSF": "YSF"}


def mhz(hz):
    return "%.5f" % (hz / 1e6) if hz else "0"


def parse_mhz(s):
    s = s.strip()
    return int(round(float(s) * 1e6)) if s and s != "0" else 0


def opt_int(s, base=10):
    s = s.strip()
    return None if s in ("", "-") else int(s, base)


def parse_bandplan(text):
    """'iden:base MHz:spacing Hz:tx offset Hz:bw Hz:slots; ...' -> [BandPlan]"""
    out = []
    for part in (text or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        f = part.split(":")
        if len(f) != 6:
            raise ValueError("band plan entry %r needs iden:MHz:spacing:offset:bw:slots" % part)
        slots = int(f[5])
        out.append(C.BandPlan(int(f[0]), parse_mhz(f[1]), int(f[2]), int(f[3]), int(f[4]), slots > 1, slots))
    return out


def chan_detail(c, cp):
    if c.mode == "FM":
        t = ("25k" if c.wide else "12.5k")
        if c.tx_tone:
            t += " T" + c.tx_tone
        if c.rx_tone:
            t += " R" + c.rx_tone
        return t
    if c.mode == "DMR":
        return "CC%d TS%d TG%d%s" % (c.cc, c.slot, c.tg, " T3" if c.trunk else "")
    if c.mode in ("P25", "P25P2"):
        return "NAC %03X TG%d%s%s" % (c.nac, c.tg, " S%d" % c.slot if c.mode == "P25P2" else "", " TRUNK" if c.trunk else "")
    if c.mode == "NXDN":
        return "RAN%d G%d" % (c.ran, c.tg)
    if c.mode == "DSTAR":
        return "UR %s" % c.ur
    if c.mode == "YSF":
        return "DG-ID %d" % c.dgid
    return ""


class Form(ttk.Frame):
    """A grid of labelled fields: spec = [(key, label, kind, choices)] kind: entry | combo | check."""

    def __init__(self, master, spec, cols=2):
        super().__init__(master)
        self.vars, self.widgets = {}, {}
        for i, (key, label, kind, choices) in enumerate(spec):
            r, c = divmod(i, cols)
            ttk.Label(self, text=label).grid(row=r, column=2 * c, sticky="e", padx=(6, 2), pady=2)
            if kind == "check":
                v = tk.BooleanVar()
                w = ttk.Checkbutton(self, variable=v)
            elif kind == "combo":
                v = tk.StringVar()
                w = ttk.Combobox(self, textvariable=v, values=choices, width=18, state="readonly")
            else:
                v = tk.StringVar()
                w = ttk.Entry(self, textvariable=v, width=20)
            w.grid(row=r, column=2 * c + 1, sticky="w", pady=2)
            self.vars[key], self.widgets[key] = v, w

    def set(self, key, val):
        self.vars[key].set(val)

    def get(self, key):
        return self.vars[key].get()


class ListEditor(ttk.Frame):
    """Named lists of member indices (zones, scan lists, TG lists)."""

    def __init__(self, app, attr, cls, member_names, extra=None):
        super().__init__(app.nb)
        self.app, self.attr, self.cls, self.member_names = app, attr, cls, member_names
        self.member_key = "contacts" if attr == "tglists" else "channels"
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=4, pady=4)
        self.lists = tk.Listbox(left, width=24, exportselection=False)
        self.lists.pack(fill="y", expand=True)
        self.lists.bind("<<ListboxSelect>>", lambda e: self.show())
        b = ttk.Frame(left)
        b.pack(fill="x")
        self.name = tk.StringVar()
        ttk.Entry(left, textvariable=self.name).pack(fill="x")
        for t, f in (("Add", self.add), ("Rename", self.rename), ("Delete", self.delete)):
            ttk.Button(b, text=t, command=f, width=7).pack(side="left")
        mid = ttk.Frame(self)
        mid.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ttk.Label(mid, text="Members (order = priority)").pack(anchor="w")
        self.members = tk.Listbox(mid, exportselection=False, selectmode="extended")
        self.members.pack(fill="both", expand=True)
        b2 = ttk.Frame(mid)
        b2.pack(fill="x")
        for t, f in (("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1)), ("Remove", self.remove)):
            ttk.Button(b2, text=t, command=f, width=7).pack(side="left")
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ttk.Label(right, text="Available (double-click or Add)").pack(anchor="w")
        self.filter = tk.StringVar()
        self.filter.trace_add("write", lambda *a: self.fill_avail())
        ttk.Entry(right, textvariable=self.filter).pack(fill="x")
        self.avail = tk.Listbox(right, exportselection=False, selectmode="extended")
        self.avail.pack(fill="both", expand=True)
        self.avail.bind("<Double-1>", lambda e: self.add_members())
        ttk.Button(right, text="<< Add", command=self.add_members).pack(anchor="w")
        self.extra = extra(self) if extra else None
        self.avail_idx = []

    @property
    def items(self):
        return getattr(self.app.cp, self.attr)

    def refresh(self):
        self.lists.delete(0, "end")
        for i, z in enumerate(self.items):
            self.lists.insert("end", "%d %s" % (i + 1, z.name))
        self.fill_avail()
        self.show()

    def fill_avail(self):
        names = self.member_names()
        f = self.filter.get().lower()
        self.avail.delete(0, "end")
        self.avail_idx = []
        for i, n in enumerate(names):
            if f in n.lower():
                self.avail.insert("end", "%d %s" % (i + 1, n))
                self.avail_idx.append(i)

    def cur(self):
        s = self.lists.curselection()
        return s[0] if s else None

    def show(self):
        self.members.delete(0, "end")
        i = self.cur()
        if i is None:
            return
        self.name.set(self.items[i].name)
        names = self.member_names()
        for m in getattr(self.items[i], self.member_key):
            self.members.insert("end", "%d %s" % (m + 1, names[m] if m < len(names) else "?"))
        if self.extra:
            self.extra.show(self.items[i])

    def add(self):
        self.items.append(self.cls(name=self.name.get()[:16] or "NEW"))
        self.app.dirty()
        self.refresh()
        self.lists.selection_set("end")
        self.show()

    def rename(self):
        i = self.cur()
        if i is not None:
            self.items[i].name = self.name.get()[:16]
            self.app.dirty()
            self.refresh()
            self.lists.selection_set(i)

    def delete(self):
        i = self.cur()
        if i is not None and messagebox.askyesno("Delete", "Delete %r?" % self.items[i].name):
            del self.items[i]
            self.app.fix_refs_after_delete(self.attr, i)
            self.refresh()

    def add_members(self):
        i = self.cur()
        if i is None:
            return
        mem = getattr(self.items[i], self.member_key)
        mem.extend(self.avail_idx[k] for k in self.avail.curselection())
        self.app.dirty()
        self.show()

    def remove(self):
        i = self.cur()
        if i is None:
            return
        mem = getattr(self.items[i], self.member_key)
        for k in sorted(self.members.curselection(), reverse=True):
            del mem[k]
        self.app.dirty()
        self.show()

    def move(self, d):
        i = self.cur()
        sel = self.members.curselection()
        if i is None or len(sel) != 1:
            return
        mem = getattr(self.items[i], self.member_key)
        k = sel[0]
        if 0 <= k + d < len(mem):
            mem[k], mem[k + d] = mem[k + d], mem[k]
            self.app.dirty()
            self.show()
            self.members.selection_set(k + d)


NOT_USED = SU.NOTE          # cfw use per model and stock node / column: schema/cfw_support.json (cps/support.py)


class StockGrid(ttk.Frame):
    """A stock CPS list table (verbatim rows): grid + row editor."""

    def __init__(self, app, table, node=None):
        super().__init__(app.nb)
        self.app, self.table = app, table
        self.cols = ST.TABLES[table]["columns"]
        vis, stored, star = SU.page_marks(app.cp.model, node or table, self.cols, table)
        if stored:                      # columns the firmware uses: no note; mixed table: * on the stored columns
            ttk.Label(self, text="%s  -  %s" % (ST.DIALOGS[table]["title"] if table in ST.DIALOGS else table, SU.STAR_NOTE if star else NOT_USED), foreground="#a05000").pack(anchor="w", padx=6, pady=2)
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(top, columns=list(range(len(self.cols))), show="headings")
        for i, c in enumerate(self.cols):
            self.tv.heading(i, text=ST.LABELS.get(c, c) + (" *" if c in star else ""))
            self.tv.column(i, width=max(60, min(220, 9 * len(ST.LABELS.get(c, c)))), stretch=False)
        xs = ttk.Scrollbar(top, orient="horizontal", command=self.tv.xview)
        ys = ttk.Scrollbar(top, command=self.tv.yview)
        self.tv.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.show())
        ed = ttk.Frame(self)
        ed.pack(fill="x")
        cv = tk.Canvas(ed, height=150)
        sb = ttk.Scrollbar(ed, orient="horizontal", command=cv.xview)
        self.fr = ttk.Frame(cv)
        cv.create_window(0, 0, window=self.fr, anchor="nw")
        cv.configure(xscrollcommand=sb.set)
        cv.pack(fill="x")
        sb.pack(fill="x")
        self.vars = []
        for i, c in enumerate(self.cols):
            r, k = divmod(i, 6)
            ttk.Label(self.fr, text=ST.LABELS.get(c, c) + (" *" if c in star else "")).grid(row=2 * r, column=k, sticky="w", padx=3)
            v = tk.StringVar()
            ttk.Entry(self.fr, textvariable=v, width=18).grid(row=2 * r + 1, column=k, sticky="w", padx=3)
            self.vars.append(v)
        self.fr.update_idletasks()
        cv.configure(scrollregion=cv.bbox("all"), height=min(260, self.fr.winfo_reqheight()))
        b = ttk.Frame(self)
        b.pack(fill="x")
        for t, f in (("Apply", self.apply), ("Add row", self.add), ("Delete row", self.delete)):
            ttk.Button(b, text=t, command=f).pack(side="left")
        self.cur = None

    @property
    def rows(self):
        return self.app.cp.stock.setdefault(self.table, ST.default_rows(self.table))

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(self.rows[:5000]):
            self.tv.insert("", "end", iid=str(i), values=r)

    def show(self):
        sel = self.tv.selection()
        if not sel:
            return
        self.cur = int(sel[0])
        r = self.rows[self.cur]
        for i, v in enumerate(self.vars):
            v.set(r[i] if i < len(r) else "")

    def apply(self):
        if self.cur is None:
            return
        r = self.rows[self.cur]
        for i, v in enumerate(self.vars):
            ST._put(r, i, v.get())
        self.app.dirty()
        self.refresh()

    def add(self):
        d = list(ST.TABLES[self.table]["defaults"]) or [""] * len(self.cols)
        if self.cols[0] in ("No.", "No", "NO."):
            d[0] = str(len(self.rows) + 1)
        self.rows.append(d)
        self.app.dirty()
        self.refresh()

    def delete(self):
        if self.cur is not None and messagebox.askyesno("Delete", "Delete row %d?" % (self.cur + 1)):
            del self.rows[self.cur]
            self.cur = None
            self.app.dirty()
            self.refresh()


class StockRecord(ttk.Frame):
    """A stock CPS settings record (Optional Settings with the stock dialog's tabs, NX Setting, APRS, Alert Tone).
    page: a schema "pages" entry (e.g. D168 Bluetooth) = one group of keys of the record with its own note."""

    def __init__(self, app, table, page=None, node=None):
        super().__init__(app.nb)
        self.app, self.table = app, table
        cols = ST.TABLES[table]["columns"]
        dlg = ST.DIALOGS.get(table)
        node = next((n for n, p in ST.PAGES.items() if p is page), table) if page else node or table
        vis, stored, star = SU.page_marks(app.cp.model, node, page["keys"] if page else cols, table)
        use = "" if not stored else SU.STAR_NOTE if star else NOT_USED
        note = "%s  -  %s Values are the stock CSV values." % (table, use) if use else "%s: values are the stock CSV values." % table
        if dlg:
            note = (dlg["title"] + (": " + use if use else "") + "  " + dlg.get("note", "")).strip()
        elif page:
            note = (page["note"] + "  " + use).strip() + (" Lists show the radio's values." if any(
                k in ST.CHOICES for k in page["keys"]) else " Values are the stock CSV values.")
        ttk.Label(self, text=note, foreground="#a05000" if stored else "", wraplength=900).pack(anchor="w", padx=6, pady=2)
        groups = [[g, list(ks)] for g, ks in dlg["groups"]] if dlg and dlg.get("groups") else [[page["title"], page["keys"]]] if page else ST.SCHEMA["optional_tabs"] if table == "OptionalSetting" else \
            [["%s %d" % (table, i // 40 + 1), cols[i:i + 40]] for i in range(0, len(cols), 40)]
        groups = [[g, [k for k in ks if k in vis]] for g, ks in groups]          # n/a keys hidden
        groups = [g for g in groups if g[1]]
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.vars = {}
        for tab, keys in groups:
            f = ttk.Frame(nb)
            nb.add(f, text=tab)
            for i, k in enumerate(keys):
                r, c = i % 20, i // 20
                ttk.Label(f, text=ST.LABELS.get(k, k) + (" *" if k in star else "")).grid(row=r, column=2 * c, sticky="e", padx=(8, 2), pady=1)
                v = tk.StringVar()
                if k in ST.CHOICES:              # radio value list; a raw value outside it is shown (and kept) as is
                    ttk.Combobox(f, textvariable=v, values=ST.CHOICES[k], width=14).grid(row=r, column=2 * c + 1, sticky="w")
                else:
                    ttk.Entry(f, textvariable=v, width=14).grid(row=r, column=2 * c + 1, sticky="w")
                self.vars[k] = v
        b = ttk.Frame(self)
        b.pack(fill="x")
        ttk.Button(b, text="Apply", command=self.apply).pack(side="left", padx=6, pady=4)
        ttk.Button(b, text="Defaults", command=self.defaults).pack(side="left")

    def refresh(self):
        view = ST.stock_settings_view(self.app.cp, self.table)
        for k, v in self.vars.items():
            v.set(ST.choice_text(k, view.get(k, "")))

    def apply(self):
        for k, v in self.vars.items():
            ST.set_stock_value(self.app.cp, self.table, k, ST.choice_value(k, v.get()))
        self.app.dirty()

    def defaults(self):
        self.app.cp.stock[self.table] = ST.default_rows(self.table)
        self.app.dirty()
        self.refresh()


class InfoPage(ttk.Frame):
    TEXT = {"@device": "Device Information (stock: model, bands, version). cfw: {model}, UHF 400-480 MHz, VHF 136-174 MHz; "
                       "identify the radio with Program > Read / cfw_cps.py info.",
            "@enccode": "Encryption Code (DMR basic privacy keys): kept verbatim inside stock .rdt files (no CSV in the stock "
                        "CPS). cfw keys: cfw Digital Modes > Encryption Keys.",
            "@friends": "Friends List: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
            "@talkalias": "Talk Alias: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
            "@alarm": "Alarm Setting: kept verbatim inside stock .rdt files (no CSV in the stock CPS).",
            "@local": "Local Information: the stock CPS reads it live from the radio over the COM port; nothing of it is in the .rdt or the codeplug.",
            "@masterid": "Master ID: see Radio Settings (DMR / radio ID, callsign)."}

    def __init__(self, app, key):
        super().__init__(app.nb)
        stored = key not in App.CFW_NODE and SU.section(key, app.cp.model) == "stored"
        ttk.Label(self, text=self.TEXT.get(key, key).replace("{model}", app.cp.model) + (" Not used by cfw yet." if stored else ""),
                  wraplength=700).pack(anchor="w", padx=10, pady=10)

    def refresh(self):
        pass


class App:
    def __init__(self, root, path=None, port="tcp:localhost:3470", model="D890UV"):
        self.root = root
        self.cp = C.new_codeplug(model)
        self.nav_model = None
        self.path = None
        self.changed = False
        self.port = tk.StringVar(value=port)
        self.q = queue.Queue()
        self.busy = False
        root.title("cfw CPS")
        root.geometry("1180x700")
        self.build_menu()
        bar = ttk.Frame(root)
        bar.pack(fill="x")
        ttk.Label(bar, text="Radio").pack(side="left", padx=4)
        self.model_var = tk.StringVar(value=self.cp.model)
        mb = ttk.Combobox(bar, textvariable=self.model_var, values=list(C.MODELS), state="readonly", width=8)
        mb.pack(side="left")
        mb.bind("<<ComboboxSelected>>", lambda e: self.set_model(self.model_var.get()))
        ttk.Label(bar, text="Port").pack(side="left", padx=4)
        ttk.Entry(bar, textvariable=self.port, width=26).pack(side="left")
        for t, f in (("Read radio", self.read_radio), ("Write radio", self.write_radio), ("Validate", self.validate)):
            ttk.Button(bar, text=t, command=f).pack(side="left", padx=2)
        self.status = tk.StringVar()
        ttk.Label(bar, textvariable=self.status).pack(side="left", padx=10)
        self.prog = ttk.Progressbar(bar, length=180)
        self.prog.pack(side="right", padx=4)
        pw = ttk.PanedWindow(root, orient="horizontal")
        pw.pack(fill="both", expand=True)
        self.nav = ttk.Treeview(pw, show="tree", selectmode="browse")
        pw.add(self.nav, weight=0)
        self.nb = ttk.Frame(pw)
        pw.add(self.nb, weight=1)
        self.pages, self.page_builders, self.cur_page = {}, {}, None
        self.build_channels()
        self.zones = ListEditor(self, "zones", C.Zone, lambda: [c.name for c in self.cp.channels])
        self.scans = ListEditor(self, "scanlists", C.ScanList, lambda: [c.name for c in self.cp.channels])
        self.build_contacts()
        self.tgl = ListEditor(self, "tglists", C.TgList, lambda: ["%s (%d)" % (c.name, c.id) for c in self.cp.contacts])
        self.build_trunk()
        self.build_settings()
        self.build_keys()
        self.build_dstar()
        self.build_digi()
        self.log = tk.Text(self.nb, wrap="none", font="TkFixedFont")
        for key, w in (("channels", self.chan_tab), ("zones", self.zones), ("scanlists", self.scans),
                       ("contacts", self.ct_tab), ("tglists", self.tgl), ("trunksys", self.ts_tab), ("settings", self.set_tab),
                       ("keys", self.keys_tab), ("dstar", self.dstar_tab), ("digi", self.digi_tab), ("log", self.log)):
            self.pages[key] = w
        self.build_nav()
        root.after(100, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if path:
            self.open(path)
        else:
            self.refresh_all()

    # ------------------------------------------------------------ menus / files
    def build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        for m_ in C.MODELS:
            f.add_command(label="New %s codeplug" % m_, command=lambda m_=m_: self.new(m_))
        f.add_command(label="Open...", command=lambda: self.open(None))
        f.add_command(label="Import .rdt (D890UV / D168UV / D878UV) / .csv / stock CSV set (.LST) / D890UV image...",
                      command=self.import_)
        rm = tk.Menu(f, tearoff=0)
        self.model_menu_var = tk.StringVar(value=self.cp.model)
        for m_ in C.MODELS:
            rm.add_radiobutton(label=m_, variable=self.model_menu_var, value=m_, command=lambda m_=m_: self.set_model(m_))
        f.add_cascade(label="Radio model (convert)", menu=rm)
        f.add_command(label="Export stock CSV set (.LST, like the stock CPS Export All)...", command=self.export_lst)
        f.add_command(label="Print to file (HTML report)...", command=self.print_report)
        f.add_separator()
        f.add_command(label="Save", command=self.save)
        f.add_command(label="Save as...", command=lambda: self.save(True))
        f.add_command(label="Export JSON / YAML / CSV...", command=self.export)
        f.add_separator()
        f.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        r = tk.Menu(m, tearoff=0)
        r.add_command(label="Read from radio", command=self.read_radio)
        r.add_command(label="Write to radio (shows diff first)", command=self.write_radio)
        m.add_cascade(label="Radio", menu=r)
        t = tk.Menu(m, tearoff=0)
        t.add_command(label="Validate", command=self.validate)
        t.add_command(label="Diff against file...", command=self.diff_file)
        m.add_cascade(label="Tools", menu=t)
        self.root.config(menu=m)

    def say(self, s):
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.status.set(s[:90])

    def dirty(self):
        self.changed = True
        self.title()

    def title(self):
        self.root.title("cfw CPS [%s] - %s%s" % (self.cp.model, os.path.basename(self.path) if self.path else "untitled",
                                                 " *" if self.changed else ""))

    def check_discard(self):
        return not self.changed or messagebox.askyesno("Unsaved changes", "Discard unsaved changes?")

    def new(self, model=None):
        if self.check_discard():
            self.cp, self.path, self.changed = C.new_codeplug(model or self.cp.model), None, False
            self.refresh_all()

    def set_model(self, model):
        """convert the codeplug to another radio model (stock CPS data of the other model is mapped by column name)"""
        if model == self.cp.model:
            return
        if self.cp.channels and not messagebox.askyesno(
                "Radio model", "Convert this codeplug from %s to %s?\n\ncfw channels, zones, contacts and digital-mode "
                "settings are kept. Stock CPS settings are mapped by name; those the %s CPS does not have are dropped."
                % (self.cp.model, model, model)):
            self.model_var.set(self.cp.model)
            self.model_menu_var.set(self.cp.model)
            return
        ST.convert_model(self.cp, model)
        self.say("converted to the %s" % model)
        self.dirty()
        self.refresh_all()

    def open(self, path):
        if path is None:
            if not self.check_discard():
                return
            path = filedialog.askopenfilename(filetypes=[("codeplug", "*.d8cp *.json *.yaml *.yml *.rdt *.LST"), ("all", "*")])
            if not path:
                return
        try:
            self.cp = C.load(path)
        except Exception as e:                  # noqa: BLE001
            messagebox.showerror("Open", str(e))
            return
        self.path, self.changed = path, False
        self.say("opened %s: %d channels" % (path, len(self.cp.channels)))
        self.refresh_all()

    def import_(self):
        if not self.check_discard():
            return
        path = filedialog.askopenfilename(filetypes=[("AnyTone CPS", "*.rdt"), ("CSV (CHIRP / cfw)", "*.csv"),
                                                     ("stock CSV set", "*.LST"),
                                                     ("D890UV image / writes.bin", "*.bin *.img"), ("all", "*")])
        if not path:
            return
        try:
            cp, rep = ops.import_any(path)
        except Exception as e:                  # noqa: BLE001
            messagebox.showerror("Import", str(e))
            return
        self.cp, self.path, self.changed = cp, None, True
        for l in rep:
            self.say(l)
        self.refresh_all()
        self.validate()

    def save(self, ask=False):
        if ask or not self.path or not self.path.lower().endswith((".d8cp", ".json", ".yaml", ".yml", ".rdt")):
            p = filedialog.asksaveasfilename(defaultextension=".d8cp",
                                             filetypes=[("cfw codeplug", "*.d8cp"), ("JSON", "*.json"), ("YAML", "*.yaml"),
                                                        ("stock %s CPS file" % self.cp.model, "*.rdt")])
            if not p:
                return
            self.path = p
        try:
            if self.path.lower().endswith(".rdt"):
                from . import rdt
                try:
                    lost = rdt.save(self.cp, self.path)
                except rdt.RdtError as e:
                    if rdt.template_path(self.cp.model) is not None or "template" not in str(e):
                        raise
                    messagebox.showinfo("Save .rdt", str(e) + "\n\nPick that stock CPS file now.")
                    t = filedialog.askopenfilename(title="stock %s CPS new file (template)" % self.cp.model,
                                                   filetypes=[("stock CPS file", "*.rdt"), ("all", "*")])
                    if not t:
                        return
                    rdt.set_template(t, self.cp.model)
                    lost = rdt.save(self.cp, self.path)
                if lost:
                    messagebox.showwarning("Save .rdt", "Saved. Not written into the .rdt (these stock tables live in the part "
                                           "of the file that is not decoded yet; use File > Export stock CSV set):\n"
                                           + "\n".join(lost))
            else:
                C.save(self.cp, self.path)
        except Exception as e:                  # noqa: BLE001
            messagebox.showerror("Save", str(e))
            return
        self.changed = False
        self.title()
        self.say("saved %s" % self.path)

    def export(self):
        p = filedialog.asksaveasfilename(filetypes=[("JSON", "*.json"), ("YAML", "*.yaml"), ("CSV", "*.csv")])
        if not p:
            return
        if p.lower().endswith(".csv"):
            from . import import_csv
            open(p, "w").write(import_csv.export_csv(self.cp))
        else:
            C.save(self.cp, p)
        self.say("exported %s" % p)

    def export_lst(self):
        p = filedialog.asksaveasfilename(defaultextension=".LST", filetypes=[("stock CSV set", "*.LST")])
        if p:
            ST.write_csv_set(ST.to_stock(self.cp), p)
            self.say("exported stock CSV set %s (+ %d CSV files)" % (p, len(ST.ORDER)))

    def print_report(self):
        from . import report
        p = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML", "*.html"), ("text", "*.txt")])
        if p:
            open(p, "w").write(report.html(self.cp) if p.lower().endswith(".html") else report.text(self.cp))
            self.say("report written to %s" % p)

    def quit(self):
        if self.check_discard():
            self.root.destroy()

    # ------------------------------------------------------------ channels
    def build_channels(self):
        t = self.chan_tab = ttk.Frame(self.nb)
        left = ttk.Frame(t)
        left.pack(side="left", fill="both", expand=True)
        cols = ("n", "name", "rx", "tx", "mode", "detail", "power")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c, w, h in zip(cols, (50, 140, 90, 90, 70, 200, 55), ("#", "Name", "RX MHz", "TX MHz", "Mode", "Details", "Power")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, stretch=c == "detail")
        sb = ttk.Scrollbar(left, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.edit_channel())
        b = ttk.Frame(left)
        b.pack(fill="x")
        for txt, f in (("New", self.ch_new), ("Duplicate", self.ch_dup), ("Delete", self.ch_del),
                       ("Up", lambda: self.ch_move(-1)), ("Down", lambda: self.ch_move(1))):
            ttk.Button(b, text=txt, command=f).pack(side="left")
        self.ch_count = tk.StringVar()
        ttk.Label(b, textvariable=self.ch_count).pack(side="right")
        right = ttk.LabelFrame(t, text="Channel")
        right.pack(side="left", fill="y", padx=4, pady=4)
        self.cf = Form(right, [("name", "Name", "entry", None), ("mode", "Mode", "combo", C.MODES),
                               ("rx", "RX MHz", "entry", None), ("tx", "TX MHz (0 = RX only)", "entry", None),
                               ("power", "Power", "combo", C.POWERS), ("scanlist", "Scan list #", "entry", None),
                               ("scan_skip", "Scan skip", "check", None), ("trunk", "Trunk CC / Tier III", "check", None),
                               ("talkaround", "Talkaround (simplex)", "check", None)],
                       cols=1)
        self.cf.pack(anchor="nw")
        self.cf.widgets["mode"].bind("<<ComboboxSelected>>", lambda e: self.show_mode_frame(self.cf.get("mode")))
        self.mode_box = ttk.LabelFrame(right, text="Mode settings")
        self.mode_box.pack(fill="x", pady=4)
        self.mf = {
            "FM": Form(self.mode_box, [("wide", "25 kHz", "check", None), ("rx_tone", "RX tone (88.5 / D023N)", "entry", None),
                                       ("tx_tone", "TX tone", "entry", None)], 1),
            "DMR": Form(self.mode_box, [("cc", "Colour code", "entry", None), ("slot", "Time slot", "combo", ["1", "2"]),
                                        ("tg", "Talkgroup", "entry", None), ("contact", "Contact #", "entry", None),
                                        ("tglist", "TG list #", "entry", None), ("trunksys", "Tier III system #", "entry", None),
                                        ("vocoder", "Vocoder", "combo", C.MODE_VOCODERS["DMR"]), ("key", "Encryption key #", "entry", None),
                                        ("tdma_direct", "TDMA direct (dual-capacity simplex)", "check", None)], 1),
            "P25": Form(self.mode_box, [("nac", "NAC (hex)", "entry", None), ("tg", "Talkgroup", "entry", None),
                                        ("slot", "Slot (Ph2)", "combo", ["1", "2"]), ("wacn", "WACN (hex)", "entry", None),
                                        ("sysid", "System ID (hex)", "entry", None), ("contact", "Contact #", "entry", None),
                                        ("tglist", "TG list #", "entry", None), ("trunksys", "Trunk system #", "entry", None),
                                        ("vocoder", "Vocoder", "combo", ["auto", "IMBE", "AMBE+2 half-rate"]),
                                        ("key", "Encryption key #", "entry", None)], 1),
            "NXDN": Form(self.mode_box, [("ran", "RAN", "entry", None), ("tg", "Group", "entry", None),
                                         ("contact", "Contact #", "entry", None), ("tglist", "TG list #", "entry", None),
                                         ("trunksys", "Type-C/D system #", "entry", None), ("nxdn_rate", "Rate", "combo", ["4800", "9600"]),
                                         ("vocoder", "Vocoder", "combo", C.MODE_VOCODERS["NXDN"]), ("key", "Encryption key #", "entry", None)], 1),
            "DSTAR": Form(self.mode_box, [("ur", "UR", "entry", None), ("rpt1", "RPT1", "entry", None),
                                          ("rpt2", "RPT2", "entry", None), ("dstar_rpt", "Repeater list #", "entry", None),
                                          ("vocoder", "Vocoder", "combo", C.MODE_VOCODERS["DSTAR"])], 1),
            "YSF": Form(self.mode_box, [("dgid", "RX DG-ID (0 = all)", "entry", None), ("dgid_tx", "TX DG-ID (empty = RX)", "entry", None),
                                        ("ysf_mode", "Mode", "combo", C.YSF_MODES), ("wiresx", "Wires-X", "check", None),
                                        ("vocoder", "Vocoder", "combo", C.MODE_VOCODERS["YSF"])], 1),
        }
        self.mf["P25P2"] = self.mf["P25"]
        bb = ttk.Frame(right)
        bb.pack(fill="x", pady=4)
        ttk.Button(bb, text="Stock settings...", command=self.ch_stock).pack(side="left")
        ttk.Button(bb, text="Apply", command=self.ch_apply).pack(side="right")
        self.ch_msg = tk.StringVar()
        ttk.Label(right, textvariable=self.ch_msg, foreground="red", wraplength=300).pack(anchor="w")
        self.cur_ch = None

    def show_mode_frame(self, mode):
        for f in set(self.mf.values()):
            f.pack_forget()
        self.mf[mode].pack(anchor="nw")
        self.mode_box.config(text="%s settings" % MODE_LABEL[mode])

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.cp.channels):
            self.tree.insert("", "end", iid=str(i), values=(i + 1, c.name, mhz(c.rx_hz), mhz(c.tx_hz), MODE_LABEL[c.mode],
                                                            chan_detail(c, self.cp), c.power))
        self.ch_count.set("%d channels" % len(self.cp.channels))

    def update_row(self, i):
        c = self.cp.channels[i]
        self.tree.item(str(i), values=(i + 1, c.name, mhz(c.rx_hz), mhz(c.tx_hz), MODE_LABEL[c.mode],
                                       chan_detail(c, self.cp), c.power))

    def edit_channel(self):
        sel = self.tree.selection()
        if len(sel) != 1:
            return
        i = int(sel[0])
        self.cur_ch = i
        c = self.cp.channels[i]
        f = self.cf
        f.set("name", c.name)
        f.set("mode", c.mode)
        f.set("rx", mhz(c.rx_hz))
        f.set("tx", mhz(c.tx_hz))
        f.set("power", c.power)
        f.set("scanlist", "" if c.scanlist is None else str(c.scanlist + 1))
        f.set("scan_skip", c.scan_skip)
        f.set("trunk", c.trunk)
        f.set("talkaround", c.talkaround)
        ref = lambda v: "" if v is None else str(v + 1)       # noqa: E731
        for k in ("DMR", "P25", "NXDN", "DSTAR", "YSF"):
            self.mf[k].set("vocoder", c.vocoder if c.mode in (k, "P25P2" if k == "P25" else k) else "auto")
        for k in ("DMR", "P25", "NXDN"):
            self.mf[k].set("key", ref(c.key))
        self.mf["NXDN"].set("trunksys", ref(c.trunksys))
        self.mf["NXDN"].set("nxdn_rate", str(c.nxdn_rate))
        self.mf["DSTAR"].set("dstar_rpt", ref(c.dstar_rpt))
        self.mf["YSF"].set("dgid_tx", "" if c.dgid_tx is None else str(c.dgid_tx))
        self.mf["YSF"].set("ysf_mode", c.ysf_mode)
        self.mf["YSF"].set("wiresx", c.wiresx)
        self.mf["DMR"].set("tdma_direct", c.tdma_direct)
        m = self.mf
        m["FM"].set("wide", c.wide)
        m["FM"].set("rx_tone", c.rx_tone or "")
        m["FM"].set("tx_tone", c.tx_tone or "")
        m["DMR"].set("cc", str(c.cc))
        m["DMR"].set("slot", str(c.slot or 1))
        for k in ("DMR", "P25", "NXDN"):
            m[k].set("tg", str(c.tg))
            m[k].set("contact", ref(c.contact))
            m[k].set("tglist", ref(c.tglist))
        m["DMR"].set("trunksys", ref(c.trunksys))
        m["P25"].set("trunksys", ref(c.trunksys))
        m["P25"].set("nac", "%X" % c.nac)
        m["P25"].set("slot", str(c.slot or 1))
        m["P25"].set("wacn", "%X" % c.wacn)
        m["P25"].set("sysid", "%X" % c.sysid)
        m["NXDN"].set("ran", str(c.ran))
        for k in ("ur", "rpt1", "rpt2"):
            m["DSTAR"].set(k, getattr(c, k))
        m["YSF"].set("dgid", str(c.dgid))
        self.show_mode_frame(c.mode)
        self.ch_msg.set("")

    def ch_apply(self):
        i = self.cur_ch
        if i is None:
            return
        f, m = self.cf, self.mf
        mode = f.get("mode")
        c = C.channel_defaults_for(mode)
        try:
            c.name = f.get("name")[:16]
            c.rx_hz, c.tx_hz = parse_mhz(f.get("rx")), parse_mhz(f.get("tx"))
            c.power = f.get("power")
            sl = opt_int(f.get("scanlist"))
            c.scanlist = None if sl is None else sl - 1
            c.scan_skip, c.trunk = bool(f.get("scan_skip")), bool(f.get("trunk"))
            c.talkaround = bool(f.get("talkaround"))
            ref = lambda s: None if opt_int(s) is None else opt_int(s) - 1   # noqa: E731
            fm = {"P25P2": "P25"}.get(mode, mode)
            if fm in ("DMR", "P25", "NXDN", "DSTAR", "YSF"):
                c.vocoder = m[fm].get("vocoder") or "auto"
            if fm in ("DMR", "P25", "NXDN"):
                c.key = ref(m[fm].get("key"))
            if mode == "FM":
                c.wide = bool(m["FM"].get("wide"))
                c.rx_tone = m["FM"].get("rx_tone").strip() or None
                c.tx_tone = m["FM"].get("tx_tone").strip() or None
            elif mode == "DMR":
                g = m["DMR"]
                c.cc, c.slot, c.tg = int(g.get("cc")), int(g.get("slot")), int(g.get("tg"))
                c.contact, c.tglist, c.trunksys = ref(g.get("contact")), ref(g.get("tglist")), ref(g.get("trunksys"))
                c.tdma_direct = bool(g.get("tdma_direct"))
            elif mode in ("P25", "P25P2"):
                g = m["P25"]
                c.nac, c.tg = int(g.get("nac"), 16), int(g.get("tg"))
                c.slot = int(g.get("slot")) if mode == "P25P2" else 0
                c.wacn, c.sysid = int(g.get("wacn") or "0", 16), int(g.get("sysid") or "0", 16)
                c.contact, c.tglist, c.trunksys = ref(g.get("contact")), ref(g.get("tglist")), ref(g.get("trunksys"))
            elif mode == "NXDN":
                g = m["NXDN"]
                c.ran, c.tg = int(g.get("ran")), int(g.get("tg"))
                c.contact, c.tglist, c.trunksys = ref(g.get("contact")), ref(g.get("tglist")), ref(g.get("trunksys"))
                c.nxdn_rate = int(g.get("nxdn_rate") or 4800)
            elif mode == "DSTAR":
                c.ur, c.rpt1, c.rpt2 = [m["DSTAR"].get(k).upper()[:8] for k in ("ur", "rpt1", "rpt2")]
                c.dstar_rpt = ref(m["DSTAR"].get("dstar_rpt"))
            elif mode == "YSF":
                c.dgid = int(m["YSF"].get("dgid"))
                dt = m["YSF"].get("dgid_tx").strip()
                c.dgid_tx = int(dt) if dt else None
                c.ysf_mode, c.wiresx = m["YSF"].get("ysf_mode") or "DN", bool(m["YSF"].get("wiresx"))
        except ValueError as e:
            self.ch_msg.set("invalid value: %s" % e)
            return
        c.stock = dict(self.cp.channels[i].stock)
        C.normalize_channel(c)
        ST.clear_mapped_overrides(c, "Channel")
        if hasattr(self.cp.channels[i], "_rdt"):
            c._rdt = self.cp.channels[i]._rdt          # keep the stock .rdt bytes cfw does not model
        ST.rename_channel_refs(self.cp, ST.channel_key(self.cp.channels[i]), ST.channel_key(c))
        tmp = C.Codeplug(settings=self.cp.settings, channels=[c], scanlists=self.cp.scanlists, contacts=self.cp.contacts,
                         tglists=self.cp.tglists, trunksys=self.cp.trunksys, keys=self.cp.keys, dstar_rpts=self.cp.dstar_rpts)
        errs = [x.msg for x in V.errors(V.validate(tmp)) if x.where.startswith("ch ")]
        self.ch_msg.set("; ".join(errs))
        self.cp.channels[i] = c
        self.update_row(i)
        self.dirty()

    def ch_stock(self):
        """the stock CPS channel columns cfw does not model, for the selected channel (stored, not used by cfw yet)"""
        i = self.cur_ch
        if i is None:
            return
        c = self.cp.channels[i]
        gen = ST._row("Channel", c, self.cp, {})
        cols, stored, star = SU.channel_marks(self.cp.model, [k for k in ST.CH_COLS if k not in ST.TABLES["Channel"]["cfw_mapped"]])
        w = tk.Toplevel(self.root)
        w.title("Channel %d: stock CPS settings%s" % (i + 1, "" if not stored else " (%s)" % SU.STAR_NOTE if star
                                                       else " (stored, not used by cfw yet)"))
        cv = tk.Canvas(w, width=560, height=560)
        sb = ttk.Scrollbar(w, command=cv.yview)
        fr = ttk.Frame(cv)
        cv.create_window(0, 0, window=fr, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        vars_ = {}
        for r, k in enumerate(cols):
            ttk.Label(fr, text=k + (" *" if k in star else "")).grid(row=r, column=0, sticky="e", padx=4)
            v = tk.StringVar(value=c.stock.get(k, gen.get(k, "")))
            ttk.Entry(fr, textvariable=v, width=28).grid(row=r, column=1, sticky="w")
            vars_[k] = v
        fr.update_idletasks()
        cv.configure(scrollregion=cv.bbox("all"))

        def ok():
            for k, v in vars_.items():
                val = v.get()
                if val == gen.get(k, ""):
                    c.stock.pop(k, None)
                else:
                    c.stock[k] = val
            self.dirty()
            w.destroy()
        ttk.Button(fr, text="OK", command=ok).grid(row=len(cols), column=1, sticky="e", pady=6)

    def ch_new(self):
        i = self.cur_ch + 1 if self.cur_ch is not None else len(self.cp.channels)
        self.insert_channel(i, C.normalize_channel(C.Channel(name="NEW %d" % (len(self.cp.channels) + 1))))

    def ch_dup(self):
        if self.cur_ch is not None:
            import copy
            self.insert_channel(self.cur_ch + 1, copy.deepcopy(self.cp.channels[self.cur_ch]))

    def insert_channel(self, i, c):
        self.cp.channels.insert(i, c)
        self.shift_channel_refs(lambda k: k + 1 if k >= i else k)
        self.dirty()
        self.fill_tree()
        self.tree.selection_set(str(i))
        self.tree.see(str(i))

    def ch_del(self):
        sel = sorted((int(s) for s in self.tree.selection()), reverse=True)
        if not sel or not messagebox.askyesno("Delete", "Delete %d channel(s)?" % len(sel)):
            return
        for i in sel:
            del self.cp.channels[i]
            self.shift_channel_refs(lambda k, i=i: None if k == i else (k - 1 if k > i else k))
        self.cur_ch = None
        self.dirty()
        self.fill_tree()

    def ch_move(self, d):
        i = self.cur_ch
        if i is None or not 0 <= i + d < len(self.cp.channels):
            return
        ch = self.cp.channels
        ch[i], ch[i + d] = ch[i + d], ch[i]
        self.shift_channel_refs(lambda k: i + d if k == i else (i if k == i + d else k))
        self.dirty()
        self.fill_tree()
        self.tree.selection_set(str(i + d))
        self.tree.see(str(i + d))

    def shift_channel_refs(self, f):
        for lst in self.cp.zones + self.cp.scanlists:
            lst.channels[:] = [x for x in (f(k) for k in lst.channels) if x is not None]
        for s in self.cp.scanlists:
            s.prio1 = None if s.prio1 is None else f(s.prio1)
            s.prio2 = None if s.prio2 is None else f(s.prio2)
        if self.cp.settings.start_channel is not None:
            self.cp.settings.start_channel = f(self.cp.settings.start_channel)

    def fix_refs_after_delete(self, attr, i):
        """A zone/scan list/TG list/contact/trunk system was deleted: fix indices that point at it or past it."""
        g = lambda v: None if v is None or v == i else (v - 1 if v > i else v)   # noqa: E731
        key = {"scanlists": "scanlist", "tglists": "tglist", "contacts": "contact", "trunksys": "trunksys", "keys": "key",
               "dstar_rpts": "dstar_rpt"}.get(attr)
        if key:
            for c in self.cp.channels:
                setattr(c, key, g(getattr(c, key)))
        if attr == "contacts":
            for t in self.cp.tglists:
                t.contacts[:] = [x for x in (g(k) for k in t.contacts) if x is not None]
        if attr == "tglists":
            for t in self.cp.trunksys:
                t.tglist = g(t.tglist)
        self.dirty()

    # ------------------------------------------------------------ contacts / trunk systems (table + form)
    def table_tab(self, attr, cls, cols, spec, to_form, from_form):
        t = ttk.Frame(self.nb)
        tree = ttk.Treeview(t, columns=[c[0] for c in cols], show="headings")
        for k, h, w in cols:
            tree.heading(k, text=h)
            tree.column(k, width=w)
        tree.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(t)
        right.pack(side="left", fill="y", padx=4)
        form = Form(right, spec, 1)
        form.pack()
        msg = tk.StringVar()
        st = {"i": None}

        def fill():
            tree.delete(*tree.get_children())
            for i, x in enumerate(getattr(self.cp, attr)):
                tree.insert("", "end", iid=str(i), values=[i + 1] + [v for v in to_form(x).values()][:len(cols) - 1])

        def sel(e=None):
            s = tree.selection()
            if s:
                st["i"] = int(s[0])
                for k, v in to_form(getattr(self.cp, attr)[st["i"]]).items():
                    form.set(k, v)

        def apply():
            if st["i"] is None:
                return
            try:
                getattr(self.cp, attr)[st["i"]] = from_form(form)
                msg.set("")
            except (ValueError, KeyError) as e:
                msg.set("invalid: %s" % e)
                return
            self.dirty()
            fill()

        def add():
            getattr(self.cp, attr).append(cls(name="NEW"))
            self.dirty()
            fill()

        def delete():
            if st["i"] is not None and messagebox.askyesno("Delete", "Delete entry %d?" % (st["i"] + 1)):
                del getattr(self.cp, attr)[st["i"]]
                self.fix_refs_after_delete(attr, st["i"])
                st["i"] = None
                fill()
        tree.bind("<<TreeviewSelect>>", sel)
        b = ttk.Frame(right)
        b.pack(fill="x", pady=4)
        for txt, f in (("Apply", apply), ("Add", add), ("Delete", delete)):
            ttk.Button(b, text=txt, command=f).pack(side="left")
        ttk.Label(right, textvariable=msg, foreground="red").pack()
        t.fill = fill
        return t

    def build_contacts(self):
        self.ct_tab = self.table_tab(
            "contacts", C.Contact, [("n", "#", 50), ("name", "Name", 160), ("id", "ID", 100), ("kind", "Kind", 80),
                                    ("mode", "Mode", 70)],
            [("name", "Name", "entry", None), ("id", "ID", "entry", None), ("kind", "Kind", "combo", C.CONTACT_KINDS),
             ("mode", "Mode", "combo", list(C.CONTACT_MODES))],
            lambda x: {"name": x.name, "id": str(x.id), "kind": x.kind, "mode": x.mode},
            lambda f: C.Contact(f.get("name")[:16], int(f.get("id")), f.get("kind"), f.get("mode")))

    def build_trunk(self):
        def to_form(t):
            return {"name": t.name, "type": t.type, "nac_cc": "%X" % t.nac_cc, "wacn": "%X" % t.wacn,
                    "sysid": "%X" % t.sysid, "ccs": " ".join(mhz(f) for f in t.control_channels),
                    "tglist": "" if t.tglist is None else str(t.tglist + 1), "step": str(t.chan_step_hz),
                    "base": mhz(t.base_hz), "rfss": str(t.rfss), "site": str(t.site), "registration": t.registration,
                    "phase2": t.phase2, "bandplan": "; ".join("%d:%s:%d:%d:%d:%d" % (b.iden, mhz(b.base_hz), b.spacing_hz,
                                                                                    b.tx_offset_hz, b.bw_hz, b.slots)
                                                              for b in t.bandplan)}

        def from_form(f):
            tl = opt_int(f.get("tglist"))
            return C.TrunkSystem(f.get("name")[:16], f.get("type"), int(f.get("nac_cc") or "0", 16),
                                 int(f.get("wacn") or "0", 16), int(f.get("sysid") or "0", 16),
                                 None if tl is None else tl - 1,
                                 [parse_mhz(x) for x in f.get("ccs").replace(",", " ").split()],
                                 int(f.get("step") or "12500"), parse_mhz(f.get("base")), 0,
                                 int(f.get("rfss") or 0), int(f.get("site") or 0), bool(f.get("registration")),
                                 bool(f.get("phase2")), parse_bandplan(f.get("bandplan")))
        self.ts_tab = self.table_tab(
            "trunksys", C.TrunkSystem, [("n", "#", 50), ("name", "Name", 160), ("type", "Type", 70), ("nac", "NAC/CC", 70),
                                        ("wacn", "WACN", 70), ("sysid", "SysID", 60), ("ccs", "Control channels MHz", 260)],
            [("name", "Name", "entry", None), ("type", "Type", "combo", list(C.TRUNK_TYPES)),
             ("rfss", "RFSS / area", "entry", None), ("site", "Site", "entry", None),
             ("registration", "Register (needs TX)", "check", None), ("phase2", "P25 Phase 2 TDMA", "check", None),
             ("bandplan", "Band plan iden:MHz:spacing:offset:bw:slots;...", "entry", None),
             ("nac_cc", "NAC / CC (hex)", "entry", None), ("wacn", "WACN (hex)", "entry", None),
             ("sysid", "System ID (hex)", "entry", None), ("ccs", "Control channels (MHz)", "entry", None),
             ("tglist", "TG priority list #", "entry", None), ("step", "T3 channel step Hz", "entry", None),
             ("base", "T3 LPCN1 MHz (0 = CC)", "entry", None)],
            to_form, from_form)

    def build_keys(self):
        self.keys_tab = self.table_tab(
            "keys", C.Key, [("n", "#", 50), ("name", "Name", 160), ("kind", "Kind", 110), ("key_id", "Key ID", 70),
                            ("algid", "ALGID", 60)],
            [("name", "Name", "entry", None), ("kind", "Kind", "combo", list(C.KEY_KINDS)), ("key_id", "Key ID", "entry", None),
             ("algid", "ALGID (hex)", "entry", None), ("hex", "Key (hex, user-entered)", "entry", None)],
            lambda k: {"name": k.name, "kind": k.kind, "key_id": str(k.key_id), "algid": "%02X" % k.algid, "hex": k.hex},
            lambda f: C.Key(f.get("name")[:16], f.get("kind"), int(f.get("key_id") or 0), int(f.get("algid") or "0", 16),
                            f.get("hex").replace(" ", "").upper()))

    def build_dstar(self):
        self.dstar_tab = self.table_tab(
            "dstar_rpts", C.DstarRepeater, [("n", "#", 50), ("name", "Name", 160), ("rpt1", "RPT1", 90), ("rpt2", "RPT2", 90),
                                            ("rx", "RX MHz", 90), ("tx", "TX MHz", 90)],
            [("name", "Name", "entry", None), ("rpt1", "RPT1 (repeater + module)", "entry", None),
             ("rpt2", "RPT2 (gateway)", "entry", None), ("rx", "RX MHz", "entry", None), ("tx", "TX MHz", "entry", None),
             ("gps", "GPS / D-PRS", "check", None)],
            lambda r: {"name": r.name, "rpt1": r.rpt1, "rpt2": r.rpt2, "rx": mhz(r.rx_hz), "tx": mhz(r.tx_hz), "gps": r.gps},
            lambda f: C.DstarRepeater(f.get("name")[:16], f.get("rpt1").upper()[:8], f.get("rpt2").upper()[:8],
                                      parse_mhz(f.get("rx")), parse_mhz(f.get("tx")), bool(f.get("gps"))))

    DIGI_SPEC = [("dstar_dprs", "D-STAR: send GPS as D-PRS", "check", None), ("dstar_gps_interval_s", "D-PRS interval s (0 = each TX)", "entry", None),
                 ("dstar_auto_reply", "D-STAR auto reply", "check", None), ("dprs_symbol", "D-PRS symbol", "entry", None),
                 ("dprs_comment", "D-PRS comment", "entry", None), ("ysf_mode", "YSF default mode", "combo", C.YSF_MODES),
                 ("ysf_wiresx_room", "Wires-X room", "entry", None), ("ysf_wiresx_auto", "Wires-X auto connect", "check", None),
                 ("dmr_t3_register", "DMR Tier III registration (needs TX)", "check", None),
                 ("p25_register", "P25 registration (needs TX)", "check", None), ("nxdn_register", "NXDN registration (needs TX)", "check", None)]

    def build_digi(self):
        t = self.digi_tab = ttk.Frame(self.nb)
        ttk.Label(t, text="Digital-mode settings (cfw). D-STAR MY / UR / RPT, slow-data message, P25 / NXDN unit IDs: Radio Settings.").pack(anchor="w", padx=6, pady=4)
        self.df = Form(t, self.DIGI_SPEC, cols=2)
        self.df.pack(anchor="nw", padx=4)
        ttk.Button(t, text="Apply", command=self.digi_apply).pack(anchor="w", padx=8, pady=4)
        self.digi_msg = tk.StringVar()
        ttk.Label(t, textvariable=self.digi_msg, foreground="red").pack(anchor="w", padx=8)

    def digi_fill(self):
        for k, _, kind, _ in self.DIGI_SPEC:
            self.df.set(k, getattr(self.cp.digi, k))

    def digi_apply(self):
        g = self.cp.digi
        try:
            for k, _, kind, _ in self.DIGI_SPEC:
                v = self.df.get(k)
                setattr(g, k, bool(v) if kind == "check" else int(v) if isinstance(getattr(g, k), int) and not isinstance(getattr(g, k), bool) else v)
        except ValueError as e:
            self.digi_msg.set("invalid value: %s" % e)
            return
        self.digi_msg.set("")
        self.dirty()

    # ------------------------------------------------------------ settings
    SETTINGS_SPEC = [("callsign", "Callsign", "entry", None), ("dmr_id", "DMR / radio ID", "entry", None),
                     ("p25_unit_id", "P25 unit ID (0 = DMR ID)", "entry", None),
                     ("nxdn_unit_id", "NXDN unit ID (0 = DMR ID)", "entry", None),
                     ("radio_name", "Radio name", "entry", None), ("step_hz", "VFO step Hz", "entry", None),
                     ("vfo_mode", "VFO mode", "combo", C.MODES), ("start_channel", "Start channel # (empty = last)", "entry", None),
                     ("boot_vfo", "Boot in VFO", "check", None), ("rx_invert", "RX polarity inverted", "check", None),
                     ("deemph_us", "De-emphasis comp us", "entry", None), ("test_tone_hz", "Test tone Hz (0 = off)", "entry", None),
                     ("backlight_level", "Backlight 0..10", "entry", None), ("backlight_timeout_s", "Backlight timeout s", "entry", None),
                     ("batt_percent", "Battery as percent", "check", None),
                     ("key_beep", "Key beep", "check", None), ("auto_keylock", "Auto key lock", "check", None),
                     ("keylock_timeout_s", "Key lock timeout s", "entry", None),
                     ("key0", "Key P1", "combo", C.KEY_FUNCS), ("key1", "Key P2", "combo", C.KEY_FUNCS),
                     ("key2", "Key PF1", "combo", C.KEY_FUNCS), ("key3", "Key PF2", "combo", C.KEY_FUNCS),
                     ("key4", "Key PF3", "combo", C.KEY_FUNCS), ("key5", "Key PF3 long", "combo", C.KEY_FUNCS),
                     ("dmr_cc", "Default DMR CC", "entry", None), ("dmr_slot", "Default DMR slot", "entry", None),
                     ("dmr_tg", "Default DMR TG", "entry", None), ("p25_nac", "Default P25 NAC (hex)", "entry", None),
                     ("p25_tg", "Default P25 TG", "entry", None), ("p25_wacn", "Default WACN (hex)", "entry", None),
                     ("p25_sysid", "Default SysID (hex)", "entry", None), ("nxdn_ran", "Default NXDN RAN", "entry", None),
                     ("nxdn_group", "Default NXDN group", "entry", None), ("ysf_dgid", "Default YSF DG-ID", "entry", None),
                     ("ur", "D-STAR UR", "entry", None), ("rpt1", "D-STAR RPT1", "entry", None),
                     ("rpt2", "D-STAR RPT2", "entry", None), ("dstar_msg", "D-STAR message", "entry", None)]
    HEX = ("p25_nac", "p25_wacn", "p25_sysid")

    def build_settings(self):
        t = self.set_tab = ttk.Frame(self.nb)
        self.sf = Form(t, self.SETTINGS_SPEC, cols=3)
        self.sf.pack(anchor="nw", padx=4, pady=4)
        ttk.Button(t, text="Apply settings", command=self.settings_apply).pack(anchor="w", padx=8)
        self.set_msg = tk.StringVar()
        ttk.Label(t, textvariable=self.set_msg, foreground="red").pack(anchor="w", padx=8)

    def settings_fill(self):
        s = self.cp.settings
        for key, _, kind, _ in self.SETTINGS_SPEC:
            if key.startswith("key") and key[3:].isdigit():
                self.sf.set(key, s.keys[int(key[3:])])
            elif key == "start_channel":
                self.sf.set(key, "" if s.start_channel is None else str(s.start_channel + 1))
            elif key in self.HEX:
                self.sf.set(key, "%X" % getattr(s, key))
            else:
                self.sf.set(key, getattr(s, key))

    def settings_apply(self):
        s = self.cp.settings
        try:
            for key, _, kind, _ in self.SETTINGS_SPEC:
                v = self.sf.get(key)
                if key.startswith("key") and key[3:].isdigit():
                    s.keys[int(key[3:])] = v
                elif key == "start_channel":
                    n = opt_int(v)
                    s.start_channel = None if n is None else n - 1
                elif kind == "check":
                    setattr(s, key, bool(v))
                elif key in self.HEX:
                    setattr(s, key, int(v, 16))
                elif isinstance(getattr(s, key), int):
                    setattr(s, key, int(v))
                else:
                    setattr(s, key, v)
        except ValueError as e:
            self.set_msg.set("invalid value: %s" % e)
            return
        self.set_msg.set("")
        self.dirty()

    # ------------------------------------------------------------ refresh
    def refresh_all(self):
        ST.use(self.cp.model)
        self.model_var.set(self.cp.model)
        self.model_menu_var.set(self.cp.model)
        if self.nav_model != self.cp.model:                 # other radio model: other stock tree / tables
            if self.cur_page and self.cur_page.startswith("stock:"):
                self.pages[self.cur_page].pack_forget()
                self.cur_page = None
            for k in [k for k in self.pages if k.startswith("stock:")]:
                self.pages.pop(k).destroy()
            self.nav.delete(*self.nav.get_children())
            self.build_nav()
        for k in [k for k in self.pages if k.startswith("stock:")]:
            if k != self.cur_page:
                self.pages.pop(k).destroy()
        self.title()
        self.cur_ch = None
        self.fill_tree()
        for e in (self.zones, self.scans, self.tgl):
            e.refresh()
        self.ct_tab.fill()
        self.ts_tab.fill()
        self.keys_tab.fill()
        self.dstar_tab.fill()
        self.digi_fill()
        self.settings_fill()

    def refresh_tab(self):
        w = self.pages.get(self.cur_page)
        if isinstance(w, (ListEditor, StockGrid, StockRecord)):
            w.refresh()

    # ------------------------------------------------------------ navigation tree (stock CPS layout + cfw sections)
    CFW_NODE = {"Channel": "channels", "DMRZone": "zones", "ScanList": "scanlists", "DMRTalkGroups": "contacts",
                "DMRReceiveGroupCallList": "tglists", "@masterid": "settings"}

    def build_nav(self):
        n = self.nav
        self.nav_model = self.cp.model
        ST.use(self.cp.model)
        root = n.insert("", "end", text="%s (cfw)" % self.cp.model, open=True, values=())
        self.nav_page = {}
        for si, (sec, nodes) in enumerate(ST.SCHEMA["tree"]):
            sid = n.insert(root, "end", text=sec, open=si == 0)
            for label, target in nodes:
                state = SU.node_state(self.cp.model, target, ST.TABLES, ST.PAGES)     # schema/cfw_support.json
                if state == "n/a":
                    continue                                    # this radio has no such feature
                key = self.CFW_NODE.get(target)
                if key is None:
                    key = "stock:" + target
                iid = n.insert(sid, "end", text=label + (" *" if state == "stored" and target not in self.CFW_NODE else ""))
                self.nav_page[iid] = key
            if sec in ("DMR", "Digital"):
                iid = n.insert(sid, "end", text="Tier III Systems (cfw)")
                self.nav_page[iid] = "trunksys"
            if sec == "NXDN":
                iid = n.insert(sid, "end", text="Type-C / Type-D Systems (cfw)")
                self.nav_page[iid] = "trunksys"
        cf = n.insert(root, "end", text="cfw Digital Modes", open=True)
        for label, key in (("Radio Settings (cfw)", "settings"), ("Trunk Systems: P25 / DMR T3 / NXDN", "trunksys"),
                           ("Encryption Keys", "keys"), ("D-STAR Repeaters / Routing", "dstar"),
                           ("D-STAR / YSF / Registration", "digi")):
            self.nav_page[n.insert(cf, "end", text=label)] = key
        self.nav_page[n.insert(root, "end", text="Log")] = "log"
        n.bind("<<TreeviewSelect>>", lambda e: self.nav_select())
        first = [i for i, k in self.nav_page.items() if k == "channels"][0]
        n.selection_set(first)
        if self.cur_page is None or self.cur_page == "channels":
            self.show_page("channels")

    def nav_select(self):
        sel = self.nav.selection()
        if sel and sel[0] in self.nav_page:
            self.show_page(self.nav_page[sel[0]])

    def show_page(self, key):
        if key not in self.pages and key.startswith("stock:"):
            node, t = key[6:], key[6:]
            t = ST.NODE_TABLE.get(t, t)             # an .rdt-only dialog that is decoded (schema/rdt_dialogs.json)
            if t.startswith("@"):
                self.pages[key] = InfoPage(self, t)
            elif "#" in t:                          # a page of one record's keys (schema "pages", e.g. Bluetooth)
                pg = ST.PAGES[t]
                self.pages[key] = StockRecord(self, pg["table"], pg)
            elif ST.TABLES[t]["kind"] == "record":
                self.pages[key] = StockRecord(self, t, node=node)
            else:
                self.pages[key] = StockGrid(self, t, node)
        if self.cur_page in self.pages:
            self.pages[self.cur_page].pack_forget()
        self.cur_page = key
        self.pages[key].pack(fill="both", expand=True)
        self.refresh_tab()

    # ------------------------------------------------------------ validate / diff / radio
    def validate(self):
        iss = V.validate(self.cp)
        self.say("validate: %d error(s), %d warning(s)" % (len(V.errors(iss)), len(iss) - len(V.errors(iss))))
        for i in iss[:300]:
            self.say("  " + str(i))
        if V.errors(iss):
            self.show_page("log")
        return not V.errors(iss)

    def diff_file(self):
        p = filedialog.askopenfilename(filetypes=[("cfw codeplug", "*.d8cp *.json *.yaml"), ("all", "*")])
        if p:
            other = C.load(p)
            self.say("diff %s -> current: %s" % (p, D.summary(other, self.cp)))
            for l in D.diff(other, self.cp):
                self.say("  " + l)
            self.show_page("log")

    def run_bg(self, fn, done):
        if self.busy:
            return
        self.busy = True

        def work():
            try:
                r = fn()
                self.q.put(("done", done, r, None))
            except Exception as e:              # noqa: BLE001
                self.q.put(("done", done, None, e))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self.say(item[1])
                elif item[0] == "prog":
                    self.prog["value"] = 100.0 * item[1] / max(1, item[2])
                elif item[0] == "ask":
                    _, lines, ev, box = item
                    box.append(self.ask_diff(lines))
                    ev.set()
                elif item[0] == "done":
                    self.busy = False
                    _, done, r, e = item
                    if e:
                        self.say("error: %s" % e)
                        messagebox.showerror("Radio", str(e))
                    else:
                        done(r)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def bg_log(self, s):
        self.q.put(("log", s))

    def bg_prog(self, a, b):
        self.q.put(("prog", a, b))

    def read_radio(self):
        if not self.check_discard():
            return
        port = self.port.get()
        self.say("reading %s ..." % port)

        def done(r):
            cp, raw, inf = r
            if cp is None:
                messagebox.showinfo("Read", "The radio holds no cfw codeplug (it runs on NAND / built-in channels).")
                return
            self.cp, self.path, self.changed = cp, None, False
            self.say("read %d bytes, %d channels" % (len(raw), len(cp.channels)))
            self.refresh_all()
        self.run_bg(lambda: ops.read_radio(port, log=self.bg_log, progress=self.bg_prog), done)

    def ask_diff(self, lines):
        w = tk.Toplevel(self.root)
        w.title("Write to radio: changes")
        w.geometry("760x480")
        txt = tk.Text(w, wrap="none", font="TkFixedFont")
        txt.insert("end", "\n".join(lines) if lines else "(no changes: the radio already holds this codeplug)")
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)
        res = {"ok": False}
        b = ttk.Frame(w)
        b.pack(fill="x")
        ttk.Label(b, text="%d change(s). Codeplug only: no firmware is written." % len(lines)).pack(side="left", padx=6)

        def ok():
            res["ok"] = True
            w.destroy()
        ttk.Button(b, text="Write", command=ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=w.destroy).pack(side="right")
        w.transient(self.root)
        w.grab_set()
        self.root.wait_window(w)
        return res["ok"]

    def write_radio(self):
        if not self.validate():
            messagebox.showerror("Write", "Fix the validation errors first (see Log).")
            return
        port = self.port.get()

        def confirm(lines):
            ev, box = threading.Event(), []
            self.q.put(("ask", lines, ev, box))
            ev.wait()
            return box[0]
        self.say("writing to %s ..." % port)
        self.run_bg(lambda: ops.write_radio(port, self.cp, log=self.bg_log, confirm=confirm, progress=self.bg_prog),
                    lambda r: self.say("write done" if r is not None else "write cancelled"))


def run(path=None, port="tcp:localhost:3470", model="D890UV"):
    root = tk.Tk()
    App(root, path, port, model)
    root.mainloop()
