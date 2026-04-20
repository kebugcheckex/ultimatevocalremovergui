"""Advanced option menus extracted from UVR.py."""

from __future__ import annotations

from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class AdvancedMenus:
    def __init__(self, ui: Any):
        self.ui = ui

    def menu_advanced_vr_options(self) -> None:
        """Open advanced VR options."""

        vr_opt = runtime.tk.Toplevel()
        tab1 = self.ui.menu_tab_control(vr_opt, self.ui.vr_secondary_model_vars)

        self.ui.is_open_menu_advanced_vr_options.set(True)
        self.ui.menu_advanced_vr_options_close_window = lambda: (
            self.ui.is_open_menu_advanced_vr_options.set(False),
            vr_opt.destroy(),
        )
        vr_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_advanced_vr_options_close_window)

        toggle_post_process = lambda: self.ui.post_process_threshold_Option.configure(state=runtime.READ_ONLY) if self.ui.is_post_process_var.get() else self.ui.post_process_threshold_Option.configure(state=runtime.tk.DISABLED)

        vr_opt_frame = self.ui.menu_FRAME_SET(tab1)
        vr_opt_frame.grid(pady=0 if self.ui.chosen_process_method_var.get() != runtime.VR_ARCH_PM else 70)

        self.ui.menu_title_LABEL_SET(vr_opt_frame, runtime.ADVANCED_VR_OPTIONS_TEXT).grid(
            padx=25, pady=runtime.MENU_PADDING_2
        )

        if self.ui.chosen_process_method_var.get() != runtime.VR_ARCH_PM:
            window_size_Label = self.ui.menu_sub_LABEL_SET(vr_opt_frame, runtime.WINDOW_SIZE_TEXT)
            window_size_Label.grid(pady=runtime.MENU_PADDING_1)
            runtime.ComboBoxEditableMenu(
                vr_opt_frame,
                values=runtime.VR_WINDOW,
                width=runtime.MENU_COMBOBOX_WIDTH,
                textvariable=self.ui.window_size_var,
                pattern=runtime.REG_WINDOW,
                default=runtime.VR_WINDOW[1],
            ).grid(pady=runtime.MENU_PADDING_1)
            self.ui.help_hints(window_size_Label, text=runtime.WINDOW_SIZE_HELP)

            aggression_setting_Label = self.ui.menu_sub_LABEL_SET(vr_opt_frame, runtime.AGGRESSION_SETTING_TEXT)
            aggression_setting_Label.grid(pady=runtime.MENU_PADDING_1)
            runtime.ComboBoxEditableMenu(
                vr_opt_frame,
                values=runtime.VR_AGGRESSION,
                width=runtime.MENU_COMBOBOX_WIDTH,
                textvariable=self.ui.aggression_setting_var,
                pattern=runtime.REG_AGGRESSION,
                default=runtime.VR_AGGRESSION[5],
            ).grid(pady=runtime.MENU_PADDING_1)
            self.ui.help_hints(aggression_setting_Label, text=runtime.AGGRESSION_SETTING_HELP)

        self.ui.batch_size_Label = self.ui.menu_sub_LABEL_SET(vr_opt_frame, runtime.BATCH_SIZE_TEXT)
        self.ui.batch_size_Label.grid(pady=runtime.MENU_PADDING_1)
        self.ui.batch_size_Option = runtime.ComboBoxEditableMenu(
            vr_opt_frame,
            values=runtime.BATCH_SIZE,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.batch_size_var,
            pattern=runtime.REG_BATCHES,
            default=runtime.BATCH_SIZE,
        )
        self.ui.batch_size_Option.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(self.ui.batch_size_Label, text=runtime.BATCH_SIZE_HELP)

        self.ui.post_process_threshold_Label = self.ui.menu_sub_LABEL_SET(
            vr_opt_frame,
            runtime.POST_PROCESS_THRESHOLD_TEXT,
        )
        self.ui.post_process_threshold_Label.grid(pady=runtime.MENU_PADDING_1)
        self.ui.post_process_threshold_Option = runtime.ComboBoxEditableMenu(
            vr_opt_frame,
            values=runtime.POST_PROCESSES_THREASHOLD_VALUES,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.post_process_threshold_var,
            pattern=runtime.REG_THES_POSTPORCESS,
            default=runtime.POST_PROCESSES_THREASHOLD_VALUES[1],
        )
        self.ui.post_process_threshold_Option.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(self.ui.post_process_threshold_Label, text=runtime.POST_PROCESS_THREASHOLD_HELP)

        self.ui.is_tta_Option = runtime.ttk.Checkbutton(
            vr_opt_frame,
            text=runtime.ENABLE_TTA_TEXT,
            width=runtime.VR_CHECKBOXS_WIDTH,
            variable=self.ui.is_tta_var,
        )
        self.ui.is_tta_Option.grid(pady=0)
        self.ui.help_hints(self.ui.is_tta_Option, text=runtime.IS_TTA_HELP)

        self.ui.is_post_process_Option = runtime.ttk.Checkbutton(
            vr_opt_frame,
            text=runtime.POST_PROCESS_TEXT,
            width=runtime.VR_CHECKBOXS_WIDTH,
            variable=self.ui.is_post_process_var,
            command=toggle_post_process,
        )
        self.ui.is_post_process_Option.grid(pady=0)
        self.ui.help_hints(self.ui.is_post_process_Option, text=runtime.IS_POST_PROCESS_HELP)

        self.ui.is_high_end_process_Option = runtime.ttk.Checkbutton(
            vr_opt_frame,
            text=runtime.HIGHEND_PROCESS_TEXT,
            width=runtime.VR_CHECKBOXS_WIDTH,
            variable=self.ui.is_high_end_process_var,
        )
        self.ui.is_high_end_process_Option.grid(pady=0)
        self.ui.help_hints(self.ui.is_high_end_process_Option, text=runtime.IS_HIGH_END_PROCESS_HELP)

        self.ui.vocal_splitter_Button_opt(vr_opt, vr_opt_frame, pady=runtime.MENU_PADDING_1, width=runtime.VR_BUT_WIDTH)

        self.ui.vr_clear_cache_Button = runtime.ttk.Button(
            vr_opt_frame,
            text=runtime.CLEAR_AUTOSET_CACHE_TEXT,
            command=lambda: self.ui.clear_cache(runtime.VR_ARCH_TYPE),
            width=runtime.VR_BUT_WIDTH,
        )
        self.ui.vr_clear_cache_Button.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(self.ui.vr_clear_cache_Button, text=runtime.CLEAR_CACHE_HELP)

        self.ui.open_vr_model_dir_Button = runtime.ttk.Button(
            vr_opt_frame,
            text=runtime.OPEN_MODELS_FOLDER_TEXT,
            command=lambda: runtime.OPEN_FILE_func(runtime.VR_MODELS_DIR),
            width=runtime.VR_BUT_WIDTH,
        )
        self.ui.open_vr_model_dir_Button.grid(pady=runtime.MENU_PADDING_1)

        self.ui.vr_return_Button = runtime.ttk.Button(
            vr_opt_frame,
            text=runtime.BACK_TO_MAIN_MENU,
            command=lambda: (self.ui.menu_advanced_vr_options_close_window(), self.ui.check_is_menu_settings_open()),
        )
        self.ui.vr_return_Button.grid(pady=runtime.MENU_PADDING_1)

        self.ui.vr_close_Button = runtime.ttk.Button(
            vr_opt_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_vr_options_close_window(),
        )
        self.ui.vr_close_Button.grid(pady=runtime.MENU_PADDING_1)

        toggle_post_process()

        self.ui.menu_placement(
            vr_opt,
            runtime.ADVANCED_VR_OPTIONS_TEXT,
            is_help_hints=True,
            close_function=self.ui.menu_advanced_vr_options_close_window,
            frame_list=[vr_opt_frame],
        )

    def menu_advanced_ensemble_options(self) -> None:
        """Open advanced ensemble options."""

        custom_ens_opt = runtime.tk.Toplevel()

        self.ui.is_open_menu_advanced_ensemble_options.set(True)
        self.ui.menu_advanced_ensemble_options_close_window = lambda: (
            self.ui.is_open_menu_advanced_ensemble_options.set(False),
            custom_ens_opt.destroy(),
        )
        custom_ens_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_advanced_ensemble_options_close_window)

        option_var = runtime.tk.StringVar(value=runtime.SELECT_SAVED_ENSEMBLE)

        custom_ens_opt_frame = self.ui.menu_FRAME_SET(custom_ens_opt)
        custom_ens_opt_frame.grid(row=0)

        self.ui.menu_title_LABEL_SET(custom_ens_opt_frame, runtime.ADVANCED_OPTION_MENU_TEXT).grid(
            pady=runtime.MENU_PADDING_2
        )

        self.ui.menu_sub_LABEL_SET(custom_ens_opt_frame, runtime.REMOVE_SAVED_ENSEMBLE_TEXT).grid(
            pady=runtime.MENU_PADDING_1
        )
        delete_entry_Option = runtime.ComboBoxMenu(
            custom_ens_opt_frame,
            textvariable=option_var,
            width=runtime.ENSEMBLE_CHECKBOXS_WIDTH + 2,
        )
        delete_entry_Option.grid(padx=20, pady=runtime.MENU_PADDING_1)

        is_save_all_outputs_ensemble_Option = runtime.ttk.Checkbutton(
            custom_ens_opt_frame,
            text=runtime.SAVE_ALL_OUTPUTS_TEXT,
            width=runtime.ENSEMBLE_CHECKBOXS_WIDTH,
            variable=self.ui.is_save_all_outputs_ensemble_var,
        )
        is_save_all_outputs_ensemble_Option.grid(pady=0)
        self.ui.help_hints(is_save_all_outputs_ensemble_Option, text=runtime.IS_SAVE_ALL_OUTPUTS_ENSEMBLE_HELP)

        is_append_ensemble_name_Option = runtime.ttk.Checkbutton(
            custom_ens_opt_frame,
            text=runtime.APPEND_ENSEMBLE_NAME_TEXT,
            width=runtime.ENSEMBLE_CHECKBOXS_WIDTH,
            variable=self.ui.is_append_ensemble_name_var,
        )
        is_append_ensemble_name_Option.grid(pady=0)
        self.ui.help_hints(is_append_ensemble_name_Option, text=runtime.IS_APPEND_ENSEMBLE_NAME_HELP)

        is_wav_ensemble_Option = runtime.ttk.Checkbutton(
            custom_ens_opt_frame,
            text=runtime.ENSEMBLE_WAVFORMS_TEXT,
            width=runtime.ENSEMBLE_CHECKBOXS_WIDTH,
            variable=self.ui.is_wav_ensemble_var,
        )
        is_wav_ensemble_Option.grid(pady=0)
        self.ui.help_hints(is_wav_ensemble_Option, text=runtime.IS_WAV_ENSEMBLE_HELP)

        runtime.ttk.Button(
            custom_ens_opt_frame,
            text=runtime.BACK_TO_MAIN_MENU,
            command=lambda: (
                self.ui.menu_advanced_ensemble_options_close_window(),
                self.ui.check_is_menu_settings_open(),
            ),
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            custom_ens_opt_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_ensemble_options_close_window(),
        ).grid(pady=runtime.MENU_PADDING_1)

        self.ui.deletion_list_fill(
            delete_entry_Option,
            option_var,
            runtime.ENSEMBLE_CACHE_DIR,
            runtime.SELECT_SAVED_ENSEMBLE,
            menu_name="deleteensemble",
        )

        self.ui.menu_placement(
            custom_ens_opt,
            runtime.ADVANCED_ENSEMBLE_OPTIONS_TEXT,
            is_help_hints=True,
            close_function=self.ui.menu_advanced_ensemble_options_close_window,
        )

    def menu_advanced_align_options(self) -> None:
        """Open advanced alignment tool options."""

        advanced_align_opt = runtime.tk.Toplevel()

        self.ui.is_open_menu_advanced_align_options.set(True)
        self.ui.menu_advanced_align_options_close_window = lambda: (
            self.ui.is_open_menu_advanced_align_options.set(False),
            advanced_align_opt.destroy(),
        )
        advanced_align_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_advanced_align_options_close_window)

        advanced_align_opt_frame = self.ui.menu_FRAME_SET(advanced_align_opt)
        advanced_align_opt_frame.grid(row=0)

        self.ui.menu_title_LABEL_SET(advanced_align_opt_frame, runtime.ADVANCED_ALIGN_TOOL_OPTIONS_TEXT).grid(
            pady=runtime.MENU_PADDING_2
        )

        phase_option_Label = self.ui.menu_sub_LABEL_SET(advanced_align_opt_frame, runtime.SECONDARY_PHASE_TEXT)
        phase_option_Label.grid(pady=4)
        runtime.ComboBoxMenu(
            advanced_align_opt_frame,
            textvariable=self.ui.phase_option_var,
            values=runtime.ALIGN_PHASE_OPTIONS,
            width=runtime.MENU_COMBOBOX_WIDTH,
        ).grid(pady=4)
        self.ui.help_hints(phase_option_Label, text=runtime.IS_PHASE_HELP)

        phase_shifts_Label = self.ui.menu_sub_LABEL_SET(advanced_align_opt_frame, runtime.PHASE_SHIFTS_TEXT)
        phase_shifts_Label.grid(pady=4)
        runtime.ComboBoxMenu(
            advanced_align_opt_frame,
            textvariable=self.ui.phase_shifts_var,
            values=list(runtime.PHASE_SHIFTS_OPT.keys()),
            width=runtime.MENU_COMBOBOX_WIDTH,
        ).grid(pady=4)
        self.ui.help_hints(phase_shifts_Label, text=runtime.PHASE_SHIFTS_ALIGN_HELP)

        is_save_align_Option = runtime.ttk.Checkbutton(
            advanced_align_opt_frame,
            text=runtime.SAVE_ALIGNED_TRACK_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_save_align_var,
        )
        is_save_align_Option.grid(pady=0)
        self.ui.help_hints(is_save_align_Option, text=runtime.IS_ALIGN_TRACK_HELP)

        is_match_silence_Option = runtime.ttk.Checkbutton(
            advanced_align_opt_frame,
            text=runtime.SILENCE_MATCHING_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_match_silence_var,
        )
        is_match_silence_Option.grid(pady=0)
        self.ui.help_hints(is_match_silence_Option, text=runtime.IS_MATCH_SILENCE_HELP)

        is_spec_match_Option = runtime.ttk.Checkbutton(
            advanced_align_opt_frame,
            text=runtime.SPECTRAL_MATCHING_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_spec_match_var,
        )
        is_spec_match_Option.grid(pady=0)
        self.ui.help_hints(is_spec_match_Option, text=runtime.IS_MATCH_SPEC_HELP)

        runtime.ttk.Button(
            advanced_align_opt_frame,
            text=runtime.BACK_TO_MAIN_MENU,
            command=lambda: (
                self.ui.menu_advanced_align_options_close_window(),
                self.ui.check_is_menu_settings_open(),
            ),
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            advanced_align_opt_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_align_options_close_window(),
        ).grid(pady=runtime.MENU_PADDING_1)

        self.ui.menu_placement(
            advanced_align_opt,
            runtime.ADVANCED_ALIGN_TOOL_OPTIONS_TEXT,
            is_help_hints=True,
            close_function=self.ui.menu_advanced_align_options_close_window,
        )
