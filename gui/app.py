"""Desktop GUI for the Website Content Auditor.

Lets the user paste one or more website URLs, runs the crawler + scanner
in a background thread (so the UI never freezes), shows live progress,
displays results in a sortable table, and exports everything to Excel.
"""
import threading
import queue
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.word_list import load_word_list, DEFAULT_PATH
from core.crawler import WebsiteCrawler
from core.scanner import WordScanner
from core.report import aggregate_rows, export_to_excel

RESULT_COLUMNS = ["Website", "URL", "Page Title", "Word Found", "Occurrences",
                  "Suggested Replacement", "Section", "Matching Sentence"]


class AuditorApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        master.title("Website Content Auditor")
        master.geometry("1250x720")
        master.minsize(950, 560)

        self.word_list_path = DEFAULT_PATH
        try:
            self.word_list = load_word_list(self.word_list_path)
        except Exception as exc:
            messagebox.showerror("Word list error", str(exc))
            self.word_list = []

        self.stop_event = threading.Event()
        self.msg_queue = queue.Queue()
        self.worker_thread = None
        self.raw_rows = []     # every raw occurrence found, across all sites
        self.result_rows = []  # aggregated rows currently shown / exportable
        self.scanning = False

        self._build_ui()
        self.after(120, self._poll_queue)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.pack(fill="both", expand=True)

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Website URL(s) — one per line:").pack(anchor="w")
        self.url_text = tk.Text(top, height=4, wrap="none")
        self.url_text.pack(fill="x", pady=(2, 8))
        self.url_text.insert("1.0", "https://freshlypestcontrol.com.au/")

        controls = ttk.Frame(top)
        controls.pack(fill="x")

        self.word_list_label = ttk.Label(
            controls,
            text=f"Word list: {self.word_list_path.name} ({len(self.word_list)} entries)"
        )
        self.word_list_label.pack(side="left")

        ttk.Button(controls, text="Load Word List...", command=self._load_word_list).pack(
            side="left", padx=8)

        self.export_btn = ttk.Button(controls, text="Export to Excel",
                                      command=self._export_excel, state="disabled")
        self.export_btn.pack(side="right", padx=4)
        self.stop_btn = ttk.Button(controls, text="Stop Scan", command=self._stop_scan,
                                    state="disabled")
        self.stop_btn.pack(side="right", padx=4)
        self.start_btn = ttk.Button(controls, text="Start Scan", command=self._start_scan)
        self.start_btn.pack(side="right", padx=4)

        prog_frame = ttk.Frame(self, padding=(10, 6))
        prog_frame.pack(fill="x")
        self.progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", side="left", expand=True)
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(prog_frame, textvariable=self.status_var, width=55, anchor="w").pack(
            side="left", padx=10)

        table_frame = ttk.Frame(self, padding=10)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(table_frame, columns=RESULT_COLUMNS, show="headings")
        widths = [130, 220, 140, 100, 90, 200, 140, 260]
        for col, w in zip(RESULT_COLUMNS, widths):
            self.tree.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._open_selected_url)

        hint = ttk.Label(
            self,
            text="Tip: double-click a row to open that page in your browser.",
            padding=(10, 0, 10, 8), foreground="#666",
        )
        hint.pack(anchor="w")

    # -------------------------------------------------------------- actions
    def _load_word_list(self):
        path = filedialog.askopenfilename(
            title="Select word list JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            new_list = load_word_list(path)
        except Exception as exc:
            messagebox.showerror("Error loading word list", str(exc))
            return
        self.word_list = new_list
        self.word_list_path = Path(path)
        self.word_list_label.config(
            text=f"Word list: {self.word_list_path.name} ({len(self.word_list)} entries)")

    def _start_scan(self):
        if self.scanning:
            return
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("No URLs", "Please enter at least one website URL.")
            return
        if not self.word_list:
            messagebox.showwarning("No word list", "Load a valid word list before scanning.")
            return

        self.tree.delete(*self.tree.get_children())
        self.raw_rows = []
        self.result_rows = []
        self.stop_event.clear()
        self.progress["value"] = 0
        self.status_var.set("Starting...")
        self.scanning = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.export_btn.config(state="disabled")

        self.worker_thread = threading.Thread(target=self._run_scan, args=(urls,), daemon=True)
        self.worker_thread.start()

    def _stop_scan(self):
        self.stop_event.set()
        self.status_var.set("Stopping... (finishing current page fetches)")
        self.stop_btn.config(state="disabled")

    # ---- runs in a background thread ----
    def _run_scan(self, urls):
        scanner = WordScanner(self.word_list)
        total_sites = len(urls)

        for site_idx, url in enumerate(urls, start=1):
            if self.stop_event.is_set():
                break

            website_name = url.split("//")[-1].split("/")[0]
            self.msg_queue.put(("status", f"[{site_idx}/{total_sites}] Crawling {website_name}..."))

            crawler = WebsiteCrawler(
                url,
                stop_event=self.stop_event,
                on_status=lambda m: self.msg_queue.put(("status", m)),
            )

            try:
                for page in crawler.crawl():
                    if self.stop_event.is_set():
                        break
                    occurrences = scanner.scan_html(page.html)
                    for occ in occurrences:
                        self.raw_rows.append({
                            "website": website_name,
                            "url": page.url,
                            "title": page.title,
                            "word": occ.word,
                            "replacements": scanner.replacements_for(occ.word),
                            "section": occ.section,
                            "sentence": occ.sentence,
                        })
                    self.msg_queue.put(("progress", None))
            except Exception as exc:  # keep going even if one site fails hard
                self.msg_queue.put(("status", f"Error scanning {website_name}: {exc}"))
                continue

        self.msg_queue.put(("done", None))

    # ---- runs on the main thread ----
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "progress":
                    current = self.progress["value"]
                    self.progress["value"] = current + 2 if current < 96 else 96
                    self._refresh_results()
                elif kind == "done":
                    self._on_scan_done()
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _refresh_results(self):
        self.result_rows = aggregate_rows(self.raw_rows)
        self.tree.delete(*self.tree.get_children())
        for row in self.result_rows:
            self.tree.insert("", "end", values=[row[c] for c in RESULT_COLUMNS])

    def _on_scan_done(self):
        self._refresh_results()
        self.scanning = False
        self.status_var.set(
            f"Done. {len(self.result_rows)} result row(s) from "
            f"{len(self.raw_rows)} total occurrence(s)."
        )
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.export_btn.config(state="normal" if self.result_rows else "disabled")
        self.progress["value"] = 100

    def _export_excel(self):
        if not self.result_rows:
            messagebox.showinfo("Nothing to export", "Run a scan first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile="Website_Audit_Report.xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not path:
            return
        try:
            export_to_excel(self.result_rows, path)
            messagebox.showinfo("Export complete", f"Report saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _open_selected_url(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        if values and len(values) > 1:
            webbrowser.open(values[1])

    def _sort_by(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda t: float(t[0]))
        except ValueError:
            items.sort(key=lambda t: t[0].lower())
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    AuditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
