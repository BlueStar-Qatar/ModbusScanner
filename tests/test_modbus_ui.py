import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # Add this line to modify the path

import pytest
from tkinter import Tk
from modbus_scanner_app import ModbusScannerApp

@pytest.fixture
def app():
    root = Tk()
    app = ModbusScannerApp(root)
    return app

def test_ui_initialization(app):
    assert app.root is not None  # Ensure root window exists
    assert app.notebook is not None  # Check if notebook (tab container) is initialized
    assert app.logo_label is not None  # Ensure the logo label is created
