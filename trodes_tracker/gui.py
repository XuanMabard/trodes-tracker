#!/usr/bin/env python3
"""
gui.py

A small Tkinter desktop front-end for the Trodes tracking tools.

It lets you:
  - Pick a mode:
      * Position tracker -- stream x,y positions and do zone detection locally
        with shapely against a .trackgeometry file
      * Trodes events -- just listen to the Trodes event bus; zone detection
        happens inside the Trodes Camera Module (zones configured there fire
        named events)
  - Load a .trackgeometry file with a file picker (position mode only)
  - Type the camera width and height in pixels (position mode only)
  - Click "Start" to run the chosen mode and watch its output live
  - Click "Stop" to end it

The GUI launches the worker as a separate process -- ``python -m
trodes_tracker.cli`` or ``python -m trodes_tracker.events`` using the same
interpreter the GUI is running under, so it stays inside your conda
environment -- and streams whatever the worker prints. Running it
out-of-process keeps the GUI responsive and lets "Stop" cleanly terminate it.

Run it with:
    python -m trodes_tracker            # this GUI (see __main__.py)
    python -m trodes_tracker.gui
    hex-tracker-gui                     # once installed

Requirements: tkinter (standard library). The workers it runs still need
trodesnetwork, pyzmq, and msgpack installed; the position tracker additionally
needs shapely.
"""

import os
import sys
import queue
import threading
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from . import trodes_io


# ----------------------------------------------------------------------------
# Pure helpers (no GUI) -- easy to test on their own
# ----------------------------------------------------------------------------

def project_root():
    """The directory that contains the ``trodes_tracker`` package."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate_inputs(geometry_path, width_str, height_str):
    """Return a list of human-readable error strings (empty == all good)."""
    errors = []

    if not geometry_path:
        errors.append("Please choose a .trackgeometry file.")
    elif not os.path.isfile(geometry_path):
        errors.append(f"Geometry file not found:\n{geometry_path}")

    for label, value in (("width", width_str), ("height", height_str)):
        try:
            if float(value) <= 0:
                errors.append(f"Camera {label} must be a positive number.")
        except (TypeError, ValueError):
            errors.append(f"Camera {label} must be a number (got {value!r}).")

    return errors


def build_command(python_exe, geometry_path, width, height, server):
    """Assemble the command line that runs the tracker module, unbuffered (-u)
    so its output streams line-by-line into the GUI instead of being buffered."""
    cmd = [
        python_exe, "-u", "-m", "trodes_tracker.cli",
        geometry_path,
        "-W", str(width),
        "-H", str(height),
    ]
    if server:
        cmd += ["--server", server]
    return cmd


def build_events_command(python_exe, server):
    """Assemble the command line that runs the Trodes event listener module,
    unbuffered (-u) so its output streams line-by-line into the GUI."""
    cmd = [python_exe, "-u", "-m", "trodes_tracker.events"]
    if server:
        cmd += ["--server", server]
    return cmd


def subprocess_env():
    """Environment for the tracker subprocess, with the project root on
    PYTHONPATH so ``-m trodes_tracker.cli`` resolves even when the package
    hasn't been pip-installed."""
    env = dict(os.environ)
    root = project_root()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root + (os.pathsep + existing if existing else "")
    return env


# ----------------------------------------------------------------------------
# The GUI
# ----------------------------------------------------------------------------

class HexTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Hex Position Tracker")
        self.root.geometry("760x560")

        self.process = None             # the running subprocess, if any
        self.output_queue = queue.Queue()

        self._build_widgets()
        # Poll the output queue regularly and flush lines into the text box.
        self.root.after(100, self._drain_output_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self):
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        # --- Mode row ---
        self.mode_var = tk.StringVar(value="position")
        mode_frm = ttk.Frame(frm)
        mode_frm.grid(row=0, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(mode_frm, text="Mode:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Radiobutton(
            mode_frm, text="Position tracker (local zone detection)",
            variable=self.mode_var, value="position",
            command=self._on_mode_change).grid(row=0, column=1, padx=(0, 12))
        ttk.Radiobutton(
            mode_frm, text="Trodes events (zone detection in Trodes)",
            variable=self.mode_var, value="events",
            command=self._on_mode_change).grid(row=0, column=2)

        # --- Geometry file row ---
        ttk.Label(frm, text="Track geometry file:").grid(row=1, column=0, sticky="w", **pad)
        self.geometry_var = tk.StringVar()
        self.geometry_entry = ttk.Entry(frm, textvariable=self.geometry_var)
        self.geometry_entry.grid(row=1, column=1, sticky="ew", **pad)
        self.browse_btn = ttk.Button(frm, text="Browse...", command=self._browse_geometry)
        self.browse_btn.grid(row=1, column=2, **pad)

        # --- Width / height row ---
        dims = ttk.Frame(frm)
        dims.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(dims, text="Camera width (px):").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.width_var = tk.StringVar()
        self.width_entry = ttk.Entry(dims, textvariable=self.width_var, width=10)
        self.width_entry.grid(row=0, column=1, padx=(0, 20))
        ttk.Label(dims, text="Camera height (px):").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.height_var = tk.StringVar()
        self.height_entry = ttk.Entry(dims, textvariable=self.height_var, width=10)
        self.height_entry.grid(row=0, column=3)

        # --- Server (optional) row ---
        ttk.Label(frm, text="Trodes server (optional):").grid(row=3, column=0, sticky="w", **pad)
        self.server_var = tk.StringVar(value=trodes_io.DEFAULT_SERVER)
        ttk.Entry(frm, textvariable=self.server_var).grid(row=3, column=1, sticky="ew", **pad)

        # --- Start / Stop buttons row ---
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        self.start_btn = ttk.Button(btns, text="Start", command=self._start)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))
        self.stop_btn = ttk.Button(btns, text="Stop", command=self._stop, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Clear output", command=self._clear_output).grid(row=0, column=2)

        # --- Status label ---
        self.status_var = tk.StringVar(value="Idle.")
        ttk.Label(frm, textvariable=self.status_var, foreground="#555").grid(
            row=5, column=0, columnspan=3, sticky="w", padx=8)

        # --- Output box ---
        ttk.Label(frm, text="Output:").grid(row=6, column=0, sticky="w", padx=8, pady=(8, 0))
        self.output = scrolledtext.ScrolledText(frm, height=18, wrap="word", state="disabled")
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        frm.rowconfigure(7, weight=1)

        # Grey out the position-only inputs if the initial mode is events.
        self._on_mode_change()

    # --- Mode switching ---
    def _on_mode_change(self):
        """Enable/disable the position-only inputs to match the chosen mode."""
        events_mode = self.mode_var.get() == "events"
        state = "disabled" if events_mode else "normal"
        for widget in (self.geometry_entry, self.browse_btn,
                       self.width_entry, self.height_entry):
            widget.config(state=state)

    # --- File picker ---
    def _browse_geometry(self):
        path = filedialog.askopenfilename(
            title="Select a track geometry file",
            filetypes=[("Track geometry", "*.trackgeometry"), ("All files", "*.*")])
        if path:
            self.geometry_var.set(path)

    # --- Start / stop ---
    def _start(self):
        if self.process is not None:
            return  # already running

        events_mode = self.mode_var.get() == "events"

        if events_mode:
            # The event listener only needs the server address; zone detection
            # happens inside Trodes, so no geometry or resolution is required.
            cmd = build_events_command(sys.executable, self.server_var.get().strip())
        else:
            errors = validate_inputs(
                self.geometry_var.get().strip(),
                self.width_var.get().strip(),
                self.height_var.get().strip(),
            )
            if errors:
                messagebox.showerror("Please fix these", "\n\n".join(errors))
                return

            cmd = build_command(
                sys.executable,
                self.geometry_var.get().strip(),
                self.width_var.get().strip(),
                self.height_var.get().strip(),
                self.server_var.get().strip(),
            )

        self._append(f"$ {' '.join(cmd)}\n\n")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # line-buffered
                cwd=project_root(),
                env=subprocess_env(),
            )
        except Exception as exc:
            messagebox.showerror("Could not start", str(exc))
            self.process = None
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        if events_mode:
            self.status_var.set("Running... (waiting for events from Trodes)")
        else:
            self.status_var.set("Running... (waiting for position data from Trodes)")

        # Reader thread: pushes each output line onto the queue.
        threading.Thread(target=self._reader_thread, args=(self.process,), daemon=True).start()

    def _reader_thread(self, proc):
        try:
            for line in proc.stdout:
                self.output_queue.put(line)
        finally:
            proc.stdout.close()
            proc.wait()
            self.output_queue.put(("__DONE__", proc.returncode))

    def _stop(self):
        if self.process is not None:
            self.status_var.set("Stopping...")
            self.process.terminate()

    # --- Output plumbing ---
    def _drain_output_queue(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__DONE__":
                    self._on_process_end(item[1])
                else:
                    self._append(item)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_output_queue)

    def _on_process_end(self, returncode):
        self.process = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set(f"Stopped (exit code {returncode}). Idle.")
        self._append(f"\n--- process ended (exit code {returncode}) ---\n")

    def _append(self, text):
        self.output.config(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.config(state="disabled")

    def _clear_output(self):
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.config(state="disabled")

    def _on_close(self):
        if self.process is not None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    HexTrackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
