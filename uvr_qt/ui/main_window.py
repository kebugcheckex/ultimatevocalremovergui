"""Main window for the PySide6 UVR shell."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QFileDialog, QMainWindow, QVBoxLayout, QWidget

from gui_data.constants import ALL_STEMS, DEFAULT_DATA, STEM_SET_MENU
from uvr.config.models import AppSettings
from uvr.config.persistence import save_settings
from uvr.config.profiles import SettingsProfileStore
from uvr_qt.services import ProcessResult, ProcessingFacade
from uvr_qt.state import AppState
from uvr_qt.ui.audio_tools_window import AudioToolsWindow
from uvr_qt.ui.dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from uvr_qt.ui.dialogs.model_defaults_dialog import ModelDefaultsDialog
from uvr_qt.ui.dialogs.profiles_dialog import ProfilesDialog
from uvr_qt.ui.download_manager_window import DownloadManagerWindow
from uvr_qt.ui.ensemble_window import EnsembleWindow
from uvr_qt.ui.main_window_builders import build_header, build_paths_group, build_process_group, build_summary_group
from uvr_qt.ui.main_window_handlers import MainWindowHandlersMixin
from uvr_qt.ui.main_window_refresh import MainWindowRefreshMixin
from uvr_qt.ui.main_window_support import MainWindowDialogMixin
from uvr_qt.ui.model_utils import available_aux_models, available_stem_targets
from uvr_qt.ui.processing_worker import ProcessingWorker


class MainWindow(MainWindowRefreshMixin, MainWindowHandlersMixin, MainWindowDialogMixin, QMainWindow):
    """Primary Qt window: paths, processing controls, progress."""

    def __init__(
        self,
        state: AppState,
        processing_facade: ProcessingFacade | None = None,
        config_path: str | Path | None = None,
        profile_store: SettingsProfileStore | None = None,
    ):
        super().__init__()
        self.state = state
        self.config_path = config_path
        self.processing_facade: ProcessingFacade | None = processing_facade
        self.profile_store = profile_store or SettingsProfileStore(default_data=DEFAULT_DATA)
        self.download_manager_window: DownloadManagerWindow | None = None
        self.ensemble_window: EnsembleWindow | None = None
        self.audio_tools_window: AudioToolsWindow | None = None
        self._advanced_dialog: AdvancedSettingsDialog | None = None
        self._profiles_dialog: ProfilesDialog | None = None
        self._model_defaults_dialog: ModelDefaultsDialog | None = None
        self.processing_thread: QThread | None = None
        self.processing_worker: ProcessingWorker | None = None
        self._is_syncing_processing_controls = False
        self.setWindowTitle("Ultimate Vocal Remover")
        self.resize(920, 640)
        self._build_menu_bar()

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)
        root_layout.addWidget(build_header(self))
        root_layout.addWidget(build_paths_group(self))
        root_layout.addWidget(build_process_group(self))
        root_layout.addWidget(build_summary_group(self))
        root_layout.addStretch(1)
        self.setCentralWidget(central_widget)
        self._refresh_view()

    # ── File path operations ─────────────────────────────────────────────────

    def _select_input_files(self) -> None:
        start_dir = self._dialog_directory()
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Input Files",
            start_dir,
            "Audio Files (*.wav *.flac *.mp3 *.m4a *.ogg *.aiff *.aif *.wma);;All Files (*)",
        )
        if not files:
            return
        last_directory = str(Path(files[0]).parent)
        self._update_paths(input_paths=tuple(files), last_directory=last_directory)

    def _clear_input_files(self) -> None:
        self._update_paths(input_paths=())

    def _select_output_directory(self) -> None:
        start_dir = self._dialog_directory()
        directory = QFileDialog.getExistingDirectory(self, "Select Output Folder", start_dir)
        if not directory:
            return
        self._update_paths(export_path=directory, last_directory=directory)

    def _clear_output_directory(self) -> None:
        self._update_paths(export_path="")

    def _dialog_directory(self) -> str:
        if self.state.paths.last_directory:
            return self.state.paths.last_directory
        if self.state.paths.export_path:
            return self.state.paths.export_path
        return str(Path.cwd())

    def _update_paths(self, **changes: object) -> None:
        self.state = replace(self.state, paths=replace(self.state.paths, **changes))
        self._persist_state()
        self._refresh_view()

    # ── State persistence ────────────────────────────────────────────────────

    def _persist_state(self) -> None:
        settings = AppSettings.from_legacy_dict(self.state.to_legacy_dict(), DEFAULT_DATA)
        save_settings(settings=settings, data_file=self.config_path)

    def _get_processing_facade(self) -> ProcessingFacade:
        if self.processing_facade is None:
            self.processing_facade = ProcessingFacade()
        return self.processing_facade

    # ── Dialog launchers ─────────────────────────────────────────────────────

    def _open_download_manager(self) -> None:
        if self.download_manager_window is None:
            self.download_manager_window = DownloadManagerWindow()
        self.download_manager_window.show()
        self.download_manager_window.raise_()
        self.download_manager_window.activateWindow()

    def _open_ensemble_window(self) -> None:
        if self.ensemble_window is None:
            self.ensemble_window = EnsembleWindow()
        self.ensemble_window.show()
        self.ensemble_window.raise_()
        self.ensemble_window.activateWindow()

    def _open_audio_tools_window(self) -> None:
        if self.audio_tools_window is None:
            self.audio_tools_window = AudioToolsWindow()
        self.audio_tools_window.show()
        self.audio_tools_window.raise_()
        self.audio_tools_window.activateWindow()

    def _open_model_defaults_dialog(self) -> None:
        facade = self._get_processing_facade()
        if self._model_defaults_dialog is None:
            self._model_defaults_dialog = ModelDefaultsDialog(
                state=self.state,
                facade=facade,
                parent=self,
            )
        else:
            self._model_defaults_dialog.update_from_state(self.state)
        self._model_defaults_dialog.show()
        self._model_defaults_dialog.raise_()
        self._model_defaults_dialog.activateWindow()

    def _open_advanced_settings(self) -> None:
        if self._advanced_dialog is None:
            self._advanced_dialog = AdvancedSettingsDialog(
                state=self.state,
                on_state_changed=self._on_advanced_state_changed,
                parent=self,
            )
        facade = self._get_processing_facade()
        self._advanced_dialog.update_from_state(
            self.state,
            aux_models=available_aux_models(facade),
            mdx_stems=available_stem_targets(facade, self.state, "MDX-Net", fallback=(ALL_STEMS, *STEM_SET_MENU)),
            demucs_stems=available_stem_targets(facade, self.state, "Demucs", fallback=(ALL_STEMS, *STEM_SET_MENU)),
        )
        self._advanced_dialog.show()
        self._advanced_dialog.raise_()
        self._advanced_dialog.activateWindow()

    def _open_profiles_dialog(self) -> None:
        if self._profiles_dialog is None:
            self._profiles_dialog = ProfilesDialog(
                profile_store=self.profile_store,
                state=self.state,
                on_state_changed=self._on_profile_state_changed,
                parent=self,
            )
        else:
            self._profiles_dialog.update_from_state(self.state)
        self._profiles_dialog.show()
        self._profiles_dialog.raise_()
        self._profiles_dialog.activateWindow()

    def _on_advanced_state_changed(self, new_state: AppState) -> None:
        self.state = new_state
        self._persist_state()
        self._refresh_view()

    def _on_profile_state_changed(self, new_state: AppState) -> None:
        self.state = new_state
        self._persist_state()
        self._append_log(f'Loaded profile: "{new_state.runtime.status_text}"')
        self._refresh_view()

    # ── Processing pipeline ──────────────────────────────────────────────────

    def _start_processing(self) -> None:
        if self.processing_thread is not None:
            return
        self._set_runtime(
            is_processing=True,
            can_cancel=True,
            progress=0.0,
            status_text="Preparing",
            log_lines=(),
            last_error=None,
        )
        self.processing_thread = QThread(self)
        self.processing_worker = ProcessingWorker(self._get_processing_facade(), self.state)
        self.processing_worker.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.processing_worker.run)
        self.processing_worker.log_emitted.connect(self._append_log)
        self.processing_worker.progress_emitted.connect(self.progress_bar.setValue)
        self.processing_worker.progress_emitted.connect(self._set_runtime_progress)
        self.processing_worker.status_emitted.connect(self._set_runtime_status)
        self.processing_worker.cancelled.connect(self._processing_cancelled)
        self.processing_worker.failed.connect(self._processing_failed)
        self.processing_worker.finished.connect(self._processing_finished)
        self.processing_worker.finished.connect(self.processing_thread.quit)
        self.processing_worker.cancelled.connect(self.processing_thread.quit)
        self.processing_worker.failed.connect(self.processing_thread.quit)
        self.processing_thread.finished.connect(self._cleanup_processing_thread)
        self.processing_thread.start()

    def _cancel_processing(self) -> None:
        if self.processing_worker is None:
            return
        self._set_runtime(status_text="Cancelling", can_cancel=False)
        self.processing_worker.cancel()

    def _processing_finished(self, result: ProcessResult) -> None:
        self._append_log(f'Output folder: "{result.output_path}"')
        self._append_log(f"Model used: {result.model.process_method} / {result.model.model_name}")
        self._set_runtime(
            is_processing=False,
            can_cancel=False,
            progress=100.0,
            status_text=f"Completed: {len(result.processed_files)} file(s)",
        )

    def _processing_cancelled(self) -> None:
        self._set_runtime(is_processing=False, can_cancel=False, progress=0.0, status_text="Cancelled")

    def _processing_failed(self, message: str) -> None:
        self._append_log(message)
        self._set_runtime(is_processing=False, can_cancel=False, status_text="Failed", last_error=message)
        self._show_error_dialog("Processing Failed", message)

    def _cleanup_processing_thread(self) -> None:
        if self.processing_worker is not None:
            self.processing_worker.deleteLater()
        if self.processing_thread is not None:
            self.processing_thread.deleteLater()
        self.processing_worker = None
        self.processing_thread = None

    # ── Runtime helpers ──────────────────────────────────────────────────────

    def _append_log(self, message: str) -> None:
        self._set_runtime(log_lines=self.state.runtime.log_lines + (message,))

    def _sync_log_console(self) -> None:
        desired = "\n".join(self.state.runtime.log_lines)
        if self.log_console.toPlainText() != desired:
            self.log_console.setPlainText(desired)

    def _set_runtime(self, **changes: object) -> None:
        self.state = replace(self.state, runtime=replace(self.state.runtime, **changes))
        self._refresh_view()

    def _set_runtime_progress(self, value: int) -> None:
        self._set_runtime(progress=float(value))

    def _set_runtime_status(self, value: str) -> None:
        self._set_runtime(status_text=value)
