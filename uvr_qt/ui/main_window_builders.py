"""Widget construction helpers for the Qt main window."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import (
    FLAC,
    MP3,
    MP3_BIT_RATES,
    WAV,
    WAV_TYPE,
)


def build_header(window: Any) -> QWidget:
    header = QWidget(window)
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

    actions = QWidget(header)
    actions_layout = QHBoxLayout(actions)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(8)
    actions_layout.addStretch(1)
    window.open_download_manager_button = QPushButton("Downloads", actions)
    window.open_download_manager_button.clicked.connect(window._open_download_manager)
    actions_layout.addWidget(window.open_download_manager_button)

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addWidget(actions)
    return header


def build_paths_group(window: Any) -> QGroupBox:
    group = QGroupBox("Paths")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(12)

    input_label = QLabel("Input Files")
    window.input_paths_field = QPlainTextEdit()
    window.input_paths_field.setReadOnly(True)
    window.input_paths_field.setPlaceholderText("No input files selected")
    window.input_paths_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    input_buttons = QWidget(group)
    input_buttons_layout = QVBoxLayout(input_buttons)
    input_buttons_layout.setContentsMargins(0, 0, 0, 0)
    input_buttons_layout.setSpacing(8)
    window.select_inputs_button = QPushButton("Select Files")
    window.clear_inputs_button = QPushButton("Clear")
    input_buttons_layout.addWidget(window.select_inputs_button)
    input_buttons_layout.addWidget(window.clear_inputs_button)
    input_buttons_layout.addStretch(1)

    output_label = QLabel("Output Folder")
    output_row = QWidget(group)
    output_layout = QHBoxLayout(output_row)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(8)
    window.output_path_field = QLineEdit()
    window.output_path_field.setReadOnly(True)
    window.output_path_field.setPlaceholderText("No output folder selected")
    window.select_output_button = QPushButton("Choose Folder")
    window.clear_output_button = QPushButton("Clear")
    output_layout.addWidget(window.output_path_field, 1)
    output_layout.addWidget(window.select_output_button)
    output_layout.addWidget(window.clear_output_button)

    layout.addWidget(input_label, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
    layout.addWidget(window.input_paths_field, 1, 0)
    layout.addWidget(input_buttons, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
    layout.addWidget(output_label, 2, 0)
    layout.addWidget(output_row, 3, 0, 1, 2)
    layout.setColumnStretch(0, 1)

    window.select_inputs_button.clicked.connect(window._select_input_files)
    window.clear_inputs_button.clicked.connect(window._clear_input_files)
    window.select_output_button.clicked.connect(window._select_output_directory)
    window.clear_output_button.clicked.connect(window._clear_output_directory)

    return group


def build_summary_group(window: Any) -> QGroupBox:
    group = QGroupBox("Current State")
    layout = QVBoxLayout(group)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    window.summary_label = QLabel()
    window.summary_label.setWordWrap(True)
    window.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    layout.addWidget(window.summary_label)
    return group


def build_process_group(window: Any) -> QGroupBox:
    group = QGroupBox("Processing")
    layout = QVBoxLayout(group)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    selector_grid = QGridLayout()
    selector_grid.setHorizontalSpacing(12)
    selector_grid.setVerticalSpacing(8)

    process_method_label = QLabel("Process Method")
    window.process_method_combo = QComboBox(group)
    window.process_method_combo.currentTextChanged.connect(window._on_process_method_changed)
    window.reload_models_button = QPushButton("Reload Models", group)
    window.reload_models_button.clicked.connect(window._reload_models)

    model_select_label = QLabel("Model")
    window.model_combo = QComboBox(group)
    window.model_combo.currentTextChanged.connect(window._on_model_changed)
    window.model_count_label = QLabel()
    window.model_count_label.setStyleSheet("color: #5f6b7a;")

    selector_grid.addWidget(process_method_label, 0, 0)
    selector_grid.addWidget(window.process_method_combo, 0, 1)
    selector_grid.addWidget(window.reload_models_button, 0, 2)
    selector_grid.addWidget(model_select_label, 1, 0)
    selector_grid.addWidget(window.model_combo, 1, 1, 1, 2)
    selector_grid.addWidget(window.model_count_label, 2, 0, 1, 3)

    window.model_label = QLabel("Backend target: detecting...")
    window.model_label.setWordWrap(True)

    button_row = QWidget(group)
    button_layout = QHBoxLayout(button_row)
    button_layout.setContentsMargins(0, 0, 0, 0)
    button_layout.setSpacing(8)
    window.process_button = QPushButton("Process with GPU")
    window.process_button.clicked.connect(window._start_processing)
    window.cancel_button = QPushButton("Cancel")
    window.cancel_button.clicked.connect(window._cancel_processing)
    button_layout.addWidget(window.process_button)
    button_layout.addWidget(window.cancel_button)
    button_layout.addStretch(1)

    window.progress_bar = QProgressBar(group)
    window.progress_bar.setRange(0, 100)

    window.status_label = QLabel("Idle")
    window.status_label.setWordWrap(True)

    window.log_console = QPlainTextEdit(group)
    window.log_console.setReadOnly(True)
    window.log_console.setPlaceholderText("Processing logs will appear here")
    window.log_console.setMinimumHeight(180)

    output_group = QGroupBox("Output")
    output_layout = QGridLayout(output_group)
    output_layout.setHorizontalSpacing(12)
    output_layout.setVerticalSpacing(8)

    output_format_label = QLabel("Save Format")
    window.save_format_combo = QComboBox(output_group)
    window.save_format_combo.addItems([WAV, FLAC, MP3])
    window.save_format_combo.currentTextChanged.connect(window._on_save_format_changed)

    wav_type_label = QLabel("Wav Type")
    window.wav_type_combo = QComboBox(output_group)
    window.wav_type_combo.addItems(list(WAV_TYPE))
    window.wav_type_combo.currentTextChanged.connect(window._on_wav_type_changed)

    mp3_bitrate_label = QLabel("MP3 Bitrate")
    window.mp3_bitrate_combo = QComboBox(output_group)
    window.mp3_bitrate_combo.addItems(list(MP3_BIT_RATES))
    window.mp3_bitrate_combo.currentTextChanged.connect(window._on_mp3_bitrate_changed)

    window.add_model_name_checkbox = QCheckBox("Append model name", output_group)
    window.add_model_name_checkbox.toggled.connect(window._on_add_model_name_changed)

    window.create_model_folder_checkbox = QCheckBox("Create model folder", output_group)
    window.create_model_folder_checkbox.toggled.connect(window._on_create_model_folder_changed)

    tuning_group = QGroupBox("Tuning")
    tuning_layout = QGridLayout(tuning_group)
    tuning_layout.setHorizontalSpacing(12)
    tuning_layout.setVerticalSpacing(8)

    window.gpu_checkbox = QCheckBox("Prefer GPU", tuning_group)
    window.gpu_checkbox.toggled.connect(window._on_gpu_changed)

    window.normalize_checkbox = QCheckBox("Normalize output", tuning_group)
    window.normalize_checkbox.toggled.connect(window._on_normalize_changed)

    window.primary_stem_only_checkbox = QCheckBox("Primary stem only", tuning_group)
    window.primary_stem_only_checkbox.toggled.connect(window._on_primary_stem_only_changed)

    window.secondary_stem_only_checkbox = QCheckBox("Secondary stem only", tuning_group)
    window.secondary_stem_only_checkbox.toggled.connect(window._on_secondary_stem_only_changed)

    window.testing_audio_checkbox = QCheckBox("Testing audio mode", tuning_group)
    window.testing_audio_checkbox.toggled.connect(window._on_testing_audio_changed)

    window.model_sample_mode_checkbox = QCheckBox("Sample mode", tuning_group)
    window.model_sample_mode_checkbox.toggled.connect(window._on_model_sample_mode_changed)

    window.model_sample_duration_spinbox = QSpinBox(tuning_group)
    window.model_sample_duration_spinbox.setRange(1, 600)
    window.model_sample_duration_spinbox.setSuffix(" sec")
    window.model_sample_duration_spinbox.valueChanged.connect(window._on_model_sample_duration_changed)

    tuning_layout.addWidget(window.gpu_checkbox, 0, 0)
    tuning_layout.addWidget(window.normalize_checkbox, 0, 1)
    tuning_layout.addWidget(window.primary_stem_only_checkbox, 1, 0)
    tuning_layout.addWidget(window.secondary_stem_only_checkbox, 1, 1)
    tuning_layout.addWidget(window.testing_audio_checkbox, 2, 0)
    tuning_layout.addWidget(window.model_sample_mode_checkbox, 2, 1)
    tuning_layout.addWidget(QLabel("Sample Duration"), 3, 0)
    tuning_layout.addWidget(window.model_sample_duration_spinbox, 3, 1)

    output_layout.addWidget(output_format_label, 0, 0)
    output_layout.addWidget(window.save_format_combo, 0, 1)
    output_layout.addWidget(wav_type_label, 1, 0)
    output_layout.addWidget(window.wav_type_combo, 1, 1)
    output_layout.addWidget(mp3_bitrate_label, 2, 0)
    output_layout.addWidget(window.mp3_bitrate_combo, 2, 1)
    output_layout.addWidget(window.add_model_name_checkbox, 3, 0, 1, 2)
    output_layout.addWidget(window.create_model_folder_checkbox, 4, 0, 1, 2)

    layout.addLayout(selector_grid)
    layout.addWidget(window.model_label)
    layout.addWidget(output_group)
    layout.addWidget(tuning_group)
    layout.addWidget(button_row)
    layout.addWidget(window.progress_bar)
    layout.addWidget(window.status_label)
    layout.addWidget(window.log_console)
    return group
