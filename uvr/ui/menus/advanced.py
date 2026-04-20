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

    def menu_help(self) -> None:
        """Open help guide."""

        help_guide_opt = runtime.tk.Toplevel()

        self.ui.is_open_menu_help.set(True)
        self.ui.menu_help_close_window = lambda: (self.ui.is_open_menu_help.set(False), help_guide_opt.destroy())
        help_guide_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_help_close_window)

        tabControl = runtime.ttk.Notebook(help_guide_opt)

        tab1 = runtime.ttk.Frame(tabControl)
        tab2 = runtime.ttk.Frame(tabControl)
        tab3 = runtime.ttk.Frame(tabControl)
        tab4 = runtime.ttk.Frame(tabControl)

        tabControl.add(tab1, text="Credits")
        tabControl.add(tab2, text="Resources")
        tabControl.add(tab3, text="Application License & Version Information")
        tabControl.add(tab4, text="Additional Information")

        tabControl.pack(expand=1, fill="both")

        tab1.grid_rowconfigure(0, weight=1)
        tab1.grid_columnconfigure(0, weight=1)
        tab2.grid_rowconfigure(0, weight=1)
        tab2.grid_columnconfigure(0, weight=1)
        tab3.grid_rowconfigure(0, weight=1)
        tab3.grid_columnconfigure(0, weight=1)
        tab4.grid_rowconfigure(0, weight=1)
        tab4.grid_columnconfigure(0, weight=1)

        section_title_Label = lambda place, frame, text, font_size=runtime.FONT_SIZE_4: runtime.tk.Label(
            master=frame,
            text=text,
            font=(runtime.MAIN_FONT_NAME, f"{font_size}", "bold"),
            justify="center",
            fg="#F4F4F4",
        ).grid(row=place, column=0, padx=0, pady=runtime.MENU_PADDING_4)
        description_Label = lambda place, frame, text, font=runtime.FONT_SIZE_2: runtime.tk.Label(
            master=frame,
            text=text,
            font=(runtime.MAIN_FONT_NAME, f"{font}"),
            justify="center",
            fg="#F6F6F7",
        ).grid(row=place, column=0, padx=0, pady=runtime.MENU_PADDING_4)

        def credit_label(
            place: int,
            frame: Any,
            text: str,
            link: str | None = None,
            message: str | None = None,
            is_link: bool = False,
            is_top: bool = False,
        ) -> None:
            if is_top:
                thank = runtime.tk.Label(
                    master=frame,
                    text=text,
                    font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_3}", "bold"),
                    justify="center",
                    fg="#13849f",
                )
            else:
                thank = runtime.tk.Label(
                    master=frame,
                    text=text,
                    font=(
                        runtime.MAIN_FONT_NAME,
                        f"{runtime.FONT_SIZE_3}",
                        "underline" if is_link else "normal",
                    ),
                    justify="center",
                    fg="#13849f",
                )
            thank.configure(cursor="hand2") if is_link else None
            thank.grid(row=place, column=0, padx=0, pady=1)
            if link:
                thank.bind("<Button-1>", lambda e: runtime.webbrowser.open_new_tab(link))
            if message:
                description_Label(place + 1, frame, message)

        def Link(place: int, frame: Any, text: str, link: str, description: str, font: int = runtime.FONT_SIZE_2) -> None:
            link_label = runtime.tk.Label(
                master=frame,
                text=text,
                font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_4}", "underline"),
                foreground=runtime.FG_COLOR,
                justify="center",
                cursor="hand2",
            )
            link_label.grid(row=place, column=0, padx=0, pady=runtime.MENU_PADDING_1)
            link_label.bind("<Button-1>", lambda e: runtime.webbrowser.open_new_tab(link))
            description_Label(place + 1, frame, description, font=font)

        def right_click_menu(event: Any) -> None:
            right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
            right_click_menu.add_command(
                label="Return to Settings Menu",
                command=lambda: (self.ui.menu_help_close_window(), self.ui.check_is_menu_settings_open()),
            )
            right_click_menu.add_command(label="Exit Window", command=lambda: self.ui.menu_help_close_window())

            try:
                right_click_menu.tk_popup(event.x_root, event.y_root)
                runtime.right_click_release_linux(right_click_menu, help_guide_opt)
            finally:
                right_click_menu.grab_release()

        help_guide_opt.bind(runtime.right_click_button, lambda e: right_click_menu(e))
        credits_Frame = runtime.tk.Frame(tab1, highlightthicknes=50)
        credits_Frame.grid(row=0, column=0, padx=0, pady=0)
        runtime.tk.Label(credits_Frame, image=self.ui.credits_img).grid(row=1, column=0, padx=0, pady=runtime.MENU_PADDING_1)

        section_title_Label(place=0, frame=credits_Frame, text="Core UVR Developers")
        credit_label(place=2, frame=credits_Frame, text="Anjok07\nAufr33", is_top=True)
        section_title_Label(place=3, frame=credits_Frame, text="Special Thanks")
        credit_label(
            place=6,
            frame=credits_Frame,
            text="Tsurumeso",
            message="Developed the original VR Architecture AI code.",
            link="https://github.com/tsurumeso/vocal-remover",
            is_link=True,
        )
        credit_label(
            place=8,
            frame=credits_Frame,
            text="Kuielab & Woosung Choi",
            message="Developed the original MDX-Net AI code.",
            link="https://github.com/kuielab",
            is_link=True,
        )
        credit_label(
            place=10,
            frame=credits_Frame,
            text="Adefossez & Demucs",
            message="Core developer of Facebook's Demucs Music Source Separation.",
            link="https://github.com/facebookresearch/demucs",
            is_link=True,
        )
        credit_label(
            place=12,
            frame=credits_Frame,
            text="Bas Curtiz",
            message="Designed the official UVR logo, icon, banner, splash screen.",
        )
        credit_label(
            place=14,
            frame=credits_Frame,
            text="DilanBoskan",
            message="Your contributions at the start of this project were essential to the success of UVR. Thank you!",
        )
        credit_label(
            place=16,
            frame=credits_Frame,
            text="Audio Separation and CC Karaoke & Friends Discord Communities",
            message="Thank you for the support!",
        )

        more_info_tab_Frame = runtime.tk.Frame(tab2, highlightthicknes=30)
        more_info_tab_Frame.grid(row=0, column=0, padx=0, pady=0)

        section_title_Label(place=3, frame=more_info_tab_Frame, text="Resources")
        Link(
            place=4,
            frame=more_info_tab_Frame,
            text="Ultimate Vocal Remover (Official GitHub)",
            link="https://github.com/Anjok07/ultimatevocalremovergui",
            description="You can find updates, report issues, and give us a shout via our official GitHub.",
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=8,
            frame=more_info_tab_Frame,
            text="X-Minus AI",
            link="https://x-minus.pro/ai",
            description="Many of the models provided are also on X-Minus.\nX-Minus benefits users without the computing resources to run the GUI or models locally.",
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=12,
            frame=more_info_tab_Frame,
            text="MVSep",
            link="https://mvsep.com/quality_checker/leaderboard.php",
            description="Some of our models are also on MVSep.\nClick the link above for a list of some of the best settings \nand model combinations recorded by fellow UVR users.\nSpecial thanks to ZFTurbo for all his work on MVSep!",
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=18,
            frame=more_info_tab_Frame,
            text="FFmpeg",
            link="https://www.wikihow.com/Install-FFmpeg-on-Windows",
            description="UVR relies on FFmpeg for processing non-wav audio files.\nIf you are missing FFmpeg, please see the installation guide via the link provided.",
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=22,
            frame=more_info_tab_Frame,
            text="Rubber Band Library",
            link="https://breakfastquay.com/rubberband/",
            description="UVR uses the Rubber Band library for the sound stretch and pitch shift tool.\nYou can get more information on it via the link provided.",
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=26,
            frame=more_info_tab_Frame,
            text="Matchering",
            link="https://github.com/sergree/matchering",
            description='UVR uses the Matchering library for the "Matchering" Audio Tool.\nYou can get more information on it via the link provided.',
            font=runtime.FONT_SIZE_1,
        )
        Link(
            place=30,
            frame=more_info_tab_Frame,
            text="Official UVR BMAC",
            link=runtime.DONATE_LINK_BMAC,
            description="If you wish to support and donate to this project, click the link above!",
            font=runtime.FONT_SIZE_1,
        )

        appplication_license_tab_Frame = runtime.tk.Frame(tab3)
        appplication_license_tab_Frame.grid(row=0, column=0, padx=0, pady=0)

        runtime.tk.Label(
            appplication_license_tab_Frame,
            text="UVR License Information",
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_6}", "bold"),
            justify="center",
            fg="#f4f4f4",
        ).grid(row=0, column=0, padx=0, pady=25)

        appplication_license_Text = runtime.tk.Text(
            appplication_license_tab_Frame,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_4}"),
            fg="white",
            bg="black",
            width=72,
            wrap=runtime.tk.WORD,
            borderwidth=0,
        )
        appplication_license_Text.grid(row=1, column=0, padx=0, pady=0)
        appplication_license_Text_scroll = runtime.ttk.Scrollbar(
            appplication_license_tab_Frame, orient=runtime.tk.VERTICAL
        )
        appplication_license_Text.config(yscrollcommand=appplication_license_Text_scroll.set)
        appplication_license_Text_scroll.configure(command=appplication_license_Text.yview)
        appplication_license_Text.grid(row=4, sticky=runtime.tk.W)
        appplication_license_Text_scroll.grid(row=4, column=1, sticky=runtime.tk.NS)
        appplication_license_Text.insert("insert", runtime.LICENSE_TEXT(runtime.VERSION, runtime.current_patch))
        appplication_license_Text.configure(state=runtime.tk.DISABLED)

        application_change_log_tab_Frame = runtime.tk.Frame(tab4)
        application_change_log_tab_Frame.grid(row=0, column=0, padx=0, pady=0)

        runtime.tk.Label(
            application_change_log_tab_Frame,
            text="Additional Information",
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_6}", "bold"),
            justify="center",
            fg="#f4f4f4",
        ).grid(row=0, column=0, padx=0, pady=25)

        application_change_log_Text = runtime.tk.Text(
            application_change_log_tab_Frame,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_4}"),
            fg="white",
            bg="black",
            width=72,
            wrap=runtime.tk.WORD,
            borderwidth=0,
        )
        application_change_log_Text.grid(row=1, column=0, padx=40 if runtime.is_macos else 30, pady=0)
        application_change_log_Text_scroll = runtime.ttk.Scrollbar(
            application_change_log_tab_Frame, orient=runtime.tk.VERTICAL
        )
        application_change_log_Text.config(yscrollcommand=application_change_log_Text_scroll.set)
        application_change_log_Text_scroll.configure(command=application_change_log_Text.yview)
        application_change_log_Text.grid(row=4, sticky=runtime.tk.W)
        application_change_log_Text_scroll.grid(row=4, column=1, sticky=runtime.tk.NS)
        application_change_log_Text.insert("insert", self.ui.bulletin_data)
        runtime.auto_hyperlink(application_change_log_Text)
        application_change_log_Text.configure(state=runtime.tk.DISABLED)

        self.ui.menu_placement(help_guide_opt, "Information Guide")

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

    def menu_advanced_demucs_options(self) -> None:
        """Open advanced Demucs options."""

        demuc_opt = runtime.tk.Toplevel()

        self.ui.is_open_menu_advanced_demucs_options.set(True)
        self.ui.menu_advanced_demucs_options_close_window = lambda: (
            self.ui.is_open_menu_advanced_demucs_options.set(False),
            demuc_opt.destroy(),
        )
        demuc_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_advanced_demucs_options_close_window)

        tab1, tab3 = self.ui.menu_tab_control(demuc_opt, self.ui.demucs_secondary_model_vars, is_demucs=True)

        demucs_frame = self.ui.menu_FRAME_SET(tab1)
        demucs_frame.grid(pady=0 if self.ui.chosen_process_method_var.get() != runtime.DEMUCS_ARCH_TYPE else 55)

        demucs_pre_model_frame = self.ui.menu_FRAME_SET(tab3)
        demucs_pre_model_frame.grid(row=0)

        self.ui.menu_title_LABEL_SET(demucs_frame, runtime.ADVANCED_DEMUCS_OPTIONS_TEXT).grid(
            pady=runtime.MENU_PADDING_2
        )

        if self.ui.chosen_process_method_var.get() != runtime.DEMUCS_ARCH_TYPE:
            segment_Label = self.ui.menu_sub_LABEL_SET(demucs_frame, runtime.SEGMENTS_TEXT)
            segment_Label.grid(pady=runtime.MENU_PADDING_2)
            runtime.ComboBoxEditableMenu(
                demucs_frame,
                values=runtime.DEMUCS_SEGMENTS,
                width=runtime.MENU_COMBOBOX_WIDTH,
                textvariable=self.ui.segment_var,
                pattern=runtime.REG_SEGMENTS,
                default=runtime.DEMUCS_SEGMENTS,
            ).grid()
            self.ui.help_hints(segment_Label, text=runtime.SEGMENT_HELP)

        self.ui.shifts_Label = self.ui.menu_sub_LABEL_SET(demucs_frame, runtime.SHIFTS_TEXT)
        self.ui.shifts_Label.grid(pady=runtime.MENU_PADDING_1)
        self.ui.shifts_Option = runtime.ComboBoxEditableMenu(
            demucs_frame,
            values=runtime.DEMUCS_SHIFTS,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.shifts_var,
            pattern=runtime.REG_SHIFTS,
            default=runtime.DEMUCS_SHIFTS[2],
        )
        self.ui.shifts_Option.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(self.ui.shifts_Label, text=runtime.SHIFTS_HELP)

        self.ui.overlap_Label = self.ui.menu_sub_LABEL_SET(demucs_frame, runtime.OVERLAP_TEXT)
        self.ui.overlap_Label.grid(pady=runtime.MENU_PADDING_1)
        self.ui.overlap_Option = runtime.ComboBoxEditableMenu(
            demucs_frame,
            values=runtime.DEMUCS_OVERLAP,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.overlap_var,
            pattern=runtime.REG_OVERLAP,
            default=runtime.DEMUCS_OVERLAP,
        )
        self.ui.overlap_Option.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(self.ui.overlap_Label, text=runtime.OVERLAP_HELP)

        pitch_shift_Label = self.ui.menu_sub_LABEL_SET(demucs_frame, runtime.SHIFT_CONVERSION_PITCH_TEXT)
        pitch_shift_Label.grid(pady=runtime.MENU_PADDING_1)
        runtime.ComboBoxEditableMenu(
            demucs_frame,
            values=runtime.SEMITONE_SEL,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.semitone_shift_var,
            pattern=runtime.REG_SEMITONES,
            default=runtime.SEMI_DEF,
        ).grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(pitch_shift_Label, text=runtime.PITCH_SHIFT_HELP)

        self.ui.is_split_mode_Option = runtime.ttk.Checkbutton(
            demucs_frame,
            text=runtime.SPLIT_MODE_TEXT,
            width=runtime.DEMUCS_CHECKBOXS_WIDTH,
            variable=self.ui.is_split_mode_var,
        )
        self.ui.is_split_mode_Option.grid()
        self.ui.help_hints(self.ui.is_split_mode_Option, text=runtime.IS_SPLIT_MODE_HELP)

        self.ui.is_demucs_combine_stems_Option = runtime.ttk.Checkbutton(
            demucs_frame,
            text=runtime.COMBINE_STEMS_TEXT,
            width=runtime.DEMUCS_CHECKBOXS_WIDTH,
            variable=self.ui.is_demucs_combine_stems_var,
        )
        self.ui.is_demucs_combine_stems_Option.grid()
        self.ui.help_hints(self.ui.is_demucs_combine_stems_Option, text=runtime.IS_DEMUCS_COMBINE_STEMS_HELP)

        is_invert_spec_Option = runtime.ttk.Checkbutton(
            demucs_frame,
            text=runtime.SPECTRAL_INVERSION_TEXT,
            width=runtime.DEMUCS_CHECKBOXS_WIDTH,
            variable=self.ui.is_invert_spec_var,
        )
        is_invert_spec_Option.grid()
        self.ui.help_hints(is_invert_spec_Option, text=runtime.IS_INVERT_SPEC_HELP)

        self.ui.vocal_splitter_Button_opt(demuc_opt, demucs_frame, width=runtime.VR_BUT_WIDTH, pady=runtime.MENU_PADDING_1)

        self.ui.open_demucs_model_dir_Button = runtime.ttk.Button(
            demucs_frame,
            text=runtime.OPEN_MODELS_FOLDER_TEXT,
            command=lambda: runtime.OPEN_FILE_func(runtime.DEMUCS_MODELS_DIR),
            width=runtime.VR_BUT_WIDTH,
        )
        self.ui.open_demucs_model_dir_Button.grid(pady=runtime.MENU_PADDING_1)

        self.ui.demucs_return_Button = runtime.ttk.Button(
            demucs_frame,
            text=runtime.BACK_TO_MAIN_MENU,
            command=lambda: (
                self.ui.menu_advanced_demucs_options_close_window(),
                self.ui.check_is_menu_settings_open(),
            ),
        )
        self.ui.demucs_return_Button.grid(pady=runtime.MENU_PADDING_1)

        self.ui.demucs_close_Button = runtime.ttk.Button(
            demucs_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_demucs_options_close_window(),
        )
        self.ui.demucs_close_Button.grid(pady=runtime.MENU_PADDING_1)

        self.ui.menu_placement(
            demuc_opt,
            runtime.ADVANCED_DEMUCS_OPTIONS_TEXT,
            is_help_hints=True,
            close_function=self.ui.menu_advanced_demucs_options_close_window,
            frame_list=[demucs_pre_model_frame, demucs_frame],
        )

    def menu_advanced_mdx_options(self) -> None:
        """Open advanced MDX options."""

        mdx_net_opt = runtime.tk.Toplevel()

        self.ui.is_open_menu_advanced_mdx_options.set(True)
        self.ui.menu_advanced_mdx_options_close_window = lambda: (
            self.ui.is_open_menu_advanced_mdx_options.set(False),
            mdx_net_opt.destroy(),
        )
        mdx_net_opt.protocol("WM_DELETE_WINDOW", self.ui.menu_advanced_mdx_options_close_window)

        tab1, tab3 = self.ui.menu_tab_control(mdx_net_opt, self.ui.mdx_secondary_model_vars, is_mdxnet=True)

        mdx_net_frame = self.ui.menu_FRAME_SET(tab1)
        mdx_net_frame.grid(pady=0)

        mdx_net23_frame = self.ui.menu_FRAME_SET(tab3)
        mdx_net23_frame.grid(pady=0)

        self.ui.menu_title_LABEL_SET(mdx_net_frame, runtime.ADVANCED_MDXNET_OPTIONS_TEXT).grid(
            pady=runtime.MENU_PADDING_1
        )

        compensate_Label = self.ui.menu_sub_LABEL_SET(mdx_net_frame, runtime.VOLUME_COMPENSATION_TEXT)
        compensate_Label.grid(pady=runtime.MENU_PADDING_4)
        runtime.ComboBoxEditableMenu(
            mdx_net_frame,
            values=runtime.VOL_COMPENSATION,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.compensate_var,
            pattern=runtime.REG_COMPENSATION,
            default=runtime.VOL_COMPENSATION,
        ).grid(pady=runtime.MENU_PADDING_4)
        self.ui.help_hints(compensate_Label, text=runtime.COMPENSATE_HELP)

        mdx_segment_size_Label = self.ui.menu_sub_LABEL_SET(mdx_net_frame, runtime.SEGMENT_SIZE_TEXT)
        mdx_segment_size_Label.grid(pady=runtime.MENU_PADDING_4)
        runtime.ComboBoxEditableMenu(
            mdx_net_frame,
            values=runtime.MDX_SEGMENTS,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.mdx_segment_size_var,
            pattern=runtime.REG_MDX_SEG,
            default="256",
        ).grid(pady=runtime.MENU_PADDING_4)
        self.ui.help_hints(mdx_segment_size_Label, text=runtime.MDX_SEGMENT_SIZE_HELP)

        overlap_mdx_Label = self.ui.menu_sub_LABEL_SET(mdx_net_frame, runtime.OVERLAP_TEXT)
        overlap_mdx_Label.grid(pady=runtime.MENU_PADDING_4)
        runtime.ComboBoxEditableMenu(
            mdx_net_frame,
            values=runtime.MDX_OVERLAP,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.overlap_mdx_var,
            pattern=runtime.REG_OVERLAP,
            default=runtime.MDX_OVERLAP,
        ).grid(pady=runtime.MENU_PADDING_4)
        self.ui.help_hints(overlap_mdx_Label, text=runtime.OVERLAP_HELP)

        pitch_shift_Label = self.ui.menu_sub_LABEL_SET(mdx_net_frame, runtime.SHIFT_CONVERSION_PITCH_TEXT)
        pitch_shift_Label.grid(pady=runtime.MENU_PADDING_4)
        runtime.ComboBoxEditableMenu(
            mdx_net_frame,
            values=runtime.SEMITONE_SEL,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.semitone_shift_var,
            pattern=runtime.REG_SEMITONES,
            default=runtime.SEMI_DEF,
        ).grid(pady=runtime.MENU_PADDING_4)
        self.ui.help_hints(pitch_shift_Label, text=runtime.PITCH_SHIFT_HELP)

        if not runtime.os.path.isfile(runtime.DENOISER_MODEL_PATH):
            denoise_options_var_text = self.ui.denoise_option_var.get()
            denoise_options = [option for option in runtime.MDX_DENOISE_OPTION if option != runtime.DENOISE_M]
            self.ui.denoise_option_var.set(
                runtime.DENOISE_S if denoise_options_var_text == runtime.DENOISE_M else denoise_options_var_text
            )
        else:
            denoise_options = runtime.MDX_DENOISE_OPTION

        denoise_option_Label = self.ui.menu_sub_LABEL_SET(mdx_net_frame, runtime.DENOISE_OUTPUT_TEXT)
        denoise_option_Label.grid(pady=runtime.MENU_PADDING_4)
        runtime.ComboBoxMenu(
            mdx_net_frame,
            textvariable=self.ui.denoise_option_var,
            values=denoise_options,
            width=runtime.MENU_COMBOBOX_WIDTH,
        ).grid(pady=runtime.MENU_PADDING_4)
        self.ui.help_hints(denoise_option_Label, text=runtime.IS_DENOISE_HELP)

        is_match_frequency_pitch_Option = runtime.ttk.Checkbutton(
            mdx_net_frame,
            text=runtime.MATCH_FREQ_CUTOFF_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_match_frequency_pitch_var,
        )
        is_match_frequency_pitch_Option.grid(pady=0)
        self.ui.help_hints(is_match_frequency_pitch_Option, text=runtime.IS_FREQUENCY_MATCH_HELP)

        is_invert_spec_Option = runtime.ttk.Checkbutton(
            mdx_net_frame,
            text=runtime.SPECTRAL_INVERSION_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_invert_spec_var,
        )
        is_invert_spec_Option.grid(pady=0)
        self.ui.help_hints(is_invert_spec_Option, text=runtime.IS_INVERT_SPEC_HELP)

        self.ui.vocal_splitter_Button_opt(mdx_net_opt, mdx_net_frame, pady=runtime.MENU_PADDING_1, width=runtime.VR_BUT_WIDTH)

        clear_mdx_cache_Button = runtime.ttk.Button(
            mdx_net_frame,
            text=runtime.CLEAR_AUTOSET_CACHE_TEXT,
            command=lambda: self.ui.clear_cache(runtime.MDX_ARCH_TYPE),
            width=runtime.VR_BUT_WIDTH,
        )
        clear_mdx_cache_Button.grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(clear_mdx_cache_Button, text=runtime.CLEAR_CACHE_HELP)

        runtime.ttk.Button(
            mdx_net_frame,
            text=runtime.OPEN_MODELS_FOLDER_TEXT,
            command=lambda: runtime.OPEN_FILE_func(runtime.MDX_MODELS_DIR),
            width=runtime.VR_BUT_WIDTH,
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            mdx_net_frame,
            text=runtime.BACK_TO_MAIN_MENU,
            command=lambda: (
                self.ui.menu_advanced_mdx_options_close_window(),
                self.ui.check_is_menu_settings_open(),
            ),
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            mdx_net_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_mdx_options_close_window(),
        ).grid(pady=runtime.MENU_PADDING_1)

        self.ui.menu_title_LABEL_SET(mdx_net23_frame, runtime.ADVANCED_MDXNET23_OPTIONS_TEXT).grid(
            pady=runtime.MENU_PADDING_2
        )

        mdx_batch_size_Label = self.ui.menu_sub_LABEL_SET(mdx_net23_frame, runtime.BATCH_SIZE_TEXT)
        mdx_batch_size_Label.grid(pady=runtime.MENU_PADDING_1)
        runtime.ComboBoxEditableMenu(
            mdx_net23_frame,
            values=runtime.BATCH_SIZE,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.mdx_batch_size_var,
            pattern=runtime.REG_BATCHES,
            default=runtime.BATCH_SIZE,
        ).grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(mdx_batch_size_Label, text=runtime.BATCH_SIZE_HELP)

        overlap_mdx23_Label = self.ui.menu_sub_LABEL_SET(mdx_net23_frame, runtime.OVERLAP_TEXT)
        overlap_mdx23_Label.grid(pady=runtime.MENU_PADDING_1)
        runtime.ComboBoxEditableMenu(
            mdx_net23_frame,
            values=runtime.MDX23_OVERLAP,
            width=runtime.MENU_COMBOBOX_WIDTH,
            textvariable=self.ui.overlap_mdx23_var,
            pattern=runtime.REG_OVERLAP23,
            default="8",
        ).grid(pady=runtime.MENU_PADDING_1)
        self.ui.help_hints(overlap_mdx23_Label, text=runtime.OVERLAP_23_HELP)

        is_mdx_c_seg_def_Option = runtime.ttk.Checkbutton(
            mdx_net23_frame,
            text=runtime.SEGMENT_DEFAULT_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_mdx_c_seg_def_var,
        )
        is_mdx_c_seg_def_Option.grid(pady=0)
        self.ui.help_hints(is_mdx_c_seg_def_Option, text=runtime.IS_SEGMENT_DEFAULT_HELP)

        is_mdx_combine_stems_Option = runtime.ttk.Checkbutton(
            mdx_net23_frame,
            text=runtime.COMBINE_STEMS_TEXT,
            width=runtime.MDX_CHECKBOXS_WIDTH,
            variable=self.ui.is_mdx23_combine_stems_var,
        )
        is_mdx_combine_stems_Option.grid()
        self.ui.help_hints(is_mdx_combine_stems_Option, text=runtime.IS_DEMUCS_COMBINE_STEMS_HELP)

        runtime.ttk.Button(
            mdx_net23_frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: self.ui.menu_advanced_mdx_options_close_window(),
        ).grid(pady=runtime.MENU_PADDING_2)

        self.ui.menu_placement(
            mdx_net_opt,
            runtime.ADVANCED_MDXNET_OPTIONS_TEXT,
            is_help_hints=True,
            close_function=self.ui.menu_advanced_mdx_options_close_window,
            frame_list=[mdx_net_frame, mdx_net23_frame],
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
