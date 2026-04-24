"""Handler mixin for basic widget signal slots in the main window."""

from __future__ import annotations

from dataclasses import replace

from uvr_qt.ui.model_utils import (
    normalize_common_workflow_state,
    selected_model_name_for_method,
    state_with_selected_model,
)


class MainWindowHandlersMixin:
    def _on_process_method_changed(self, process_method: str) -> None:
        if self._is_syncing_processing_controls or not process_method:
            return
        available_models = self._get_processing_facade().available_models_for_method(process_method)
        selected_model = selected_model_name_for_method(self.state, process_method)
        if selected_model not in available_models:
            selected_model = available_models[0] if available_models else ""
        self.state = replace(
            state_with_selected_model(self.state, process_method, selected_model),
            processing=replace(self.state.processing, process_method=process_method),
        )
        self.state = normalize_common_workflow_state(self.state)
        self._persist_state()
        self._refresh_view()

    def _on_model_changed(self, model_name: str) -> None:
        if self._is_syncing_processing_controls or not model_name:
            return
        process_method = self.process_method_combo.currentText()
        self.state = state_with_selected_model(self.state, process_method, model_name)
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
        cur_models = dict(self.state.models.secondary_models)
        cur_scales = dict(self.state.models.secondary_model_scales)
        cur_acts = dict(self.state.models.secondary_model_activations)
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

    def _update_extra_settings(self, **changes: object) -> None:
        updated = dict(self.state.extra_settings)
        updated.update(changes)
        self.state = replace(self.state, extra_settings=updated)
        self._persist_state()
        self._refresh_view()

    def _extra_flag(self, key: str) -> bool:
        return bool(self.state.extra_settings.get(key, False))
