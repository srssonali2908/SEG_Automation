# -*- coding: utf-8 -*-
"""
Desktop app for the PDF broken link checker.

Run with `python gui.py`, or build BrokenLinkChecker.exe with build_exe.bat.
A PDF path can be passed as the first argument (e.g. by dropping a PDF onto
the .exe).
"""
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

try:
    # Use the Windows certificate store so HTTPS works behind corporate
    # TLS-inspecting proxies.
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import link_checker

APP_TITLE = "PDF Broken Link Checker"
COLUMNS = (
    ("page", "Page", 50, False),
    ("link", "Original Link", 360, True),
    ("status", "Status", 200, False),
    ("redirect", "Redirect / Detail", 300, True),
    ("broken", "Broken?", 110, False),
)


class App(tk.Tk):
    def __init__(self, initial_pdf=None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1050x620")
        self.minsize(760, 420)

        self.pdf_path = None
        self.rows = []
        self.events = queue.Queue()
        self.only_problems = tk.BooleanVar(value=False)

        self._build()
        self.after(100, self._poll)
        if initial_pdf:
            self._set_pdf(initial_pdf)

    def _build(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Summary.TLabel", font=("Segoe UI", 10, "bold"))

        top = ttk.Frame(self, padding=(12, 12, 12, 6))
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="Checks every external hyperlink in a PDF and exports a CSV report.").pack(anchor="w")

        picker = ttk.Frame(self, padding=(12, 6))
        picker.pack(fill="x")
        ttk.Button(picker, text="Choose PDF...", command=self._choose_pdf).pack(side="left")
        self.file_label = ttk.Label(picker, text="No file selected", foreground="#616e7c")
        self.file_label.pack(side="left", padx=10, fill="x", expand=True)
        self.check_btn = ttk.Button(picker, text="Check links", command=self._start, state="disabled")
        self.check_btn.pack(side="right")

        prog = ttk.Frame(self, padding=(12, 0))
        prog.pack(fill="x")
        self.progress = ttk.Progressbar(prog, mode="determinate")
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(prog, text="")
        self.status_label.pack(anchor="w", pady=(4, 0))

        table = ttk.Frame(self, padding=(12, 6))
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in COLUMNS], show="headings")
        for key, heading, width, stretch in COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, stretch=stretch, anchor="w")
        self.tree.tag_configure("broken", background="#fde2e1")
        self.tree.tag_configure("vpn", background="#fff4d6")
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected)

        bottom = ttk.Frame(self, padding=(12, 6, 12, 12))
        bottom.pack(fill="x")
        self.summary_label = ttk.Label(bottom, text="", style="Summary.TLabel")
        self.summary_label.pack(side="left")
        self.save_btn = ttk.Button(bottom, text="Save CSV report...", command=self._save, state="disabled")
        self.save_btn.pack(side="right")
        ttk.Checkbutton(bottom, text="Show only problems", variable=self.only_problems,
                        command=self._render).pack(side="right", padx=12)
        ttk.Label(bottom, text="Double-click a row to open the link.", foreground="#616e7c").pack(side="right", padx=12)

    def _choose_pdf(self):
        path = filedialog.askopenfilename(title="Choose a PDF", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self._set_pdf(path)

    def _set_pdf(self, path):
        if not os.path.isfile(path):
            messagebox.showerror(APP_TITLE, "File not found:\n{}".format(path))
            return
        self.pdf_path = path
        self.file_label.configure(text=path, foreground="")
        self.check_btn.configure(state="normal")

    def _start(self):
        self.rows = []
        self._render()
        self.summary_label.configure(text="")
        self.save_btn.configure(state="disabled")
        self.check_btn.configure(state="disabled")
        self.progress.configure(value=0, maximum=1)
        self.status_label.configure(text="Reading PDF...")
        threading.Thread(target=self._worker, args=(self.pdf_path,), daemon=True).start()

    def _worker(self, path):
        try:
            links = link_checker.extract_links(path)
        except Exception as e:
            self.events.put(("error", "Could not read the PDF:\n{}".format(e)))
            return
        if not links:
            self.events.put(("done", []))
            return
        self.events.put(("status", "Found {} link(s). Checking...".format(len(links))))
        rows = link_checker.check_links(links, progress=lambda d, t: self.events.put(("progress", (d, t))))
        self.events.put(("done", rows))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status_label.configure(text=payload)
                elif kind == "progress":
                    done, total = payload
                    self.progress.configure(value=done, maximum=total)
                    self.status_label.configure(text="Checked {} of {} unique link(s)...".format(done, total))
                elif kind == "error":
                    self.status_label.configure(text="")
                    self.check_btn.configure(state="normal")
                    messagebox.showerror(APP_TITLE, payload)
                elif kind == "done":
                    self._finish(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, rows):
        self.rows = rows
        self.check_btn.configure(state="normal")
        if not rows:
            self.progress.configure(value=0)
            self.status_label.configure(text=link_checker.NO_LINKS_MESSAGE)
            return
        self.progress.configure(value=self.progress["maximum"])
        self.status_label.configure(text="Done.")
        broken = sum(1 for r in rows if r[5] == "Yes")
        vpn = sum(1 for r in rows if r[5] != "Yes" and r[5] != "No")
        self.summary_label.configure(
            text="{} link(s): {} broken, {} need VPN, {} OK".format(len(rows), broken, vpn, len(rows) - broken - vpn))
        self.save_btn.configure(state="normal")
        self._render()

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.rows:
            page, url, status, redirect, _is_intel, broken = row
            if self.only_problems.get() and broken == "No":
                continue
            tag = "broken" if broken == "Yes" else "vpn" if broken != "No" else ""
            self.tree.insert("", "end", values=(page, url, status, redirect, broken), tags=(tag,))

    def _open_selected(self, _event):
        item = self.tree.focus()
        if item:
            webbrowser.open(self.tree.item(item, "values")[1])

    def _save(self):
        initial_dir = os.path.dirname(self.pdf_path) if self.pdf_path else os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Save CSV report",
            initialdir=initial_dir,
            initialfile=link_checker.report_filename(self.pdf_path or "document.pdf"),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                f.write(link_checker.rows_to_csv(self.rows))
        except OSError as e:
            messagebox.showerror(APP_TITLE, "Could not save the report:\n{}".format(e))
            return
        if messagebox.askyesno(APP_TITLE, "Report saved to:\n{}\n\nOpen it now?".format(path)):
            _open_file(path)


def _open_file(path):
    if sys.platform.startswith("win"):
        os.startfile(path)
    else:
        webbrowser.open("file://" + os.path.abspath(path))


def main():
    App(initial_pdf=sys.argv[1] if len(sys.argv) > 1 else None).mainloop()


if __name__ == "__main__":
    main()
