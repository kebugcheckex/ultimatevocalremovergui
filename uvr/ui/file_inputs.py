"""File/input helper flows extracted from UVR.py."""

from __future__ import annotations

import os
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class MainWindowFileInputs:
    def __init__(self, ui: Any):
        self.ui = ui

    def linux_filebox_fix(self, is_on: bool = True) -> None:
        fg_color_set = "#575757" if is_on else "#F6F6F7"
        style = runtime.ttk.Style(self.ui)
        style.configure("TButton", foreground="#F6F6F7")
        style.configure("TCheckbutton", foreground="#F6F6F7")
        style.configure("TCombobox", foreground="#F6F6F7")
        style.configure("TEntry", foreground="#F6F6F7")
        style.configure("TLabel", foreground="#F6F6F7")
        style.configure("TMenubutton", foreground="#F6F6F7")
        style.configure("TRadiobutton", foreground="#F6F6F7")
        runtime.gui_data.sv_ttk.set_theme("dark", runtime.MAIN_FONT_NAME, 10, fg_color_set=fg_color_set)

    def show_file_dialog(self, text: str = "Select Audio files", dialoge_type: Any = None) -> Any:
        parent_win = self.ui
        is_linux = not runtime.is_windows and not runtime.is_macos

        if is_linux:
            self.linux_filebox_fix()
            top = runtime.tk.Toplevel(self.ui)
            top.withdraw()
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            parent_win = top

        if dialoge_type == runtime.MULTIPLE_FILE:
            filenames = runtime.filedialog.askopenfilenames(parent=parent_win, title=text)
        elif dialoge_type == runtime.MAIN_MULTIPLE_FILE:
            filenames = runtime.filedialog.askopenfilenames(
                parent=parent_win,
                title=text,
                initialfile="",
                initialdir=self.ui.lastDir,
            )
        elif dialoge_type == runtime.SINGLE_FILE:
            filenames = runtime.filedialog.askopenfilename(parent=parent_win, title=text)
        elif dialoge_type == runtime.CHOOSE_EXPORT_FIR:
            filenames = runtime.filedialog.askdirectory(parent=parent_win, title="Select Folder")
        else:
            filenames = ()

        if is_linux:
            self.linux_filebox_fix(False)
            top.destroy()

        return filenames

    def input_select_filedialog(self) -> None:
        if self.ui.lastDir is not None and not os.path.isdir(self.ui.lastDir):
            self.ui.lastDir = None

        paths = self.show_file_dialog(dialoge_type=runtime.MAIN_MULTIPLE_FILE)

        if paths:
            self.ui.inputPaths = paths
            self.process_input_selections()
            self.update_input_paths()

    def export_select_filedialog(self) -> str | None:
        export_path = None
        path = self.show_file_dialog(dialoge_type=runtime.CHOOSE_EXPORT_FIR)

        if path:
            self.ui.export_path_var.set(path)
            export_path = self.ui.export_path_var.get()

        return export_path

    def update_input_paths(self) -> None:
        if self.ui.inputPaths:
            if len(self.ui.inputPaths) == 1:
                text = self.ui.inputPaths[0]
            else:
                count = len(self.ui.inputPaths) - 1
                file_text = "file" if len(self.ui.inputPaths) == 2 else "files"
                text = f"{self.ui.inputPaths[0]}, +{count} {file_text}"
        else:
            text = ""

        self.ui.inputPathsEntry_var.set(text)

    def select_audiofile(self, path: str | None = None, is_primary: bool = True) -> None:
        vars_map = {
            True: (
                self.ui.fileOneEntry_Full_var,
                self.ui.fileOneEntry_var,
                self.ui.fileTwoEntry_Full_var,
                self.ui.fileTwoEntry_var,
            ),
            False: (
                self.ui.fileTwoEntry_Full_var,
                self.ui.fileTwoEntry_var,
                self.ui.fileOneEntry_Full_var,
                self.ui.fileOneEntry_var,
            ),
        }

        file_path_var, file_basename_var, file_path_2_var, file_basename_2_var = vars_map[is_primary]

        if not path:
            path = self.show_file_dialog(text="Select Audio file", dialoge_type=runtime.SINGLE_FILE)

        if path:
            file_path_var.set(path)
            file_basename_var.set(os.path.basename(path))

            if runtime.BATCH_MODE_DUAL in file_path_2_var.get():
                file_path_2_var.set("")
                file_basename_2_var.set("")

            self.ui.DualBatch_inputPaths = []
            self.check_dual_paths()

    def check_dual_paths(self, is_fill_menu: bool = False) -> Any:
        if self.ui.DualBatch_inputPaths:
            first_paths = tuple(self.ui.DualBatch_inputPaths)
            first_paths_len = len(first_paths)
            first_paths = first_paths[0]

            if first_paths_len == 1:
                file1_base_text = os.path.basename(first_paths[0])
                file2_base_text = os.path.basename(first_paths[1])
            else:
                first_paths_len = first_paths_len - 1
                file1_base_text = f"{os.path.basename(first_paths[0])}, +{first_paths_len} file(s){runtime.BATCH_MODE_DUAL}"
                file2_base_text = f"{os.path.basename(first_paths[1])}, +{first_paths_len} file(s){runtime.BATCH_MODE_DUAL}"

            self.ui.fileOneEntry_var.set(file1_base_text)
            self.ui.fileOneEntry_Full_var.set(f"{first_paths[0]}")
            self.ui.fileTwoEntry_var.set(file2_base_text)
            self.ui.fileTwoEntry_Full_var.set(f"{first_paths[1]}")
        else:
            if is_fill_menu:
                file_one = self.ui.fileOneEntry_Full_var.get()
                file_two = self.ui.fileTwoEntry_Full_var.get()

                if file_one and file_two and runtime.BATCH_MODE_DUAL not in file_one and runtime.BATCH_MODE_DUAL not in file_two:
                    self.ui.DualBatch_inputPaths = [(file_one, file_two)]
            else:
                if runtime.BATCH_MODE_DUAL in self.ui.fileOneEntry_var.get():
                    self.ui.fileOneEntry_var.set("")
                    self.ui.fileOneEntry_Full_var.set("")
                if runtime.BATCH_MODE_DUAL in self.ui.fileTwoEntry_var.get():
                    self.ui.fileTwoEntry_var.set("")
                    self.ui.fileTwoEntry_Full_var.set("")

        return self.ui.DualBatch_inputPaths

    def process_input_selections(self) -> None:
        input_list = []
        ext = runtime.FFMPEG_EXT if not self.ui.is_accept_any_input_var.get() else runtime.ANY_EXT

        for item in self.ui.inputPaths:
            if os.path.isfile(item):
                if item.endswith(ext):
                    input_list.append(item)
            for root, _dirs, files in os.walk(item):
                for file in files:
                    if file.endswith(ext):
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            input_list.append(file_path)

        self.ui.inputPaths = tuple(input_list)
