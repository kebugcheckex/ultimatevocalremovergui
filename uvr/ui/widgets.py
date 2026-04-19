"""Tk widgets extracted from UVR.py."""

from __future__ import annotations

import os
import queue
import re
import tkinter as tk
import tkinter.ttk as ttk
from collections import Counter
from tkinter.font import Font
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class ToolTip:
    def __init__(self, widget: Any):
        self.widget = widget
        self.tooltip = None

    def showtip(self, text: str, is_message_box: bool = False, is_success_message: Any = None) -> None:
        self.hidetip()

        def create_label_config() -> dict[str, Any]:
            font_size = runtime.FONT_SIZE_3 if is_message_box else runtime.FONT_SIZE_2

            common_config = {
                "text": text,
                "relief": runtime.tk.SOLID,
                "borderwidth": 1,
                "font": (runtime.MAIN_FONT_NAME, f"{font_size}", "normal"),
            }
            if is_message_box:
                background_color = "#03692d" if is_success_message else "#8B0000"
                return {
                    **common_config,
                    "background": background_color,
                    "foreground": "#ffffff",
                }
            return {
                **common_config,
                "background": "#1C1C1C",
                "foreground": "#ffffff",
                "highlightcolor": "#898b8e",
                "justify": runtime.tk.LEFT,
            }

        if is_message_box:
            temp_tooltip = runtime.tk.Toplevel(self.widget)
            temp_tooltip.wm_overrideredirect(True)
            temp_tooltip.withdraw()
            label = runtime.tk.Label(temp_tooltip, **create_label_config())
            label.pack()
            if runtime.is_windows:
                temp_tooltip.update()
            else:
                temp_tooltip.update_idletasks()

            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - (temp_tooltip.winfo_reqwidth() // 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height()

            temp_tooltip.destroy()
        else:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 25

        self.tooltip = runtime.tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label_config = create_label_config()
        if not is_message_box:
            label_config["padx"] = 10
            label_config["pady"] = 10
            label_config["wraplength"] = 750
        label = runtime.tk.Label(self.tooltip, **label_config)

        label.pack()

        if is_message_box:
            self.tooltip.after(3000 if type(is_success_message) is bool else 2000, self.hidetip)

    def hidetip(self) -> None:
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class ListboxBatchFrame(tk.Frame):
    def __init__(
        self,
        master: Any = None,
        name: str = "Listbox",
        command: Any = None,
        image_sel: Any = None,
        img_mapper: dict[str, Any] | None = None,
    ):
        super().__init__(master)
        self.master = master

        self.path_list: list[str] = []
        self.basename_to_path: dict[str, str] = {}

        self.label = tk.Label(
            self,
            text=name,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_5}"),
            foreground=runtime.FG_COLOR,
        )
        self.label.pack(pady=(10, 8))

        self.input_button = ttk.Button(self, text=runtime.SELECT_INPUTS, command=self.select_input)
        self.input_button.pack(pady=(0, 10))

        self.listbox = tk.Listbox(
            self,
            activestyle="dotbox",
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_4}"),
            foreground="#cdd3ce",
            background="#101414",
            exportselection=0,
            width=70,
            height=15,
        )
        self.listbox.pack(fill="both", expand=True)

        self.button_frame = tk.Frame(self)
        self.button_frame.pack()

        img_mapper = img_mapper or {}
        self.up_button = ttk.Button(self.button_frame, image=img_mapper["up"], command=self.move_up)
        self.up_button.grid(row=0, column=0)

        self.down_button = ttk.Button(self.button_frame, image=img_mapper["down"], command=self.move_down)
        self.down_button.grid(row=0, column=1)

        if command and image_sel:
            self.move_button = ttk.Button(self.button_frame, image=image_sel, command=command)
            self.move_button.grid(row=0, column=2)

        self.duplicate_button = ttk.Button(
            self.button_frame,
            image=img_mapper["copy"],
            command=self.duplicate_selected,
        )
        self.duplicate_button.grid(row=0, column=3)

        self.delete_button = ttk.Button(
            self.button_frame,
            image=img_mapper["clear"],
            command=self.delete_selected,
        )
        self.delete_button.grid(row=0, column=4)

    def delete_selected(self) -> None:
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]
            path_to_delete = self.basename_to_path[basename]
            del self.basename_to_path[basename]
            self.path_list.remove(path_to_delete)
            self.listbox.delete(selected)
            self.update_displayed_index()

    def select_input(self, inputs: list[str] | None = None) -> None:
        files = inputs if inputs else runtime.root.show_file_dialog(dialoge_type=runtime.MULTIPLE_FILE)
        for file in files:
            if file not in self.path_list:
                basename = os.path.basename(file)
                self.listbox.insert(tk.END, basename)
                self.path_list.append(file)
                self.basename_to_path[basename] = file
        self.update_displayed_index(is_acc_dupe=False)

    def duplicate_selected(self) -> None:
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]
            path_to_duplicate = self.basename_to_path[basename]
            self.path_list.append(path_to_duplicate)
            self.update_displayed_index()

    def update_displayed_index(self, inputs: list[str] | None = None, is_acc_dupe: bool = True) -> None:
        self.basename_to_path = {}

        if inputs:
            self.path_list = inputs

        basename_count = Counter(self.path_list)

        for index in range(len(self.path_list)):
            basename = os.path.basename(self.path_list[index])

            if basename_count[self.path_list[index]] > 1 and is_acc_dupe:
                duplicate_index = 1
                new_basename = f"{basename} ({duplicate_index})"
                while new_basename in self.basename_to_path:
                    duplicate_index += 1
                    new_basename = f"{basename} ({duplicate_index})"
                basename = new_basename

            self.basename_to_path[basename] = self.path_list[index]
            self.listbox.delete(index)
            self.listbox.insert(index, f"{index + 1}: {basename}")

    def move_up(self) -> None:
        selected = self.listbox.curselection()
        if selected and selected[0] > 0:
            self.path_list[selected[0] - 1], self.path_list[selected[0]] = (
                self.path_list[selected[0]],
                self.path_list[selected[0] - 1],
            )
            self.update_displayed_index()
            self.listbox.select_set(selected[0] - 1)

    def move_down(self) -> None:
        selected = self.listbox.curselection()
        if selected and selected[0] < self.listbox.size() - 1:
            self.path_list[selected[0] + 1], self.path_list[selected[0]] = (
                self.path_list[selected[0]],
                self.path_list[selected[0] + 1],
            )
            self.update_displayed_index()
            self.listbox.select_set(selected[0] + 1)

    def get_selected_path(self) -> str | None:
        selected = self.listbox.curselection()
        if selected:
            basename = self.listbox.get(selected[0]).split(": ", 1)[1]
            return self.basename_to_path[basename]
        return None


class ComboBoxEditableMenu(ttk.Combobox):
    def __init__(
        self,
        master: Any = None,
        pattern: str | None = None,
        default: Any = None,
        width: int | None = None,
        is_stay_disabled: bool = False,
        **kw: Any,
    ):
        if "values" in kw:
            kw["values"] = tuple(kw["values"]) + (runtime.OPT_SEPARATOR, runtime.USER_INPUT)
        else:
            kw["values"] = runtime.USER_INPUT

        super().__init__(master, **kw)

        self.textvariable = kw.get("textvariable", tk.StringVar())
        self.pattern = pattern
        self.test = 1
        self.tooltip = ToolTip(self)
        self.is_user_input_var = tk.BooleanVar(value=False)
        self.is_stay_disabled = is_stay_disabled

        self.default = default if isinstance(default, (str, int)) else default[0]

        self.menu_combobox_configure()
        self.var_validation(is_start_up=True)

        if width:
            self.configure(width=width)

    def menu_combobox_configure(self) -> None:
        self.bind("<<ComboboxSelected>>", self.check_input)
        self.bind("<Button-1>", lambda e: self.focus())
        self.bind("<FocusIn>", self.focusin)
        self.bind("<FocusOut>", lambda e: self.var_validation(is_focus_only=True))

        if runtime.is_macos:
            self.bind("<Enter>", lambda e: self.button_released())

        if not self.is_stay_disabled:
            self.configure(state=runtime.READ_ONLY)

    def check_input(self, event: Any = None) -> None:
        if self.textvariable.get() == runtime.USER_INPUT:
            self.textvariable.set("")
            self.configure(state=tk.NORMAL)
            self.focus()
            self.selection_range(0, 0)
        else:
            self.var_validation()

    def var_validation(self, is_focus_only: bool = False, is_start_up: bool = False) -> None:
        if is_focus_only and not self.is_stay_disabled:
            self.configure(state=runtime.READ_ONLY)

        if re.fullmatch(self.pattern, self.textvariable.get()) is None:
            if not is_start_up and self.textvariable.get() not in (runtime.OPT_SEPARATOR, runtime.USER_INPUT):
                self.tooltip.showtip(runtime.INVALID_INPUT_E, True)

            self.textvariable.set(self.default)

    def button_released(self, e: Any = None) -> None:
        self.event_generate("<Button-3>")
        self.event_generate("<ButtonRelease-3>")

    def focusin(self, e: Any) -> None:
        self.selection_clear()
        if runtime.is_macos:
            self.event_generate("<Leave>")


class ComboBoxMenu(ttk.Combobox):
    def __init__(
        self,
        master: Any = None,
        dropdown_name: str | None = None,
        offset: int = 185,
        is_download_menu: bool = False,
        command: Any = None,
        width: int | None = None,
        **kw: Any,
    ):
        super().__init__(master, **kw)

        self.menu_combobox_configure(is_download_menu, width=width)

        if dropdown_name and "values" in kw:
            self.update_dropdown_size(kw["values"], dropdown_name, offset)

        if command:
            self.command(command)

    def menu_combobox_configure(self, is_download_menu: bool = False, command: Any = None, width: int | None = None) -> None:
        self.bind("<FocusIn>", self.focusin)
        self.bind("<MouseWheel>", lambda e: "break")

        if runtime.is_macos:
            self.bind("<Enter>", lambda e: self.button_released())

        if not is_download_menu:
            self.configure(state=runtime.READ_ONLY)

        if command:
            self.command(command)

        if width:
            self.configure(width=width)

    def button_released(self, e: Any = None) -> None:
        self.event_generate("<Button-3>")
        self.event_generate("<ButtonRelease-3>")

    def command(self, command: Any) -> None:
        if not self.bind("<<ComboboxSelected>>"):
            self.bind("<<ComboboxSelected>>", command)

    def focusin(self, e: Any) -> None:
        self.selection_clear()
        if runtime.is_macos:
            self.event_generate("<Leave>")

    def update_dropdown_size(
        self,
        option_list: list[str] | tuple[str, ...],
        dropdown_name: str,
        offset: int = 185,
        command: Any = None,
    ) -> None:
        dropdown_style = f"{dropdown_name}.TCombobox"
        if option_list:
            max_string = max(option_list, key=len)
            font = Font(font=self.cget("font"))
            width_in_pixels = font.measure(max_string) - offset
            width_in_pixels = 0 if width_in_pixels < 0 else width_in_pixels
        else:
            width_in_pixels = 0

        style = ttk.Style(self)
        style.configure(dropdown_style, padding=(0, 0, 0, 0), postoffset=(0, 0, width_in_pixels, 0))
        self.configure(style=dropdown_style)

        if command:
            self.command(command)


class ThreadSafeConsole(tk.Text):
    """Text widget which is thread safe for tkinter."""

    def __init__(self, master: Any, **options: Any):
        tk.Text.__init__(self, master, **options)
        self.queue = queue.Queue()
        self.update_me()

    def write(self, line: Any) -> None:
        self.queue.put(line)

    def clear(self) -> None:
        self.queue.put(None)

    def update_me(self) -> None:
        self.configure(state=tk.NORMAL)
        try:
            while 1:
                line = self.queue.get_nowait()
                if line is None:
                    self.delete(1.0, tk.END)
                else:
                    self.insert(tk.END, str(line))
                self.see(tk.END)
                self.update_idletasks()
        except queue.Empty:
            pass
        self.configure(state=tk.DISABLED)
        self.after(100, self.update_me)

    def copy_text(self) -> None:
        highlighted_text = self.selection_get()
        self.clipboard_clear()
        self.clipboard_append(highlighted_text)

    def select_all_text(self) -> None:
        self.tag_add("sel", "1.0", "end")
