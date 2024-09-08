import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
import threading

def create_settings_tab(parent, scan_callback, stop_event):
    # Configuration dictionary
    config = {}
    
    # Detect available serial ports and populate the combobox
    def get_serial_ports():
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    # Map descriptive parity values to actual values
    parity_map = {
        'N (None)': 'N',
        'E (Even)': 'E',
        'O (Odd)': 'O'
    }

    # Function to start scan in a separate thread
    def on_scan():
       # Clear the stop event flag before starting a new scan
        stop_event.clear()

        # Collect user input into config and call the scan callback
        config['port'] = port_combobox.get()
        config['baudrate'] = int(baudrate_combobox.get())
        config['parity'] = parity_map[parity_combobox.get()]  # Use the mapped value
        config['stopbits'] = int(stopbits_combobox.get())
        config['bytesize'] = int(bytesize_combobox.get())
        config['start_address'] = int(start_address_entry.get())
        config['end_address'] = int(end_address_entry.get())
        config['timeout'] = int(timeout_combobox.get())

        # Start the scan in a new thread, pass the stop event to the scan callback
        scan_thread = threading.Thread(target=scan_callback, args=(config, stop_event))
        scan_thread.start()

    # Function to stop scan
    def on_stop():
        stop_event.set()  # Set the stop event flag to signal the scan to stop

    # Serial Port Selection (ComboBox)
    ttk.Label(parent, text="Select Port:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
    port_combobox = ttk.Combobox(parent, values=get_serial_ports())
    port_combobox.grid(row=0, column=1, padx=10, pady=5)
    if port_combobox['values']:  # Set the first available port as default
        port_combobox.current(0)

    def refresh_ports():
        port_combobox['values'] = get_serial_ports()
        if port_combobox['values']:
            port_combobox.current(0)

    # Add a refresh button in the UI
    ttk.Button(parent, text="Refresh Ports", command=refresh_ports).grid(row=0, column=2, padx=5, pady=5)


    # Baudrate Selection (ComboBox)
    ttk.Label(parent, text="Baudrate:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    baudrate_combobox = ttk.Combobox(parent, values=['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200'])
    baudrate_combobox.grid(row=1, column=1, padx=10, pady=5)
    baudrate_combobox.current(3)  # Default is 9600

    # Parity Selection (ComboBox)
    ttk.Label(parent, text="Parity:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    parity_combobox = ttk.Combobox(parent, values=['N (None)', 'E (Even)', 'O (Odd)'])
    parity_combobox.grid(row=2, column=1, padx=10, pady=5)
    parity_combobox.current(0)  # Default is None

    # Stopbits Selection (ComboBox)
    ttk.Label(parent, text="Stopbits:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
    stopbits_combobox = ttk.Combobox(parent, values=['1', '2'])
    stopbits_combobox.grid(row=3, column=1, padx=10, pady=5)
    stopbits_combobox.current(0)  # Default is 1

    # Bytesize Selection (ComboBox)
    ttk.Label(parent, text="Bytesize:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
    bytesize_combobox = ttk.Combobox(parent, values=['5', '6', '7', '8'])
    bytesize_combobox.grid(row=4, column=1, padx=10, pady=5)
    bytesize_combobox.current(3)  # Default is 8

    # Timeout Selection (ComboBox)
    ttk.Label(parent, text="Timeout (sec):").grid(row=5, column=0, padx=10, pady=5, sticky="w")
    timeout_combobox = ttk.Combobox(parent, values=['1', '2', '3', '4', '5', '10'])
    timeout_combobox.grid(row=5, column=1, padx=10, pady=5)
    timeout_combobox.current(0)  # Default is 1 second

    # draw a line
    ttk.Separator(parent, orient='horizontal').grid(row=6, columnspan=3, sticky="ew", pady=10)

    # Start Address (Textbox)
    ttk.Label(parent, text="Start Address:").grid(row=7, column=0, padx=10, pady=5, sticky="w")
    start_address_entry = ttk.Entry(parent)
    start_address_entry.grid(row=7, column=1, padx=10, pady=5)
    start_address_entry.insert(0, '1')

    # End Address (Textbox)
    ttk.Label(parent, text="End Address:").grid(row=8, column=0, padx=10, pady=5, sticky="w")
    end_address_entry = ttk.Entry(parent)
    end_address_entry.grid(row=8, column=1, padx=10, pady=5)
    end_address_entry.insert(0, '247')


    # Start and Stop Scan Buttons
    ttk.Button(parent, text="Start Scan", command=on_scan).grid(row=9, column=1, padx=10, pady=10)
    ttk.Button(parent, text="Stop Scan", command=on_stop).grid(row=9, column=2, padx=10, pady=10)



def create_results_tab(parent, stop_callback):
    # Result display area
    result_text = tk.Text(parent, height=10, width=50)
    result_text.grid(row=0, column=0, padx=10, pady=10)

    # Progress bar
    progress_bar = ttk.Progressbar(parent, orient='horizontal', length=300, mode='determinate')
    progress_bar.grid(row=1, column=0, padx=10, pady=10)

    # Stop Scan Button in Results Tab
    ttk.Button(parent, text="Stop Scan", command=stop_callback).grid(row=2, column=0, padx=10, pady=10)

    return result_text, progress_bar

def create_about_tab(parent):
    # Create a frame for the content inside the About tab
    about_frame = ttk.Frame(parent)
    about_frame.pack(fill="both", expand=1, padx=10, pady=10)

    # Create a rectangular box using a Canvas for the background
    canvas = tk.Canvas(about_frame, height=150, width=300, bg="#2e2e2e", highlightthickness=0)
    canvas.pack(padx=20, pady=20)

    # Draw a rectangle inside the canvas (adjust the coordinates to fit your design)
    canvas.create_rectangle(10, 10, 290, 140, outline="#ffffff", width=2)

    # Add text information inside the rectangular box
    app_group = ttk.Label(about_frame, text="Modbus Scanner App", font=("Arial", 10), background="#2e2e2e", foreground="#ffffff")
    app_group.place(x=75, y=45)

    version_label = ttk.Label(about_frame, text="Version: 0.1.0", font=("Arial", 8), background="#2e2e2e", foreground="#ffffff")
    version_label.place(x=75, y=70)
    
    authors = ttk.Label(about_frame, text="Author : Shan", font=("Arial", 8), background="#2e2e2e", foreground="#ffffff")
    authors.place(x=75, y=90)
    
    copyright_label = ttk.Label(about_frame, text="© 2024 Star Utilities Collection - Blue Star Qatar", font=("Arial", 8), background="#2e2e2e", foreground="#ffffff")
    copyright_label.place(x=75, y=110)
    
    license_label = ttk.Label(about_frame, text="License: MIT", font=("Arial", 8), background="#2e2e2e", foreground="#ffffff")
    license_label.place(x=75, y=130)

    return about_frame

def get_logo_base64():
    return """
    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
    """
