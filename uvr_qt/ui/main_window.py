"""Main window for the initial PySide6 UVR shell."""

from __future__ import annotations

import traceback
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
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

from gui_data.constants import DEFAULT_DATA
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

        self.model_label = QLabel("Backend model: detecting...")
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

        layout.addWidget(self.model_label)
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
        resolved_model = self._get_processing_facade().resolve_model(self.state)
        if resolved_model is None:
            self.model_label.setText("Backend model: none found")
        else:
            self.model_label.setText(
                f"Backend model: {resolved_model.process_method} / {resolved_model.model_name}"
            )

        input_count = len(input_paths)
        input_hint = "No files selected" if input_count == 0 else f"{input_count} file(s) selected"
        output_hint = self.state.paths.export_path or "No output folder selected"
        self.summary_label.setText(
            "\n".join(
                [
                    f"Process method: {self.state.processing.process_method}",
                    f"Input: {input_hint}",
                    f"Output: {output_hint}",
                    "Execution mode: GPU preferred",
                ]
            )
        )

    def _get_processing_facade(self) -> ProcessingFacade:
        if self.processing_facade is None:
            self.processing_facade = ProcessingFacade()
        return self.processing_facade

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
