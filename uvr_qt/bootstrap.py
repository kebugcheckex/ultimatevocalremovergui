"""Bootstrap helpers for the PySide6 application shell."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from uvr.config.persistence import DEFAULT_DATA_FILE
from uvr_qt.state import load_app_state
from uvr_qt.ui.main_window import MainWindow


def run(config_path: str | Path | None = None) -> int:
    """Start the Qt application."""
    app = QApplication(sys.argv)
    state = load_app_state(config_path)
    window = MainWindow(state=state, config_path=config_path)
    window.show()
    return app.exec()


def default_config_path() -> Path:
    """Return the default persisted settings path for UI launchers."""
    return DEFAULT_DATA_FILE
