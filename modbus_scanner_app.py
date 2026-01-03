from __future__ import annotations

import base64
import csv
import json
import queue
import threading
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any, Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import ttkbootstrap as ttk

    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    from tkinter import ttk  # type: ignore

    TTKBOOTSTRAP_AVAILABLE = False

from PIL import Image, ImageTk

from modbus_decode import decode_registers, registers_per_value
from modbus_config import DEFAULT_CONFIG
from modbus_helpers import default_results_path, switch_to_tab, write_text_file
from modbus_prefs import PreferencesStore
from modbus_scanner import read_modbus_registers, start_modbus_scan
from modbus_ui import (
    create_about_tab,
    create_preferences_tab,
    create_read_tab,
    create_results_tab,
    create_settings_tab,
    get_logo_base64,
)

# Convert the base64 string back to an image
def load_logo_from_base64():
    logo_base64 = get_logo_base64()  # Call the function to get the base64 string
    logo_data = base64.b64decode(logo_base64)
    logo_image = Image.open(BytesIO(logo_data))  # Load the image from the byte stream
    return ImageTk.PhotoImage(logo_image)  # Since it's already resized, no need to resize again


class ModbusScannerApp:
    POLL_INTERVAL_MS = 50

    def __init__(self, root):
        self.root = root
        self.root.title("Modbus Scanner - Blue Star Qatar")
        self.root.minsize(900, 500)
        self.root.geometry("980x520")

        self.style: Optional[Any] = None
        self.theme_mode = "light"
        self._theme_change_in_progress = False
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.prefs = PreferencesStore()
        self.profiles: Dict[str, Any] = {}

        # Header (logo + title + subtitle)
        self.header_frame = ttk.Frame(self.root, style="Header.TFrame")
        self.header_frame.pack(fill="x", pady=(0, 6))

        self.accent_bar = tk.Frame(self.header_frame, background="#1e88e5", height=3)
        self.accent_bar.pack(fill="x", side="top")

        self.top_frame = ttk.Frame(self.header_frame, style="Header.TFrame", padding=(14, 8))
        self.top_frame.pack(fill="x")
        self.top_frame.grid_columnconfigure(1, weight=1)

        # Load and display the logo from base64
        self.logo_image = load_logo_from_base64()  # Call the function to load the logo
        self.root.iconphoto(True, self.logo_image)
        self.logo_label = ttk.Label(self.top_frame, image=self.logo_image, style="Header.TLabel")
        self.logo_label.grid(row=0, column=0,  padx=10)

        # Add a title text next to the logo
        self.title_label = ttk.Label(self.top_frame, text="Modbus Scanner", style="HeaderTitle.TLabel")
        self.title_label.grid(row=0, column=1, padx=10, sticky="w")

        # Add a description text below the title
        self.description_label = ttk.Label(
            self.top_frame,
            text="Scan a Modbus RTU loop for responding slave IDs. Configure your connection, choose a probe, then start scanning.",
            style="HeaderSubtitle.TLabel",
            wraplength=880,
        )
        self.description_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(4, 0), sticky="w")



        # Create a Notebook (tabs container)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        # Create stop event for stopping the scan
        self.stop_event = threading.Event()
        self.scan_running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._active_client: Optional[Any] = None

        self.scan_lines: list[str] = []
        self.scan_results: list[Dict[str, Any]] = []
        self.details_by_address: Dict[int, Any] = {}
        self.counts: Dict[str, int] = {"responded": 0, "exception": 0, "no_response": 0, "error": 0}
        self.total_addresses = 0
        self.scan_started_at: Optional[float] = None
        self.last_summary: Optional[Dict[str, Any]] = None
        self.last_config: Optional[Dict[str, Any]] = None
        self.status_var = tk.StringVar(value="Ready")
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.read_status_var = tk.StringVar(value="Ready")
        self.read_running = False
        self.read_thread: Optional[threading.Thread] = None
        self.read_event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.read_stop_event = threading.Event()
        self.last_read_config: Optional[Dict[str, Any]] = None
        self.read_polling = False
        self.read_poll_interval_ms = 1000
        self._read_poll_after_id: Optional[str] = None
        self._active_read_client: Optional[Any] = None
        self._read_layout_signature: Optional[tuple] = None

        # Create tabs
        self.settings_frame = ttk.Frame(self.notebook, width=400, height=280)
        self.results_frame = ttk.Frame(self.notebook, width=400, height=280)
        self.read_frame = ttk.Frame(self.notebook, width=400, height=280)

        self.settings_frame.pack(fill="both", expand=1)
        self.results_frame.pack(fill="both", expand=1)
        self.read_frame.pack(fill="both", expand=1)

        # Add tabs to Notebook
        self.notebook.add(self.settings_frame, text='Settings')
        self.notebook.add(self.results_frame, text='Results')
        self.notebook.add(self.read_frame, text="Read")

        self.preferences_frame = create_preferences_tab(self.notebook, self.dark_mode_var, self._on_theme_toggle)
        self.notebook.add(self.preferences_frame, text="Preferences")

        # Create the About tab
        self.about_frame = create_about_tab(self.notebook)
        self.notebook.add(self.about_frame, text='About')
        
        # Initialize the tabs
        (
            self.start_button,
            self.settings_stop_button,
            self.reset_button,
            self.get_connection_config,
            self.get_scan_config,
            self.set_scan_config,
            self.profile_combobox,
            self.profile_save_button,
            self.profile_delete_button,
        ) = create_settings_tab(
            self.settings_frame,
            self.start_scan,
            self.stop_scan,
        )
        (
            self.results_tree,
            self.result_text,
            self.progress_bar,
            self.results_settings_button,
            self.results_stop_button,
            self.save_button,
            self.clear_button,
            self.toggle_log_button,
        ) = create_results_tab(
            self.results_frame,
            self.open_settings,
            self.stop_scan,
            self.save_results_as,
            self.clear_results,
            self.status_var,
            self.auto_scroll_var,
        )

        (
            self.read_tree,
            self.read_once_button,
            self.read_start_poll_button,
            self.read_stop_button,
            self.read_clear_button,
        ) = create_read_tab(
            self.read_frame,
            self.get_connection_config,
            self.read_once,
            self.start_read_polling,
            self.stop_read,
            self.clear_read_results,
            self.read_status_var,
        )

        self.results_tree.bind("<Double-1>", self._on_tree_double_click)
        self.results_tree.bind("<Return>", self._on_tree_double_click)
        self.results_tree.tag_configure("responded", foreground="#166534", background="#dcfce7")
        self.results_tree.tag_configure("exception", foreground="#92400e", background="#fffbeb")
        self.results_tree.tag_configure("no_response", foreground="#475569", background="#f8fafc")
        self.results_tree.tag_configure("error", foreground="#991b1b", background="#fee2e2")

        self._init_preferences()
        self._configure_accessibility()
        self.apply_theme(self.theme_mode)
        self._set_scanning_ui_state(False)

    def _on_theme_toggle(self) -> None:
        if self._theme_change_in_progress:
            return
        mode = "dark" if self.dark_mode_var.get() else "light"
        self.apply_theme(mode)
        try:
            self.prefs.set_theme(self.theme_mode)
            self.prefs.save()
        except Exception:
            pass

    def _default_scan_profile(self) -> Dict[str, Any]:
        return {
            "port": DEFAULT_CONFIG.get("port", ""),
            "baudrate": DEFAULT_CONFIG.get("baudrate", 9600),
            "parity": DEFAULT_CONFIG.get("parity", "N"),
            "stopbits": DEFAULT_CONFIG.get("stopbits", 1),
            "bytesize": DEFAULT_CONFIG.get("bytesize", 8),
            "timeout": DEFAULT_CONFIG.get("timeout", 1),
            "probe_method": "holding_registers",
            "probe_register": 0,
            "probe_count": 1,
            "start_address": DEFAULT_CONFIG.get("start_address", 1),
            "end_address": DEFAULT_CONFIG.get("end_address", 247),
        }

    @staticmethod
    def _profile_sort_key(name: str) -> tuple:
        if name == "Last used":
            return (0, "")
        if name == "Default":
            return (1, "")
        return (2, name.lower())

    def _refresh_profile_list(self) -> None:
        names = sorted(self.profiles.keys(), key=self._profile_sort_key)
        try:
            self.profile_combobox["values"] = names
        except Exception:
            pass

    def _apply_profile(self, name: str) -> None:
        config = self.profiles.get(name)
        if not isinstance(config, dict):
            return
        try:
            self.set_scan_config(config)
        except Exception:
            pass

    def _on_profile_selected(self, _event=None) -> None:
        name = str(self.profile_combobox.get()).strip()
        if not name:
            return
        self._apply_profile(name)
        try:
            self.prefs.set_last_profile(name)
            self.prefs.save()
        except Exception:
            pass

    def _on_save_profile(self) -> None:
        name = str(self.profile_combobox.get()).strip()
        if not name:
            messagebox.showerror("Profile Name Required", "Please enter a profile name to save.")
            return

        try:
            config = self.get_scan_config()
        except ValueError as exc:
            messagebox.showerror("Invalid Settings", str(exc))
            return

        if not isinstance(config, dict):
            return

        self.profiles[name] = dict(config)
        self.profiles.setdefault("Default", self._default_scan_profile())
        self.profiles["Last used"] = dict(config)
        self._refresh_profile_list()

        self.profile_combobox.set(name)
        try:
            self.prefs.set_profiles(self.profiles)
            self.prefs.set_last_profile(name)
            self.prefs.set_last_used_scan(config)
            self.prefs.save()
        except Exception:
            pass

    def _on_delete_profile(self) -> None:
        name = str(self.profile_combobox.get()).strip()
        if not name:
            return
        if name in {"Default", "Last used"}:
            messagebox.showinfo("Protected Profile", f"'{name}' cannot be deleted.")
            return

        if not messagebox.askyesno("Delete Profile", f"Delete profile '{name}'?"):
            return

        self.profiles.pop(name, None)
        if "Default" not in self.profiles:
            self.profiles["Default"] = self._default_scan_profile()
        self._refresh_profile_list()

        self.profile_combobox.set("Last used" if "Last used" in self.profiles else "Default")
        self._on_profile_selected()

        try:
            self.prefs.set_profiles(self.profiles)
            self.prefs.set_last_profile(str(self.profile_combobox.get()).strip() or "Default")
            self.prefs.save()
        except Exception:
            pass

    def _persist_last_used_scan(self, config: Dict[str, Any]) -> None:
        if not isinstance(config, dict):
            return
        try:
            self.profiles["Last used"] = dict(config)
            self.prefs.set_last_used_scan(config)
            self.prefs.set_profiles(self.profiles)
            self.prefs.save()
        except Exception:
            pass

    def _persist_last_used_read(self, config: Dict[str, Any], interval_sec: Optional[float] = None) -> None:
        if not isinstance(config, dict):
            return
        payload = dict(config)
        if interval_sec is not None:
            payload["poll_interval_sec"] = float(interval_sec)
        try:
            self.prefs.set_last_used_read(payload)
            self.prefs.save()
        except Exception:
            pass

    def _persist_current_ui_state(self) -> None:
        try:
            config = self.get_scan_config()
        except Exception:
            config = None

        if isinstance(config, dict):
            self.profiles["Last used"] = dict(config)
            self.prefs.set_last_used_scan(config)

        self.prefs.set_theme(self.theme_mode)
        self.prefs.set_last_profile(str(self.profile_combobox.get()).strip() or "Default")
        self.prefs.set_profiles(self.profiles)
        try:
            self.prefs.save()
        except Exception:
            pass

    def _on_close(self) -> None:
        if self.scan_running or self.read_running or self.read_polling:
            if not messagebox.askyesno("Exit", "An operation is running. Stop and exit?"):
                return
            try:
                self.stop_scan()
            except Exception:
                pass
            try:
                self.stop_read()
            except Exception:
                pass

        self._persist_current_ui_state()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _init_preferences(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.theme_mode = self.prefs.get_theme("light")

        profiles = self.prefs.get_profiles()
        if not profiles:
            profiles = {"Default": self._default_scan_profile()}
        if "Default" not in profiles:
            profiles["Default"] = self._default_scan_profile()

        last_used_scan = self.prefs.get_last_used_scan()
        if isinstance(last_used_scan, dict):
            profiles["Last used"] = last_used_scan
        else:
            profiles["Last used"] = profiles.get("Default", self._default_scan_profile())

        self.profiles = profiles
        self._refresh_profile_list()

        selected = self.prefs.get_last_profile("Last used")
        if selected not in self.profiles:
            selected = "Last used"

        self.profile_combobox.set(selected)
        self.profile_combobox.bind("<<ComboboxSelected>>", self._on_profile_selected)

        self.profile_save_button.configure(command=self._on_save_profile)
        self.profile_delete_button.configure(command=self._on_delete_profile)

        self._apply_profile(selected)

    def apply_theme(self, mode: str) -> None:
        mode = "dark" if mode == "dark" else "light"
        self.theme_mode = mode

        if mode == "dark":
            app_bg = "#0b1220"
            header_bg = "#0f172a"
            surface = "#111827"
            text_color = "#e2e8f0"
            muted_text = "#94a3b8"
            accent = "#3b82f6"
            accent_hover = "#2563eb"
            border = "#334155"
            log_bg = "#0b1220"
            log_fg = "#e2e8f0"
        else:
            app_bg = "#f7f9fc"
            header_bg = "#e8f1ff"
            surface = "#ffffff"
            text_color = "#0f172a"
            muted_text = "#475569"
            accent = "#1e88e5"
            accent_hover = "#1565c0"
            border = "#d0d7e2"
            log_bg = "#ffffff"
            log_fg = "#0f172a"

        self._theme_change_in_progress = True
        try:
            if self.dark_mode_var.get() != (mode == "dark"):
                self.dark_mode_var.set(mode == "dark")
        finally:
            self._theme_change_in_progress = False

        # Update root/tk widgets that aren't style-driven
        try:
            self.root.configure(background=app_bg)
        except Exception:
            pass
        try:
            self.accent_bar.configure(background=accent)
        except Exception:
            pass
        if hasattr(self, "result_text"):
            try:
                self.result_text.configure(background=log_bg, foreground=log_fg, insertbackground=log_fg)
            except Exception:
                pass

        if TTKBOOTSTRAP_AVAILABLE:
            theme_name = "darkly" if mode == "dark" else "cosmo"
            if self.style is None:
                self.style = ttk.Style(theme=theme_name)
            else:
                try:
                    self.style.theme_use(theme_name)
                except Exception:
                    self.style = ttk.Style(theme=theme_name)

            self.style.configure("HeaderTitle.TLabel", background=header_bg, foreground=accent, font=("Segoe UI", 16, "bold"))
            self.style.configure("HeaderSubtitle.TLabel", background=header_bg, foreground=muted_text, font=("Segoe UI", 9))
            self.style.configure("Header.TFrame", background=header_bg)
            self.style.configure("Header.TLabel", background=header_bg, foreground=text_color)
            self.style.configure("Treeview", rowheight=28)
            self.style.configure("TLabel", font=("Segoe UI", 10))
            self.style.configure("TButton", font=("Segoe UI", 10))
            self.style.configure("TEntry", font=("Segoe UI", 10))
            self.style.configure("TCombobox", font=("Segoe UI", 10))
        else:
            # Fallback (no ttkbootstrap): custom light/dark palettes on clam.
            self.style = ttk.Style()
            self.style.theme_use("clam")

            self.style.configure("TFrame", background=app_bg)
            self.style.configure("TLabel", background=app_bg, foreground=text_color, font=("Segoe UI", 10))

            self.style.configure("Header.TFrame", background=header_bg)
            self.style.configure("Header.TLabel", background=header_bg, foreground=text_color)
            self.style.configure("HeaderTitle.TLabel", background=header_bg, foreground=accent, font=("Segoe UI", 16, "bold"))
            self.style.configure("HeaderSubtitle.TLabel", background=header_bg, foreground=muted_text, font=("Segoe UI", 9))

            self.style.configure("TNotebook", background=app_bg, borderwidth=0)
            tab_bg = "#1e293b" if mode == "dark" else "#dde9ff"
            self.style.configure("TNotebook.Tab", background=tab_bg, foreground=text_color, padding=(14, 8))
            self.style.map("TNotebook.Tab", background=[("selected", accent)], foreground=[("selected", "#ffffff")])

            self.style.configure("TLabelframe", background=app_bg, bordercolor=border, relief="flat")
            self.style.configure("TLabelframe.Label", background=app_bg, foreground=text_color, font=("Segoe UI", 10))
            self.style.configure("TPanedwindow", background=app_bg)

            self.style.configure("TEntry", fieldbackground=surface, foreground=text_color, font=("Segoe UI", 10))
            self.style.configure("TCombobox", fieldbackground=surface, foreground=text_color, font=("Segoe UI", 10))
            self.style.map("TCombobox", fieldbackground=[("readonly", surface)], foreground=[("readonly", text_color)])

            button_bg = "#334155" if mode == "dark" else "#e2e8f0"
            button_active = "#475569" if mode == "dark" else "#cbd5e1"
            self.style.configure(
                "TButton", background=button_bg, foreground=text_color, relief="flat", padding=(12, 6), font=("Segoe UI", 10)
            )
            self.style.map(
                "TButton",
                background=[("active", button_active), ("disabled", button_bg)],
                foreground=[("disabled", muted_text)],
            )
            self.style.configure("Primary.TButton", background=accent, foreground="#ffffff")
            self.style.map(
                "Primary.TButton",
                background=[("active", accent_hover), ("disabled", "#93c5fd")],
                foreground=[("disabled", "#f8fafc")],
            )
            self.style.configure("Danger.TButton", background="#ef4444" if mode == "dark" else "#d32f2f", foreground="#ffffff")
            self.style.map(
                "Danger.TButton",
                background=[("active", "#dc2626" if mode == "dark" else "#b71c1c"), ("disabled", "#fca5a5")],
                foreground=[("disabled", "#f8fafc")],
            )

            self.style.configure("TCheckbutton", background=app_bg, foreground=text_color, font=("Segoe UI", 10))
            self.style.map("TCheckbutton", foreground=[("disabled", muted_text)])

            self.style.configure(
                "Treeview",
                background=surface,
                fieldbackground=surface,
                foreground=text_color,
                rowheight=28,
                borderwidth=0,
                font=("Segoe UI", 10),
            )
            self.style.map("Treeview", background=[("selected", accent)], foreground=[("selected", "#ffffff")])
            self.style.configure("Treeview.Heading", background=tab_bg, foreground=text_color, relief="flat", font=("Segoe UI", 10, "bold"))
            self.style.map("Treeview.Heading", background=[("active", "#334155" if mode == "dark" else "#c7dbff")])

            self.style.configure("TProgressbar", troughcolor=tab_bg, background=accent)

        if hasattr(self, "results_tree"):
            if mode == "dark":
                self.results_tree.tag_configure("responded", foreground="#86efac", background="#052e16")
                self.results_tree.tag_configure("exception", foreground="#fdba74", background="#451a03")
                self.results_tree.tag_configure("no_response", foreground="#e2e8f0", background="#0f172a")
                self.results_tree.tag_configure("error", foreground="#fca5a5", background="#450a0a")
            else:
                self.results_tree.tag_configure("responded", foreground="#166534", background="#dcfce7")
                self.results_tree.tag_configure("exception", foreground="#92400e", background="#fffbeb")
                self.results_tree.tag_configure("no_response", foreground="#475569", background="#f8fafc")
                self.results_tree.tag_configure("error", foreground="#991b1b", background="#fee2e2")

    def _configure_accessibility(self) -> None:
        def invoke(widget) -> None:
            try:
                widget.invoke()
            except Exception:
                pass

        def on_escape(_event) -> None:
            if self.scan_running:
                self.stop_scan()
            elif self.read_running or self.read_polling:
                self.stop_read()

        self.root.bind_all("<Escape>", on_escape)
        self.root.bind_all("<Control-Return>", lambda _event: invoke(self.start_button))
        self.root.bind_all("<F5>", lambda _event: invoke(self.read_once_button))
        self.root.bind_all("<Control-r>", lambda _event: invoke(self.read_once_button))
        self.root.bind_all("<Control-p>", lambda _event: invoke(self.read_start_poll_button))
        self.root.bind_all("<Control-s>", lambda _event: self.save_results_as())
        self.root.bind_all("<Control-l>", lambda _event: invoke(self.toggle_log_button))
        self.root.bind_all(
            "<Control-t>",
            lambda _event: (
                self.dark_mode_var.set(not self.dark_mode_var.get()),
                self._on_theme_toggle(),
            ),
        )

    def open_settings(self) -> None:
        switch_to_tab(self.notebook, self.settings_frame)

    def _on_tree_double_click(self, _event) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return

        values = self.results_tree.item(selection[0], "values")
        if not values:
            return

        try:
            address = int(values[0])
        except (TypeError, ValueError):
            return

        details = self.details_by_address.get(address)
        if details is None and len(values) >= 4:
            details = values[3]

        if not isinstance(details, str):
            details = json.dumps(details, indent=2, ensure_ascii=False)

        messagebox.showinfo(f"Slave {address} Details", str(details))

    def _set_scan_status(self, address: Any, current: int, total: int) -> None:
        port = (self.last_config or {}).get("port", "")
        start_address = (self.last_config or {}).get("start_address", "")
        end_address = (self.last_config or {}).get("end_address", "")

        found = self.counts["responded"] + self.counts["exception"]

        eta = ""
        if self.scan_started_at is not None and current > 0:
            elapsed = monotonic() - self.scan_started_at
            avg = elapsed / current
            eta = self._format_duration((total - current) * avg)

        eta_part = f" | ETA {eta}" if eta else ""
        self.status_var.set(
            f"Port {port} | {start_address}-{end_address} | Slave {address} ({current}/{total}) | Found {found}{eta_part}"
        )

    def _set_scanning_ui_state(self, scanning: bool) -> None:
        busy = scanning or self.read_running or self.read_polling
        start_state = "disabled" if busy else "normal"
        stop_state = "normal" if scanning else "disabled"

        self.start_button.configure(state=start_state)
        self.reset_button.configure(state=start_state)
        self.settings_stop_button.configure(state=stop_state)
        self.results_stop_button.configure(state=stop_state)
        self.read_once_button.configure(state="disabled" if (scanning or self.read_running) else "normal")
        self.read_start_poll_button.configure(state="disabled" if (scanning or self.read_running or self.read_polling) else "normal")
        self.read_stop_button.configure(state="normal" if (self.read_running or self.read_polling) else "disabled")
        self.read_clear_button.configure(state="disabled" if (scanning or self.read_running or self.read_polling) else "normal")

        has_results = bool(self.scan_lines)
        self.save_button.configure(state="normal" if (scanning or has_results) else "disabled")
        self.clear_button.configure(state="disabled" if scanning else ("normal" if has_results else "disabled"))

    def _append_line(self, line: str) -> None:
        self.scan_lines.append(line)
        self.result_text.insert("end", f"{line}\n")
        if self.auto_scroll_var.get():
            self.result_text.see("end")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0.0, seconds)
        total = int(round(seconds))
        minutes, sec = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"

    def clear_results(self) -> None:
        if self.scan_running:
            return

        self.scan_lines = []
        self.scan_results = []
        self.details_by_address = {}
        self.counts = {"responded": 0, "exception": 0, "no_response": 0, "error": 0}
        self.total_addresses = 0
        self.scan_started_at = None
        self.last_summary = None
        self.last_config = None
        self.status_var.set("Ready")

        self.result_text.delete(1.0, tk.END)
        self.results_tree.delete(*self.results_tree.get_children())
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 0
        self._set_scanning_ui_state(False)

    def clear_read_results(self) -> None:
        if self.read_running or self.read_polling:
            return

        self.last_read_config = None
        self.read_status_var.set("Ready")
        self.read_tree.delete(*self.read_tree.get_children())
        self._set_scanning_ui_state(self.scan_running)

    def _cancel_read_poll_timer(self) -> None:
        if self._read_poll_after_id is None:
            return
        try:
            self.root.after_cancel(self._read_poll_after_id)
        except Exception:
            pass
        self._read_poll_after_id = None

    @staticmethod
    def _read_layout_sig(config: Dict[str, Any]) -> tuple:
        read_type = config.get("read_type")
        address = config.get("read_address")
        count = config.get("read_count")
        if read_type in {"coils", "discrete_inputs"}:
            return (read_type, address, count, config.get("bit_format"))
        return (
            read_type,
            address,
            count,
            config.get("data_type"),
            config.get("byte_order"),
            config.get("word_order"),
        )

    def stop_read(self) -> None:
        self.read_polling = False
        self._cancel_read_poll_timer()

        if self.read_running:
            self.read_stop_event.set()
            try:
                if self._active_read_client is not None:
                    self._active_read_client.close()
            except Exception:
                pass
        else:
            self.read_status_var.set("Read stopped.")

        self._set_scanning_ui_state(self.scan_running)

    def read_once(self, config: Dict[str, Any]) -> None:
        if self.scan_running:
            messagebox.showwarning("Scan In Progress", "Stop the scan before reading data.")
            return

        if self.read_running:
            messagebox.showwarning("Read In Progress", "A read is already running.")
            return

        self._cancel_read_poll_timer()
        switch_to_tab(self.notebook, self.read_frame)
        self._persist_last_used_read(config)
        self._start_read_worker(config)

    def start_read_polling(self, config: Dict[str, Any], interval_sec: float) -> None:
        if self.scan_running:
            messagebox.showwarning("Scan In Progress", "Stop the scan before starting polling.")
            return

        if interval_sec <= 0:
            messagebox.showerror("Invalid Poll Interval", "Poll interval must be greater than 0 seconds.")
            return

        self.read_polling = True
        self.read_poll_interval_ms = max(100, int(interval_sec * 1000))
        self.last_read_config = dict(config)
        self._persist_last_used_read(config, interval_sec=interval_sec)

        self._cancel_read_poll_timer()
        switch_to_tab(self.notebook, self.read_frame)

        if self.read_running:
            self.read_status_var.set(f"Polling enabled (every {interval_sec:g} sec).")
            self._set_scanning_ui_state(self.scan_running)
            return

        self._start_read_worker(config)

    def _schedule_next_read_poll(self) -> None:
        if not self.read_polling:
            return
        if self.scan_running or self.read_running:
            return
        if not self.root.winfo_exists():
            return
        if not self.last_read_config:
            return

        self._cancel_read_poll_timer()
        self._read_poll_after_id = self.root.after(self.read_poll_interval_ms, lambda: self._start_read_worker(self.last_read_config))

    def _start_read_worker(self, config: Dict[str, Any]) -> None:
        self.read_running = True
        self.last_read_config = dict(config)
        self._active_read_client = None

        sig = self._read_layout_sig(config)
        if sig != self._read_layout_signature:
            self.read_tree.delete(*self.read_tree.get_children())
            self._read_layout_signature = sig

        self.read_status_var.set("Starting read…")

        self.read_stop_event = threading.Event()
        self.read_event_queue = queue.Queue()
        self.read_thread = threading.Thread(
            target=read_modbus_registers,
            args=(config, self.read_stop_event, self.read_event_queue.put),
            daemon=True,
        )
        self.read_thread.start()

        self._set_scanning_ui_state(self.scan_running)
        self.root.after(self.POLL_INTERVAL_MS, self._poll_read_events)

    def _poll_read_events(self) -> None:
        try:
            while True:
                event = self.read_event_queue.get_nowait()
                self._handle_read_event(event)
        except queue.Empty:
            pass

        if self.read_running and self.root.winfo_exists():
            self.root.after(self.POLL_INTERVAL_MS, self._poll_read_events)

    def _handle_read_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")

        if event_type == "read_log":
            self.read_status_var.set(str(event.get("message", "")))
            return

        if event_type == "read_client_ready":
            self._active_read_client = event.get("client")
            return

        if event_type == "read_error":
            message = str(event.get("message", "Unknown error"))
            self.read_status_var.set(f"Error: {message}")
            if not self.read_polling:
                messagebox.showerror("Read Error", message)
            return

        if event_type == "read_result":
            registers = event.get("registers") or []
            bits = event.get("bits") or []
            unit_id = event.get("unit_id")
            read_type = str(event.get("read_type", "holding_registers"))
            address = int(event.get("address", 0))
            count = int(event.get("count", len(registers)))
            response_time_ms = event.get("response_time_ms", "")

            config = self.last_read_config or {}
            function_label = {
                "coils": "Coils (0x01)",
                "discrete_inputs": "Discrete Inputs (0x02)",
                "holding_registers": "Holding Registers (0x03)",
                "input_registers": "Input Registers (0x04)",
            }.get(read_type, read_type)

            poll_part = f" | Polling {self.read_poll_interval_ms / 1000:g}s" if self.read_polling else ""

            if read_type in {"coils", "discrete_inputs"}:
                bit_format = str(config.get("bit_format", "bool"))
                self.read_status_var.set(
                    f"Slave {unit_id} | {function_label} | {address}-{address + max(count - 1, 0)} | {response_time_ms} ms{poll_part}"
                )

                for offset, bit in enumerate(bits[:count]):
                    item_address = address + offset
                    iid = str(item_address)
                    raw_text = "1" if bool(bit) else "0"
                    if bit_format == "01":
                        value_text = raw_text
                    else:
                        value_text = str(bool(bit))

                    values = (item_address, raw_text, value_text)
                    if self.read_tree.exists(iid):
                        self.read_tree.item(iid, values=values)
                    else:
                        self.read_tree.insert("", "end", iid=iid, values=values)
                return

            data_type = str(config.get("data_type", "uint16"))
            byte_order = str(config.get("byte_order", "big"))
            word_order = str(config.get("word_order", "big"))

            self.read_status_var.set(
                f"Slave {unit_id} | {function_label} | {address}-{address + max(count - 1, 0)} | {data_type} | {response_time_ms} ms{poll_part}"
            )

            try:
                regs_per = registers_per_value(data_type)
                decoded = decode_registers(registers, data_type, byte_order=byte_order, word_order=word_order)
            except Exception as exc:
                raw = " ".join(f"0x{int(r):04X}" for r in registers)
                self.read_tree.insert("", "end", values=(address, raw, f"Decode error: {exc}"))
                return

            for index, value in enumerate(decoded):
                start_register = address + index * regs_per
                iid = str(start_register)
                raw_regs = registers[index * regs_per : (index + 1) * regs_per]
                raw_text = " ".join(f"0x{int(r):04X}" for r in raw_regs)
                if isinstance(value, float):
                    value_text = f"{value:.6g}"
                else:
                    value_text = str(value)

                values = (start_register, raw_text, value_text)
                if self.read_tree.exists(iid):
                    self.read_tree.item(iid, values=values)
                else:
                    self.read_tree.insert("", "end", iid=iid, values=values)
            return

        if event_type == "read_done":
            self.read_running = False
            self._active_read_client = None
            if event.get("stopped"):
                self.read_status_var.set("Read stopped.")
            self._set_scanning_ui_state(self.scan_running)
            self._schedule_next_read_poll()
            return

    def start_scan(self, config):
        if self.scan_running:
            messagebox.showwarning("Scan In Progress", "A scan is already running.")
            return
        if self.read_running or self.read_polling:
            messagebox.showwarning(
                "Read In Progress",
                "Stop reading/polling before starting a scan.",
            )
            return

        self.stop_event.clear()
        self.scan_running = True
        self.last_config = dict(config)
        self._persist_last_used_scan(self.last_config)
        self.last_summary = None
        self._active_client = None
        self.details_by_address = {}
        self.counts = {"responded": 0, "exception": 0, "no_response": 0, "error": 0}
        self.total_addresses = 0
        self.scan_started_at = monotonic()
        self.status_var.set("Starting scan…")

        # Switch to the results tab
        switch_to_tab(self.notebook, self.results_frame)

        # Clear previous results
        self.scan_lines = []
        self.scan_results = []
        self.result_text.delete(1.0, tk.END)
        self.results_tree.delete(*self.results_tree.get_children())
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 0

        probe_desc = config.get("probe_method", "holding_registers")
        if probe_desc == "input_registers":
            probe_desc = "Input Register (0x04)"
        else:
            probe_desc = "Holding Register (0x03)"

        self._append_line(
            "Starting scan: "
            f"port={config.get('port')} baud={config.get('baudrate')} parity={config.get('parity')} "
            f"stop={config.get('stopbits')} data={config.get('bytesize')} timeout={config.get('timeout')}s "
            f"range={config.get('start_address')}-{config.get('end_address')} probe={probe_desc} "
            f"reg={config.get('probe_register')} count={config.get('probe_count')}"
        )

        # Start scanning in a worker thread and process results via a queue.
        self.event_queue = queue.Queue()
        self.scan_thread = threading.Thread(
            target=start_modbus_scan,
            args=(config, self.stop_event, self.event_queue.put),
            daemon=True,
        )
        self.scan_thread.start()

        self._set_scanning_ui_state(True)
        self.root.after(self.POLL_INTERVAL_MS, self._poll_scan_events)

    def _poll_scan_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_scan_event(event)
        except queue.Empty:
            pass

        if self.scan_running and self.root.winfo_exists():
            self.root.after(self.POLL_INTERVAL_MS, self._poll_scan_events)

    def _handle_scan_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")

        if event_type == "log":
            self._append_line(str(event.get("message", "")))
            return

        if event_type == "client_ready":
            self._active_client = event.get("client")
            return

        if event_type == "error":
            message = str(event.get("message", "Unknown error"))
            self._append_line(message)
            messagebox.showerror("Scan Error", message)
            return

        if event_type == "progress_init":
            total = int(event.get("total", 0))
            self.total_addresses = total
            self.progress_bar["maximum"] = max(total, 0)
            self.progress_bar["value"] = 0
            port = (self.last_config or {}).get("port", "")
            start_address = (self.last_config or {}).get("start_address", "")
            end_address = (self.last_config or {}).get("end_address", "")
            self.status_var.set(f"Port {port} | {start_address}-{end_address} | Scanning (0/{total})")
            return

        if event_type == "progress":
            current = int(event.get("current", 0))
            total = int(event.get("total", self.total_addresses))
            address = event.get("address")

            self.progress_bar["value"] = current
            self._set_scan_status(address=address, current=current, total=total)
            return

        if event_type == "result":
            address = event.get("address")
            status = event.get("status")
            response_time_ms = event.get("response_time_ms")
            details = event.get("details")

            self.scan_results.append(
                {
                    "address": address,
                    "status": status,
                    "response_time_ms": response_time_ms,
                    "details": details,
                }
            )

            if status in self.counts:
                self.counts[status] += 1
            else:
                self.counts["error"] += 1

            try:
                address_int = int(address)
            except (TypeError, ValueError):
                address_int = None

            if address_int is not None:
                self.details_by_address[address_int] = details

            status_display = {
                "responded": "● Responded",
                "exception": "▲ Exception",
                "no_response": "○ No response",
                "error": "× Error",
            }.get(status, str(status))

            if isinstance(details, str):
                details_text = details
            else:
                details_text = json.dumps(details, ensure_ascii=False)
            details_single_line = details_text.replace("\n", " ").strip()
            if len(details_single_line) > 140:
                details_display = details_single_line[:137] + "..."
            else:
                details_display = details_single_line

            if address_int is not None:
                iid = str(address_int)
                values = (address_int, status_display, response_time_ms, details_display)
                if self.results_tree.exists(iid):
                    self.results_tree.item(iid, values=values, tags=(status,))
                else:
                    self.results_tree.insert("", "end", iid=iid, values=values, tags=(status,))

            if status == "responded":
                self._append_line(f"Slave {address}: Responded ({response_time_ms} ms) registers={details}")
            elif status == "exception":
                self._append_line(f"Slave {address}: Responded with exception ({response_time_ms} ms) {details}")
            elif status == "no_response":
                self._append_line(f"Slave {address}: No response ({response_time_ms} ms) {details}")
            else:
                self._append_line(f"Slave {address}: Error ({response_time_ms} ms) {details}")

            self._set_scan_status(
                address=address,
                current=int(self.progress_bar["value"]),
                total=int(self.progress_bar["maximum"]),
            )
            return

        if event_type == "done":
            self.scan_running = False
            self.last_summary = event.get("summary")
            self._active_client = None

            duration = ""
            if self.scan_started_at is not None:
                duration = self._format_duration(monotonic() - self.scan_started_at)
            self.scan_started_at = None

            if event.get("stopped"):
                self._append_line("Scan stopped.")
                self.status_var.set(f"Scan stopped{f' | {duration}' if duration else ''}")
            else:
                self._append_line("Scan completed.")
                self.status_var.set(f"Scan completed{f' | {duration}' if duration else ''}")

            if isinstance(self.last_summary, dict):
                self._append_line(
                    "Summary: "
                    f"responded={self.last_summary.get('responded', 0)}, "
                    f"exception={self.last_summary.get('responded_exception', 0)}, "
                    f"no_response={self.last_summary.get('no_response', 0)}, "
                    f"errors={self.last_summary.get('errors', 0)}"
                )

            self._set_scanning_ui_state(False)
            self._auto_save_results()
            return

    def _results_text(self) -> str:
        if not self.scan_lines:
            return ""
        return "\n".join(self.scan_lines) + "\n"

    def _auto_save_results(self) -> None:
        text = self._results_text()
        if not text.strip():
            return

        try:
            path = default_results_path(".txt")
            write_text_file(path, text)
            self._append_line(f"Auto-saved results to {path}")
        except Exception as exc:
            messagebox.showerror("Save Failed", f"Failed to save results: {exc}")

    def save_results_as(self) -> None:
        if not self.scan_lines:
            messagebox.showinfo("No Results", "There are no results to save yet.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Results As",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return

        path = Path(file_path)
        suffix = path.suffix.lower()

        try:
            if suffix == ".csv":
                self._save_results_csv(path)
            elif suffix == ".json":
                self._save_results_json(path)
            else:
                write_text_file(path, self._results_text())

            messagebox.showinfo("Save Successful", f"Results saved to {path}")
        except Exception as exc:
            messagebox.showerror("Save Failed", f"Failed to save results: {exc}")

    def _save_results_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["address", "status", "response_time_ms", "details"])
            writer.writeheader()
            for row in self.scan_results:
                details = row.get("details")
                if not isinstance(details, str):
                    details = json.dumps(details, ensure_ascii=False)
                writer.writerow(
                    {
                        "address": row.get("address"),
                        "status": row.get("status"),
                        "response_time_ms": row.get("response_time_ms"),
                        "details": details,
                    }
                )

    def _save_results_json(self, path: Path) -> None:
        payload = {
            "config": self.last_config,
            "summary": self.last_summary,
            "results": self.scan_results,
            "log": self.scan_lines,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def stop_scan(self):
        # Signal to stop the scan
        if not self.scan_running:
            return

        self.stop_event.set()
        self._append_line("Stop requested…")
        try:
            if self._active_client is not None:
                self._active_client.close()
        except Exception:
            pass

# Main window creation
if __name__ == '__main__':
    if TTKBOOTSTRAP_AVAILABLE:
        root = ttk.Window(themename="cosmo")
    else:
        root = tk.Tk()
    app = ModbusScannerApp(root)
    root.mainloop()
