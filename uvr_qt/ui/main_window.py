"""Main window for the initial PySide6 UVR shell."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFileDialog, QInputDialog, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from gui_data.constants import AUTO_SELECT, ALL_STEMS, DEFAULT_DATA, DEF_OPT, INST_STEM, MP3, NO_MODEL, STEM_SET_MENU, VOCAL_STEM
from uvr.config.models import AppSettings
from uvr.config.persistence import save_settings
from uvr.config.profiles import SettingsProfileStore
from uvr_qt.services import ProcessResult, ProcessingFacade
from uvr_qt.state import AppState
from uvr_qt.ui.download_manager_window import DownloadManagerWindow
from uvr_qt.ui.main_window_builders import (
    SECONDARY_MODEL_SLOTS,
    build_header,
    build_paths_group,
    build_process_group,
    build_summary_group,
)
from uvr_qt.ui.main_window_support import MainWindowDialogMixin, MainWindowProfileMixin, ProcessingWorker


class MainWindow(MainWindowDialogMixin, MainWindowProfileMixin, QMainWindow):
    """Basic Qt shell with input/output path selection."""

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
        self.processing_thread: QThread | None = None
        self.processing_worker: ProcessingWorker | None = None
        self._is_syncing_processing_controls = False
        self.secondary_model_combos: dict[str, QComboBox] = {}
        self.secondary_scale_spinboxes: dict[str, QDoubleSpinBox] = {}
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
        root_layout.addWidget(self._build_profiles_group())
        root_layout.addWidget(build_summary_group(self))
        root_layout.addStretch(1)

        self.setCentralWidget(central_widget)
        self._refresh_view()

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
        self.last_error_action.setEnabled(bool(self.state.runtime.last_error))
        self._refresh_profile_controls()
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
        self._show_error_dialog("Processing Failed", message)

    def _cleanup_processing_thread(self) -> None:
        if self.processing_worker is not None:
            self.processing_worker.deleteLater()
        if self.processing_thread is not None:
            self.processing_thread.deleteLater()
        self.processing_worker = None
        self.processing_thread = None
