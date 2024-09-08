import tkinter as tk
from tkinter import ttk
from modbus_ui import create_about_tab, create_settings_tab, create_results_tab, get_logo_base64
from modbus_helpers import switch_to_tab
from modbus_scanner import start_modbus_scan
import threading
from PIL import Image, ImageTk  # Import the necessary modules

import base64
from io import BytesIO

# Convert the base64 string back to an image
def load_logo_from_base64():
    logo_base64 = get_logo_base64()  # Call the function to get the base64 string
    logo_data = base64.b64decode(logo_base64)
    logo_image = Image.open(BytesIO(logo_data))  # Load the image from the byte stream
    return ImageTk.PhotoImage(logo_image)  # Since it's already resized, no need to resize again

class ModbusScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modbus Scanner - Blue Star Qatar")
        
        # Set root background to match dark theme
        self.root.configure(background="#2e2e2e")

        # Apply Dark Theme
        self.apply_dark_theme()

        # Create a top frame for logo and title
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill="x", pady=10)

        # Load and display the logo from base64
        self.logo_image = load_logo_from_base64()  # Call the function to load the logo
        self.logo_label = ttk.Label(self.top_frame, image=self.logo_image, background="#2e2e2e")
        self.logo_label.grid(row=0, column=0,  padx=10)

        # Add a title text next to the logo
        self.title_label = ttk.Label(self.top_frame, text="Modbus Scanner", font=("Arial", 18, "bold"), background="#2e2e2e", foreground="#ffffff", anchor="e")
        self.title_label.grid(row=0, column=1, columnspan=2, padx=10)


        # Add a description text below the title
        self.description_label = ttk.Label(self.top_frame, text="This application scans a range of Modbus addresses to identify connected devices.\nConfigure your parameters and click start.", 
                                           font=("Arial", 10), background="#2e2e2e", foreground="#cccccc", wraplength=400)
        self.description_label.grid(row=1, column=0, columnspan=2, padx=10, pady=10)



        # Create a Notebook (tabs container)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=5, expand=True)

        # Create stop event for stopping the scan
        self.stop_event = threading.Event()

        # Create tabs
        self.settings_frame = ttk.Frame(self.notebook, width=400, height=280)
        self.results_frame = ttk.Frame(self.notebook, width=400, height=280)

        self.settings_frame.pack(fill="both", expand=1)
        self.results_frame.pack(fill="both", expand=1)

        # Add tabs to Notebook
        self.notebook.add(self.settings_frame, text='Settings')
        self.notebook.add(self.results_frame, text='Results')

        # Create the About tab
        self.about_frame = create_about_tab(self.notebook)
        self.notebook.add(self.about_frame, text='About')
        
        # Initialize the tabs
        create_settings_tab(self.settings_frame, self.start_scan, self.stop_event)
        self.result_text, self.progress_bar = create_results_tab(self.results_frame, self.stop_scan)

    def apply_dark_theme(self):
        # Configure a dark theme using ttk.Style
        style = ttk.Style()

        # Set the default theme to 'clam', which is better suited for styling
        style.theme_use("clam")

        # Define dark theme colors for all widgets
        dark_bg = "#2e2e2e"
        light_bg = "#444444"
        text_color = "#ffffff"
        button_hover_color = "#5e5e5e"

        # Apply styles to frames, labels, buttons, tabs, and other widgets
        style.configure("TFrame", background=dark_bg)  # Frame backgrounds
        style.configure("TLabel", background=dark_bg, foreground=text_color)  # Label text
        style.configure("TButton", background=light_bg, foreground=text_color, relief="flat")  # Button background and text
        style.map("TButton", background=[("active", button_hover_color)])  # Button hover effect
        style.configure("TNotebook", background=dark_bg)  # Notebook background
        style.configure("TNotebook.Tab", background=light_bg, foreground=text_color, padding=10)  # Tab background and text
        style.map("TNotebook.Tab", background=[("selected", dark_bg)])  # Selected tab styling

        # Text boxes and progress bar styles
        style.configure("TEntry", fieldbackground=light_bg, foreground=text_color)
        style.configure("TProgressbar", background="#5e5e5e", troughcolor=dark_bg)

        # Apply the same dark theme to other widgets like Combobox, Scrollbars, etc.
        style.configure("TCombobox", fieldbackground=light_bg, foreground=text_color)
        style.map("TCombobox", fieldbackground=[("readonly", light_bg)], foreground=[("readonly", text_color)])

    def start_scan(self, config, stop_event):
        # Switch to the results tab
        switch_to_tab(self.notebook, self.results_frame)

        # Clear previous results
        self.result_text.delete(1.0, tk.END)

        # Start scanning (with progress bar)
        start_modbus_scan(config, self.stop_event, self.result_text, self.progress_bar)

    def stop_scan(self):
        # Signal to stop the scan
        self.stop_event.set()

# Main window creation
if __name__ == '__main__':
    root = tk.Tk()
    app = ModbusScannerApp(root)
    root.mainloop()
