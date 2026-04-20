"""Bootstrap helpers for the PySide6 application shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from uvr_qt.state import load_app_state
from uvr_qt.ui.main_window import MainWindow


def run() -> int:
    """Start the Qt application."""
    app = QApplication(sys.argv)
    state = load_app_state()
    window = MainWindow(state=state)
    window.show()
    return app.exec()

