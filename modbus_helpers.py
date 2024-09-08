import tkinter as tk
from tkinter import ttk, messagebox

def switch_to_tab(notebook, tab_frame):
    notebook.select(tab_frame)

def log_results(results):
    with open("modbus_scan_results.txt", "w") as file:
        file.write(results)
    messagebox.showinfo("Save Successful", "Results saved to modbus_scan_results.txt")
