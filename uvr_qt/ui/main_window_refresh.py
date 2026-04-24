"""Refresh mixin for the Qt main window."""

from __future__ import annotations

from gui_data.constants import ALL_STEMS, DEF_OPT, MP3, STEM_SET_MENU, WAV
from uvr_qt.ui.model_utils import (
    available_aux_models,
    available_stem_targets,
    coerce_model_stem_selection,
    normalize_common_workflow_state,
    selected_model_name,
    workflow_validation_issue,
)


class MainWindowRefreshMixin:
    def _refresh_view(self) -> None:
        input_paths = self.state.paths.input_paths
        self.input_paths_field.setPlainText("\n".join(input_paths))
        self.output_path_field.setText(self.state.paths.export_path)
        self.last_error_action.setEnabled(bool(self.state.runtime.last_error))
        self._refresh_processing_controls()
        self._refresh_output_controls()
        self._refresh_tuning_controls()
        self._refresh_advanced_dialog()
        self._refresh_profile_dialog()

        resolved_model = self._get_processing_facade().resolve_model(self.state)
        if resolved_model is None:
            self.model_label.setText("Backend target: unavailable for the selected process method")
        else:
            self.model_label.setText(
                f"Backend target: {resolved_model.process_method} / {resolved_model.model_name}"
            )

        adv_open = self._advanced_dialog is not None and self._advanced_dialog.isVisible()
        validation_issue = workflow_validation_issue(self.state)
        input_count = len(input_paths)
        input_hint = "No files selected" if input_count == 0 else f"{input_count} file(s) selected"
        output_hint = self.state.paths.export_path or "No output folder selected"
        summary_lines = [
            f"Process method: {self.state.processing.process_method}",
            f"Selected model: {selected_model_name(self.state) or 'None'}",
            f"Save format: {self.state.output.save_format}",
            f"Wav type: {self.state.output.wav_type}",
            f"MP3 bitrate: {self.state.output.mp3_bitrate}",
            f"GPU preferred: {'Yes' if self.state.processing.use_gpu else 'No'}",
            f"Advanced settings: {'Open' if adv_open else 'Closed'}",
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

    def _refresh_processing_controls(self) -> None:
        facade = self._get_processing_facade()
        available_methods = facade.available_process_methods()
        selected_method = self.state.processing.process_method

        if selected_method not in available_methods and available_methods:
            from dataclasses import replace
            selected_method = available_methods[0]
            self.state = replace(
                self.state,
                processing=replace(self.state.processing, process_method=selected_method),
            )

        available_models = facade.available_models_for_method(selected_method) if selected_method else ()
        self.model_count_label.setText(
            f"{len(available_models)} model(s) available for {selected_method or 'this method'}"
        )
        from uvr_qt.ui.model_utils import selected_model_name_for_method, state_with_selected_model
        selected_model = selected_model_name_for_method(self.state, selected_method)
        if selected_model not in available_models and available_models:
            selected_model = available_models[0]
            self.state = state_with_selected_model(self.state, selected_method, selected_model)
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

    def _refresh_advanced_dialog(self) -> None:
        facade = self._get_processing_facade()
        mdx_stems = available_stem_targets(facade, self.state, "MDX-Net", fallback=(ALL_STEMS, *STEM_SET_MENU))
        demucs_stems = available_stem_targets(facade, self.state, "Demucs", fallback=(ALL_STEMS, *STEM_SET_MENU))

        new_state = coerce_model_stem_selection(self.state, "MDX-Net", mdx_stems)
        if new_state is not self.state:
            self.state = normalize_common_workflow_state(new_state)
            self._persist_state()
        new_state = coerce_model_stem_selection(self.state, "Demucs", demucs_stems)
        if new_state is not self.state:
            self.state = normalize_common_workflow_state(new_state)
            self._persist_state()

        if self._advanced_dialog is not None and self._advanced_dialog.isVisible():
            aux_models = available_aux_models(facade)
            self._advanced_dialog.update_from_state(
                self.state,
                aux_models=aux_models,
                mdx_stems=mdx_stems,
                demucs_stems=demucs_stems,
            )

    def _refresh_profile_dialog(self) -> None:
        if self._profiles_dialog is not None and self._profiles_dialog.isVisible():
            self._profiles_dialog.update_from_state(self.state)
