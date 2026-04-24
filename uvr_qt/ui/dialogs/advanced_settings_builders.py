"""Widget construction for each section of the Advanced Settings dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)

from gui_data.constants import (
    ALL_STEMS,
    BATCH_SIZE,
    DEF_OPT,
    DEMUCS_OVERLAP,
    DEMUCS_SEGMENTS,
    MDX_OVERLAP,
    MDX_SEGMENTS,
    STEM_SET_MENU,
    VR_AGGRESSION,
    VR_WINDOW,
)
from uvr_qt.ui.model_utils import SECONDARY_MODEL_SLOTS

if TYPE_CHECKING:
    from uvr_qt.ui.dialogs.advanced_settings_dialog import AdvancedSettingsDialog


def build_vr_group(d: "AdvancedSettingsDialog") -> QGroupBox:
    group = QGroupBox("VR")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(8)

    d.vr_aggression_combo = QComboBox(group)
    d.vr_aggression_combo.addItems([str(v) for v in VR_AGGRESSION])
    d.vr_aggression_combo.currentTextChanged.connect(d._on_vr_aggression_changed)

    d.vr_window_combo = QComboBox(group)
    d.vr_window_combo.addItems(list(VR_WINDOW))
    d.vr_window_combo.currentTextChanged.connect(d._on_vr_window_changed)

    d.vr_batch_size_combo = QComboBox(group)
    d.vr_batch_size_combo.addItems(list(BATCH_SIZE))
    d.vr_batch_size_combo.currentTextChanged.connect(d._on_vr_batch_size_changed)

    d.vr_crop_size_spinbox = QSpinBox(group)
    d.vr_crop_size_spinbox.setRange(1, 4096)
    d.vr_crop_size_spinbox.valueChanged.connect(d._on_vr_crop_size_changed)

    d.vr_tta_checkbox = QCheckBox("TTA", group)
    d.vr_tta_checkbox.toggled.connect(d._on_vr_tta_changed)
    d.vr_post_process_checkbox = QCheckBox("Post Process", group)
    d.vr_post_process_checkbox.toggled.connect(d._on_vr_post_process_changed)
    d.vr_high_end_checkbox = QCheckBox("High End Mirroring", group)
    d.vr_high_end_checkbox.toggled.connect(d._on_vr_high_end_changed)
    d.vr_post_process_threshold_spinbox = QDoubleSpinBox(group)
    d.vr_post_process_threshold_spinbox.setRange(0.0, 1.0)
    d.vr_post_process_threshold_spinbox.setSingleStep(0.05)
    d.vr_post_process_threshold_spinbox.valueChanged.connect(d._on_vr_post_process_threshold_changed)

    layout.addWidget(QLabel("Aggression"), 0, 0)
    layout.addWidget(d.vr_aggression_combo, 0, 1)
    layout.addWidget(QLabel("Window Size"), 1, 0)
    layout.addWidget(d.vr_window_combo, 1, 1)
    layout.addWidget(QLabel("Batch Size"), 2, 0)
    layout.addWidget(d.vr_batch_size_combo, 2, 1)
    layout.addWidget(QLabel("Crop Size"), 3, 0)
    layout.addWidget(d.vr_crop_size_spinbox, 3, 1)
    layout.addWidget(d.vr_tta_checkbox, 4, 0)
    layout.addWidget(d.vr_post_process_checkbox, 4, 1)
    layout.addWidget(d.vr_high_end_checkbox, 5, 0)
    layout.addWidget(QLabel("Post Threshold"), 5, 1)
    layout.addWidget(d.vr_post_process_threshold_spinbox, 5, 2)
    return group


def build_mdx_group(d: "AdvancedSettingsDialog") -> QGroupBox:
    group = QGroupBox("MDX")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(8)

    d.mdx_stems_combo = QComboBox(group)
    d.mdx_stems_combo.addItems([ALL_STEMS, *STEM_SET_MENU])
    d.mdx_stems_combo.currentTextChanged.connect(d._on_mdx_stems_changed)

    d.mdx_segment_size_combo = QComboBox(group)
    d.mdx_segment_size_combo.setEditable(True)
    d.mdx_segment_size_combo.addItems([str(v) for v in MDX_SEGMENTS])
    d.mdx_segment_size_combo.currentTextChanged.connect(d._on_mdx_segment_size_changed)

    d.mdx_overlap_combo = QComboBox(group)
    d.mdx_overlap_combo.addItems([str(v) for v in MDX_OVERLAP])
    d.mdx_overlap_combo.currentTextChanged.connect(d._on_mdx_overlap_changed)

    d.mdx_batch_size_combo = QComboBox(group)
    d.mdx_batch_size_combo.addItems(list(BATCH_SIZE))
    d.mdx_batch_size_combo.currentTextChanged.connect(d._on_mdx_batch_size_changed)

    d.mdx_margin_spinbox = QSpinBox(group)
    d.mdx_margin_spinbox.setRange(0, 999999)
    d.mdx_margin_spinbox.valueChanged.connect(d._on_mdx_margin_changed)

    d.mdx_compensate_field = QLineEdit(group)
    d.mdx_compensate_field.editingFinished.connect(d._on_mdx_compensate_changed)

    layout.addWidget(QLabel("Stem Target"), 0, 0)
    layout.addWidget(d.mdx_stems_combo, 0, 1)
    layout.addWidget(QLabel("Segment Size"), 1, 0)
    layout.addWidget(d.mdx_segment_size_combo, 1, 1)
    layout.addWidget(QLabel("Overlap"), 2, 0)
    layout.addWidget(d.mdx_overlap_combo, 2, 1)
    layout.addWidget(QLabel("Batch Size"), 3, 0)
    layout.addWidget(d.mdx_batch_size_combo, 3, 1)
    layout.addWidget(QLabel("Margin"), 4, 0)
    layout.addWidget(d.mdx_margin_spinbox, 4, 1)
    layout.addWidget(QLabel("Compensate"), 5, 0)
    layout.addWidget(d.mdx_compensate_field, 5, 1)
    return group


def build_demucs_group(d: "AdvancedSettingsDialog") -> QGroupBox:
    group = QGroupBox("Demucs")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(8)

    d.demucs_stems_combo = QComboBox(group)
    d.demucs_stems_combo.addItems([ALL_STEMS, *STEM_SET_MENU])
    d.demucs_stems_combo.currentTextChanged.connect(d._on_demucs_stems_changed)

    d.demucs_segment_combo = QComboBox(group)
    d.demucs_segment_combo.addItems([str(v) for v in DEMUCS_SEGMENTS])
    d.demucs_segment_combo.currentTextChanged.connect(d._on_demucs_segment_changed)

    d.demucs_overlap_combo = QComboBox(group)
    d.demucs_overlap_combo.addItems([str(v) for v in DEMUCS_OVERLAP])
    d.demucs_overlap_combo.currentTextChanged.connect(d._on_demucs_overlap_changed)

    d.demucs_shifts_spinbox = QSpinBox(group)
    d.demucs_shifts_spinbox.setRange(0, 100)
    d.demucs_shifts_spinbox.valueChanged.connect(d._on_demucs_shifts_changed)

    d.demucs_margin_spinbox = QSpinBox(group)
    d.demucs_margin_spinbox.setRange(0, 999999)
    d.demucs_margin_spinbox.valueChanged.connect(d._on_demucs_margin_changed)

    layout.addWidget(QLabel("Stem Target"), 0, 0)
    layout.addWidget(d.demucs_stems_combo, 0, 1)
    layout.addWidget(QLabel("Segment"), 1, 0)
    layout.addWidget(d.demucs_segment_combo, 1, 1)
    layout.addWidget(QLabel("Overlap"), 2, 0)
    layout.addWidget(d.demucs_overlap_combo, 2, 1)
    layout.addWidget(QLabel("Shifts"), 3, 0)
    layout.addWidget(d.demucs_shifts_spinbox, 3, 1)
    layout.addWidget(QLabel("Margin"), 4, 0)
    layout.addWidget(d.demucs_margin_spinbox, 4, 1)
    return group


def build_composition_group(d: "AdvancedSettingsDialog") -> QGroupBox:
    group = QGroupBox("Workflow Composition")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(8)

    d.demucs_pre_proc_checkbox = QCheckBox("Enable Demucs Pre-Proc", group)
    d.demucs_pre_proc_checkbox.toggled.connect(d._on_demucs_pre_proc_enabled_changed)
    d.demucs_pre_proc_model_combo = QComboBox(group)
    d.demucs_pre_proc_model_combo.currentTextChanged.connect(d._on_demucs_pre_proc_model_changed)
    d.demucs_pre_proc_inst_mix_checkbox = QCheckBox("Save Instrumental Mixture", group)
    d.demucs_pre_proc_inst_mix_checkbox.toggled.connect(d._on_demucs_pre_proc_inst_mix_changed)
    d.vocal_splitter_checkbox = QCheckBox("Enable Vocal Splitter", group)
    d.vocal_splitter_checkbox.toggled.connect(d._on_vocal_splitter_enabled_changed)
    d.vocal_splitter_model_combo = QComboBox(group)
    d.vocal_splitter_model_combo.currentTextChanged.connect(d._on_vocal_splitter_model_changed)
    d.vocal_splitter_save_inst_checkbox = QCheckBox("Save Split Instrumentals", group)
    d.vocal_splitter_save_inst_checkbox.toggled.connect(d._on_vocal_splitter_save_inst_changed)

    layout.addWidget(d.demucs_pre_proc_checkbox, 0, 0, 1, 2)
    layout.addWidget(QLabel("Pre-Proc Model"), 1, 0)
    layout.addWidget(d.demucs_pre_proc_model_combo, 1, 1)
    layout.addWidget(d.demucs_pre_proc_inst_mix_checkbox, 2, 0, 1, 2)
    layout.addWidget(d.vocal_splitter_checkbox, 3, 0, 1, 2)
    layout.addWidget(QLabel("Vocal Splitter Model"), 4, 0)
    layout.addWidget(d.vocal_splitter_model_combo, 4, 1)
    layout.addWidget(d.vocal_splitter_save_inst_checkbox, 5, 0, 1, 2)
    return group


def build_secondary_group(d: "AdvancedSettingsDialog") -> QGroupBox:
    group = QGroupBox("Secondary Models")
    layout = QGridLayout(group)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(8)

    d.secondary_models_checkbox = QCheckBox("Enable secondary models for selected method", group)
    d.secondary_models_checkbox.toggled.connect(d._on_secondary_models_enabled_changed)
    layout.addWidget(d.secondary_models_checkbox, 0, 0, 1, 3)
    layout.addWidget(QLabel("Stem"), 1, 0)
    layout.addWidget(QLabel("Model"), 1, 1)
    layout.addWidget(QLabel("Scale"), 1, 2)

    for row, (slot, label) in enumerate(SECONDARY_MODEL_SLOTS, start=2):
        combo = QComboBox(group)
        combo.currentTextChanged.connect(lambda value, s=slot: d._on_secondary_model_changed(s, value))
        scale = QDoubleSpinBox(group)
        scale.setRange(0.01, 0.99)
        scale.setSingleStep(0.01)
        scale.setDecimals(2)
        scale.valueChanged.connect(lambda value, s=slot: d._on_secondary_model_scale_changed(s, value))
        d.secondary_model_combos[slot] = combo
        d.secondary_scale_spinboxes[slot] = scale
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(combo, row, 1)
        layout.addWidget(scale, row, 2)
    return group
