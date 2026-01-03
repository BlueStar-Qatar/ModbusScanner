import tkinter as tk
from tkinter import messagebox

import serial.tools.list_ports

from modbus_config import DEFAULT_CONFIG
from modbus_version import APP_VERSION

try:
    import ttkbootstrap as ttk

    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    from tkinter import ttk  # type: ignore

    TTKBOOTSTRAP_AVAILABLE = False


def create_settings_tab(parent, scan_callback, stop_callback):
    parent.grid_columnconfigure(0, weight=1)

    # Detect available serial ports and populate the combobox
    def get_serial_ports():
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    parity_map = {
        "N (None)": "N",
        "E (Even)": "E",
        "O (Odd)": "O",
    }

    probe_method_map = {
        "Holding Register (0x03)": "holding_registers",
        "Input Register (0x04)": "input_registers",
    }

    def validation_error(message: str) -> None:
        messagebox.showerror("Invalid Settings", message)

    def build_connection_config() -> dict:
        port = port_combobox.get().strip()
        if not port:
            raise ValueError("Please select a serial port.")

        parity_display = parity_combobox.get()
        if parity_display not in parity_map:
            raise ValueError("Please select a valid parity option.")

        try:
            baudrate = int(baudrate_combobox.get())
            stopbits = int(stopbits_combobox.get())
            bytesize = int(bytesize_combobox.get())
            timeout = float(timeout_combobox.get())
        except ValueError as exc:
            raise ValueError("Please ensure all connection fields contain valid numbers.") from exc

        if timeout <= 0:
            raise ValueError("Timeout must be greater than 0 seconds.")

        return {
            "port": port,
            "baudrate": baudrate,
            "parity": parity_map[parity_display],
            "stopbits": stopbits,
            "bytesize": bytesize,
            "timeout": timeout,
        }

    def build_scan_config() -> dict:
        probe_display = probe_method_combobox.get()
        if probe_display not in probe_method_map:
            raise ValueError("Please select a valid probe method.")

        try:
            probe_register = int(probe_register_entry.get())
            probe_count = int(probe_count_entry.get())
            start_address = int(start_address_entry.get())
            end_address = int(end_address_entry.get())
        except ValueError as exc:
            raise ValueError("Please ensure all numeric fields contain valid numbers.") from exc

        if probe_register < 0:
            raise ValueError("Probe register must be 0 or greater.")

        if probe_count <= 0:
            raise ValueError("Probe count must be 1 or greater.")

        if not (1 <= start_address <= 247) or not (1 <= end_address <= 247):
            raise ValueError("Start/End address must be between 1 and 247.")

        if start_address > end_address:
            raise ValueError("Start address must be less than or equal to end address.")

        config = build_connection_config()
        config.update(
            {
                "probe_method": probe_method_map[probe_display],
                "probe_register": probe_register,
                "probe_count": probe_count,
                "start_address": start_address,
                "end_address": end_address,
            }
        )
        return config

    def set_scan_config(config: dict) -> None:
        if not isinstance(config, dict):
            return

        refresh_ports()
        ports = list(port_combobox["values"])

        port = str(config.get("port", "")).strip()
        if port:
            if port not in ports:
                port_combobox["values"] = [port] + ports
            port_combobox.set(port)

        if "baudrate" in config:
            baudrate_combobox.set(str(config.get("baudrate", "")))

        parity_value = config.get("parity")
        if parity_value:
            parity_display = next((k for k, v in parity_map.items() if v == parity_value), None)
            if parity_display:
                parity_combobox.set(parity_display)

        if "stopbits" in config:
            stopbits_combobox.set(str(config.get("stopbits", "")))
        if "bytesize" in config:
            bytesize_combobox.set(str(config.get("bytesize", "")))
        if "timeout" in config:
            timeout_combobox.set(str(config.get("timeout", "")))

        probe_method = config.get("probe_method")
        if probe_method:
            probe_display = next((k for k, v in probe_method_map.items() if v == probe_method), None)
            if probe_display:
                probe_method_combobox.set(probe_display)

        def set_entry(entry, value) -> None:
            if value is None:
                return
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

        set_entry(probe_register_entry, config.get("probe_register"))
        set_entry(probe_count_entry, config.get("probe_count"))
        set_entry(start_address_entry, config.get("start_address"))
        set_entry(end_address_entry, config.get("end_address"))

    def reset_to_defaults() -> None:
        ports = get_serial_ports()
        port_combobox["values"] = ports

        if ports:
            if DEFAULT_CONFIG["port"] in ports:
                port_combobox.set(DEFAULT_CONFIG["port"])
            else:
                port_combobox.current(0)
        else:
            port_combobox.set("")

        baudrate_combobox.set(str(DEFAULT_CONFIG["baudrate"]))
        default_parity_display = next((k for k, v in parity_map.items() if v == DEFAULT_CONFIG["parity"]), "N (None)")
        parity_combobox.set(default_parity_display)
        stopbits_combobox.set(str(DEFAULT_CONFIG["stopbits"]))
        bytesize_combobox.set(str(DEFAULT_CONFIG["bytesize"]))
        timeout_combobox.set(str(DEFAULT_CONFIG["timeout"]))

        probe_method_combobox.set("Holding Register (0x03)")

        probe_register_entry.delete(0, tk.END)
        probe_register_entry.insert(0, "0")
        probe_count_entry.delete(0, tk.END)
        probe_count_entry.insert(0, "1")

        start_address_entry.delete(0, tk.END)
        start_address_entry.insert(0, str(DEFAULT_CONFIG["start_address"]))
        end_address_entry.delete(0, tk.END)
        end_address_entry.insert(0, str(DEFAULT_CONFIG["end_address"]))

    def on_scan():
        try:
            config = build_scan_config()
        except ValueError as exc:
            validation_error(str(exc))
            return

        scan_callback(config)

    content = ttk.Frame(parent, padding=(10, 8))
    content.grid(row=0, column=0, sticky="nsew")
    parent.grid_rowconfigure(0, weight=1)
    content.grid_columnconfigure(0, weight=1, uniform="col")
    content.grid_columnconfigure(1, weight=1, uniform="col")

    connection_frame = ttk.Labelframe(content, text="Connection", padding=(12, 8))
    connection_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
    connection_frame.grid_columnconfigure(1, weight=1)
    connection_frame.grid_columnconfigure(3, weight=1)

    ttk.Label(connection_frame, text="Port").grid(row=0, column=0, padx=(0, 10), pady=4, sticky="w")
    port_combobox = ttk.Combobox(connection_frame, values=get_serial_ports(), state="readonly")
    port_combobox.grid(row=0, column=1, columnspan=3, pady=4, sticky="ew")

    def refresh_ports():
        current = port_combobox.get()
        ports = get_serial_ports()
        port_combobox["values"] = ports

        if current in ports:
            port_combobox.set(current)
        elif ports:
            port_combobox.current(0)
        else:
            port_combobox.set("")

    refresh_button = ttk.Button(connection_frame, text="Refresh", command=refresh_ports)
    refresh_button.grid(row=0, column=4, padx=(10, 0), pady=4)

    ttk.Label(connection_frame, text="Baudrate").grid(row=1, column=0, padx=(0, 10), pady=4, sticky="w")
    baudrate_combobox = ttk.Combobox(
        connection_frame,
        values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
        state="readonly",
    )
    baudrate_combobox.grid(row=1, column=1, pady=4, sticky="ew")

    ttk.Label(connection_frame, text="Parity").grid(row=1, column=2, padx=(16, 10), pady=4, sticky="w")
    parity_combobox = ttk.Combobox(connection_frame, values=list(parity_map.keys()), state="readonly")
    parity_combobox.grid(row=1, column=3, pady=4, sticky="ew")

    ttk.Label(connection_frame, text="Stop bits").grid(row=2, column=0, padx=(0, 10), pady=4, sticky="w")
    stopbits_combobox = ttk.Combobox(connection_frame, values=["1", "2"], state="readonly")
    stopbits_combobox.grid(row=2, column=1, pady=4, sticky="ew")

    ttk.Label(connection_frame, text="Byte size").grid(row=2, column=2, padx=(16, 10), pady=4, sticky="w")
    bytesize_combobox = ttk.Combobox(connection_frame, values=["5", "6", "7", "8"], state="readonly")
    bytesize_combobox.grid(row=2, column=3, pady=4, sticky="ew")

    ttk.Label(connection_frame, text="Timeout (sec)").grid(row=3, column=0, padx=(0, 10), pady=4, sticky="w")
    timeout_combobox = ttk.Combobox(connection_frame, values=["0.5", "1", "2", "3", "4", "5", "10"], state="readonly")
    timeout_combobox.grid(row=3, column=1, pady=4, sticky="ew")

    probe_frame = ttk.Labelframe(content, text="Probe", padding=(12, 8))
    probe_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
    probe_frame.grid_columnconfigure(1, weight=1)
    probe_frame.grid_columnconfigure(3, weight=1)

    ttk.Label(probe_frame, text="Method").grid(row=0, column=0, padx=(0, 10), pady=4, sticky="w")
    probe_method_combobox = ttk.Combobox(probe_frame, values=list(probe_method_map.keys()), state="readonly")
    probe_method_combobox.grid(row=0, column=1, columnspan=3, pady=4, sticky="ew")

    ttk.Label(probe_frame, text="Register").grid(row=1, column=0, padx=(0, 10), pady=4, sticky="w")
    probe_register_entry = ttk.Entry(probe_frame)
    probe_register_entry.grid(row=1, column=1, pady=4, sticky="ew")

    ttk.Label(probe_frame, text="Count").grid(row=1, column=2, padx=(16, 10), pady=4, sticky="w")
    probe_count_entry = ttk.Entry(probe_frame)
    probe_count_entry.grid(row=1, column=3, pady=4, sticky="ew")

    range_frame = ttk.Labelframe(content, text="Scan Range", padding=(12, 8))
    range_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=(0, 10))
    range_frame.grid_columnconfigure(1, weight=1)
    range_frame.grid_columnconfigure(3, weight=1)

    ttk.Label(range_frame, text="Start address").grid(row=0, column=0, padx=(0, 10), pady=4, sticky="w")
    start_address_entry = ttk.Entry(range_frame)
    start_address_entry.grid(row=0, column=1, pady=4, sticky="ew")

    ttk.Label(range_frame, text="End address").grid(row=0, column=2, padx=(16, 10), pady=4, sticky="w")
    end_address_entry = ttk.Entry(range_frame)
    end_address_entry.grid(row=0, column=3, pady=4, sticky="ew")

    actions_frame = ttk.Labelframe(content, text="Actions", padding=(12, 10))
    actions_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 0), pady=(0, 10))
    actions_frame.grid_columnconfigure(0, weight=1)
    actions_frame.grid_columnconfigure(1, weight=1)
    actions_frame.grid_columnconfigure(2, weight=1)

    profile_row = ttk.Frame(actions_frame)
    profile_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    profile_row.grid_columnconfigure(1, weight=1)

    ttk.Label(profile_row, text="Profile").grid(row=0, column=0, padx=(0, 8), sticky="w")
    profile_combobox = ttk.Combobox(profile_row, state="normal")
    profile_combobox.grid(row=0, column=1, sticky="ew")

    profile_save_button = ttk.Button(profile_row, text="Save")
    profile_save_button.grid(row=0, column=2, padx=(8, 0))

    profile_delete_button = ttk.Button(profile_row, text="Delete")
    profile_delete_button.grid(row=0, column=3, padx=(8, 0))

    reset_button = ttk.Button(actions_frame, text="Reset", command=reset_to_defaults)
    reset_button.grid(row=1, column=0, padx=(0, 10), sticky="ew")

    start_button_kwargs = {"bootstyle": "primary"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Primary.TButton"}
    start_button = ttk.Button(actions_frame, text="Start Scan", command=on_scan, **start_button_kwargs)
    start_button.grid(row=1, column=1, padx=(0, 10), sticky="ew")

    stop_button_kwargs = {"bootstyle": "danger"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Danger.TButton"}
    stop_button = ttk.Button(actions_frame, text="Stop", command=stop_callback, **stop_button_kwargs)
    stop_button.grid(row=1, column=2, sticky="ew")

    reset_to_defaults()
    try:
        port_combobox.focus_set()
    except Exception:
        pass

    return (
        start_button,
        stop_button,
        reset_button,
        build_connection_config,
        build_scan_config,
        set_scan_config,
        profile_combobox,
        profile_save_button,
        profile_delete_button,
    )

def create_results_tab(
    parent,
    open_settings_callback,
    stop_callback,
    save_callback,
    clear_callback,
    status_var,
    auto_scroll_var,
):
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    toolbar = ttk.Frame(parent)
    toolbar.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
    toolbar.grid_columnconfigure(5, weight=1)

    settings_button = ttk.Button(toolbar, text="Settings", command=open_settings_callback)
    settings_button.grid(row=0, column=0, padx=(0, 8))

    stop_button_kwargs = {"bootstyle": "danger"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Danger.TButton"}
    stop_button = ttk.Button(toolbar, text="Stop", command=stop_callback, **stop_button_kwargs)
    stop_button.grid(row=0, column=1, padx=(0, 8))

    save_button_kwargs = {"bootstyle": "primary"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Primary.TButton"}
    save_button = ttk.Button(toolbar, text="Save As…", command=save_callback, **save_button_kwargs)
    save_button.grid(row=0, column=2, padx=(0, 8))

    clear_button = ttk.Button(toolbar, text="Clear", command=clear_callback)
    clear_button.grid(row=0, column=3, padx=(0, 8))

    toggle_log_button = ttk.Button(toolbar, text="Show Log")
    toggle_log_button.grid(row=0, column=4)

    auto_scroll_check = ttk.Checkbutton(toolbar, text="Auto-scroll", variable=auto_scroll_var)
    auto_scroll_check.grid(row=0, column=5, sticky="e")

    paned = ttk.Panedwindow(parent, orient="vertical")
    paned.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    devices_frame = ttk.Frame(paned)
    devices_frame.grid_rowconfigure(0, weight=1)
    devices_frame.grid_columnconfigure(0, weight=1)

    columns = ("address", "status", "response_time_ms", "details")
    results_tree = ttk.Treeview(devices_frame, columns=columns, show="headings", selectmode="browse")
    results_tree.heading("address", text="Slave ID")
    results_tree.column("address", width=80, anchor="center", stretch=False)
    results_tree.heading("status", text="Status")
    results_tree.column("status", width=130, anchor="w", stretch=False)
    results_tree.heading("response_time_ms", text="RTT (ms)")
    results_tree.column("response_time_ms", width=80, anchor="e", stretch=False)
    results_tree.heading("details", text="Details")
    results_tree.column("details", width=520, anchor="w", stretch=True)

    tree_scroll_y = ttk.Scrollbar(devices_frame, orient="vertical", command=results_tree.yview)
    tree_scroll_x = ttk.Scrollbar(devices_frame, orient="horizontal", command=results_tree.xview)
    results_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

    results_tree.grid(row=0, column=0, sticky="nsew")
    tree_scroll_y.grid(row=0, column=1, sticky="ns")
    tree_scroll_x.grid(row=1, column=0, sticky="ew")

    log_frame = ttk.Frame(paned)
    log_frame.grid_rowconfigure(0, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)

    log_text = tk.Text(
        log_frame,
        height=8,
        wrap="word",
        background="#ffffff",
        foreground="#0f172a",
        insertbackground="#0f172a",
    )
    log_text.grid(row=0, column=0, sticky="nsew")

    log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
    log_scroll.grid(row=0, column=1, sticky="ns")
    log_text.configure(yscrollcommand=log_scroll.set)

    paned.add(devices_frame, weight=3)

    log_visible = False

    def toggle_log() -> None:
        nonlocal log_visible

        if log_visible:
            paned.forget(log_frame)
            toggle_log_button.configure(text="Show Log")
            log_visible = False
        else:
            paned.add(log_frame, weight=1)
            toggle_log_button.configure(text="Hide Log")
            log_visible = True

    toggle_log_button.configure(command=toggle_log)

    status_frame = ttk.Frame(parent)
    status_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
    status_frame.grid_columnconfigure(0, weight=1)

    progress_bar = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
    progress_bar.grid(row=0, column=0, sticky="ew")

    status_label = ttk.Label(status_frame, textvariable=status_var, anchor="w")
    status_label.grid(row=1, column=0, pady=(6, 0), sticky="ew")

    return (
        results_tree,
        log_text,
        progress_bar,
        settings_button,
        stop_button,
        save_button,
        clear_button,
        toggle_log_button,
    )


def create_read_tab(
    parent,
    get_connection_config,
    read_once_callback,
    start_poll_callback,
    stop_callback,
    clear_callback,
    status_var,
):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    controls = ttk.Labelframe(parent, text="Read Data", padding=(12, 8))
    controls.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")

    for col in (1, 3, 5, 7):
        controls.grid_columnconfigure(col, weight=1)

    function_map = {
        "Coils (0x01)": "coils",
        "Discrete Inputs (0x02)": "discrete_inputs",
        "Holding Registers (0x03)": "holding_registers",
        "Input Registers (0x04)": "input_registers",
    }

    data_type_map = {
        "UInt16": ("uint16", 1),
        "Int16": ("int16", 1),
        "UInt32": ("uint32", 2),
        "Int32": ("int32", 2),
        "Float32": ("float32", 2),
        "Float64": ("float64", 4),
    }

    endian_map = {"Big": "big", "Little": "little"}
    bit_format_map = {"Bool (True/False)": "bool", "0/1": "01"}

    ttk.Label(controls, text="Slave ID").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
    unit_entry = ttk.Entry(controls, width=8)
    unit_entry.grid(row=0, column=1, pady=4, sticky="w")

    ttk.Label(controls, text="Function").grid(row=0, column=2, padx=(16, 8), pady=4, sticky="w")
    function_combobox = ttk.Combobox(controls, values=list(function_map.keys()), state="readonly")
    function_combobox.grid(row=0, column=3, pady=4, sticky="ew")

    start_label = ttk.Label(controls, text="Start address (0-based)")
    start_label.grid(row=0, column=4, padx=(16, 8), pady=4, sticky="w")
    start_entry = ttk.Entry(controls, width=10)
    start_entry.grid(row=0, column=5, pady=4, sticky="w")

    count_label = ttk.Label(controls, text="Count")
    count_label.grid(row=0, column=6, padx=(16, 8), pady=4, sticky="w")
    count_entry = ttk.Entry(controls, width=10)
    count_entry.grid(row=0, column=7, pady=4, sticky="w")

    ttk.Label(controls, text="Data type").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
    data_type_combobox = ttk.Combobox(controls, values=list(data_type_map.keys()), state="readonly", width=12)
    data_type_combobox.grid(row=1, column=1, pady=4, sticky="w")

    ttk.Label(controls, text="Byte order").grid(row=1, column=2, padx=(16, 8), pady=4, sticky="w")
    byte_order_combobox = ttk.Combobox(controls, values=list(endian_map.keys()), state="readonly", width=10)
    byte_order_combobox.grid(row=1, column=3, pady=4, sticky="w")

    ttk.Label(controls, text="Word order").grid(row=1, column=4, padx=(16, 8), pady=4, sticky="w")
    word_order_combobox = ttk.Combobox(controls, values=list(endian_map.keys()), state="readonly", width=10)
    word_order_combobox.grid(row=1, column=5, pady=4, sticky="w")

    ttk.Label(controls, text="Bit format").grid(row=1, column=6, padx=(16, 8), pady=4, sticky="w")
    bit_format_combobox = ttk.Combobox(controls, values=list(bit_format_map.keys()), state="readonly", width=14)
    bit_format_combobox.grid(row=1, column=7, pady=4, sticky="w")

    ttk.Label(controls, text="Poll every (sec)").grid(row=2, column=0, padx=(0, 8), pady=4, sticky="w")
    poll_entry = ttk.Entry(controls, width=10)
    poll_entry.grid(row=2, column=1, pady=4, sticky="w")

    read_button_kwargs = {"bootstyle": "primary"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Primary.TButton"}
    read_once_button = ttk.Button(controls, text="Read Once", **read_button_kwargs)
    read_once_button.grid(row=2, column=2, padx=(16, 8), pady=4, sticky="w")

    start_poll_button = ttk.Button(controls, text="Start Poll")
    start_poll_button.grid(row=2, column=3, pady=4, sticky="w")

    stop_button_kwargs = {"bootstyle": "danger"} if TTKBOOTSTRAP_AVAILABLE else {"style": "Danger.TButton"}
    stop_button = ttk.Button(controls, text="Stop", command=stop_callback, **stop_button_kwargs)
    stop_button.grid(row=2, column=4, padx=(16, 8), pady=4, sticky="w")

    clear_button = ttk.Button(controls, text="Clear", command=clear_callback)
    clear_button.grid(row=2, column=5, pady=4, sticky="w")

    values_frame = ttk.Labelframe(parent, text="Values", padding=(10, 8))
    values_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
    values_frame.grid_rowconfigure(0, weight=1)
    values_frame.grid_columnconfigure(0, weight=1)

    columns = ("address", "raw", "value")
    values_tree = ttk.Treeview(values_frame, columns=columns, show="headings", selectmode="browse")
    values_tree.heading("address", text="Address")
    values_tree.column("address", width=120, anchor="center", stretch=False)
    values_tree.heading("raw", text="Raw")
    values_tree.column("raw", width=240, anchor="w", stretch=False)
    values_tree.heading("value", text="Value")
    values_tree.column("value", width=520, anchor="w", stretch=True)

    values_scroll_y = ttk.Scrollbar(values_frame, orient="vertical", command=values_tree.yview)
    values_scroll_x = ttk.Scrollbar(values_frame, orient="horizontal", command=values_tree.xview)
    values_tree.configure(yscrollcommand=values_scroll_y.set, xscrollcommand=values_scroll_x.set)

    values_tree.grid(row=0, column=0, sticky="nsew")
    values_scroll_y.grid(row=0, column=1, sticky="ns")
    values_scroll_x.grid(row=1, column=0, sticky="ew")

    status_line = ttk.Label(parent, textvariable=status_var, anchor="w")
    status_line.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")

    def reset_defaults() -> None:
        unit_entry.delete(0, tk.END)
        unit_entry.insert(0, "1")
        function_combobox.set("Holding Registers (0x03)")
        start_entry.delete(0, tk.END)
        start_entry.insert(0, "0")
        count_entry.delete(0, tk.END)
        count_entry.insert(0, "10")
        data_type_combobox.set("UInt16")
        byte_order_combobox.set("Big")
        word_order_combobox.set("Big")
        bit_format_combobox.set("Bool (True/False)")
        poll_entry.delete(0, tk.END)
        poll_entry.insert(0, "1.0")

    def update_mode() -> None:
        mode = function_map.get(function_combobox.get(), "holding_registers")
        if mode in {"coils", "discrete_inputs"}:
            start_label.configure(text="Start address (0-based)")
            count_label.configure(text="Count (bits)")
            data_type_combobox.configure(state="disabled")
            byte_order_combobox.configure(state="disabled")
            word_order_combobox.configure(state="disabled")
            bit_format_combobox.configure(state="readonly")
        else:
            start_label.configure(text="Start register (0-based)")
            count_label.configure(text="Count (registers)")
            data_type_combobox.configure(state="readonly")
            byte_order_combobox.configure(state="readonly")
            word_order_combobox.configure(state="readonly")
            bit_format_combobox.configure(state="disabled")

    def validation_error(message: str) -> None:
        messagebox.showerror("Invalid Read Settings", message)

    def build_config() -> dict:
        try:
            conn_config = get_connection_config()
        except ValueError as exc:
            validation_error(str(exc))
            raise

        try:
            unit_id = int(unit_entry.get())
            start_address = int(start_entry.get())
            count = int(count_entry.get())
        except ValueError:
            validation_error("Please ensure Slave ID, Start register, and Count are valid integers.")
            raise

        if not (1 <= unit_id <= 247):
            validation_error("Slave ID must be between 1 and 247.")
            raise ValueError("Invalid Slave ID")

        if start_address < 0:
            validation_error("Start address must be 0 or greater.")
            raise ValueError("Invalid start address")

        if count <= 0:
            validation_error("Count must be 1 or greater.")
            raise ValueError("Invalid count")

        function_display = function_combobox.get()
        if function_display not in function_map:
            validation_error("Please select a valid function.")
            raise ValueError("Invalid function")

        read_type = function_map[function_display]
        if read_type in {"coils", "discrete_inputs"}:
            if count > 2000:
                validation_error("Count must be 2000 bits or less.")
                raise ValueError("Count too large")

            bit_format_display = bit_format_combobox.get()
            if bit_format_display not in bit_format_map:
                validation_error("Please select a valid bit format.")
                raise ValueError("Invalid bit format")

            config = dict(conn_config)
            config.update(
                {
                    "unit_id": unit_id,
                    "read_type": read_type,
                    "read_address": start_address,
                    "read_count": count,
                    "bit_format": bit_format_map[bit_format_display],
                }
            )
            return config

        if count > 125:
            validation_error("Count must be 125 registers or less.")
            raise ValueError("Count too large")

        data_type_display = data_type_combobox.get()
        if data_type_display not in data_type_map:
            validation_error("Please select a valid data type.")
            raise ValueError("Invalid data type")

        data_type_key, regs_per_value = data_type_map[data_type_display]
        if count % regs_per_value != 0:
            validation_error(f"Count must be a multiple of {regs_per_value} for {data_type_display}.")
            raise ValueError("Invalid count for data type")

        byte_order_display = byte_order_combobox.get()
        word_order_display = word_order_combobox.get()
        if byte_order_display not in endian_map or word_order_display not in endian_map:
            validation_error("Please select valid endianness options.")
            raise ValueError("Invalid endianness")

        config = dict(conn_config)
        config.update(
            {
                "unit_id": unit_id,
                "read_type": read_type,
                "read_address": start_address,
                "read_count": count,
                "data_type": data_type_key,
                "byte_order": endian_map[byte_order_display],
                "word_order": endian_map[word_order_display],
            }
        )

        return config

    def on_read_once() -> None:
        try:
            config = build_config()
        except Exception:
            return
        read_once_callback(config)

    def on_start_poll() -> None:
        try:
            config = build_config()
        except Exception:
            return

        try:
            interval_sec = float(poll_entry.get())
        except ValueError:
            validation_error("Poll interval must be a valid number of seconds.")
            return

        if interval_sec <= 0:
            validation_error("Poll interval must be greater than 0 seconds.")
            return

        start_poll_callback(config, interval_sec)

    reset_defaults()
    update_mode()
    function_combobox.bind("<<ComboboxSelected>>", lambda _event: update_mode())

    read_once_button.configure(command=on_read_once)
    start_poll_button.configure(command=on_start_poll)
    stop_button.configure(state="disabled")

    return values_tree, read_once_button, start_poll_button, stop_button, clear_button

def create_about_tab(parent):
    about_frame = ttk.Frame(parent, padding=(16, 14))
    about_frame.pack(fill="both", expand=1)

    card = ttk.Labelframe(about_frame, text="About", padding=(14, 10))
    card.pack(anchor="n", fill="x")

    title = ttk.Label(card, text="Modbus Scanner", font=("Segoe UI", 14, "bold"))
    title.pack(anchor="w")

    ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(10, 10))

    ttk.Label(card, text=f"Version: {APP_VERSION}").pack(anchor="w")
    ttk.Label(card, text="Author: Shan").pack(anchor="w", pady=(4, 0))
    ttk.Label(card, text="© 2026 Star Utilities Collection - Blue Star Qatar").pack(anchor="w", pady=(4, 0))
    ttk.Label(card, text="License: MIT").pack(anchor="w", pady=(4, 0))

    hint = ttk.Label(
        about_frame,
        text="Tip: Double-click any row in Results to view full details.",
        foreground="#475569",
    )
    hint.pack(anchor="w", pady=(12, 0))

    return about_frame

def create_preferences_tab(parent, theme_var, theme_callback):
    prefs_frame = ttk.Frame(parent, padding=(16, 14))
    prefs_frame.pack(fill="both", expand=1)

    appearance = ttk.Labelframe(prefs_frame, text="Appearance", padding=(14, 10))
    appearance.pack(anchor="n", fill="x")

    theme_toggle = ttk.Checkbutton(appearance, text="Dark mode", variable=theme_var, command=theme_callback)
    theme_toggle.pack(anchor="w")

    shortcuts = ttk.Labelframe(prefs_frame, text="Keyboard Shortcuts", padding=(14, 10))
    shortcuts.pack(anchor="n", fill="x", pady=(12, 0))

    ttk.Label(shortcuts, text="Ctrl+Enter — Start scan").pack(anchor="w")
    ttk.Label(shortcuts, text="Esc — Stop scan/read").pack(anchor="w", pady=(2, 0))
    ttk.Label(shortcuts, text="Ctrl+S — Save results").pack(anchor="w", pady=(2, 0))
    ttk.Label(shortcuts, text="Ctrl+L — Toggle results log").pack(anchor="w", pady=(2, 0))
    ttk.Label(shortcuts, text="F5 / Ctrl+R — Read once").pack(anchor="w", pady=(2, 0))
    ttk.Label(shortcuts, text="Ctrl+P — Start polling").pack(anchor="w", pady=(2, 0))
    ttk.Label(shortcuts, text="Ctrl+T — Toggle dark mode").pack(anchor="w", pady=(2, 0))

    return prefs_frame


def get_logo_base64():
    return """
    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
    """
