"""Input-related menu and popup flows extracted from UVR.py."""

from __future__ import annotations

import os
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class InputMenus:
    def __init__(self, ui: Any):
        self.ui = ui

    def input_right_click_menu(self, event: Any) -> None:
        right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
        right_click_menu.add_command(
            label="See All Inputs",
            command=lambda: self.ui.check_is_menu_open(runtime.INPUTS_MENU),
        )

        try:
            right_click_menu.tk_popup(event.x_root, event.y_root)
            runtime.right_click_release_linux(right_click_menu)
        finally:
            right_click_menu.grab_release()

    def input_dual_right_click_menu(self, event: Any, is_primary: bool) -> None:
        input_path = self.ui.fileOneEntry_Full_var.get() if is_primary else self.ui.fileTwoEntry_Full_var.get()
        right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
        right_click_menu.add_command(
            label=runtime.CHOOSE_INPUT_TEXT,
            command=lambda: self.ui.select_audiofile(is_primary=is_primary),
        )
        if input_path and os.path.isdir(os.path.dirname(input_path)):
            right_click_menu.add_command(
                label=runtime.OPEN_INPUT_DIR_TEXT,
                command=lambda: runtime.OPEN_FILE_func(os.path.dirname(input_path)),
            )
        right_click_menu.add_command(label=runtime.BATCH_PROCESS_MENU_TEXT, command=self.menu_batch_dual)

        try:
            right_click_menu.tk_popup(event.x_root, event.y_root)
            runtime.right_click_release_linux(right_click_menu)
        finally:
            right_click_menu.grab_release()

    def menu_view_inputs(self) -> None:
        menu_view_inputs_top = runtime.tk.Toplevel(runtime.root)

        self.ui.is_open_menu_view_inputs.set(True)
        self.ui.menu_view_inputs_close_window = lambda: close_window()
        menu_view_inputs_top.protocol("WM_DELETE_WINDOW", self.ui.menu_view_inputs_close_window)

        input_length_var = runtime.tk.StringVar(value="")
        input_info_text_var = runtime.tk.StringVar(value="")
        is_widen_box_var = runtime.tk.BooleanVar(value=False)
        is_play_file_var = runtime.tk.BooleanVar(value=False)
        varification_text_var = runtime.tk.StringVar(value=runtime.VERIFY_INPUTS_TEXT)

        reset_list = lambda: (
            input_files_listbox_Option.delete(0, "end"),
            [input_files_listbox_Option.insert(runtime.tk.END, inputs) for inputs in self.ui.inputPaths],
        )
        audio_input_total = lambda: input_length_var.set(f"{runtime.AUDIO_INPUT_TOTAL_TEXT}: {len(self.ui.inputPaths)}")
        audio_input_total()

        def list_diff(list1: list[str] | tuple[str, ...], list2: list[str] | tuple[str, ...]) -> list[str]:
            return list(set(list1).symmetric_difference(set(list2)))

        def list_to_string(list1: list[str]) -> str:
            return "\n".join("".join(sub) for sub in list1)

        def close_window() -> None:
            self.ui.verification_thread.kill() if self.ui.thread_check(self.ui.verification_thread) else None
            self.ui.is_open_menu_view_inputs.set(False)
            menu_view_inputs_top.destroy()

        def drag_n_drop(e: Any) -> None:
            input_info_text_var.set("")
            runtime.drop(e, accept_mode="files")
            reset_list()
            audio_input_total()

        def selected_files(is_remove: bool = False) -> None:
            if not self.ui.thread_check(self.ui.active_processing_thread):
                items_list = [input_files_listbox_Option.get(i) for i in input_files_listbox_Option.curselection()]
                input_paths = list(self.ui.inputPaths)
                if is_remove:
                    [input_paths.remove(i) for i in items_list if items_list]
                else:
                    [input_paths.remove(i) for i in self.ui.inputPaths if i not in items_list]
                removed_files = list_diff(self.ui.inputPaths, input_paths)
                [input_files_listbox_Option.delete(input_files_listbox_Option.get(0, runtime.tk.END).index(i)) for i in removed_files]
                starting_len = len(self.ui.inputPaths)
                self.ui.inputPaths = tuple(input_paths)
                self.ui.update_inputPaths()
                audio_input_total()
                input_info_text_var.set(f"{starting_len - len(self.ui.inputPaths)} input(s) removed.")
            else:
                input_info_text_var.set("You cannot remove inputs during an active process.")

        def box_size() -> None:
            input_info_text_var.set("")
            if is_widen_box_var.get():
                input_files_listbox_Option.config(width=230, height=25)
            else:
                input_files_listbox_Option.config(width=110, height=17)
            self.ui.menu_placement(menu_view_inputs_top, "Selected Inputs", pop_up=True)

        def input_options(is_select_inputs: bool = True) -> None:
            input_info_text_var.set("")
            if is_select_inputs:
                self.ui.input_select_filedialog()
            else:
                self.ui.inputPaths = ()
            reset_list()
            self.ui.update_inputPaths()
            audio_input_total()

        def pop_open_file_path(is_play_file: bool = False) -> None:
            if self.ui.inputPaths:
                track_selected = self.ui.inputPaths[input_files_listbox_Option.index(runtime.tk.ACTIVE)]
                if os.path.isfile(track_selected):
                    runtime.OPEN_FILE_func(track_selected if is_play_file else os.path.dirname(track_selected))

        def get_export_dir() -> str | None:
            if os.path.isdir(self.ui.export_path_var.get()):
                export_dir = self.ui.export_path_var.get()
            else:
                export_dir = self.ui.export_select_filedialog()

            return export_dir

        def verify_audio(is_create_samples: bool = False) -> None:
            input_paths = list(self.ui.inputPaths)
            iterated_list = (
                self.ui.inputPaths
                if not is_create_samples
                else [input_files_listbox_Option.get(i) for i in input_files_listbox_Option.curselection()]
            )
            removed_files: list[str] = []
            total_audio_count, current_file = len(iterated_list), 0
            if iterated_list:
                for item in iterated_list:
                    current_file += 1
                    input_info_text_var.set(
                        f"{runtime.SAMPLE_BEGIN if is_create_samples else runtime.VERIFY_BEGIN}{current_file}/{total_audio_count}"
                    )
                    export_dir = None
                    if is_create_samples:
                        export_dir = get_export_dir()
                        if not export_dir:
                            input_info_text_var.set("No export directory selected.")
                            return
                    is_good, error_data = self.ui.verify_audio(item, is_process=False, sample_path=export_dir)
                    if not is_good:
                        input_paths.remove(item)
                        removed_files.append(error_data)

                varification_text_var.set(runtime.VERIFY_INPUTS_TEXT)
                input_files_listbox_Option.configure(state=runtime.tk.NORMAL)

                if removed_files:
                    input_info_text_var.set(f"{len(removed_files)} {runtime.BROKEN_OR_INCOM_TEXT}")
                    error_text = ""
                    for item in removed_files:
                        error_text += item
                    removed_file_names = list_diff(self.ui.inputPaths, input_paths)
                    [
                        input_files_listbox_Option.delete(input_files_listbox_Option.get(0, runtime.tk.END).index(i))
                        for i in removed_file_names
                    ]
                    self.ui.error_log_var.set(runtime.REMOVED_FILES(list_to_string(removed_file_names), error_text))
                    self.ui.inputPaths = tuple(input_paths)
                    self.ui.update_inputPaths()
                else:
                    input_info_text_var.set("No errors found!")

                audio_input_total()
            else:
                input_info_text_var.set(
                    f"{runtime.NO_FILES_TEXT} {runtime.SELECTED_VER if is_create_samples else runtime.DETECTED_VER}"
                )
                varification_text_var.set(runtime.VERIFY_INPUTS_TEXT)
                input_files_listbox_Option.configure(state=runtime.tk.NORMAL)
                return

            audio_input_total()

        def verify_audio_start_thread(is_create_samples: bool = False) -> None:
            if not self.ui.thread_check(self.ui.active_processing_thread):
                if not self.ui.thread_check(self.ui.verification_thread):
                    varification_text_var.set("Stop Progress")
                    input_files_listbox_Option.configure(state=runtime.tk.DISABLED)
                    self.ui.verification_thread = runtime.KThread(
                        target=lambda: verify_audio(is_create_samples=is_create_samples)
                    )
                    self.ui.verification_thread.start()
                else:
                    input_files_listbox_Option.configure(state=runtime.tk.NORMAL)
                    varification_text_var.set(runtime.VERIFY_INPUTS_TEXT)
                    input_info_text_var.set("Process Stopped")
                    self.ui.verification_thread.kill()
            else:
                input_info_text_var.set("You cannot verify inputs during an active process.")

        def right_click_menu(event: Any) -> None:
            right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
            right_click_menu.add_command(label="Remove Selected Items Only", command=lambda: selected_files(is_remove=True))
            right_click_menu.add_command(label="Keep Selected Items Only", command=lambda: selected_files(is_remove=False))
            right_click_menu.add_command(label="Clear All Input(s)", command=lambda: input_options(is_select_inputs=False))
            right_click_menu.add_separator()
            right_click_menu_sub = runtime.tk.Menu(right_click_menu, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=False)
            right_click_menu.add_command(
                label="Verify and Create Samples of Selected Inputs",
                command=lambda: verify_audio_start_thread(is_create_samples=True),
            )
            right_click_menu.add_cascade(label="Preferred Double Click Action", menu=right_click_menu_sub)
            if is_play_file_var.get():
                right_click_menu_sub.add_command(
                    label="Enable: Open Audio File Directory",
                    command=lambda: (
                        input_files_listbox_Option.bind("<Double-Button>", lambda e: pop_open_file_path()),
                        is_play_file_var.set(False),
                    ),
                )
            else:
                right_click_menu_sub.add_command(
                    label="Enable: Open Audio File",
                    command=lambda: (
                        input_files_listbox_Option.bind("<Double-Button>", lambda e: pop_open_file_path(is_play_file=True)),
                        is_play_file_var.set(True),
                    ),
                )

            try:
                right_click_menu.tk_popup(event.x_root, event.y_root)
                runtime.right_click_release_linux(right_click_menu, menu_view_inputs_top)
            finally:
                right_click_menu.grab_release()

        menu_view_inputs_Frame = self.ui.menu_FRAME_SET(menu_view_inputs_top)
        menu_view_inputs_Frame.grid(row=0)

        self.ui.main_window_LABEL_SET(menu_view_inputs_Frame, runtime.SELECTED_INPUTS).grid(
            row=0, column=0, padx=0, pady=runtime.MENU_PADDING_1
        )
        runtime.tk.Label(
            menu_view_inputs_Frame,
            textvariable=input_length_var,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_1}"),
            foreground=runtime.FG_COLOR,
        ).grid(row=1, column=0, padx=0, pady=runtime.MENU_PADDING_1)
        if runtime.OPERATING_SYSTEM != "Linux":
            runtime.ttk.Button(
                menu_view_inputs_Frame,
                text=runtime.SELECT_INPUTS,
                command=lambda: input_options(),
            ).grid(row=2, column=0, padx=0, pady=runtime.MENU_PADDING_2)
        input_files_listbox_Option = runtime.tk.Listbox(
            menu_view_inputs_Frame,
            selectmode=runtime.tk.EXTENDED,
            activestyle="dotbox",
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_1}"),
            background="#101414",
            exportselection=0,
            width=110,
            height=17,
            relief=runtime.tk.SOLID,
            borderwidth=0,
        )
        input_files_listbox_vertical_scroll = runtime.ttk.Scrollbar(menu_view_inputs_Frame, orient=runtime.tk.VERTICAL)
        input_files_listbox_Option.config(yscrollcommand=input_files_listbox_vertical_scroll.set)
        input_files_listbox_vertical_scroll.configure(command=input_files_listbox_Option.yview)
        input_files_listbox_Option.grid(row=4, sticky=runtime.tk.W)
        input_files_listbox_vertical_scroll.grid(row=4, column=1, sticky=runtime.tk.NS)

        runtime.tk.Label(
            menu_view_inputs_Frame,
            textvariable=input_info_text_var,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_1}"),
            foreground=runtime.FG_COLOR,
        ).grid(row=5, column=0, padx=0, pady=0)
        runtime.ttk.Checkbutton(
            menu_view_inputs_Frame,
            text=runtime.WIDEN_BOX,
            variable=is_widen_box_var,
            command=lambda: box_size(),
        ).grid(row=6, column=0, padx=0, pady=0)
        verify_audio_button = runtime.ttk.Button(
            menu_view_inputs_Frame,
            textvariable=varification_text_var,
            command=lambda: verify_audio_start_thread(),
        )
        verify_audio_button.grid(row=7, column=0, padx=0, pady=runtime.MENU_PADDING_1)
        runtime.ttk.Button(
            menu_view_inputs_Frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: menu_view_inputs_top.destroy(),
        ).grid(row=8, column=0, padx=0, pady=runtime.MENU_PADDING_1)

        if runtime.is_dnd_compatible:
            menu_view_inputs_top.drop_target_register(runtime.DND_FILES)
            menu_view_inputs_top.dnd_bind("<<Drop>>", lambda e: drag_n_drop(e))
        input_files_listbox_Option.bind(runtime.right_click_button, lambda e: right_click_menu(e))
        input_files_listbox_Option.bind("<Double-Button>", lambda e: pop_open_file_path())
        input_files_listbox_Option.bind("<Delete>", lambda e: selected_files(is_remove=True))
        input_files_listbox_Option.bind("<BackSpace>", lambda e: selected_files(is_remove=False))

        reset_list()

        self.ui.menu_placement(menu_view_inputs_top, "Selected Inputs", pop_up=True)

    def menu_batch_dual(self) -> None:
        menu_batch_dual_top = runtime.tk.Toplevel(runtime.root)

        def drag_n_drop(event: Any, accept_mode: str) -> None:
            listbox = left_frame if accept_mode == runtime.FILE_1_LB else right_frame
            paths = runtime.drop(event, accept_mode)
            for item in paths:
                if item not in listbox.path_list:
                    basename = os.path.basename(item)
                    listbox.listbox.insert(runtime.tk.END, basename)
                    listbox.path_list.append(item)
            listbox.update_displayed_index()

        def move_entry(is_primary: bool = True) -> None:
            if is_primary:
                selected_frame, other_frame = left_frame, right_frame
            else:
                selected_frame, other_frame = right_frame, left_frame

            selected = selected_frame.listbox.curselection()

            if selected:
                basename = selected_frame.listbox.get(selected[0]).split(": ", 1)[1]

                if basename in other_frame.basename_to_path:
                    return

                path = selected_frame.basename_to_path[basename]

                selected_frame.listbox.delete(selected)
                other_frame.listbox.insert(runtime.tk.END, basename)

                selected_frame.path_list.remove(path)
                del selected_frame.basename_to_path[basename]

                other_frame.path_list.append(path)
                other_frame.basename_to_path[basename] = path

                selected_frame.update_displayed_index()
                other_frame.update_displayed_index()

        def open_selected_path(lb: str, is_play_file: bool = False) -> None:
            selected_frame = left_frame if lb == runtime.FILE_1_LB else right_frame
            selected_path = selected_frame.get_selected_path()

            if selected_path and os.path.isfile(selected_path):
                runtime.OPEN_FILE_func(selected_path if is_play_file else os.path.dirname(selected_path))

        def clear_all_data(lb: str) -> None:
            selected_frame = left_frame if lb == runtime.FILE_1_LB else right_frame
            selected_frame.listbox.delete(0, "end")
            selected_frame.path_list.clear()
            selected_frame.basename_to_path.clear()

        def clear_all(event: Any, lb: str) -> None:
            selected_frame = left_frame if lb == runtime.FILE_1_LB else right_frame
            selected = selected_frame.listbox.curselection()

            right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
            if selected:
                right_click_menu.add_command(label="Open Location", command=lambda: open_selected_path(lb))
                right_click_menu.add_command(label="Open File", command=lambda: open_selected_path(lb, is_play_file=True))
            right_click_menu.add_command(label="Clear All", command=lambda: clear_all_data(lb))

            try:
                right_click_menu.tk_popup(event.x_root, event.y_root)
                runtime.right_click_release_linux(right_click_menu, menu_batch_dual_top)
            finally:
                right_click_menu.grab_release()

        def gather_input_list() -> None:
            left_paths = list(left_frame.basename_to_path.values())
            right_paths = list(right_frame.basename_to_path.values())

            clear_all_data(runtime.FILE_1_LB)
            clear_all_data(runtime.FILE_2_LB)

            if left_paths and right_paths:
                left_frame.select_input(left_paths)
                right_frame.select_input(right_paths)

            self.ui.DualBatch_inputPaths = list(zip(left_paths, right_paths))
            self.ui.check_dual_paths()
            menu_batch_dual_top.destroy()

        menu_view_inputs_Frame = self.ui.menu_FRAME_SET(menu_batch_dual_top)
        menu_view_inputs_Frame.grid(row=0)

        left_frame = runtime.ListboxBatchFrame(
            menu_view_inputs_Frame,
            self.ui.file_one_sub_var.get().title(),
            move_entry,
            self.ui.right_img,
            self.ui.img_mapper,
        )
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        right_frame = runtime.ListboxBatchFrame(
            menu_view_inputs_Frame,
            self.ui.file_two_sub_var.get().title(),
            lambda: move_entry(False),
            self.ui.left_img,
            self.ui.img_mapper,
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        if runtime.is_dnd_compatible:
            left_frame.listbox.drop_target_register(runtime.DND_FILES)
            right_frame.listbox.drop_target_register(runtime.DND_FILES)
            left_frame.listbox.dnd_bind("<<Drop>>", lambda e: drag_n_drop(e, runtime.FILE_1_LB))
            right_frame.listbox.dnd_bind("<<Drop>>", lambda e: drag_n_drop(e, runtime.FILE_2_LB))
        left_frame.listbox.bind(runtime.right_click_button, lambda e: clear_all(e, runtime.FILE_1_LB))
        right_frame.listbox.bind(runtime.right_click_button, lambda e: clear_all(e, runtime.FILE_2_LB))

        menu_view_inputs_bottom_Frame = self.ui.menu_FRAME_SET(menu_batch_dual_top)
        menu_view_inputs_bottom_Frame.grid(row=1)

        confirm_btn = runtime.ttk.Button(
            menu_view_inputs_bottom_Frame,
            text=runtime.CONFIRM_ENTRIES,
            command=gather_input_list,
        )
        confirm_btn.grid(pady=runtime.MENU_PADDING_1)

        close_btn = runtime.ttk.Button(
            menu_view_inputs_bottom_Frame,
            text=runtime.CLOSE_WINDOW,
            command=lambda: menu_batch_dual_top.destroy(),
        )
        close_btn.grid(pady=runtime.MENU_PADDING_1)

        if self.ui.check_dual_paths():
            left_frame_pane = [i[0] for i in self.ui.DualBatch_inputPaths]
            right_frame_pane = [i[1] for i in self.ui.DualBatch_inputPaths]
            left_frame.update_displayed_index(left_frame_pane)
            right_frame.update_displayed_index(right_frame_pane)
            self.ui.check_dual_paths()

        self.ui.menu_placement(menu_batch_dual_top, runtime.DUAL_AUDIO_PROCESSING, pop_up=True)
