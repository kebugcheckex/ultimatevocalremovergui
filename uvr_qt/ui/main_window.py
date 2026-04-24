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
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QToolButton,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import (
    AUTO_SELECT,
    ALL_STEMS,
    BATCH_SIZE,
    DEFAULT_DATA,
    DEF_OPT,
    DEMUCS_OVERLAP,
    DEMUCS_SEGMENTS,
    FLAC,
    INST_STEM,
    MDX_OVERLAP,
    MDX_SEGMENTS,
    MP3,
    MP3_BIT_RATES,
    NO_MODEL,
    STEM_SET_MENU,
    VOCAL_STEM,
    VR_AGGRESSION,
    VR_WINDOW,
    WAV,
    WAV_TYPE,
)
from uvr.config.models import AppSettings
from uvr.config.persistence import save_settings
from uvr_qt.services import JobCancelledError, ProcessResult, ProcessingFacade
from uvr_qt.state import AppState
from uvr_qt.ui.download_manager_window import DownloadManagerWindow


SECONDARY_MODEL_SLOTS = (
    ("voc_inst", "Vocals / Instrumental"),
    ("other", "Other / No Other"),
    ("bass", "Bass / No Bass"),
    ("drums", "Drums / No Drums"),
)


class MainWindow(QMainWindow):
    """Basic Qt shell with input/output path selection."""

    def __init__(
        self,
        state: AppState,
        processing_facade: ProcessingFacade | None = None,
        config_path: str | Path | None = None,
    ):
        super().__init__()
        self.state = state
        self.config_path = config_path
        self.processing_facade: ProcessingFacade | None = processing_facade
        self.download_manager_window: DownloadManagerWindow | None = None
        self.processing_thread: QThread | None = None
        self.processing_worker: _ProcessingWorker | None = None
        self._is_syncing_processing_controls = False
        self.secondary_model_combos: dict[str, QComboBox] = {}
        self.secondary_scale_spinboxes: dict[str, QDoubleSpinBox] = {}
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

        actions = QWidget(header)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addStretch(1)
        self.open_download_manager_button = QPushButton("Downloads", actions)
        self.open_download_manager_button.clicked.connect(self._open_download_manager)
        actions_layout.addWidget(self.open_download_manager_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(actions)
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
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_processing)
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.cancel_button)
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

        mp3_bitrate_label = QLabel("MP3 Bitrate")
        self.mp3_bitrate_combo = QComboBox(output_group)
        self.mp3_bitrate_combo.addItems(list(MP3_BIT_RATES))
        self.mp3_bitrate_combo.currentTextChanged.connect(self._on_mp3_bitrate_changed)

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

        self.testing_audio_checkbox = QCheckBox("Testing audio mode", tuning_group)
        self.testing_audio_checkbox.toggled.connect(self._on_testing_audio_changed)

        self.model_sample_mode_checkbox = QCheckBox("Sample mode", tuning_group)
        self.model_sample_mode_checkbox.toggled.connect(self._on_model_sample_mode_changed)

        self.model_sample_duration_spinbox = QSpinBox(tuning_group)
        self.model_sample_duration_spinbox.setRange(1, 600)
        self.model_sample_duration_spinbox.setSuffix(" sec")
        self.model_sample_duration_spinbox.valueChanged.connect(self._on_model_sample_duration_changed)

        tuning_layout.addWidget(self.gpu_checkbox, 0, 0)
        tuning_layout.addWidget(self.normalize_checkbox, 0, 1)
        tuning_layout.addWidget(self.primary_stem_only_checkbox, 1, 0)
        tuning_layout.addWidget(self.secondary_stem_only_checkbox, 1, 1)
        tuning_layout.addWidget(self.testing_audio_checkbox, 2, 0)
        tuning_layout.addWidget(self.model_sample_mode_checkbox, 2, 1)
        tuning_layout.addWidget(QLabel("Sample Duration"), 3, 0)
        tuning_layout.addWidget(self.model_sample_duration_spinbox, 3, 1)

        output_layout.addWidget(output_format_label, 0, 0)
        output_layout.addWidget(self.save_format_combo, 0, 1)
        output_layout.addWidget(wav_type_label, 1, 0)
        output_layout.addWidget(self.wav_type_combo, 1, 1)
        output_layout.addWidget(mp3_bitrate_label, 2, 0)
        output_layout.addWidget(self.mp3_bitrate_combo, 2, 1)
        output_layout.addWidget(self.add_model_name_checkbox, 3, 0, 1, 2)
        output_layout.addWidget(self.create_model_folder_checkbox, 4, 0, 1, 2)

        layout.addLayout(selector_grid)
        layout.addWidget(self.model_label)
        layout.addWidget(output_group)
        layout.addWidget(tuning_group)
        layout.addWidget(button_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_console)
        layout.addWidget(self._build_advanced_group())
        return group

    def _build_advanced_group(self) -> QGroupBox:
        group = QGroupBox("Advanced Model Controls")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(12, 12, 12, 12)
        group_layout.setSpacing(10)

        self.advanced_toggle_button = QToolButton(group)
        self.advanced_toggle_button.setText("Show Advanced Controls")
        self.advanced_toggle_button.setCheckable(True)
        self.advanced_toggle_button.setChecked(False)
        self.advanced_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.advanced_toggle_button.toggled.connect(self._toggle_advanced_controls)

        self.advanced_container = QWidget(group)
        self.advanced_container.setVisible(False)
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(12)

        self.vr_advanced_group = QGroupBox("VR")
        vr_layout = QGridLayout(self.vr_advanced_group)
        vr_layout.setHorizontalSpacing(12)
        vr_layout.setVerticalSpacing(8)
        self.vr_aggression_combo = QComboBox(self.vr_advanced_group)
        self.vr_aggression_combo.addItems([str(value) for value in VR_AGGRESSION])
        self.vr_aggression_combo.currentTextChanged.connect(self._on_vr_aggression_changed)
        self.vr_window_combo = QComboBox(self.vr_advanced_group)
        self.vr_window_combo.addItems(list(VR_WINDOW))
        self.vr_window_combo.currentTextChanged.connect(self._on_vr_window_changed)
        self.vr_batch_size_combo = QComboBox(self.vr_advanced_group)
        self.vr_batch_size_combo.addItems(list(BATCH_SIZE))
        self.vr_batch_size_combo.currentTextChanged.connect(self._on_vr_batch_size_changed)
        self.vr_crop_size_spinbox = QSpinBox(self.vr_advanced_group)
        self.vr_crop_size_spinbox.setRange(1, 4096)
        self.vr_crop_size_spinbox.valueChanged.connect(self._on_vr_crop_size_changed)
        self.vr_tta_checkbox = QCheckBox("TTA", self.vr_advanced_group)
        self.vr_tta_checkbox.toggled.connect(self._on_vr_tta_changed)
        self.vr_post_process_checkbox = QCheckBox("Post Process", self.vr_advanced_group)
        self.vr_post_process_checkbox.toggled.connect(self._on_vr_post_process_changed)
        self.vr_high_end_checkbox = QCheckBox("High End Mirroring", self.vr_advanced_group)
        self.vr_high_end_checkbox.toggled.connect(self._on_vr_high_end_changed)
        self.vr_post_process_threshold_spinbox = QDoubleSpinBox(self.vr_advanced_group)
        self.vr_post_process_threshold_spinbox.setRange(0.0, 1.0)
        self.vr_post_process_threshold_spinbox.setSingleStep(0.05)
        self.vr_post_process_threshold_spinbox.valueChanged.connect(self._on_vr_post_process_threshold_changed)
        vr_layout.addWidget(QLabel("Aggression"), 0, 0)
        vr_layout.addWidget(self.vr_aggression_combo, 0, 1)
        vr_layout.addWidget(QLabel("Window Size"), 1, 0)
        vr_layout.addWidget(self.vr_window_combo, 1, 1)
        vr_layout.addWidget(QLabel("Batch Size"), 2, 0)
        vr_layout.addWidget(self.vr_batch_size_combo, 2, 1)
        vr_layout.addWidget(QLabel("Crop Size"), 3, 0)
        vr_layout.addWidget(self.vr_crop_size_spinbox, 3, 1)
        vr_layout.addWidget(self.vr_tta_checkbox, 4, 0)
        vr_layout.addWidget(self.vr_post_process_checkbox, 4, 1)
        vr_layout.addWidget(self.vr_high_end_checkbox, 5, 0)
        vr_layout.addWidget(QLabel("Post Threshold"), 5, 1)
        vr_layout.addWidget(self.vr_post_process_threshold_spinbox, 5, 2)

        self.mdx_advanced_group = QGroupBox("MDX")
        mdx_layout = QGridLayout(self.mdx_advanced_group)
        mdx_layout.setHorizontalSpacing(12)
        mdx_layout.setVerticalSpacing(8)
        self.mdx_stems_combo = QComboBox(self.mdx_advanced_group)
        self.mdx_stems_combo.addItems([ALL_STEMS, *STEM_SET_MENU])
        self.mdx_stems_combo.currentTextChanged.connect(self._on_mdx_stems_changed)
        self.mdx_segment_size_combo = QComboBox(self.mdx_advanced_group)
        self.mdx_segment_size_combo.setEditable(True)
        self.mdx_segment_size_combo.addItems([str(value) for value in MDX_SEGMENTS])
        self.mdx_segment_size_combo.currentTextChanged.connect(self._on_mdx_segment_size_changed)
        self.mdx_overlap_combo = QComboBox(self.mdx_advanced_group)
        self.mdx_overlap_combo.addItems([str(value) for value in MDX_OVERLAP])
        self.mdx_overlap_combo.currentTextChanged.connect(self._on_mdx_overlap_changed)
        self.mdx_batch_size_combo = QComboBox(self.mdx_advanced_group)
        self.mdx_batch_size_combo.addItems(list(BATCH_SIZE))
        self.mdx_batch_size_combo.currentTextChanged.connect(self._on_mdx_batch_size_changed)
        self.mdx_margin_spinbox = QSpinBox(self.mdx_advanced_group)
        self.mdx_margin_spinbox.setRange(0, 999999)
        self.mdx_margin_spinbox.valueChanged.connect(self._on_mdx_margin_changed)
        self.mdx_compensate_field = QLineEdit(self.mdx_advanced_group)
        self.mdx_compensate_field.editingFinished.connect(self._on_mdx_compensate_changed)
        mdx_layout.addWidget(QLabel("Stem Target"), 0, 0)
        mdx_layout.addWidget(self.mdx_stems_combo, 0, 1)
        mdx_layout.addWidget(QLabel("Segment Size"), 1, 0)
        mdx_layout.addWidget(self.mdx_segment_size_combo, 1, 1)
        mdx_layout.addWidget(QLabel("Overlap"), 2, 0)
        mdx_layout.addWidget(self.mdx_overlap_combo, 2, 1)
        mdx_layout.addWidget(QLabel("Batch Size"), 3, 0)
        mdx_layout.addWidget(self.mdx_batch_size_combo, 3, 1)
        mdx_layout.addWidget(QLabel("Margin"), 4, 0)
        mdx_layout.addWidget(self.mdx_margin_spinbox, 4, 1)
        mdx_layout.addWidget(QLabel("Compensate"), 5, 0)
        mdx_layout.addWidget(self.mdx_compensate_field, 5, 1)

        self.demucs_advanced_group = QGroupBox("Demucs")
        demucs_layout = QGridLayout(self.demucs_advanced_group)
        demucs_layout.setHorizontalSpacing(12)
        demucs_layout.setVerticalSpacing(8)
        self.demucs_stems_combo = QComboBox(self.demucs_advanced_group)
        self.demucs_stems_combo.addItems([ALL_STEMS, *STEM_SET_MENU])
        self.demucs_stems_combo.currentTextChanged.connect(self._on_demucs_stems_changed)
        self.demucs_segment_combo = QComboBox(self.demucs_advanced_group)
        self.demucs_segment_combo.addItems([str(value) for value in DEMUCS_SEGMENTS])
        self.demucs_segment_combo.currentTextChanged.connect(self._on_demucs_segment_changed)
        self.demucs_overlap_combo = QComboBox(self.demucs_advanced_group)
        self.demucs_overlap_combo.addItems([str(value) for value in DEMUCS_OVERLAP])
        self.demucs_overlap_combo.currentTextChanged.connect(self._on_demucs_overlap_changed)
        self.demucs_shifts_spinbox = QSpinBox(self.demucs_advanced_group)
        self.demucs_shifts_spinbox.setRange(0, 100)
        self.demucs_shifts_spinbox.valueChanged.connect(self._on_demucs_shifts_changed)
        self.demucs_margin_spinbox = QSpinBox(self.demucs_advanced_group)
        self.demucs_margin_spinbox.setRange(0, 999999)
        self.demucs_margin_spinbox.valueChanged.connect(self._on_demucs_margin_changed)
        demucs_layout.addWidget(QLabel("Stem Target"), 0, 0)
        demucs_layout.addWidget(self.demucs_stems_combo, 0, 1)
        demucs_layout.addWidget(QLabel("Segment"), 1, 0)
        demucs_layout.addWidget(self.demucs_segment_combo, 1, 1)
        demucs_layout.addWidget(QLabel("Overlap"), 2, 0)
        demucs_layout.addWidget(self.demucs_overlap_combo, 2, 1)
        demucs_layout.addWidget(QLabel("Shifts"), 3, 0)
        demucs_layout.addWidget(self.demucs_shifts_spinbox, 3, 1)
        demucs_layout.addWidget(QLabel("Margin"), 4, 0)
        demucs_layout.addWidget(self.demucs_margin_spinbox, 4, 1)

        self.composition_group = QGroupBox("Workflow Composition")
        composition_layout = QGridLayout(self.composition_group)
        composition_layout.setHorizontalSpacing(12)
        composition_layout.setVerticalSpacing(8)
        self.demucs_pre_proc_checkbox = QCheckBox("Enable Demucs Pre-Proc", self.composition_group)
        self.demucs_pre_proc_checkbox.toggled.connect(self._on_demucs_pre_proc_enabled_changed)
        self.demucs_pre_proc_model_combo = QComboBox(self.composition_group)
        self.demucs_pre_proc_model_combo.currentTextChanged.connect(self._on_demucs_pre_proc_model_changed)
        self.demucs_pre_proc_inst_mix_checkbox = QCheckBox("Save Instrumental Mixture", self.composition_group)
        self.demucs_pre_proc_inst_mix_checkbox.toggled.connect(self._on_demucs_pre_proc_inst_mix_changed)
        self.vocal_splitter_checkbox = QCheckBox("Enable Vocal Splitter", self.composition_group)
        self.vocal_splitter_checkbox.toggled.connect(self._on_vocal_splitter_enabled_changed)
        self.vocal_splitter_model_combo = QComboBox(self.composition_group)
        self.vocal_splitter_model_combo.currentTextChanged.connect(self._on_vocal_splitter_model_changed)
        self.vocal_splitter_save_inst_checkbox = QCheckBox("Save Split Instrumentals", self.composition_group)
        self.vocal_splitter_save_inst_checkbox.toggled.connect(self._on_vocal_splitter_save_inst_changed)
        composition_layout.addWidget(self.demucs_pre_proc_checkbox, 0, 0, 1, 2)
        composition_layout.addWidget(QLabel("Pre-Proc Model"), 1, 0)
        composition_layout.addWidget(self.demucs_pre_proc_model_combo, 1, 1)
        composition_layout.addWidget(self.demucs_pre_proc_inst_mix_checkbox, 2, 0, 1, 2)
        composition_layout.addWidget(self.vocal_splitter_checkbox, 3, 0, 1, 2)
        composition_layout.addWidget(QLabel("Vocal Splitter Model"), 4, 0)
        composition_layout.addWidget(self.vocal_splitter_model_combo, 4, 1)
        composition_layout.addWidget(self.vocal_splitter_save_inst_checkbox, 5, 0, 1, 2)

        self.secondary_models_group = QGroupBox("Secondary Models")
        secondary_layout = QGridLayout(self.secondary_models_group)
        secondary_layout.setHorizontalSpacing(12)
        secondary_layout.setVerticalSpacing(8)
        self.secondary_models_checkbox = QCheckBox("Enable secondary models for selected method", self.secondary_models_group)
        self.secondary_models_checkbox.toggled.connect(self._on_secondary_models_enabled_changed)
        secondary_layout.addWidget(self.secondary_models_checkbox, 0, 0, 1, 3)
        secondary_layout.addWidget(QLabel("Stem"), 1, 0)
        secondary_layout.addWidget(QLabel("Model"), 1, 1)
        secondary_layout.addWidget(QLabel("Scale"), 1, 2)
        for row_index, (slot, label) in enumerate(SECONDARY_MODEL_SLOTS, start=2):
            combo = QComboBox(self.secondary_models_group)
            combo.currentTextChanged.connect(
                lambda value, slot=slot: self._on_secondary_model_changed(slot, value)
            )
            scale = QDoubleSpinBox(self.secondary_models_group)
            scale.setRange(0.01, 0.99)
            scale.setSingleStep(0.01)
            scale.setDecimals(2)
            scale.valueChanged.connect(
                lambda value, slot=slot: self._on_secondary_model_scale_changed(slot, value)
            )
            self.secondary_model_combos[slot] = combo
            self.secondary_scale_spinboxes[slot] = scale
            secondary_layout.addWidget(QLabel(label), row_index, 0)
            secondary_layout.addWidget(combo, row_index, 1)
            secondary_layout.addWidget(scale, row_index, 2)

        advanced_layout.addWidget(self.vr_advanced_group)
        advanced_layout.addWidget(self.mdx_advanced_group)
        advanced_layout.addWidget(self.demucs_advanced_group)
        advanced_layout.addWidget(self.composition_group)
        advanced_layout.addWidget(self.secondary_models_group)
        group_layout.addWidget(self.advanced_toggle_button)
        group_layout.addWidget(self.advanced_container)
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
        save_settings(settings=settings, data_file=self.config_path)

    def _refresh_view(self) -> None:
        input_paths = self.state.paths.input_paths
        self.input_paths_field.setPlainText("\n".join(input_paths))
        self.output_path_field.setText(self.state.paths.export_path)
        self._refresh_processing_controls()
        self._refresh_output_controls()
        self._refresh_tuning_controls()
        self._refresh_advanced_controls()
        resolved_model = self._get_processing_facade().resolve_model(self.state)
        if resolved_model is None:
            self.model_label.setText("Backend target: unavailable for the selected process method")
        else:
            self.model_label.setText(
                f"Backend target: {resolved_model.process_method} / {resolved_model.model_name}"
            )

        validation_issue = self._workflow_validation_issue()
        input_count = len(input_paths)
        input_hint = "No files selected" if input_count == 0 else f"{input_count} file(s) selected"
        output_hint = self.state.paths.export_path or "No output folder selected"
        summary_lines = [
            f"Process method: {self.state.processing.process_method}",
            f"Selected model: {self._selected_model_name() or 'None'}",
            f"Save format: {self.state.output.save_format}",
            f"Wav type: {self.state.output.wav_type}",
            f"MP3 bitrate: {self.state.output.mp3_bitrate}",
            f"GPU preferred: {'Yes' if self.state.processing.use_gpu else 'No'}",
            f"Advanced controls: {'Expanded' if self.advanced_container.isVisible() else 'Collapsed'}",
            f"Normalize output: {'Yes' if self.state.processing.normalize_output else 'No'}",
            f"Input: {input_hint}",
            f"Output: {output_hint}",
        ]
        if validation_issue:
            summary_lines.append(f"Validation: {validation_issue}")
        self.summary_label.setText("\n".join(summary_lines))
        self.process_button.setEnabled(
            not self.state.runtime.is_processing
            and resolved_model is not None
            and bool(input_paths)
            and bool(self.state.paths.export_path)
            and validation_issue is None
        )
        self.process_button.setText("Process with GPU" if self.state.processing.use_gpu else "Process on CPU")
        self.cancel_button.setEnabled(self.state.runtime.can_cancel)
        if self.state.runtime.status_text:
            self.status_label.setText(self.state.runtime.status_text)
        elif validation_issue:
            self.status_label.setText(validation_issue)
        else:
            self.status_label.setText("Idle")
        self.progress_bar.setValue(int(max(0.0, min(self.state.runtime.progress, 100.0))))
        self._sync_log_console()

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

            self.mp3_bitrate_combo.blockSignals(True)
            self.mp3_bitrate_combo.setCurrentText(self.state.output.mp3_bitrate or "320k")
            self.mp3_bitrate_combo.blockSignals(False)

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

            self.testing_audio_checkbox.blockSignals(True)
            self.testing_audio_checkbox.setChecked(self.state.processing.testing_audio)
            self.testing_audio_checkbox.blockSignals(False)

            self.model_sample_mode_checkbox.blockSignals(True)
            self.model_sample_mode_checkbox.setChecked(self.state.processing.model_sample_mode)
            self.model_sample_mode_checkbox.blockSignals(False)

            self.model_sample_duration_spinbox.blockSignals(True)
            self.model_sample_duration_spinbox.setValue(self.state.processing.model_sample_duration)
            self.model_sample_duration_spinbox.blockSignals(False)
        finally:
            self._is_syncing_processing_controls = False
        is_mp3 = self.state.output.save_format == MP3
        self.mp3_bitrate_combo.setEnabled(is_mp3)
        self.wav_type_combo.setEnabled(not is_mp3)
        self.model_sample_duration_spinbox.setEnabled(self.state.processing.model_sample_mode)

    def _refresh_advanced_controls(self) -> None:
        aux_models = self._available_aux_models()
        mdx_stems = self._available_stem_targets("MDX-Net", fallback=(ALL_STEMS, *STEM_SET_MENU))
        demucs_stems = self._available_stem_targets("Demucs", fallback=(ALL_STEMS, *STEM_SET_MENU))
        self._coerce_model_stem_selection("MDX-Net", mdx_stems)
        self._coerce_model_stem_selection("Demucs", demucs_stems)
        self._is_syncing_processing_controls = True
        try:
            self.vr_aggression_combo.blockSignals(True)
            self.vr_aggression_combo.setCurrentText(str(self.state.advanced.aggression_setting))
            self.vr_aggression_combo.blockSignals(False)

            self.vr_window_combo.blockSignals(True)
            self.vr_window_combo.setCurrentText(str(self.state.advanced.window_size))
            self.vr_window_combo.blockSignals(False)

            self.vr_batch_size_combo.blockSignals(True)
            self.vr_batch_size_combo.setCurrentText(self.state.advanced.batch_size or DEF_OPT)
            self.vr_batch_size_combo.blockSignals(False)

            self.vr_crop_size_spinbox.blockSignals(True)
            self.vr_crop_size_spinbox.setValue(self.state.advanced.crop_size)
            self.vr_crop_size_spinbox.blockSignals(False)

            self.vr_tta_checkbox.blockSignals(True)
            self.vr_tta_checkbox.setChecked(self.state.advanced.is_tta)
            self.vr_tta_checkbox.blockSignals(False)

            self.vr_post_process_checkbox.blockSignals(True)
            self.vr_post_process_checkbox.setChecked(self.state.advanced.is_post_process)
            self.vr_post_process_checkbox.blockSignals(False)

            self.vr_high_end_checkbox.blockSignals(True)
            self.vr_high_end_checkbox.setChecked(self.state.advanced.is_high_end_process)
            self.vr_high_end_checkbox.blockSignals(False)

            self.vr_post_process_threshold_spinbox.blockSignals(True)
            self.vr_post_process_threshold_spinbox.setValue(self.state.advanced.post_process_threshold)
            self.vr_post_process_threshold_spinbox.blockSignals(False)

            self.mdx_stems_combo.blockSignals(True)
            self.mdx_stems_combo.clear()
            self.mdx_stems_combo.addItems(list(mdx_stems))
            self.mdx_stems_combo.setCurrentText(self.state.models.mdx_stems or ALL_STEMS)
            self.mdx_stems_combo.blockSignals(False)

            self.mdx_segment_size_combo.blockSignals(True)
            self.mdx_segment_size_combo.setCurrentText(str(self.state.advanced.mdx_segment_size))
            self.mdx_segment_size_combo.blockSignals(False)

            self.mdx_overlap_combo.blockSignals(True)
            self.mdx_overlap_combo.setCurrentText(str(self.state.advanced.overlap_mdx))
            self.mdx_overlap_combo.blockSignals(False)

            self.mdx_batch_size_combo.blockSignals(True)
            self.mdx_batch_size_combo.setCurrentText(self.state.advanced.mdx_batch_size or DEF_OPT)
            self.mdx_batch_size_combo.blockSignals(False)

            self.mdx_margin_spinbox.blockSignals(True)
            self.mdx_margin_spinbox.setValue(self.state.advanced.margin)
            self.mdx_margin_spinbox.blockSignals(False)

            self.mdx_compensate_field.blockSignals(True)
            self.mdx_compensate_field.setText(self.state.advanced.compensate or AUTO_SELECT)
            self.mdx_compensate_field.blockSignals(False)

            self.demucs_stems_combo.blockSignals(True)
            self.demucs_stems_combo.clear()
            self.demucs_stems_combo.addItems(list(demucs_stems))
            self.demucs_stems_combo.setCurrentText(self.state.models.demucs_stems or ALL_STEMS)
            self.demucs_stems_combo.blockSignals(False)

            self.demucs_segment_combo.blockSignals(True)
            self.demucs_segment_combo.setCurrentText(str(self.state.advanced.segment))
            self.demucs_segment_combo.blockSignals(False)

            self.demucs_overlap_combo.blockSignals(True)
            self.demucs_overlap_combo.setCurrentText(str(self.state.advanced.overlap))
            self.demucs_overlap_combo.blockSignals(False)

            self.demucs_shifts_spinbox.blockSignals(True)
            self.demucs_shifts_spinbox.setValue(self.state.advanced.shifts)
            self.demucs_shifts_spinbox.blockSignals(False)

            self.demucs_margin_spinbox.blockSignals(True)
            self.demucs_margin_spinbox.setValue(self.state.advanced.margin_demucs)
            self.demucs_margin_spinbox.blockSignals(False)

            self.demucs_pre_proc_checkbox.blockSignals(True)
            self.demucs_pre_proc_checkbox.setChecked(self._extra_flag("is_demucs_pre_proc_model_activate"))
            self.demucs_pre_proc_checkbox.blockSignals(False)

            self.demucs_pre_proc_model_combo.blockSignals(True)
            self.demucs_pre_proc_model_combo.clear()
            self.demucs_pre_proc_model_combo.addItems(list(aux_models))
            self.demucs_pre_proc_model_combo.setCurrentText(
                self.state.models.demucs_pre_proc_model if self.state.models.demucs_pre_proc_model in aux_models else NO_MODEL
            )
            self.demucs_pre_proc_model_combo.blockSignals(False)

            self.demucs_pre_proc_inst_mix_checkbox.blockSignals(True)
            self.demucs_pre_proc_inst_mix_checkbox.setChecked(self._extra_flag("is_demucs_pre_proc_model_inst_mix"))
            self.demucs_pre_proc_inst_mix_checkbox.blockSignals(False)

            self.vocal_splitter_checkbox.blockSignals(True)
            self.vocal_splitter_checkbox.setChecked(self._extra_flag("is_set_vocal_splitter"))
            self.vocal_splitter_checkbox.blockSignals(False)

            self.vocal_splitter_model_combo.blockSignals(True)
            self.vocal_splitter_model_combo.clear()
            self.vocal_splitter_model_combo.addItems(list(aux_models))
            self.vocal_splitter_model_combo.setCurrentText(
                self.state.models.vocal_splitter_model if self.state.models.vocal_splitter_model in aux_models else NO_MODEL
            )
            self.vocal_splitter_model_combo.blockSignals(False)

            self.vocal_splitter_save_inst_checkbox.blockSignals(True)
            self.vocal_splitter_save_inst_checkbox.setChecked(self._extra_flag("is_save_inst_set_vocal_splitter"))
            self.vocal_splitter_save_inst_checkbox.blockSignals(False)

            activation_key = self._secondary_activation_key(self.state.processing.process_method)
            is_secondary_enabled = bool(
                activation_key
                and self.state.models.secondary_model_activations.get(activation_key, False)
            )
            self.secondary_models_checkbox.blockSignals(True)
            self.secondary_models_checkbox.setChecked(is_secondary_enabled)
            self.secondary_models_checkbox.blockSignals(False)

            for slot, _label in SECONDARY_MODEL_SLOTS:
                model_key = self._secondary_model_key(slot)
                scale_key = f"{model_key}_scale" if model_key else ""
                combo = self.secondary_model_combos[slot]
                scale = self.secondary_scale_spinboxes[slot]

                combo.blockSignals(True)
                combo.clear()
                combo.addItems(list(aux_models))
                if model_key:
                    combo.setCurrentText(
                        self.state.models.secondary_models.get(model_key, NO_MODEL)
                        if self.state.models.secondary_models.get(model_key, NO_MODEL) in aux_models
                        else NO_MODEL
                    )
                combo.blockSignals(False)

                scale.blockSignals(True)
                scale.setValue(float(self.state.models.secondary_model_scales.get(scale_key, DEFAULT_DATA.get(scale_key, 0.5))))
                scale.blockSignals(False)
        finally:
            self._is_syncing_processing_controls = False

        process_method = self.state.processing.process_method
        self.vr_advanced_group.setVisible(process_method == "VR Architecture")
        self.mdx_advanced_group.setVisible(process_method == "MDX-Net")
        self.demucs_advanced_group.setVisible(process_method == "Demucs")
        self.composition_group.setVisible(process_method in {"VR Architecture", "MDX-Net", "Demucs"})
        self.secondary_models_group.setVisible(process_method in {"VR Architecture", "MDX-Net", "Demucs"})
        self.demucs_pre_proc_model_combo.setEnabled(self.demucs_pre_proc_checkbox.isChecked())
        self.demucs_pre_proc_inst_mix_checkbox.setEnabled(self.demucs_pre_proc_checkbox.isChecked())
        self.vocal_splitter_model_combo.setEnabled(self.vocal_splitter_checkbox.isChecked())
        self.vocal_splitter_save_inst_checkbox.setEnabled(self.vocal_splitter_checkbox.isChecked())
        for combo in self.secondary_model_combos.values():
            combo.setEnabled(self.secondary_models_checkbox.isChecked())
        for scale in self.secondary_scale_spinboxes.values():
            scale.setEnabled(self.secondary_models_checkbox.isChecked())

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
        self._normalize_common_workflow_state()
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

    def _on_mp3_bitrate_changed(self, bitrate: str) -> None:
        if self._is_syncing_processing_controls or not bitrate:
            return
        self.state = replace(self.state, output=replace(self.state.output, mp3_bitrate=bitrate))
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

    def _on_testing_audio_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, processing=replace(self.state.processing, testing_audio=checked))
        self._persist_state()
        self._refresh_view()

    def _on_model_sample_mode_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, processing=replace(self.state.processing, model_sample_mode=checked))
        self._persist_state()
        self._refresh_view()

    def _on_model_sample_duration_changed(self, value: int) -> None:
        if self._is_syncing_processing_controls:
            return
        self.state = replace(self.state, processing=replace(self.state.processing, model_sample_duration=value))
        self._persist_state()
        self._refresh_view()

    def _toggle_advanced_controls(self, checked: bool) -> None:
        self.advanced_toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self.advanced_toggle_button.setText("Hide Advanced Controls" if checked else "Show Advanced Controls")
        self.advanced_container.setVisible(checked)
        self._refresh_view()

    def _update_advanced(self, **changes: object) -> None:
        self.state = replace(self.state, advanced=replace(self.state.advanced, **changes))
        self._persist_state()
        self._refresh_view()

    def _update_models(self, **changes: object) -> None:
        self.state = replace(self.state, models=replace(self.state.models, **changes))
        self._persist_state()
        self._refresh_view()

    def _update_secondary_model_maps(
        self,
        *,
        models: dict[str, str] | None = None,
        scales: dict[str, float] | None = None,
        activations: dict[str, bool] | None = None,
    ) -> None:
        current_models = dict(self.state.models.secondary_models)
        current_scales = dict(self.state.models.secondary_model_scales)
        current_activations = dict(self.state.models.secondary_model_activations)
        if models:
            current_models.update(models)
        if scales:
            current_scales.update(scales)
        if activations:
            current_activations.update(activations)
        self._update_models(
            secondary_models=current_models,
            secondary_model_scales=current_scales,
            secondary_model_activations=current_activations,
        )

    def _update_extra_settings(self, **changes: object) -> None:
        updated = dict(self.state.extra_settings)
        updated.update(changes)
        self.state = replace(self.state, extra_settings=updated)
        self._persist_state()
        self._refresh_view()

    def _extra_flag(self, key: str) -> bool:
        return bool(self.state.extra_settings.get(key, False))

    def _available_aux_models(self) -> tuple[str, ...]:
        models = self._get_processing_facade().available_tagged_models_for_methods(("VR Architecture", "MDX-Net"))
        return (NO_MODEL, *models)

    def _available_stem_targets(self, process_method: str, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
        try:
            targets = self._get_processing_facade().available_stem_targets(self.state, process_method)
        except Exception:
            targets = ()
        return targets or fallback

    def _coerce_model_stem_selection(self, process_method: str, available_targets: tuple[str, ...]) -> None:
        if process_method == "MDX-Net":
            current_value = self.state.models.mdx_stems
            field_name = "mdx_stems"
        elif process_method == "Demucs":
            current_value = self.state.models.demucs_stems
            field_name = "demucs_stems"
        else:
            return

        if not available_targets or current_value in available_targets:
            return
        self.state = replace(self.state, models=replace(self.state.models, **{field_name: available_targets[0]}))
        self._normalize_common_workflow_state()
        self._persist_state()

    def _normalize_common_workflow_state(self) -> None:
        extra_settings = dict(self.state.extra_settings)
        process_method = self.state.processing.process_method
        demucs_stem = self.state.models.demucs_stems

        if process_method != "Demucs":
            extra_settings["is_demucs_pre_proc_model_activate"] = False
            extra_settings["is_demucs_pre_proc_model_inst_mix"] = False

        if demucs_stem in {VOCAL_STEM, INST_STEM}:
            extra_settings["is_demucs_pre_proc_model_activate"] = False
            extra_settings["is_demucs_pre_proc_model_inst_mix"] = False

        if not extra_settings.get("is_set_vocal_splitter", False):
            extra_settings["is_save_inst_set_vocal_splitter"] = False

        # TODO: When combine-stems and saved workflow profiles move into Qt, normalize those
        # cross-field interactions here instead of relying on legacy Tk menus.
        self.state = replace(self.state, extra_settings=extra_settings)

    def _workflow_validation_issue(self) -> str | None:
        if self._extra_flag("is_demucs_pre_proc_model_activate"):
            if self.state.processing.process_method != "Demucs":
                return "Demucs pre-proc is only available for Demucs workflows."
            if self.state.models.demucs_stems in {VOCAL_STEM, INST_STEM}:
                return "Demucs pre-proc requires All Stems or a non-vocal Demucs stem target."
            if self.state.models.demucs_pre_proc_model == NO_MODEL:
                return "Select an installed pre-proc model before starting."

        if self._extra_flag("is_demucs_pre_proc_model_inst_mix") and not self._extra_flag("is_demucs_pre_proc_model_activate"):
            return "Save Instrumental Mixture requires Demucs pre-proc to be enabled."

        if self._extra_flag("is_set_vocal_splitter") and self.state.models.vocal_splitter_model == NO_MODEL:
            return "Select an installed vocal splitter model before starting."

        if self._extra_flag("is_save_inst_set_vocal_splitter") and not self._extra_flag("is_set_vocal_splitter"):
            return "Save Split Instrumentals requires the vocal splitter workflow to be enabled."

        return None

    def _secondary_prefix(self, process_method: str | None = None) -> str | None:
        method = process_method or self.state.processing.process_method
        if method == "VR Architecture":
            return "vr"
        if method == "MDX-Net":
            return "mdx"
        if method == "Demucs":
            return "demucs"
        return None

    def _secondary_activation_key(self, process_method: str | None = None) -> str | None:
        prefix = self._secondary_prefix(process_method)
        return f"{prefix}_is_secondary_model_activate" if prefix else None

    def _secondary_model_key(self, slot: str, process_method: str | None = None) -> str | None:
        prefix = self._secondary_prefix(process_method)
        return f"{prefix}_{slot}_secondary_model" if prefix else None

    def _on_vr_aggression_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(aggression_setting=int(value))

    def _on_vr_window_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(window_size=int(value))

    def _on_vr_batch_size_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(batch_size=value)

    def _on_vr_crop_size_changed(self, value: int) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(crop_size=value)

    def _on_vr_tta_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(is_tta=checked)

    def _on_vr_post_process_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(is_post_process=checked)

    def _on_vr_high_end_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(is_high_end_process=checked)

    def _on_vr_post_process_threshold_changed(self, value: float) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(post_process_threshold=value)

    def _on_mdx_segment_size_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(mdx_segment_size=int(value))

    def _on_mdx_stems_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_models(mdx_stems=value)

    def _on_mdx_overlap_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(overlap_mdx=value)

    def _on_mdx_batch_size_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(mdx_batch_size=value)

    def _on_mdx_margin_changed(self, value: int) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(margin=value)

    def _on_mdx_compensate_changed(self) -> None:
        if self._is_syncing_processing_controls:
            return
        value = self.mdx_compensate_field.text().strip() or AUTO_SELECT
        self._update_advanced(compensate=value)

    def _on_demucs_segment_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(segment=value)

    def _on_demucs_stems_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self.state = replace(self.state, models=replace(self.state.models, demucs_stems=value))
        self._normalize_common_workflow_state()
        self._persist_state()
        self._refresh_view()

    def _on_demucs_overlap_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_advanced(overlap=value)

    def _on_demucs_shifts_changed(self, value: int) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(shifts=value)

    def _on_demucs_margin_changed(self, value: int) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_advanced(margin_demucs=value)

    def _on_demucs_pre_proc_enabled_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        updated = dict(self.state.extra_settings)
        updated["is_demucs_pre_proc_model_activate"] = checked
        if not checked:
            updated["is_demucs_pre_proc_model_inst_mix"] = False
        self.state = replace(self.state, extra_settings=updated)
        self._normalize_common_workflow_state()
        self._persist_state()
        self._refresh_view()

    def _on_demucs_pre_proc_model_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_models(demucs_pre_proc_model=value)

    def _on_demucs_pre_proc_inst_mix_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_extra_settings(is_demucs_pre_proc_model_inst_mix=checked)

    def _on_vocal_splitter_enabled_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        updated = dict(self.state.extra_settings)
        updated["is_set_vocal_splitter"] = checked
        if not checked:
            updated["is_save_inst_set_vocal_splitter"] = False
        self.state = replace(self.state, extra_settings=updated)
        self._persist_state()
        self._refresh_view()

    def _on_vocal_splitter_model_changed(self, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        self._update_models(vocal_splitter_model=value)

    def _on_vocal_splitter_save_inst_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        self._update_extra_settings(is_save_inst_set_vocal_splitter=checked)

    def _on_secondary_models_enabled_changed(self, checked: bool) -> None:
        if self._is_syncing_processing_controls:
            return
        activation_key = self._secondary_activation_key()
        if activation_key:
            self._update_secondary_model_maps(activations={activation_key: checked})

    def _on_secondary_model_changed(self, slot: str, value: str) -> None:
        if self._is_syncing_processing_controls or not value:
            return
        model_key = self._secondary_model_key(slot)
        if model_key:
            self._update_secondary_model_maps(models={model_key: value})

    def _on_secondary_model_scale_changed(self, slot: str, value: float) -> None:
        if self._is_syncing_processing_controls:
            return
        model_key = self._secondary_model_key(slot)
        if model_key:
            self._update_secondary_model_maps(scales={f"{model_key}_scale": float(value)})

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

        self._set_runtime(
            is_processing=True,
            can_cancel=True,
            progress=0.0,
            status_text="Preparing",
            log_lines=(),
            last_error=None,
        )

        self.processing_thread = QThread(self)
        self.processing_worker = _ProcessingWorker(self._get_processing_facade(), self.state)
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

    def _append_log(self, message: str) -> None:
        self._set_runtime(log_lines=self.state.runtime.log_lines + (message,))

    def _open_download_manager(self) -> None:
        if self.download_manager_window is None:
            self.download_manager_window = DownloadManagerWindow()
        self.download_manager_window.show()
        self.download_manager_window.raise_()
        self.download_manager_window.activateWindow()

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
        self._set_runtime(
            is_processing=False,
            can_cancel=False,
            progress=0.0,
            status_text="Cancelled",
        )

    def _processing_failed(self, message: str) -> None:
        self._append_log(message)
        self._set_runtime(
            is_processing=False,
            can_cancel=False,
            status_text="Failed",
            last_error=message,
        )

    def _cleanup_processing_thread(self) -> None:
        if self.processing_worker is not None:
            self.processing_worker.deleteLater()
        if self.processing_thread is not None:
            self.processing_thread.deleteLater()
        self.processing_worker = None
        self.processing_thread = None


class _ProcessingWorker(QObject):
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
