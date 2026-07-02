import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from data_fetcher import send_report_email

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(SCRIPT_DIR, "M365_Audit_Report.xlsx")

STAGES = [
    # (status_text, progress_value, keyword_triggers)
    # Stage 1 is set immediately on button click — no keyword needed.
    ("Authenticating...",              0,   None),
    ("Fetching M365 reports...",       20,  None),          # triggers on first stdout line
    ("Fetching Purview audit logs...", 40,  {"audit", "purview", "search", "poll"}),
    ("Building report...",             75,  {"build", "writ", "format", "summary", "parsing"}),
]


class AuditApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("M365 SharePoint Audit Tool")
        root.resizable(True, True)
        root.geometry("700x560")
        root.minsize(560, 400)

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)   # log box row expands

        # --- Button ---
        self.btn = ttk.Button(frame, text="Generate Report", command=self._start_audit)
        self.btn.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # --- Status label ---
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            frame,
            textvariable=self.status_var,
            anchor="center",
            font=("Segoe UI", 10),
            pady=6,
        )
        self.status_label.grid(row=1, column=0, sticky="ew")

        # --- Progress bar ---
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # --- Log box ---
        log_frame = ttk.Frame(frame)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(
            log_frame,
            state="disabled",
            wrap="none",
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            relief="flat",
            borderwidth=0,
        )
        self.log.grid(row=0, column=0, sticky="nsew")

        log_scroll_y = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        log_scroll_y.grid(row=0, column=1, sticky="ns")
        log_scroll_x = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log.xview)
        log_scroll_x.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)

        # --- File path label (hidden until report is done) ---
        self.path_var = tk.StringVar()
        self.path_label = tk.Label(
            frame,
            textvariable=self.path_var,
            anchor="w",
            font=("Segoe UI", 9),
            fg="#0078d4",
            wraplength=660,
            justify="left",
            pady=4,
        )
        self.path_label.grid(row=4, column=0, sticky="ew")

    # ------------------------------------------------------------------
    def _set_status(self, text: str, color: str = "black", progress: int | None = None):
        self.status_var.set(text)
        self.status_label.config(fg=color)
        if progress is not None:
            self.progress["value"] = progress

    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------
    def _start_audit(self):
        self.btn.config(state="disabled")
        self.path_var.set("")
        self._clear_log()
        self._set_status("Authenticating...", progress=0)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        output_lines: list[str] = []
        stage = 0

        def advance(new_stage: int):
            nonlocal stage
            if new_stage <= stage:
                return
            stage = new_stage
            text, pct, _ = STAGES[new_stage]
            self.root.after(0, self._set_status, text, "black", pct)

        try:
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            process = subprocess.Popen(
                [sys.executable, "-u", "audit_final.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=SCRIPT_DIR,
                env=env,
            )

            first_line = True
            for raw_line in process.stdout:
                # Stream every line to the log box as-is (preserves spacing/symbols)
                self.root.after(0, self._append_log, raw_line)

                line = raw_line.strip()
                if not line:
                    continue
                output_lines.append(line)

                if first_line:
                    first_line = False
                    advance(1)

                lower = line.lower()

                if stage < 2 and STAGES[2][2] and any(k in lower for k in STAGES[2][2]):
                    advance(2)

                if stage < 3 and STAGES[3][2] and any(k in lower for k in STAGES[3][2]):
                    advance(3)

            process.wait()

            if process.returncode == 0:
                self.root.after(0, self.path_var.set, f"Report saved to: {REPORT_PATH}")
                self.root.after(0, self._set_status, "Sending report...", "black", 95)
                self.root.after(0, self._append_log, "\nSending report via email...\n")
                sent = send_report_email(REPORT_PATH)
                if sent:
                    self.root.after(0, self._append_log, "Report sent successfully.\n")
                    self.root.after(0, self._set_status, "Done! Report sent.", "black", 100)
                else:
                    self.root.after(0, self._append_log, "Email failed — check log above for details.\n")
                    self.root.after(0, self._set_status, "Done! (Email failed.)", "black", 100)
            else:
                tail = "\n".join(output_lines[-15:]) or "(no output captured)"
                self.root.after(0, self._set_status, "Error.", "red", self.progress["value"])
                self.root.after(
                    0,
                    messagebox.showerror,
                    "Audit Failed",
                    f"The audit script exited with an error:\n\n{tail}",
                )

        except Exception as exc:
            self.root.after(0, self._set_status, "Error.", "red")
            self.root.after(0, messagebox.showerror, "Unexpected Error", str(exc))
        finally:
            self.root.after(0, self.btn.config, {"state": "normal"})


def main():
    root = tk.Tk()
    AuditApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
