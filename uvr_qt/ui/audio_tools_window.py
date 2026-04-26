"""Separate window for audio-tool operations (align, match, pitch/time, manual ensemble)."""

from __future__ import annotations

import sys
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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import (
    ALIGN_INPUTS,
    ALIGN_PHASE_OPTIONS,
    AUDIO_TOOL_OPTIONS,
    CHANGE_PITCH,
    FLAC,
    INTRO_MAPPER,
    MANUAL_ENSEMBLE,
    MANUAL_ENSEMBLE_OPTIONS,
    MATCH_INPUTS,
    MP3,
    MP3_BIT_RATES,
    PHASE_SHIFTS_OPT,
    TIME_PITCH,
    TIME_STRETCH,
    TIME_WINDOW_MAPPER,
    VOLUME_MAPPER,
    WAV,
    WAV_TYPE,
)
from uvr_core.jobs import AudioToolJobResult
from uvr_core.requests import AudioToolRequest
from uvr_qt.services.tool_facades import AudioToolFacade
from uvr_qt.ui.tool_workers import AudioToolWorker

_IS_STRETCH_AVAILABLE = sys.platform in ("win32", "darwin")


class AudioToolsWindow(QMainWindow):
    """Standalone window for all audio-tool operations."""

    def __init__(self, facade: AudioToolFacade | None = None) -> None:
        super().__init__()
        self.facade = facade or AudioToolFacade()
        self.job_thread: QThread | None = None
        self.job_worker: AudioToolWorker | None = None
        self._last_directory: str = str(Path.cwd())

        self.setWindowTitle("Audio Tools")
        self.resize(800, 700)

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        # Tool selector always at top
        root_layout.addWidget(self._build_tool_selector_group())

        # Scrollable settings area
        scroll = QScrollArea(central)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        self._settings_layout = QVBoxLayout(scroll_content)
        self._settings_layout.setContentsMargins(0, 0, 0, 0)
        self._settings_layout.setSpacing(12)

        # Per-tool settings groups (hidden/shown based on selection)
        self._align_group = self._build_align_group()
        self._settings_layout.addWidget(self._align_group)

        self._pitch_time_group = self._build_pitch_time_group()
        self._settings_layout.addWidget(self._pitch_time_group)

        self._manual_ensemble_group = self._build_manual_ensemble_group()
        self._settings_layout.addWidget(self._manual_ensemble_group)

        # Output format is common to all tools
        self._settings_layout.addWidget(self._build_output_format_group())

        self._settings_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, 1)

        root_layout.addWidget(self._build_files_group())
        root_layout.addWidget(self._build_activity_group())
        self.setCentralWidget(central)

        self._on_tool_changed(self.tool_combo.currentText())

    # ── Tool selector ─────────────────────────────────────────────────────────

    def _build_tool_selector_group(self) -> QGroupBox:
        group = QGroupBox("Tool")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Select Tool"))
        self.tool_combo = QComboBox(group)
        self.tool_combo.addItems(list(AUDIO_TOOL_OPTIONS))
        self.tool_combo.currentTextChanged.connect(self._on_tool_changed)
        layout.addWidget(self.tool_combo)
        layout.addStretch(1)
        return group

    # ── Align Inputs settings ─────────────────────────────────────────────────

    def _build_align_group(self) -> QGroupBox:
        group = QGroupBox("Align / Matchering Settings")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Align Window"), 0, 0)
        self.align_window_combo = QComboBox(group)
        self.align_window_combo.addItems(list(TIME_WINDOW_MAPPER.keys()))
        self.align_window_combo.setCurrentText("3")
        layout.addWidget(self.align_window_combo, 0, 1)

        layout.addWidget(QLabel("Intro Length"), 1, 0)
        self.align_intro_combo = QComboBox(group)
        self.align_intro_combo.addItems(list(INTRO_MAPPER.keys()))
        self.align_intro_combo.setCurrentText("Default")
        layout.addWidget(self.align_intro_combo, 1, 1)

        layout.addWidget(QLabel("Volume Analysis"), 2, 0)
        self.db_analysis_combo = QComboBox(group)
        self.db_analysis_combo.addItems(list(VOLUME_MAPPER.keys()))
        self.db_analysis_combo.setCurrentText("Medium")
        layout.addWidget(self.db_analysis_combo, 2, 1)

        layout.addWidget(QLabel("Phase Option"), 3, 0)
        self.phase_option_combo = QComboBox(group)
        self.phase_option_combo.addItems(list(ALIGN_PHASE_OPTIONS))
        layout.addWidget(self.phase_option_combo, 3, 1)

        layout.addWidget(QLabel("Phase Shifts"), 4, 0)
        self.phase_shifts_combo = QComboBox(group)
        self.phase_shifts_combo.addItems(list(PHASE_SHIFTS_OPT.keys()))
        layout.addWidget(self.phase_shifts_combo, 4, 1)

        self.save_aligned_check = QCheckBox("Save Aligned Outputs", group)
        layout.addWidget(self.save_aligned_check, 5, 0, 1, 2)

        self.match_silence_check = QCheckBox("Match Silence", group)
        self.match_silence_check.setChecked(True)
        layout.addWidget(self.match_silence_check, 6, 0, 1, 2)

        self.spec_match_check = QCheckBox("Spectrogram Match", group)
        layout.addWidget(self.spec_match_check, 7, 0, 1, 2)

        layout.setColumnStretch(1, 1)
        return group

    # ── Pitch / Time settings ─────────────────────────────────────────────────

    def _build_pitch_time_group(self) -> QGroupBox:
        group = QGroupBox("Pitch / Time Shift Settings")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Rate"), 0, 0)
        self.pitch_time_rate_combo = QComboBox(group)
        self.pitch_time_rate_combo.addItems(list(TIME_PITCH))
        self.pitch_time_rate_combo.setCurrentText("2.0")
        layout.addWidget(self.pitch_time_rate_combo, 0, 1)

        self.time_correction_check = QCheckBox("Time Correction (Time Stretch only)", group)
        self.time_correction_check.setChecked(True)
        layout.addWidget(self.time_correction_check, 1, 0, 1, 2)

        layout.setColumnStretch(1, 1)
        return group

    # ── Manual Ensemble settings ──────────────────────────────────────────────

    def _build_manual_ensemble_group(self) -> QGroupBox:
        group = QGroupBox("Manual Ensemble Settings")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Algorithm"), 0, 0)
        self.ensemble_algo_combo = QComboBox(group)
        self.ensemble_algo_combo.addItems(list(MANUAL_ENSEMBLE_OPTIONS))
        layout.addWidget(self.ensemble_algo_combo, 0, 1)

        layout.setColumnStretch(1, 1)
        return group

    # ── Output format ─────────────────────────────────────────────────────────

    def _build_output_format_group(self) -> QGroupBox:
        group = QGroupBox("Output Format")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Save Format"), 0, 0)
        self.format_combo = QComboBox(group)
        self.format_combo.addItems([WAV, FLAC, MP3])
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        layout.addWidget(self.format_combo, 0, 1)

        self.wav_type_label = QLabel("WAV Bit Depth", group)
        layout.addWidget(self.wav_type_label, 1, 0)
        self.wav_type_combo = QComboBox(group)
        self.wav_type_combo.addItems(list(WAV_TYPE))
        self.wav_type_combo.setCurrentText("PCM_16")
        layout.addWidget(self.wav_type_combo, 1, 1)

        self.mp3_rate_label = QLabel("MP3 Bitrate", group)
        layout.addWidget(self.mp3_rate_label, 2, 0)
        self.mp3_rate_combo = QComboBox(group)
        self.mp3_rate_combo.addItems(list(MP3_BIT_RATES))
        self.mp3_rate_combo.setCurrentText("320k")
        layout.addWidget(self.mp3_rate_combo, 2, 1)

        self.normalize_check = QCheckBox("Normalize Output", group)
        layout.addWidget(self.normalize_check, 3, 0, 1, 2)

        layout.setColumnStretch(1, 1)
        self._on_format_changed(self.format_combo.currentText())
        return group

    # ── Input files + output folder ───────────────────────────────────────────

    def _build_files_group(self) -> QGroupBox:
        group = QGroupBox("Files")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._input_hint = QLabel("Select audio files below:", group)
        layout.addWidget(self._input_hint)

        self.input_list = QListWidget(group)
        self.input_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.input_list.setMaximumHeight(110)
        layout.addWidget(self.input_list)

        input_btns = QWidget(group)
        input_btn_layout = QHBoxLayout(input_btns)
        input_btn_layout.setContentsMargins(0, 0, 0, 0)
        input_btn_layout.setSpacing(8)

        self.add_files_btn = QPushButton("Add Files…", group)
        self.add_files_btn.clicked.connect(self._add_files)
        input_btn_layout.addWidget(self.add_files_btn)

        self.remove_btn = QPushButton("Remove Selected", group)
        self.remove_btn.clicked.connect(self._remove_selected)
        input_btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear", group)
        self.clear_btn.clicked.connect(self._clear_inputs)
        input_btn_layout.addWidget(self.clear_btn)
        input_btn_layout.addStretch(1)
        layout.addWidget(input_btns)

        output_row = QWidget(group)
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(8)
        output_layout.addWidget(QLabel("Output Folder"))
        self.output_path_edit = QLineEdit(group)
        self.output_path_edit.setPlaceholderText("No folder selected")
        self.output_path_edit.setReadOnly(True)
        output_layout.addWidget(self.output_path_edit)
        browse_btn = QPushButton("Browse…", group)
        browse_btn.clicked.connect(self._select_output)
        output_layout.addWidget(browse_btn)
        layout.addWidget(output_row)
        return group

    # ── Activity ──────────────────────────────────────────────────────────────

    def _build_activity_group(self) -> QGroupBox:
        group = QGroupBox("Activity")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Idle", group)
        layout.addWidget(self.status_label)

        self.log_console = QPlainTextEdit(group)
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(70)
        self.log_console.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.log_console)

        btn_row = QWidget(group)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch(1)

        self.run_btn = QPushButton("Run", group)
        self.run_btn.setMinimumWidth(100)
        self.run_btn.clicked.connect(self._start_job)
        btn_layout.addWidget(self.run_btn)
        layout.addWidget(btn_row)
        return group

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_tool_changed(self, tool: str) -> None:
        is_align = tool in (ALIGN_INPUTS, MATCH_INPUTS)
        is_pitch_time = tool in (CHANGE_PITCH, TIME_STRETCH)
        is_ensemble = tool == MANUAL_ENSEMBLE

        self._align_group.setVisible(is_align)
        self._pitch_time_group.setVisible(is_pitch_time)
        self._manual_ensemble_group.setVisible(is_ensemble)

        if tool == TIME_STRETCH:
            self.time_correction_check.setVisible(True)
        elif tool == CHANGE_PITCH:
            self.time_correction_check.setVisible(False)

        if is_align:
            self._input_hint.setText("Select exactly 2 audio files:")
        elif is_ensemble:
            self._input_hint.setText("Select 2 or more audio files to ensemble:")
        else:
            self._input_hint.setText("Select audio file(s):")

        self._refresh_controls()

    def _on_format_changed(self, fmt: str) -> None:
        self.wav_type_label.setVisible(fmt == WAV)
        self.wav_type_combo.setVisible(fmt == WAV)
        self.mp3_rate_label.setVisible(fmt == MP3)
        self.mp3_rate_combo.setVisible(fmt == MP3)

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

    def _refresh_controls(self) -> None:
        busy = self.job_thread is not None
        tool = self.tool_combo.currentText()
        n = self.input_list.count()
        has_output = bool(self.output_path_edit.text().strip())

        if tool in (ALIGN_INPUTS, MATCH_INPUTS):
            ok_inputs = n == 2
        elif tool == MANUAL_ENSEMBLE:
            ok_inputs = n >= 2
        else:
            ok_inputs = n >= 1

        self.run_btn.setEnabled(not busy and ok_inputs and has_output)
        self.add_files_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

    def _build_request(self) -> AudioToolRequest:
        tool = self.tool_combo.currentText()
        fmt = self.format_combo.currentText()
        return AudioToolRequest(
            audio_tool=tool,
            input_paths=tuple(
                self.input_list.item(i).text() for i in range(self.input_list.count())
            ),
            export_path=self.output_path_edit.text().strip(),
            save_format=fmt,
            wav_type=self.wav_type_combo.currentText() if fmt == WAV else "PCM_16",
            mp3_bitrate=self.mp3_rate_combo.currentText() if fmt == MP3 else "320k",
            normalize_output=self.normalize_check.isChecked(),
            align_window=self.align_window_combo.currentText(),
            align_intro=self.align_intro_combo.currentText(),
            db_analysis=self.db_analysis_combo.currentText(),
            save_aligned=self.save_aligned_check.isChecked(),
            match_silence=self.match_silence_check.isChecked(),
            spec_match=self.spec_match_check.isChecked(),
            phase_option=self.phase_option_combo.currentText(),
            phase_shifts=self.phase_shifts_combo.currentText(),
            time_stretch_rate=self.pitch_time_rate_combo.currentText(),
            pitch_rate=self.pitch_time_rate_combo.currentText(),
            time_correction=self.time_correction_check.isChecked(),
        )

    def _start_job(self) -> None:
        if self.job_thread is not None:
            return
        self.log_console.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting…")

        request = self._build_request()
        self.job_thread = QThread(self)
        self.job_worker = AudioToolWorker(self.facade, request)
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

    def _on_finished(self, result: AudioToolJobResult) -> None:
        self._append_log(f"Tool: {result.audio_tool}")
        self._append_log(f"Output(s): {', '.join(result.output_paths)}")
        self.status_label.setText(f"Completed — {len(result.output_paths)} output(s)")
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
