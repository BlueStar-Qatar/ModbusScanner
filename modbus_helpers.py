from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union


def switch_to_tab(notebook, tab_frame) -> None:
    notebook.select(tab_frame)


def get_default_results_dir() -> Path:
    home = Path.home()
    documents = home / "Documents"
    if documents.exists() and documents.is_dir():
        return documents
    return home


def default_results_path(suffix: str = ".txt") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return get_default_results_dir() / f"modbus_scan_results_{timestamp}{suffix}"


def write_text_file(path: Union[str, Path], text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
