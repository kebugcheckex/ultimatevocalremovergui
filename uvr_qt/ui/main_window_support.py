"""Support mixins and helpers for the Qt main window."""

from __future__ import annotations

import traceback
from dataclasses import replace

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from __version__ import VERSION
from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings
from uvr.config.profiles import ProfileError
from uvr_qt.services import JobCancelledError, ProcessResult, ProcessingFacade
from uvr_qt.state import AppState


class MainWindowDialogMixin:
    def _build_menu_bar(self) -> None:
        tools_menu = self.menuBar().addMenu("&Tools")
        self.open_download_manager_action = QAction("Model Downloads", self)
        self.open_download_manager_action.triggered.connect(self._open_download_manager)
        tools_menu.addAction(self.open_download_manager_action)

        help_menu = self.menuBar().addMenu("&Help")
        self.quick_start_action = QAction("Quick Start", self)
        self.quick_start_action.triggered.connect(self._show_quick_start_dialog)
        help_menu.addAction(self.quick_start_action)

        self.last_error_action = QAction("View Last Error", self)
        self.last_error_action.triggered.connect(self._show_last_error_dialog)
        help_menu.addAction(self.last_error_action)

        self.about_action = QAction("About UVR", self)
        self.about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(self.about_action)

    def _show_quick_start_dialog(self) -> None:
        QMessageBox.information(
            self,
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

    def _show_about_dialog(self) -> None:
        config_path = str(self.config_path) if self.config_path else "default config path"
        QMessageBox.about(
            self,
            "About Ultimate Vocal Remover",
            "\n".join(
                (
                    f"Ultimate Vocal Remover {VERSION}",
                    "PySide6 frontend on top of the shared uvr_core backend.",
                    f"Settings path: {config_path}",
                )
            ),
        )

    def _show_last_error_dialog(self) -> None:
        if not self.state.runtime.last_error:
            QMessageBox.information(self, "Last Error", "No processing errors have been recorded in this session.")
            return
        self._show_error_dialog("Last Processing Error", self.state.runtime.last_error)

    def _show_error_dialog(self, title: str, message: str) -> None:
        summary = message.strip().splitlines()[0] if message.strip() else "An unknown error occurred."
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(summary)
        dialog.setInformativeText("See details for the full traceback.")
        dialog.setDetailedText(message)
        dialog.exec()


class MainWindowProfileMixin:
    def _build_profiles_group(self) -> QGroupBox:
        group = QGroupBox("Saved Profiles")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Profile"), 0, 0)
        self.profile_combo = QComboBox(group)
        self.profile_combo.currentTextChanged.connect(lambda _value: self._refresh_profile_controls())
        layout.addWidget(self.profile_combo, 0, 1)

        button_row = QWidget(group)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.save_profile_button = QPushButton("Save Current", group)
        self.save_profile_button.clicked.connect(self._save_profile)
        self.load_profile_button = QPushButton("Load Selected", group)
        self.load_profile_button.clicked.connect(self._load_profile)
        self.delete_profile_button = QPushButton("Delete Selected", group)
        self.delete_profile_button.clicked.connect(self._delete_profile)
        self.refresh_profiles_button = QPushButton("Refresh", group)
        self.refresh_profiles_button.clicked.connect(self._refresh_view)

        button_layout.addWidget(self.save_profile_button)
        button_layout.addWidget(self.load_profile_button)
        button_layout.addWidget(self.delete_profile_button)
        button_layout.addWidget(self.refresh_profiles_button)
        button_layout.addStretch(1)

        self.profile_status_label = QLabel(group)
        self.profile_status_label.setWordWrap(True)
        self.profile_status_label.setStyleSheet("color: #5f6b7a;")

        layout.addWidget(button_row, 1, 0, 1, 2)
        layout.addWidget(self.profile_status_label, 2, 0, 1, 2)
        return group

    def _refresh_profile_controls(self) -> None:
        selected_profile = self.profile_combo.currentText() if hasattr(self, "profile_combo") else ""
        profiles = self.profile_store.list_profiles()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(list(profiles))
        if selected_profile in profiles:
            self.profile_combo.setCurrentText(selected_profile)
        self.profile_combo.blockSignals(False)
        has_selection = bool(self.profile_combo.currentText())
        is_processing = self.state.runtime.is_processing
        self.save_profile_button.setEnabled(not is_processing)
        self.load_profile_button.setEnabled(not is_processing and has_selection)
        self.delete_profile_button.setEnabled(not is_processing and has_selection)
        self.refresh_profiles_button.setEnabled(True)
        if profiles:
            self.profile_status_label.setText(f"{len(profiles)} saved profile(s) available.")
        else:
            self.profile_status_label.setText("No saved profiles yet.")

    def _save_profile(self) -> None:
        if self.state.runtime.is_processing:
            return
        profile_name, accepted = QInputDialog.getText(
            self,
            "Save Profile",
            "Profile name:",
            text=self.profile_combo.currentText(),
        )
        if not accepted:
            return
        try:
            saved_name = self.profile_store.save_profile(profile_name, self.state.to_legacy_dict())
        except (OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return
        self._refresh_view()
        self.profile_combo.setCurrentText(saved_name)
        self._append_log(f'Saved profile: "{saved_name}"')
        self._set_runtime(status_text=f'Profile saved: "{saved_name}"', last_error=None)

    def _load_profile(self) -> None:
        if self.state.runtime.is_processing:
            return
        profile_name = self.profile_combo.currentText().strip()
        if not profile_name:
            return
        try:
            payload = self.profile_store.load_profile(profile_name)
        except (FileNotFoundError, OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Load Profile Failed", str(exc))
            self._refresh_view()
            return

        loaded_state = AppState.from_settings(AppSettings.from_legacy_dict(payload, DEFAULT_DATA))
        loaded_runtime = replace(
            self.state.runtime,
            status_text=f'Profile loaded: "{profile_name}"',
            last_error=None,
        )
        self.state = replace(loaded_state, paths=self.state.paths, runtime=loaded_runtime)
        self._persist_state()
        self._append_log(f'Loaded profile: "{profile_name}"')
        self._refresh_view()

    def _delete_profile(self) -> None:
        if self.state.runtime.is_processing:
            return
        profile_name = self.profile_combo.currentText().strip()
        if not profile_name:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Profile",
            f'Delete profile "{profile_name}"?',
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.profile_store.delete_profile(profile_name)
        except (FileNotFoundError, OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Delete Profile Failed", str(exc))
            self._refresh_view()
            return
        self._append_log(f'Deleted profile: "{profile_name}"')
        self._set_runtime(status_text=f'Profile deleted: "{profile_name}"', last_error=None)
        self._refresh_view()


class ProcessingWorker(QObject):
    finished = Signal(object)
    cancelled = Signal()
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: ProcessingFacade, state: AppState):
        super().__init__()
        self.facade = facade
        self.state = state

    def cancel(self) -> None:
        self.facade.cancel()

    def run(self) -> None:
        try:
            result = self.facade.process(
                self.state,
                log=self.log_emitted.emit,
                progress=lambda value: self.progress_emitted.emit(int(max(0, min(value, 100)))),
                status=self.status_emitted.emit,
            )
        except JobCancelledError:
            self.cancelled.emit()
            return
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self.failed.emit(error_message)
            return

        self.finished.emit(result)
