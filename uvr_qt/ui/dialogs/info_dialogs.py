"""Simple informational dialogs (quick-start, about, error)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from __version__ import VERSION


def show_quick_start_dialog(parent: QWidget) -> None:
    QMessageBox.information(
        parent,
        "Quick Start",
        "\n".join(
            (
                "1. Select one or more input audio files.",
                "2. Choose an output folder.",
                "3. Pick a process method and installed model.",
                "4. Adjust output or advanced options as needed.",
                "5. Start processing and monitor progress in the log panel.",
            )
        ),
    )


def show_about_dialog(parent: QWidget, config_path: str | Path | None) -> None:
    path_str = str(config_path) if config_path else "default config path"
    QMessageBox.about(
        parent,
        "About Ultimate Vocal Remover",
        "\n".join(
            (
                f"Ultimate Vocal Remover {VERSION}",
                "PySide6 frontend on top of the shared uvr_core backend.",
                f"Settings path: {path_str}",
            )
        ),
    )


def show_last_error_dialog(parent: QWidget, last_error: str | None) -> None:
    if not last_error:
        QMessageBox.information(parent, "Last Error", "No processing errors have been recorded in this session.")
        return
    show_error_dialog(parent, "Last Processing Error", last_error)


def show_error_dialog(parent: QWidget, title: str, message: str) -> None:
    summary = message.strip().splitlines()[0] if message.strip() else "An unknown error occurred."
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(summary)
    dialog.setInformativeText("See details for the full traceback.")
    dialog.setDetailedText(message)
    dialog.exec()
