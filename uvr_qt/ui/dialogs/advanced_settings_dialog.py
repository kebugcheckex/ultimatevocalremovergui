"""Non-modal Advanced Model Controls dialog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QDoubleSpinBox, QScrollArea, QVBoxLayout, QWidget

from gui_data.constants import ALL_STEMS, AUTO_SELECT, DEFAULT_DATA, DEF_OPT, NO_MODEL, STEM_SET_MENU
from uvr_qt.state import AppState
from uvr_qt.ui.dialogs.advanced_settings_builders import (
    build_composition_group,
    build_demucs_group,
    build_mdx_group,
    build_secondary_group,
    build_vr_group,
)
from uvr_qt.ui.model_utils import (
    SECONDARY_MODEL_SLOTS,
    normalize_common_workflow_state,
    secondary_activation_key,
    secondary_model_key,
    secondary_prefix,
)


def _set_combo(combo: QComboBox, value: str) -> None:
    combo.blockSignals(True)
    combo.setCurrentText(value)
    combo.blockSignals(False)


def _repopulate_combo(combo: QComboBox, items: tuple[str, ...], current: str) -> None:
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(list(items))
    combo.setCurrentText(current)
    combo.blockSignals(False)


class AdvancedSettingsDialog(QDialog):
    """Non-modal dialog for per-method advanced controls, workflow, and secondary models."""

    def __init__(
        self,
        state: AppState,
        on_state_changed: Callable[[AppState], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Model Controls")
        self.setModal(False)
        self.resize(640, 700)
        self._state = state
        self._on_state_changed = on_state_changed
        self._syncing = False
        self.secondary_model_combos: dict[str, QComboBox] = {}
        self.secondary_scale_spinboxes: dict[str, QDoubleSpinBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        self.vr_advanced_group = build_vr_group(self)
        self.mdx_advanced_group = build_mdx_group(self)
        self.demucs_advanced_group = build_demucs_group(self)
        self.composition_group = build_composition_group(self)
        self.secondary_models_group = build_secondary_group(self)

        content_layout.addWidget(self.vr_advanced_group)
        content_layout.addWidget(self.mdx_advanced_group)
        content_layout.addWidget(self.demucs_advanced_group)
        content_layout.addWidget(self.composition_group)
        content_layout.addWidget(self.secondary_models_group)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def update_from_state(
        self,
        state: AppState,
        *,
        aux_models: tuple[str, ...],
        mdx_stems: tuple[str, ...],
        demucs_stems: tuple[str, ...],
    ) -> None:
        self._state = state
        self._syncing = True
        try:
            adv = state.advanced
            _set_combo(self.vr_aggression_combo, str(adv.aggression_setting))
            _set_combo(self.vr_window_combo, str(adv.window_size))
            _set_combo(self.vr_batch_size_combo, adv.batch_size or DEF_OPT)
            self.vr_crop_size_spinbox.blockSignals(True)
            self.vr_crop_size_spinbox.setValue(adv.crop_size)
            self.vr_crop_size_spinbox.blockSignals(False)
            self.vr_tta_checkbox.blockSignals(True)
            self.vr_tta_checkbox.setChecked(adv.is_tta)
            self.vr_tta_checkbox.blockSignals(False)
            self.vr_post_process_checkbox.blockSignals(True)
            self.vr_post_process_checkbox.setChecked(adv.is_post_process)
            self.vr_post_process_checkbox.blockSignals(False)
            self.vr_high_end_checkbox.blockSignals(True)
            self.vr_high_end_checkbox.setChecked(adv.is_high_end_process)
            self.vr_high_end_checkbox.blockSignals(False)
            self.vr_post_process_threshold_spinbox.blockSignals(True)
            self.vr_post_process_threshold_spinbox.setValue(adv.post_process_threshold)
            self.vr_post_process_threshold_spinbox.blockSignals(False)

            _repopulate_combo(self.mdx_stems_combo, mdx_stems, state.models.mdx_stems or ALL_STEMS)
            _set_combo(self.mdx_segment_size_combo, str(adv.mdx_segment_size))
            _set_combo(self.mdx_overlap_combo, str(adv.overlap_mdx))
            _set_combo(self.mdx_batch_size_combo, adv.mdx_batch_size or DEF_OPT)
            self.mdx_margin_spinbox.blockSignals(True)
            self.mdx_margin_spinbox.setValue(adv.margin)
            self.mdx_margin_spinbox.blockSignals(False)
            self.mdx_compensate_field.blockSignals(True)
            self.mdx_compensate_field.setText(adv.compensate or AUTO_SELECT)
            self.mdx_compensate_field.blockSignals(False)

            _repopulate_combo(self.demucs_stems_combo, demucs_stems, state.models.demucs_stems or ALL_STEMS)
            _set_combo(self.demucs_segment_combo, str(adv.segment))
            _set_combo(self.demucs_overlap_combo, str(adv.overlap))
            self.demucs_shifts_spinbox.blockSignals(True)
            self.demucs_shifts_spinbox.setValue(adv.shifts)
            self.demucs_shifts_spinbox.blockSignals(False)
            self.demucs_margin_spinbox.blockSignals(True)
            self.demucs_margin_spinbox.setValue(adv.margin_demucs)
            self.demucs_margin_spinbox.blockSignals(False)

            self.demucs_pre_proc_checkbox.blockSignals(True)
            self.demucs_pre_proc_checkbox.setChecked(self._flag("is_demucs_pre_proc_model_activate"))
            self.demucs_pre_proc_checkbox.blockSignals(False)
            _repopulate_combo(
                self.demucs_pre_proc_model_combo,
                aux_models,
                state.models.demucs_pre_proc_model if state.models.demucs_pre_proc_model in aux_models else NO_MODEL,
            )
            self.demucs_pre_proc_inst_mix_checkbox.blockSignals(True)
            self.demucs_pre_proc_inst_mix_checkbox.setChecked(self._flag("is_demucs_pre_proc_model_inst_mix"))
            self.demucs_pre_proc_inst_mix_checkbox.blockSignals(False)
            self.vocal_splitter_checkbox.blockSignals(True)
            self.vocal_splitter_checkbox.setChecked(self._flag("is_set_vocal_splitter"))
            self.vocal_splitter_checkbox.blockSignals(False)
            _repopulate_combo(
                self.vocal_splitter_model_combo,
                aux_models,
                state.models.vocal_splitter_model if state.models.vocal_splitter_model in aux_models else NO_MODEL,
            )
            self.vocal_splitter_save_inst_checkbox.blockSignals(True)
            self.vocal_splitter_save_inst_checkbox.setChecked(self._flag("is_save_inst_set_vocal_splitter"))
            self.vocal_splitter_save_inst_checkbox.blockSignals(False)

            act_key = secondary_activation_key(state.processing.process_method)
            is_secondary = bool(act_key and state.models.secondary_model_activations.get(act_key, False))
            self.secondary_models_checkbox.blockSignals(True)
            self.secondary_models_checkbox.setChecked(is_secondary)
            self.secondary_models_checkbox.blockSignals(False)
            for slot, _label in SECONDARY_MODEL_SLOTS:
                mk = secondary_model_key(slot, state.processing.process_method)
                sk = f"{mk}_scale" if mk else ""
                combo = self.secondary_model_combos[slot]
                spinbox = self.secondary_scale_spinboxes[slot]
                _repopulate_combo(
                    combo,
                    aux_models,
                    state.models.secondary_models.get(mk, NO_MODEL)
                    if mk and state.models.secondary_models.get(mk, NO_MODEL) in aux_models
                    else NO_MODEL,
                )
                spinbox.blockSignals(True)
                spinbox.setValue(float(state.models.secondary_model_scales.get(sk, DEFAULT_DATA.get(sk, 0.5))))
                spinbox.blockSignals(False)
        finally:
            self._syncing = False

        process_method = state.processing.process_method
        self.vr_advanced_group.setVisible(process_method == "VR Architecture")
        self.mdx_advanced_group.setVisible(process_method == "MDX-Net")
        self.demucs_advanced_group.setVisible(process_method == "Demucs")
        self.composition_group.setVisible(process_method in {"VR Architecture", "MDX-Net", "Demucs"})
        self.secondary_models_group.setVisible(process_method in {"VR Architecture", "MDX-Net", "Demucs"})
        self.demucs_pre_proc_model_combo.setEnabled(self.demucs_pre_proc_checkbox.isChecked())
        self.demucs_pre_proc_inst_mix_checkbox.setEnabled(self.demucs_pre_proc_checkbox.isChecked())
        self.vocal_splitter_model_combo.setEnabled(self.vocal_splitter_checkbox.isChecked())
        self.vocal_splitter_save_inst_checkbox.setEnabled(self.vocal_splitter_checkbox.isChecked())
        enabled = self.secondary_models_checkbox.isChecked()
        for combo in self.secondary_model_combos.values():
            combo.setEnabled(enabled)
        for spinbox in self.secondary_scale_spinboxes.values():
            spinbox.setEnabled(enabled)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _flag(self, key: str) -> bool:
        return bool(self._state.extra_settings.get(key, False))

    def _update_advanced(self, **changes: object) -> None:
        self._state = replace(self._state, advanced=replace(self._state.advanced, **changes))
        self._on_state_changed(self._state)

    def _update_models(self, **changes: object) -> None:
        self._state = replace(self._state, models=replace(self._state.models, **changes))
        self._on_state_changed(self._state)

    def _update_extra(self, **changes: object) -> None:
        extra = dict(self._state.extra_settings)
        extra.update(changes)
        self._state = replace(self._state, extra_settings=extra)
        self._on_state_changed(self._state)

    def _update_secondary_maps(
        self,
        *,
        models: dict[str, str] | None = None,
        scales: dict[str, float] | None = None,
        activations: dict[str, bool] | None = None,
    ) -> None:
        cur_models = dict(self._state.models.secondary_models)
        cur_scales = dict(self._state.models.secondary_model_scales)
        cur_acts = dict(self._state.models.secondary_model_activations)
        if models:
            cur_models.update(models)
        if scales:
            cur_scales.update(scales)
        if activations:
            cur_acts.update(activations)
        self._update_models(
            secondary_models=cur_models,
            secondary_model_scales=cur_scales,
            secondary_model_activations=cur_acts,
        )

    # ── VR handlers ──────────────────────────────────────────────────────────

    def _on_vr_aggression_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(aggression_setting=int(value))

    def _on_vr_window_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(window_size=int(value))

    def _on_vr_batch_size_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(batch_size=value)

    def _on_vr_crop_size_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._update_advanced(crop_size=value)

    def _on_vr_tta_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._update_advanced(is_tta=checked)

    def _on_vr_post_process_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._update_advanced(is_post_process=checked)

    def _on_vr_high_end_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._update_advanced(is_high_end_process=checked)

    def _on_vr_post_process_threshold_changed(self, value: float) -> None:
        if self._syncing:
            return
        self._update_advanced(post_process_threshold=value)

    # ── MDX handlers ─────────────────────────────────────────────────────────

    def _on_mdx_segment_size_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(mdx_segment_size=int(value))

    def _on_mdx_stems_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_models(mdx_stems=value)

    def _on_mdx_overlap_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(overlap_mdx=value)

    def _on_mdx_batch_size_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(mdx_batch_size=value)

    def _on_mdx_margin_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._update_advanced(margin=value)

    def _on_mdx_compensate_changed(self) -> None:
        if self._syncing:
            return
        value = self.mdx_compensate_field.text().strip() or AUTO_SELECT
        self._update_advanced(compensate=value)

    # ── Demucs handlers ──────────────────────────────────────────────────────

    def _on_demucs_segment_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(segment=value)

    def _on_demucs_stems_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._state = replace(self._state, models=replace(self._state.models, demucs_stems=value))
        self._state = normalize_common_workflow_state(self._state)
        self._on_state_changed(self._state)

    def _on_demucs_overlap_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_advanced(overlap=value)

    def _on_demucs_shifts_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._update_advanced(shifts=value)

    def _on_demucs_margin_changed(self, value: int) -> None:
        if self._syncing:
            return
        self._update_advanced(margin_demucs=value)

    def _on_demucs_pre_proc_enabled_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        extra = dict(self._state.extra_settings)
        extra["is_demucs_pre_proc_model_activate"] = checked
        if not checked:
            extra["is_demucs_pre_proc_model_inst_mix"] = False
        self._state = replace(self._state, extra_settings=extra)
        self._state = normalize_common_workflow_state(self._state)
        self._on_state_changed(self._state)

    def _on_demucs_pre_proc_model_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_models(demucs_pre_proc_model=value)

    def _on_demucs_pre_proc_inst_mix_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._update_extra(is_demucs_pre_proc_model_inst_mix=checked)

    # ── Workflow handlers ────────────────────────────────────────────────────

    def _on_vocal_splitter_enabled_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        extra = dict(self._state.extra_settings)
        extra["is_set_vocal_splitter"] = checked
        if not checked:
            extra["is_save_inst_set_vocal_splitter"] = False
        self._state = replace(self._state, extra_settings=extra)
        self._on_state_changed(self._state)

    def _on_vocal_splitter_model_changed(self, value: str) -> None:
        if self._syncing or not value:
            return
        self._update_models(vocal_splitter_model=value)

    def _on_vocal_splitter_save_inst_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        self._update_extra(is_save_inst_set_vocal_splitter=checked)

    # ── Secondary model handlers ─────────────────────────────────────────────

    def _on_secondary_models_enabled_changed(self, checked: bool) -> None:
        if self._syncing:
            return
        act_key = secondary_activation_key(self._state.processing.process_method)
        if act_key:
            self._update_secondary_maps(activations={act_key: checked})

    def _on_secondary_model_changed(self, slot: str, value: str) -> None:
        if self._syncing or not value:
            return
        mk = secondary_model_key(slot, self._state.processing.process_method)
        if mk:
            self._update_secondary_maps(models={mk: value})

    def _on_secondary_model_scale_changed(self, slot: str, value: float) -> None:
        if self._syncing:
            return
        mk = secondary_model_key(slot, self._state.processing.process_method)
        if mk:
            self._update_secondary_maps(scales={f"{mk}_scale": float(value)})
