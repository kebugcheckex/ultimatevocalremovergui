"""Separate window for manual ensemble operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import (
    FLAC,
    MANUAL_ENSEMBLE_OPTIONS,
    MP3,
    MP3_BIT_RATES,
    WAV,
    WAV_TYPE,
)
from uvr_core.jobs import EnsembleJobResult
from uvr_core.requests import EnsembleRequest
from uvr_qt.services.tool_facades import EnsembleFacade
from uvr_qt.ui.tool_workers import EnsembleWorker


class EnsembleWindow(QMainWindow):
    """Standalone window for manual ensemble of stem files."""

    def __init__(self, facade: EnsembleFacade | None = None) -> None:
        super().__init__()
        self.facade = facade or EnsembleFacade()
        self.job_thread: QThread | None = None
        self.job_worker: EnsembleWorker | None = None
        self._last_directory: str = str(Path.cwd())

        self.setWindowTitle("Manual Ensemble")
        self.resize(760, 620)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(self._build_inputs_group())
        layout.addWidget(self._build_settings_group())
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_activity_group())
        self.setCentralWidget(central)
        self._refresh_controls()

    # ── Input files ──────────────────────────────────────────────────────────

    def _build_inputs_group(self) -> QGroupBox:
        group = QGroupBox("Input Files")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.input_list = QListWidget(group)
        self.input_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.input_list.setMinimumHeight(120)
        layout.addWidget(self.input_list)

        btn_row = QWidget(group)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.add_files_btn = QPushButton("Add Files…", group)
        self.add_files_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_files_btn)

        self.remove_btn = QPushButton("Remove Selected", group)
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All", group)
        self.clear_btn.clicked.connect(self._clear_inputs)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch(1)
        layout.addWidget(btn_row)
        return group

    # ── Ensemble settings ────────────────────────────────────────────────────

    def _build_settings_group(self) -> QGroupBox:
        group = QGroupBox("Ensemble Settings")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Algorithm"), 0, 0)
        self.algorithm_combo = QComboBox(group)
        self.algorithm_combo.addItems(list(MANUAL_ENSEMBLE_OPTIONS))
        layout.addWidget(self.algorithm_combo, 0, 1)

        layout.addWidget(QLabel("Output Name"), 1, 0)
        self.output_name_edit = QLineEdit("Ensembled", group)
        layout.addWidget(self.output_name_edit, 1, 1)

        layout.addWidget(QLabel("Save Format"), 2, 0)
        self.format_combo = QComboBox(group)
        self.format_combo.addItems([WAV, FLAC, MP3])
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        layout.addWidget(self.format_combo, 2, 1)

        self.wav_type_label = QLabel("WAV Bit Depth", group)
        layout.addWidget(self.wav_type_label, 3, 0)
        self.wav_type_combo = QComboBox(group)
        self.wav_type_combo.addItems(list(WAV_TYPE))
        self.wav_type_combo.setCurrentText("PCM_16")
        layout.addWidget(self.wav_type_combo, 3, 1)

        self.mp3_rate_label = QLabel("MP3 Bitrate", group)
        layout.addWidget(self.mp3_rate_label, 4, 0)
        self.mp3_rate_combo = QComboBox(group)
        self.mp3_rate_combo.addItems(list(MP3_BIT_RATES))
        self.mp3_rate_combo.setCurrentText("320k")
        layout.addWidget(self.mp3_rate_combo, 4, 1)

        self.normalize_check = QCheckBox("Normalize Output", group)
        layout.addWidget(self.normalize_check, 5, 0, 1, 2)

        self.wav_ensemble_check = QCheckBox("WAV Ensemble (waveform-domain algorithm)", group)
        layout.addWidget(self.wav_ensemble_check, 6, 0, 1, 2)

        layout.setColumnStretch(1, 1)
        self._on_format_changed(self.format_combo.currentText())
        return group

    # ── Output folder ────────────────────────────────────────────────────────

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output Folder")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)

        self.output_path_edit = QLineEdit(group)
        self.output_path_edit.setPlaceholderText("No folder selected")
        self.output_path_edit.setReadOnly(True)
        layout.addWidget(self.output_path_edit)

        browse_btn = QPushButton("Browse…", group)
        browse_btn.clicked.connect(self._select_output)
        layout.addWidget(browse_btn)
        return group

    # ── Activity log ─────────────────────────────────────────────────────────

    def _build_activity_group(self) -> QGroupBox:
        group = QGroupBox("Activity")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Idle", group)
        layout.addWidget(self.status_label)

        self.log_console = QPlainTextEdit(group)
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(80)
        self.log_console.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.log_console)

        btn_row = QWidget(group)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch(1)

        self.run_btn = QPushButton("Run Ensemble", group)
        self.run_btn.setMinimumWidth(120)
        self.run_btn.clicked.connect(self._start_job)
        btn_layout.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("Cancel", group)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)

        layout.addWidget(btn_row)
        return group

    # ── Slots ────────────────────────────────────────────────────────────────

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            self._last_directory,
            "Audio Files (*.wav *.flac *.mp3 *.m4a *.ogg *.aiff *.aif);;All Files (*)",
        )
        if not files:
            return
        self._last_directory = str(Path(files[0]).parent)
        existing = {self.input_list.item(i).text() for i in range(self.input_list.count())}
        for f in files:
            if f not in existing:
                self.input_list.addItem(f)
        self._refresh_controls()

    def _remove_selected(self) -> None:
        for item in reversed(self.input_list.selectedItems()):
            self.input_list.takeItem(self.input_list.row(item))
        self._refresh_controls()

    def _clear_inputs(self) -> None:
        self.input_list.clear()
        self._refresh_controls()

    def _select_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._last_directory)
        if directory:
            self.output_path_edit.setText(directory)
            self._last_directory = directory
        self._refresh_controls()

    def _on_format_changed(self, fmt: str) -> None:
        self.wav_type_label.setVisible(fmt == WAV)
        self.wav_type_combo.setVisible(fmt == WAV)
        self.mp3_rate_label.setVisible(fmt == MP3)
        self.mp3_rate_combo.setVisible(fmt == MP3)

    def _refresh_controls(self) -> None:
        busy = self.job_thread is not None
        n_inputs = self.input_list.count()
        has_output = bool(self.output_path_edit.text().strip())
        can_run = not busy and n_inputs >= 2 and has_output
        self.run_btn.setEnabled(can_run)
        self.cancel_btn.setEnabled(busy)
        self.add_files_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

    def _build_request(self) -> EnsembleRequest:
        fmt = self.format_combo.currentText()
        return EnsembleRequest(
            input_paths=tuple(
                self.input_list.item(i).text() for i in range(self.input_list.count())
            ),
            export_path=self.output_path_edit.text().strip(),
            algorithm=self.algorithm_combo.currentText(),
            output_name=self.output_name_edit.text().strip() or "Ensembled",
            save_format=fmt,
            wav_type=self.wav_type_combo.currentText() if fmt == WAV else "PCM_16",
            mp3_bitrate=self.mp3_rate_combo.currentText() if fmt == MP3 else "320k",
            normalize_output=self.normalize_check.isChecked(),
            wav_ensemble=self.wav_ensemble_check.isChecked(),
        )

    def _start_job(self) -> None:
        if self.job_thread is not None:
            return
        self.log_console.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting…")

        request = self._build_request()
        self.job_thread = QThread(self)
        self.job_worker = EnsembleWorker(self.facade, request)
        self.job_worker.moveToThread(self.job_thread)
        self.job_thread.started.connect(self.job_worker.run)
        self.job_worker.log_emitted.connect(self._append_log)
        self.job_worker.progress_emitted.connect(self.progress_bar.setValue)
        self.job_worker.status_emitted.connect(self.status_label.setText)
        self.job_worker.finished.connect(self._on_finished)
        self.job_worker.failed.connect(self._on_failed)
        self.job_worker.finished.connect(self.job_thread.quit)
        self.job_worker.failed.connect(self.job_thread.quit)
        self.job_thread.finished.connect(self._cleanup_thread)
        self.job_thread.start()
        self._refresh_controls()

    def _on_finished(self, result: EnsembleJobResult) -> None:
        self._append_log(f'Output: "{result.output_path}"')
        self._append_log(f"Algorithm: {result.algorithm} — {len(result.inputs)} file(s) ensembled")
        self.status_label.setText(f"Completed — {len(result.inputs)} files")
        self.progress_bar.setValue(100)

    def _on_failed(self, message: str) -> None:
        self._append_log(message)
        self.status_label.setText("Failed")

    def _cleanup_thread(self) -> None:
        if self.job_worker is not None:
            self.job_worker.deleteLater()
        if self.job_thread is not None:
            self.job_thread.deleteLater()
        self.job_worker = None
        self.job_thread = None
        self._refresh_controls()

    def _append_log(self, message: str) -> None:
        self.log_console.appendPlainText(message)
