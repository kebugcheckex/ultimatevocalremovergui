"""Dialog mixin for the Qt main window."""

from __future__ import annotations

from PySide6.QtGui import QAction

from uvr_qt.ui.dialogs.info_dialogs import (
    show_about_dialog,
    show_error_dialog,
    show_last_error_dialog,
    show_quick_start_dialog,
)


class MainWindowDialogMixin:
    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        select_inputs_action = QAction("Select Input Files...", self)
        select_inputs_action.triggered.connect(self._select_input_files)
        file_menu.addAction(select_inputs_action)
        select_output_action = QAction("Set Output Folder...", self)
        select_output_action.triggered.connect(self._select_output_directory)
        file_menu.addAction(select_output_action)

        tools_menu = self.menuBar().addMenu("&Tools")
        downloads_action = QAction("Download Models...", self)
        downloads_action.triggered.connect(self._open_download_manager)
        tools_menu.addAction(downloads_action)
        advanced_action = QAction("Advanced Settings...", self)
        advanced_action.triggered.connect(self._open_advanced_settings)
        tools_menu.addAction(advanced_action)
        profiles_action = QAction("Manage Profiles...", self)
        profiles_action.triggered.connect(self._open_profiles_dialog)
        tools_menu.addAction(profiles_action)
        model_defaults_action = QAction("Model Defaults...", self)
        model_defaults_action.triggered.connect(self._open_model_defaults_dialog)
        tools_menu.addAction(model_defaults_action)
        tools_menu.addSeparator()
        ensemble_action = QAction("Manual Ensemble...", self)
        ensemble_action.triggered.connect(self._open_ensemble_window)
        tools_menu.addAction(ensemble_action)
        audio_tools_action = QAction("Audio Tools...", self)
        audio_tools_action.triggered.connect(self._open_audio_tools_window)
        tools_menu.addAction(audio_tools_action)

        help_menu = self.menuBar().addMenu("&Help")
        self.quick_start_action = QAction("Quick Start Guide", self)
        self.quick_start_action.triggered.connect(self._show_quick_start_dialog)
        help_menu.addAction(self.quick_start_action)
        self.last_error_action = QAction("View Last Error", self)
        self.last_error_action.triggered.connect(self._show_last_error_dialog)
        help_menu.addAction(self.last_error_action)
        help_menu.addSeparator()
        self.about_action = QAction("About UVR", self)
        self.about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(self.about_action)

    def _show_quick_start_dialog(self) -> None:
        show_quick_start_dialog(self)

    def _show_about_dialog(self) -> None:
        show_about_dialog(self, self.config_path)

    def _show_last_error_dialog(self) -> None:
        last_error = self.state.runtime.last_error
        if not last_error:
            show_last_error_dialog(self, None)
        else:
            self._show_error_dialog("Last Processing Error", last_error)

    def _show_error_dialog(self, title: str, message: str) -> None:
        show_error_dialog(self, title, message)
