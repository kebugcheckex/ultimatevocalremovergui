"""Main window for the initial PySide6 UVR shell."""

from __future__ import annotations

import traceback
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import DEFAULT_DATA, FLAC, MP3, WAV, WAV_TYPE
from uvr.config.models import AppSettings
from uvr.config.persistence import save_settings
from uvr_qt.services import ProcessResult, ProcessingFacade
from uvr_qt.state import AppState


class MainWindow(QMainWindow):
    """Basic Qt shell with input/output path selection."""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.processing_facade: ProcessingFacade | None = None
        self.processing_thread: QThread | None = None
        self.processing_worker: _ProcessingWorker | None = None
        self._is_syncing_processing_controls = False
        self.setWindowTitle("Ultimate Vocal Remover")
        self.resize(920, 640)

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_paths_group())
        root_layout.addWidget(self._build_process_group())
        root_layout.addWidget(self._build_summary_group())
        root_layout.addStretch(1)

        self.setCentralWidget(central_widget)
        self._refresh_view()

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("PySide6 Frontend")
        title.setObjectName("windowTitle")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")

        subtitle = QLabel(
            "First shell: select input files and an output directory using the new Qt state model."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #5f6b7a;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Paths")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        input_label = QLabel("Input Files")
        self.input_paths_field = QPlainTextEdit()
        self.input_paths_field.setReadOnly(True)
        self.input_paths_field.setPlaceholderText("No input files selected")
        self.input_paths_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        input_buttons = QWidget(group)
        input_buttons_layout = QVBoxLayout(input_buttons)
        input_buttons_layout.setContentsMargins(0, 0, 0, 0)
        input_buttons_layout.setSpacing(8)
        self.select_inputs_button = QPushButton("Select Files")
        self.clear_inputs_button = QPushButton("Clear")
        input_buttons_layout.addWidget(self.select_inputs_button)
        input_buttons_layout.addWidget(self.clear_inputs_button)
        input_buttons_layout.addStretch(1)

        output_label = QLabel("Output Folder")
        output_row = QWidget(group)
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(8)
        self.output_path_field = QLineEdit()
        self.output_path_field.setReadOnly(True)
        self.output_path_field.setPlaceholderText("No output folder selected")
        self.select_output_button = QPushButton("Choose Folder")
        self.clear_output_button = QPushButton("Clear")
        output_layout.addWidget(self.output_path_field, 1)
        output_layout.addWidget(self.select_output_button)
        output_layout.addWidget(self.clear_output_button)

        layout.addWidget(input_label, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.input_paths_field, 1, 0)
        layout.addWidget(input_buttons, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(output_label, 2, 0)
        layout.addWidget(output_row, 3, 0, 1, 2)
        layout.setColumnStretch(0, 1)

        self.select_inputs_button.clicked.connect(self._select_input_files)
        self.clear_inputs_button.clicked.connect(self._clear_input_files)
        self.select_output_button.clicked.connect(self._select_output_directory)
        self.clear_output_button.clicked.connect(self._clear_output_directory)

        return group

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Current State")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(self.summary_label)
        return group

    def _build_process_group(self) -> QGroupBox:
        group = QGroupBox("Processing")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        selector_grid = QGridLayout()
        selector_grid.setHorizontalSpacing(12)
        selector_grid.setVerticalSpacing(8)

        process_method_label = QLabel("Process Method")
        self.process_method_combo = QComboBox(group)
        self.process_method_combo.currentTextChanged.connect(self._on_process_method_changed)
        self.reload_models_button = QPushButton("Reload Models", group)
        self.reload_models_button.clicked.connect(self._reload_models)

        model_select_label = QLabel("Model")
        self.model_combo = QComboBox(group)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_count_label = QLabel()
        self.model_count_label.setStyleSheet("color: #5f6b7a;")

        selector_grid.addWidget(process_method_label, 0, 0)
        selector_grid.addWidget(self.process_method_combo, 0, 1)
        selector_grid.addWidget(self.reload_models_button, 0, 2)
        selector_grid.addWidget(model_select_label, 1, 0)
        selector_grid.addWidget(self.model_combo, 1, 1, 1, 2)
        selector_grid.addWidget(self.model_count_label, 2, 0, 1, 3)

        self.model_label = QLabel("Backend target: detecting...")
        self.model_label.setWordWrap(True)

        button_row = QWidget(group)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        self.process_button = QPushButton("Process with GPU")
        self.process_button.clicked.connect(self._start_processing)
        button_layout.addWidget(self.process_button)
        button_layout.addStretch(1)

        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)

        self.status_label = QLabel("Idle")
        self.status_label.setWordWrap(True)

        self.log_console = QPlainTextEdit(group)
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("Processing logs will appear here")
        self.log_console.setMinimumHeight(180)

        output_group = QGroupBox("Output")
        output_layout = QGridLayout(output_group)
        output_layout.setHorizontalSpacing(12)
        output_layout.setVerticalSpacing(8)

        output_format_label = QLabel("Save Format")
        self.save_format_combo = QComboBox(output_group)
        self.save_format_combo.addItems([WAV, FLAC, MP3])
        self.save_format_combo.currentTextChanged.connect(self._on_save_format_changed)

        wav_type_label = QLabel("Wav Type")
        self.wav_type_combo = QComboBox(output_group)
        self.wav_type_combo.addItems(list(WAV_TYPE))
        self.wav_type_combo.currentTextChanged.connect(self._on_wav_type_changed)

        self.add_model_name_checkbox = QCheckBox("Append model name", output_group)
        self.add_model_name_checkbox.toggled.connect(self._on_add_model_name_changed)

        self.create_model_folder_checkbox = QCheckBox("Create model folder", output_group)
        self.create_model_folder_checkbox.toggled.connect(self._on_create_model_folder_changed)

        tuning_group = QGroupBox("Tuning")
        tuning_layout = QGridLayout(tuning_group)
        tuning_layout.setHorizontalSpacing(12)
        tuning_layout.setVerticalSpacing(8)

        self.gpu_checkbox = QCheckBox("Prefer GPU", tuning_group)
        self.gpu_checkbox.toggled.connect(self._on_gpu_changed)

        self.normalize_checkbox = QCheckBox("Normalize output", tuning_group)
        self.normalize_checkbox.toggled.connect(self._on_normalize_changed)

        self.primary_stem_only_checkbox = QCheckBox("Primary stem only", tuning_group)
        self.primary_stem_only_checkbox.toggled.connect(self._on_primary_stem_only_changed)

        self.secondary_stem_only_checkbox = QCheckBox("Secondary stem only", tuning_group)
        self.secondary_stem_only_checkbox.toggled.connect(self._on_secondary_stem_only_changed)

        tuning_layout.addWidget(self.gpu_checkbox, 0, 0)
        tuning_layout.addWidget(self.normalize_checkbox, 0, 1)
        tuning_layout.addWidget(self.primary_stem_only_checkbox, 1, 0)
        tuning_layout.addWidget(self.secondary_stem_only_checkbox, 1, 1)

        output_layout.addWidget(output_format_label, 0, 0)
        output_layout.addWidget(self.save_format_combo, 0, 1)
        output_layout.addWidget(wav_type_label, 1, 0)
        output_layout.addWidget(self.wav_type_combo, 1, 1)
        output_layout.addWidget(self.add_model_name_checkbox, 2, 0, 1, 2)
        output_layout.addWidget(self.create_model_folder_checkbox, 3, 0, 1, 2)

        layout.addLayout(selector_grid)
        layout.addWidget(self.model_label)
        layout.addWidget(output_group)
        layout.addWidget(tuning_group)
        layout.addWidget(button_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_console)
        return group

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

    def _persist_state(self) -> None:
        settings = AppSettings.from_legacy_dict(self.state.to_legacy_dict(), DEFAULT_DATA)
        save_settings(settings=settings)

    def _refresh_view(self) -> None:
        input_paths = self.state.paths.input_paths
        self.input_paths_field.setPlainText("\n".join(input_paths))
        self.output_path_field.setText(self.state.paths.export_path)
        self._refresh_processing_controls()
        self._refresh_output_controls()
        self._refresh_tuning_controls()
        resolved_model = self._get_processing_facade().resolve_model(self.state)
        if resolved_model is None:
            self.model_label.setText("Backend target: unavailable for the selected process method")
        else:
            self.model_label.setText(
                f"Backend target: {resolved_model.process_method} / {resolved_model.model_name}"
            )

        input_count = len(input_paths)
        input_hint = "No files selected" if input_count == 0 else f"{input_count} file(s) selected"
        output_hint = self.state.paths.export_path or "No output folder selected"
        self.summary_label.setText(
            "\n".join(
                [
                    f"Process method: {self.state.processing.process_method}",
                    f"Selected model: {self._selected_model_name() or 'None'}",
                    f"Save format: {self.state.output.save_format}",
                    f"Wav type: {self.state.output.wav_type}",
                    f"GPU preferred: {'Yes' if self.state.processing.use_gpu else 'No'}",
                    f"Normalize output: {'Yes' if self.state.processing.normalize_output else 'No'}",
                    f"Input: {input_hint}",
                    f"Output: {output_hint}",
                ]
            )
        )
        self.process_button.setEnabled(
            self.processing_thread is None
            and resolved_model is not None
            and bool(input_paths)
            and bool(self.state.paths.export_path)
        )

    def _get_processing_facade(self) -> ProcessingFacade:
        if self.processing_facade is None:
            self.processing_facade = ProcessingFacade()
        return self.processing_facade

    def _refresh_processing_controls(self) -> None:
        facade = self._get_processing_facade()
        available_methods = facade.available_process_methods()
        selected_method = self.state.processing.process_method

        if selected_method not in available_methods and available_methods:
            selected_method = available_methods[0]
            self.state = replace(
                self.state,
                processing=replace(self.state.processing, process_method=selected_method),
            )

        available_models = facade.available_models_for_method(selected_method) if selected_method else ()
        self.model_count_label.setText(f"{len(available_models)} model(s) available for {selected_method or 'this method'}")
        selected_model = self._selected_model_name_for_method(selected_method)
        if selected_model not in available_models and available_models:
            selected_model = available_models[0]
            self.state = self._state_with_selected_model(selected_method, selected_model)
            self._persist_state()

        self._is_syncing_processing_controls = True
        try:
            self.process_method_combo.blockSignals(True)
            self.process_method_combo.clear()
            self.process_method_combo.addItems(list(available_methods))
            if selected_method:
                self.process_method_combo.setCurrentText(selected_method)
            self.process_method_combo.blockSignals(False)

            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(list(available_models))
            if selected_model:
                self.model_combo.setCurrentText(selected_model)
            self.model_combo.blockSignals(False)
        finally:
            self._is_syncing_processing_controls = False

    def _refresh_output_controls(self) -> None:
        self._is_syncing_processing_controls = True
        try:
            self.save_format_combo.blockSignals(True)
            self.save_format_combo.setCurrentText(self.state.output.save_format or WAV)
            self.save_format_combo.blockSignals(False)

            self.wav_type_combo.blockSignals(True)
            self.wav_type_combo.setCurrentText(self.state.output.wav_type or "PCM_16")
            self.wav_type_combo.blockSignals(False)

            self.add_model_name_checkbox.blockSignals(True)
            self.add_model_name_checkbox.setChecked(self.state.output.add_model_name)
            self.add_model_name_checkbox.blockSignals(False)

            self.create_model_folder_checkbox.blockSignals(True)
            self.create_model_folder_checkbox.setChecked(self.state.output.create_model_folder)
            self.create_model_folder_checkbox.blockSignals(False)
        finally:
            self._is_syncing_processing_controls = False

    def _refresh_tuning_controls(self) -> None:
        self._is_syncing_processing_controls = True
        try:
            self.gpu_checkbox.blockSignals(True)
            self.gpu_checkbox.setChecked(self.state.processing.use_gpu)
            self.gpu_checkbox.blockSignals(False)

            self.normalize_checkbox.blockSignals(True)
            self.normalize_checkbox.setChecked(self.state.processing.normalize_output)
            self.normalize_checkbox.blockSignals(False)

            self.primary_stem_only_checkbox.blockSignals(True)
            self.primary_stem_only_checkbox.setChecked(self.state.processing.primary_stem_only)
            self.primary_stem_only_checkbox.blockSignals(False)

            self.secondary_stem_only_checkbox.blockSignals(True)
            self.secondary_stem_only_checkbox.setChecked(self.state.processing.secondary_stem_only)
            self.secondary_stem_only_checkbox.blockSignals(False)
        finally:
            self._is_syncing_processing_controls = False

    def _on_process_method_changed(self, process_method: str) -> None:
        if self._is_syncing_processing_controls or not process_method:
            return

        available_models = self._get_processing_facade().available_models_for_method(process_method)
        selected_model = self._selected_model_name_for_method(process_method)
        if selected_model not in available_models:
            selected_model = available_models[0] if available_models else ""

        self.state = replace(
            self._state_with_selected_model(process_method, selected_model),
            processing=replace(self.state.processing, process_method=process_method),
        )
        self._persist_state()
        self._refresh_view()

    def _on_model_changed(self, model_name: str) -> None:
        if self._is_syncing_processing_controls or not model_name:
            return

        process_method = self.process_method_combo.currentText()
        self.state = self._state_with_selected_model(process_method, model_name)
        self._persist_state()
        self._refresh_view()

    def _reload_models(self) -> None:
        self.processing_facade = None
        self._refresh_view()

    def _on_save_format_changed(self, save_format: str) -> None:
        if self._is_syncing_processing_controls or not save_format:
            return
        self.state = replace(self.state, output=replace(self.state.output, save_format=save_format))
        self._persist_state()
        self._refresh_view()

    def _on_wav_type_changed(self, wav_type: str) -> None:
        if self._is_syncing_processing_controls or not wav_type:
            return
        self.state = replace(self.state, output=replace(self.state.output, wav_type=wav_type))
        self._persist_state()
        self._refresh_view()

    def _on_add_model_name_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, output=replace(self.state.output, add_model_name=checked))
        self._persist_state()
        self._refresh_view()

    def _on_create_model_folder_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, output=replace(self.state.output, create_model_folder=checked))
        self._persist_state()
        self._refresh_view()

    def _on_gpu_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, processing=replace(self.state.processing, use_gpu=checked))
        self._persist_state()
        self._refresh_view()

    def _on_normalize_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, processing=replace(self.state.processing, normalize_output=checked))
        self._persist_state()
        self._refresh_view()

    def _on_primary_stem_only_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(
            self.state,
            processing=replace(
                self.state.processing,
                primary_stem_only=checked,
                secondary_stem_only=False if checked else self.state.processing.secondary_stem_only,
            ),
        )
        self._persist_state()
        self._refresh_view()

    def _on_secondary_stem_only_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(
            self.state,
            processing=replace(
                self.state.processing,
                secondary_stem_only=checked,
                primary_stem_only=False if checked else self.state.processing.primary_stem_only,
            ),
        )
        self._persist_state()
        self._refresh_view()

    def _selected_model_name(self) -> str:
        return self._selected_model_name_for_method(self.state.processing.process_method)

    def _selected_model_name_for_method(self, process_method: str) -> str:
        if process_method == "VR Architecture":
            return self.state.models.vr_model
        if process_method == "MDX-Net":
            return self.state.models.mdx_net_model
        if process_method == "Demucs":
            return self.state.models.demucs_model
        return ""

    def _state_with_selected_model(self, process_method: str, model_name: str) -> AppState:
        if process_method == "VR Architecture":
            return replace(self.state, models=replace(self.state.models, vr_model=model_name))
        if process_method == "MDX-Net":
            return replace(self.state, models=replace(self.state.models, mdx_net_model=model_name))
        if process_method == "Demucs":
            return replace(self.state, models=replace(self.state.models, demucs_model=model_name))
        return self.state

    def _start_processing(self) -> None:
        if self.processing_thread is not None:
            return

        self.log_console.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Preparing")
        self.process_button.setEnabled(False)

        self.processing_thread = QThread(self)
        self.processing_worker = _ProcessingWorker(self._get_processing_facade(), self.state)
        self.processing_worker.moveToThread(self.processing_thread)

        self.processing_thread.started.connect(self.processing_worker.run)
        self.processing_worker.log_emitted.connect(self._append_log)
        self.processing_worker.progress_emitted.connect(self.progress_bar.setValue)
        self.processing_worker.status_emitted.connect(self.status_label.setText)
        self.processing_worker.failed.connect(self._processing_failed)
        self.processing_worker.finished.connect(self._processing_finished)
        self.processing_worker.finished.connect(self.processing_thread.quit)
        self.processing_worker.failed.connect(self.processing_thread.quit)
        self.processing_thread.finished.connect(self._cleanup_processing_thread)
        self.processing_thread.start()

    def _append_log(self, message: str) -> None:
        self.log_console.appendPlainText(message)

    def _processing_finished(self, result: ProcessResult) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Completed: {len(result.processed_files)} file(s)")
        self._append_log(f'Output folder: "{result.output_path}"')
        self._append_log(f"Model used: {result.model.process_method} / {result.model.model_name}")
        self.process_button.setEnabled(True)

    def _processing_failed(self, message: str) -> None:
        self.status_label.setText("Failed")
        self._append_log(message)
        self.process_button.setEnabled(True)

    def _cleanup_processing_thread(self) -> None:
        if self.processing_worker is not None:
            self.processing_worker.deleteLater()
        if self.processing_thread is not None:
            self.processing_thread.deleteLater()
        self.processing_worker = None
        self.processing_thread = None


class _ProcessingWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: ProcessingFacade, state: AppState):
        super().__init__()
        self.facade = facade
        self.state = state

    def run(self) -> None:
        try:
            result = self.facade.process(
                self.state,
                log=self.log_emitted.emit,
                progress=lambda value: self.progress_emitted.emit(int(max(0, min(value, 100)))),
                status=self.status_emitted.emit,
            )
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self.failed.emit(error_message)
            return

        self.finished.emit(result)
