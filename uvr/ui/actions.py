"""UI selection and state-update actions extracted from UVR.py."""

from __future__ import annotations

import json
import os
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class MainWindowActions:
    def __init__(self, ui: Any):
        self.ui = ui

    def update_main_widget_states_mdx(self) -> None:
        if self.ui.mdx_net_model_var.get() != runtime.DOWNLOAD_MORE:
            self.update_main_widget_states()

    def update_main_widget_states(self) -> None:
        def place_widgets(*widgets: Any) -> None:
            for widget in widgets:
                widget()

        def general_shared_buttons() -> None:
            place_widgets(self.ui.is_gpu_conversion_Option_place, self.ui.model_sample_mode_Option_place)

        def stem_save_options() -> None:
            place_widgets(self.ui.is_primary_stem_only_Option_place, self.ui.is_secondary_stem_only_Option_place)

        def stem_save_demucs_options() -> None:
            place_widgets(
                self.ui.is_primary_stem_only_Demucs_Option_place,
                self.ui.is_secondary_stem_only_Demucs_Option_place,
            )

        def no_ensemble_shared() -> None:
            place_widgets(self.ui.save_current_settings_Label_place, self.ui.save_current_settings_Option_place)

        process_method = self.ui.chosen_process_method_var.get()
        audio_tool = self.ui.chosen_audio_tool_var.get()

        for widget in self.ui.GUI_LIST:
            widget.place(x=-1000, y=-1000)

        if process_method == runtime.MDX_ARCH_TYPE:
            place_widgets(
                self.ui.mdx_net_model_Label_place,
                self.ui.mdx_net_model_Option_place,
                general_shared_buttons,
                stem_save_options,
                no_ensemble_shared,
            )
        elif process_method == runtime.VR_ARCH_PM:
            place_widgets(
                self.ui.vr_model_Label_place,
                self.ui.vr_model_Option_place,
                self.ui.aggression_setting_Label_place,
                self.ui.aggression_setting_Option_place,
                self.ui.window_size_Label_place,
                self.ui.window_size_Option_place,
                general_shared_buttons,
                stem_save_options,
                no_ensemble_shared,
            )
        elif process_method == runtime.DEMUCS_ARCH_TYPE:
            place_widgets(
                self.ui.demucs_model_Label_place,
                self.ui.demucs_model_Option_place,
                self.ui.demucs_stems_Label_place,
                self.ui.demucs_stems_Option_place,
                self.ui.segment_Label_place,
                self.ui.segment_Option_place,
                general_shared_buttons,
                stem_save_demucs_options,
                no_ensemble_shared,
            )
        elif process_method == runtime.AUDIO_TOOLS:
            place_widgets(self.ui.chosen_audio_tool_Label_place, self.ui.chosen_audio_tool_Option_place)

            if audio_tool == runtime.ALIGN_INPUTS:
                self.ui.file_one_sub_var.set(runtime.FILE_ONE_MAIN_LABEL)
                self.ui.file_two_sub_var.set(runtime.FILE_TWO_MAIN_LABEL)
            elif audio_tool == runtime.MATCH_INPUTS:
                self.ui.file_one_sub_var.set(runtime.FILE_ONE_MATCH_MAIN_LABEL)
                self.ui.file_two_sub_var.set(runtime.FILE_TWO_MATCH_MAIN_LABEL)

            audio_tool_options = {
                runtime.MANUAL_ENSEMBLE: [
                    self.ui.choose_algorithm_Label_place,
                    self.ui.choose_algorithm_Option_place,
                    self.ui.is_wav_ensemble_Option_place,
                ],
                runtime.TIME_STRETCH: [
                    lambda: self.ui.model_sample_mode_Option_place(rely=5),
                    self.ui.time_stretch_rate_Label_place,
                    self.ui.time_stretch_rate_Option_place,
                ],
                runtime.CHANGE_PITCH: [
                    self.ui.is_time_correction_Option_place,
                    lambda: self.ui.model_sample_mode_Option_place(rely=6),
                    self.ui.pitch_rate_Label_place,
                    self.ui.pitch_rate_Option_place,
                ],
                runtime.ALIGN_INPUTS: [
                    self.ui.fileOne_Label_place,
                    self.ui.fileOne_Entry_place,
                    self.ui.fileTwo_Label_place,
                    self.ui.fileTwo_Entry_place,
                    self.ui.fileOne_Open_place,
                    self.ui.fileTwo_Open_place,
                    self.ui.intro_analysis_Label_place,
                    self.ui.intro_analysis_Option_place,
                    self.ui.db_analysis_Label_place,
                    self.ui.db_analysis_Option_place,
                    self.ui.time_window_Label_place,
                    self.ui.time_window_Option_place,
                ],
                runtime.MATCH_INPUTS: [
                    self.ui.fileOne_Label_place,
                    self.ui.fileOne_Entry_place,
                    self.ui.fileTwo_Label_place,
                    self.ui.fileTwo_Entry_place,
                    self.ui.fileOne_Open_place,
                    self.ui.fileTwo_Open_place,
                    self.ui.wav_type_set_Label_place,
                    self.ui.wav_type_set_Option_place,
                ],
            }
            place_widgets(*audio_tool_options.get(audio_tool, []))
        elif process_method == runtime.ENSEMBLE_MODE:
            place_widgets(
                self.ui.chosen_ensemble_Label_place,
                self.ui.chosen_ensemble_Option_place,
                self.ui.ensemble_main_stem_Label_place,
                self.ui.ensemble_main_stem_Option_place,
                self.ui.ensemble_type_Label_place,
                self.ui.ensemble_type_Option_place,
                self.ui.ensemble_listbox_Label_place,
                self.ui.ensemble_listbox_Option_place,
                self.ui.ensemble_listbox_Option_pack,
                general_shared_buttons,
                stem_save_options,
            )

        if not self.ui.is_gpu_available:
            self.ui.is_gpu_conversion_Disable()

        self.ui.update_inputPaths()

    def update_button_states(self) -> None:
        if self.ui.chosen_process_method_var.get() == runtime.DEMUCS_ARCH_TYPE:
            if self.ui.demucs_stems_var.get() == runtime.ALL_STEMS:
                self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, demucs=True)
            elif self.ui.demucs_stems_var.get() == runtime.VOCAL_STEM:
                self.update_stem_checkbox_labels(runtime.VOCAL_STEM, demucs=True, is_disable_demucs_boxes=False)
                self.ui.is_stem_only_Demucs_Options_Enable()
            else:
                self.ui.is_stem_only_Demucs_Options_Enable()

            if self.ui.demucs_model_var.get() != runtime.CHOOSE_MODEL:
                if runtime.DEMUCS_UVR_MODEL in self.ui.demucs_model_var.get():
                    stems = runtime.DEMUCS_2_STEM_OPTIONS
                elif runtime.DEMUCS_6_STEM_MODEL in self.ui.demucs_model_var.get():
                    stems = runtime.DEMUCS_6_STEM_OPTIONS
                else:
                    stems = runtime.DEMUCS_4_STEM_OPTIONS

                self.ui.demucs_stems_Option["values"] = stems
                self.ui.demucs_stems_Option.command(
                    lambda e: self.update_stem_checkbox_labels(self.ui.demucs_stems_var.get(), demucs=True)
                )

    def update_button_states_mdx(self, model_stems: list[str]) -> None:
        model_stems = [stem for stem in model_stems]

        if len(model_stems) >= 3:
            model_stems.insert(0, runtime.ALL_STEMS)
            self.ui.mdxnet_stems_var.set(runtime.ALL_STEMS)
        else:
            self.ui.mdxnet_stems_var.set(model_stems[0])

        if self.ui.mdxnet_stems_var.get() == runtime.ALL_STEMS:
            self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
        elif self.ui.mdxnet_stems_var.get() == runtime.VOCAL_STEM:
            self.update_stem_checkbox_labels(runtime.VOCAL_STEM)
            self.ui.is_stem_only_Options_Enable()
        else:
            self.ui.is_stem_only_Options_Enable()

        if self.ui.mdx_net_model_var.get() != runtime.CHOOSE_MODEL:
            self.ui.mdxnet_stems_Option["values"] = model_stems
            self.ui.mdxnet_stems_Option.command(
                lambda e: self.update_stem_checkbox_labels(self.ui.mdxnet_stems_var.get())
            )

    def update_stem_checkbox_labels(
        self,
        selection: str,
        demucs: bool = False,
        disable_boxes: bool = False,
        is_disable_demucs_boxes: bool = True,
    ) -> None:
        stem_text = (self.ui.is_primary_stem_only_Text_var, self.ui.is_secondary_stem_only_Text_var)

        if selection == runtime.ALL_STEMS:
            selection = runtime.PRIMARY_STEM
        else:
            self.ui.is_stem_only_Options_Enable()

        if disable_boxes or selection == runtime.PRIMARY_STEM:
            self.ui.is_primary_stem_only_Option.configure(state=runtime.tk.DISABLED)
            self.ui.is_secondary_stem_only_Option.configure(state=runtime.tk.DISABLED)
            self.ui.is_primary_stem_only_var.set(False)
            self.ui.is_secondary_stem_only_var.set(False)
        else:
            self.ui.is_primary_stem_only_Option.configure(state=runtime.tk.NORMAL)
            self.ui.is_secondary_stem_only_Option.configure(state=runtime.tk.NORMAL)

        if demucs:
            stem_text = (self.ui.is_primary_stem_only_Demucs_Text_var, self.ui.is_secondary_stem_only_Demucs_Text_var)

            if is_disable_demucs_boxes:
                self.ui.is_primary_stem_only_Demucs_Option.configure(state=runtime.tk.DISABLED)
                self.ui.is_secondary_stem_only_Demucs_Option.configure(state=runtime.tk.DISABLED)
                self.ui.is_primary_stem_only_Demucs_var.set(False)
                self.ui.is_secondary_stem_only_Demucs_var.set(False)

            if selection != runtime.PRIMARY_STEM:
                self.ui.is_primary_stem_only_Demucs_Option.configure(state=runtime.tk.NORMAL)
                self.ui.is_secondary_stem_only_Demucs_Option.configure(state=runtime.tk.NORMAL)

        stem_text[0].set(f"{selection} Only")
        stem_text[1].set(f"{runtime.secondary_stem(selection)} Only")

    def update_ensemble_algorithm_menu(self, is_4_stem: bool = False) -> None:
        options = runtime.ENSEMBLE_TYPE_4_STEM if is_4_stem else runtime.ENSEMBLE_TYPE
        if "/" not in self.ui.ensemble_type_var.get() or is_4_stem:
            self.ui.ensemble_type_var.set(options[0])
        self.ui.ensemble_type_Option["values"] = options

    def selection_action(self, event: Any, option_var: Any, is_mdx_net: bool = False) -> None:
        selected_value = event.widget.get()
        selected_value = runtime.CHOOSE_MODEL if selected_value == runtime.OPT_SEPARATOR else selected_value
        option_var.set(selected_value)
        if is_mdx_net:
            self.update_main_widget_states_mdx()
        self.selection_action_models(selected_value)

    def selection_action_models(self, selection: str) -> Any:
        if selection in runtime.CHOOSE_MODEL:
            self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
        else:
            self.ui.is_stem_only_Options_Enable()

        self._handle_model_by_chosen_method(selection)

        if self.ui.chosen_process_method_var.get() == runtime.ENSEMBLE_MODE:
            return self._handle_ensemble_mode_selection(selection)

        if not self.ui.is_menu_settings_open and selection == runtime.DOWNLOAD_MORE:
            self.ui.update_checkbox_text()
            self.ui.menu_settings(select_tab_3=True)

        return None

    def _handle_model_by_chosen_method(self, selection: str) -> None:
        current_method = self.ui.chosen_process_method_var.get()
        model_var = self.ui.method_mapper.get(current_method)
        if model_var:
            self.selection_action_models_sub(selection, current_method, model_var)

    def _handle_ensemble_mode_selection(self, selection: str) -> Any:
        model_data = self.ui.assemble_model_data(selection, runtime.ENSEMBLE_CHECK)[0]
        if not model_data.model_status:
            return self.ui.model_stems_list.index(selection)
        return False

    def selection_action_models_sub(self, selection: str, ai_type: str, var: Any) -> None:
        if selection == runtime.DOWNLOAD_MORE:
            is_model_status = False
        else:
            model_data = self.ui.assemble_model_data(selection, ai_type)[0]
            is_model_status = model_data.model_status

        if not is_model_status:
            var.set(runtime.CHOOSE_MODEL)
            if ai_type == runtime.MDX_ARCH_TYPE:
                self.ui.mdx_segment_size_Label_place()
                self.ui.mdx_segment_size_Option_place()
                self.ui.overlap_mdx_Label_place()
                self.ui.overlap_mdx_Option_place()
                self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
        else:
            if ai_type == runtime.DEMUCS_ARCH_TYPE:
                if self.ui.demucs_stems_var.get().lower() not in model_data.demucs_source_list:
                    self.ui.demucs_stems_var.set(
                        runtime.ALL_STEMS if model_data.demucs_stem_count == 4 else runtime.VOCAL_STEM
                    )
                self.update_button_states()
            else:
                if model_data.is_mdx_c and len(model_data.mdx_model_stems) >= 1:
                    if len(model_data.mdx_model_stems) >= 3:
                        self.ui.mdxnet_stems_Label_place()
                        self.ui.mdxnet_stems_Option_place()
                    else:
                        self.ui.mdx_segment_size_Label_place()
                        self.ui.mdx_segment_size_Option_place()
                    self.ui.overlap_mdx_Label_place()
                    self.ui.overlap_mdx23_Option_place()
                    self.update_button_states_mdx(model_data.mdx_model_stems)
                else:
                    if ai_type == runtime.MDX_ARCH_TYPE:
                        self.ui.mdx_segment_size_Label_place()
                        self.ui.mdx_segment_size_Option_place()
                        self.ui.overlap_mdx_Label_place()
                        self.ui.overlap_mdx_Option_place()

                    stem = model_data.primary_stem
                    self.update_stem_checkbox_labels(stem)

    def selection_action_process_method(self, selection: str, from_widget: bool = False, is_from_conv_menu: bool = False) -> None:
        if is_from_conv_menu:
            self.update_main_widget_states()

        if from_widget:
            self.ui.save_current_settings_var.set(runtime.CHOOSE_ENSEMBLE_OPTION)

        if selection == runtime.ENSEMBLE_MODE:
            ensemble_choice = self.ui.ensemble_main_stem_var.get()
            if ensemble_choice in [runtime.CHOOSE_STEM_PAIR, runtime.FOUR_STEM_ENSEMBLE, runtime.MULTI_STEM_ENSEMBLE]:
                self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
            else:
                self.update_stem_checkbox_labels(self.ui.return_ensemble_stems(is_primary=True))
                self.ui.is_stem_only_Options_Enable()
            return

        for method_type, model_var in self.ui.method_mapper.items():
            if method_type in selection:
                self.selection_action_models(model_var.get())
                break

    def selection_action_chosen_ensemble(self, selection: str) -> None:
        if selection not in runtime.ENSEMBLE_OPTIONS:
            self.selection_action_chosen_ensemble_load_saved(selection)
        elif selection == runtime.SAVE_ENSEMBLE:
            self.ui.chosen_ensemble_var.set(runtime.CHOOSE_ENSEMBLE_OPTION)
            self.ui.pop_up_save_ensemble()
        elif selection == runtime.OPT_SEPARATOR_SAVE:
            self.ui.chosen_ensemble_var.set(runtime.CHOOSE_ENSEMBLE_OPTION)
        elif selection == runtime.CLEAR_ENSEMBLE:
            self.ui.ensemble_listbox_Option.selection_clear(0, "end")
            self.ui.chosen_ensemble_var.set(runtime.CHOOSE_ENSEMBLE_OPTION)

    def selection_action_chosen_ensemble_load_saved(self, saved_ensemble: str) -> None:
        saved_data = None
        saved_ensemble = saved_ensemble.replace(" ", "_")
        saved_ensemble_path = os.path.join(runtime.ENSEMBLE_CACHE_DIR, f"{saved_ensemble}.json")

        if os.path.isfile(saved_ensemble_path):
            saved_data = json.load(open(saved_ensemble_path))

        if saved_data:
            self.selection_action_ensemble_stems(saved_data["ensemble_main_stem"], from_menu=False)
            self.ui.ensemble_main_stem_var.set(saved_data["ensemble_main_stem"])
            self.ui.ensemble_type_var.set(saved_data["ensemble_type"])
            self.ui.saved_model_list = saved_data["selected_models"]

            for saved_model in self.ui.saved_model_list:
                status = self.ui.assemble_model_data(saved_model, runtime.ENSEMBLE_CHECK)[0].model_status
                if not status:
                    self.ui.saved_model_list.remove(saved_model)

            indexes = self.ui.ensemble_listbox_get_indexes_for_files(self.ui.model_stems_list, self.ui.saved_model_list)
            for index in indexes:
                self.ui.ensemble_listbox_Option.selection_set(index)

        self.ui.update_checkbox_text()

    def selection_action_ensemble_stems(self, selection: str, from_menu: bool = True, auto_update: Any = None) -> None:
        is_multi_stem = False

        if selection != runtime.CHOOSE_STEM_PAIR:
            if selection in [runtime.FOUR_STEM_ENSEMBLE, runtime.MULTI_STEM_ENSEMBLE]:
                self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
                self.update_ensemble_algorithm_menu(is_4_stem=True)
                self.ui.ensemble_primary_stem = runtime.PRIMARY_STEM
                self.ui.ensemble_secondary_stem = runtime.SECONDARY_STEM
                is_4_stem_check = True
                if selection == runtime.MULTI_STEM_ENSEMBLE:
                    is_multi_stem = True
            else:
                self.update_ensemble_algorithm_menu()
                self.ui.is_stem_only_Options_Enable()
                stems = selection.partition("/")
                self.update_stem_checkbox_labels(stems[0])
                self.ui.ensemble_primary_stem = stems[0]
                self.ui.ensemble_secondary_stem = stems[2]
                is_4_stem_check = False

            self.ui.model_stems_list = self.ui.model_list(
                self.ui.ensemble_primary_stem,
                self.ui.ensemble_secondary_stem,
                is_4_stem_check=is_4_stem_check,
                is_multi_stem=is_multi_stem,
            )
            self.ui.ensemble_listbox_Option.configure(state=runtime.tk.NORMAL)
            self.ui.ensemble_listbox_clear_and_insert_new(self.ui.model_stems_list)

            if auto_update:
                indexes = self.ui.ensemble_listbox_get_indexes_for_files(self.ui.model_stems_list, auto_update)
                self.ui.ensemble_listbox_select_from_indexs(indexes)
        else:
            self.ui.ensemble_listbox_Option.configure(state=runtime.tk.DISABLED)
            self.update_stem_checkbox_labels(runtime.PRIMARY_STEM, disable_boxes=True)
            self.ui.model_stems_list = ()

        if from_menu:
            self.ui.chosen_ensemble_var.set(runtime.CHOOSE_ENSEMBLE_OPTION)

    def selection_action_saved_settings(self, selection: str, process_method: str | None = None) -> None:
        if self.ui.thread_check(self.ui.active_processing_thread):
            self.ui.error_dialoge(runtime.SET_TO_ANY_PROCESS_ERROR)
            return

        chosen_process_method = process_method or self.ui.chosen_process_method_var.get()
        if selection in runtime.SAVE_SET_OPTIONS:
            self.handle_special_options(selection, chosen_process_method)
        else:
            self.handle_saved_settings(selection, chosen_process_method)

        self.ui.update_checkbox_text()

    def handle_special_options(self, selection: str, process_method: str) -> None:
        if selection == runtime.SAVE_SETTINGS:
            self.ui.save_current_settings_var.set(runtime.SELECT_SAVED_SET)
            self.ui.pop_up_save_current_settings()
        elif selection == runtime.RESET_TO_DEFAULT:
            self.ui.save_current_settings_var.set(runtime.SELECT_SAVED_SET)
            self.ui.load_saved_settings(runtime.DEFAULT_DATA, process_method)
        elif selection == runtime.OPT_SEPARATOR_SAVE:
            self.ui.save_current_settings_var.set(runtime.SELECT_SAVED_SET)

    def handle_saved_settings(self, selection: str, process_method: str) -> None:
        selection = selection.replace(" ", "_")
        saved_ensemble_path = os.path.join(runtime.SETTINGS_CACHE_DIR, f"{selection}.json")

        if os.path.isfile(saved_ensemble_path):
            with open(saved_ensemble_path, "r") as file:
                saved_data = json.load(file)

            if saved_data:
                self.ui.load_saved_settings(saved_data, process_method)
