"""Shared menu helpers extracted from UVR.py."""

from __future__ import annotations

from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class MenuHelpers:
    def __init__(self, ui: Any):
        self.ui = ui

    def vocal_splitter_button_opt(self, top_window: Any, frame: Any, pady: Any, width: int = 15) -> None:
        vocal_splitter_button = runtime.ttk.Button(
            frame,
            text=runtime.VOCAL_SPLITTER_OPTIONS_TEXT,
            command=lambda: self.ui.pop_up_set_vocal_splitter(top_window),
            width=width,
        )
        vocal_splitter_button.grid(pady=pady)

    def menu_placement(
        self,
        window: Any,
        title: str,
        pop_up: bool = False,
        is_help_hints: bool = False,
        close_function: Any = None,
        frame_list: list[Any] | None = None,
        top_window: Any = None,
    ) -> None:
        top_window = top_window if top_window else runtime.root
        window.withdraw()
        window.resizable(False, False)
        window.wm_transient(top_window)
        window.title(title)
        if runtime.is_windows:
            window.iconbitmap(runtime.ICON_IMG_PATH)
        else:
            self.ui.tk.call("wm", "iconphoto", window._w, runtime.tk.PhotoImage(file=runtime.MAIN_ICON_IMG_PATH))

        root_location_x = runtime.root.winfo_x()
        root_location_y = runtime.root.winfo_y()
        root_x = runtime.root.winfo_width()
        root_y = runtime.root.winfo_height()
        window.update() if runtime.is_windows else window.update_idletasks()
        sub_menu_x = window.winfo_reqwidth()
        sub_menu_y = window.winfo_reqheight()
        menu_offset_x = (root_x - sub_menu_x) // 2
        menu_offset_y = (root_y - sub_menu_y) // 2
        window.geometry("+%d+%d" % (root_location_x + menu_offset_x, root_location_y + menu_offset_y))

        window.deiconify()
        window.configure(bg=runtime.BG_COLOR)

        if not runtime.is_macos:
            self.ui.toplevels.append(window)

        def right_click_menu(event: Any) -> None:
            help_hints_label = "Enable" if self.ui.help_hints_var.get() is False else "Disable"
            help_hints_bool = True if self.ui.help_hints_var.get() is False else False
            right_click_menu = runtime.tk.Menu(self.ui, font=(runtime.MAIN_FONT_NAME, runtime.FONT_SIZE_1), tearoff=0)
            if is_help_hints:
                right_click_menu.add_command(
                    label=f"{help_hints_label} Help Hints",
                    command=lambda: self.ui.help_hints_var.set(help_hints_bool),
                )
            right_click_menu.add_command(label="Exit Window", command=close_function)

            try:
                right_click_menu.tk_popup(event.x_root, event.y_root)
                runtime.right_click_release_linux(right_click_menu, window)
            finally:
                right_click_menu.grab_release()

        if close_function:
            window.bind(runtime.right_click_button, lambda e: right_click_menu(e))

        if frame_list:
            for frame in frame_list:
                self.ui.focus_out_widgets(frame.winfo_children() + [frame], frame)

        if pop_up:
            window.attributes("-topmost", "true") if runtime.OPERATING_SYSTEM == "Linux" else None
            window.grab_set()
            runtime.root.wait_window(window)

    def adjust_widget_widths(self, frame: Any) -> None:
        def resize_widget(widgets: list[Any]) -> None:
            max_width = max(wid.winfo_width() for wid in widgets)
            for wid in widgets:
                if isinstance(wid, (runtime.tk.Button, runtime.ttk.Combobox)):
                    wid.configure(width=int(max_width / wid.winfo_pixels("1c")))
                else:
                    wid.configure(width=max_width)

        resize_widget([widget for widget in frame.winfo_children() if isinstance(widget, runtime.tk.Button)])
        resize_widget([widget for widget in frame.winfo_children() if isinstance(widget, runtime.ttk.Combobox)])

    def menu_move_tab(self, notebook: Any, tab_text: str, new_position: int) -> None:
        tab_id = None
        for tab in notebook.tabs():
            if notebook.tab(tab, "text") == tab_text:
                tab_id = tab
                break

        if tab_id is None:
            print(f"No tab named '{tab_text}'")
            return

        notebook.forget(tab_id)
        notebook.insert(new_position, tab_id)

    def menu_tab_control(self, toplevel: Any, ai_network_vars: Any, is_demucs: bool = False, is_mdxnet: bool = False):
        tab_control = runtime.ttk.Notebook(toplevel)

        tab1 = runtime.ttk.Frame(tab_control)
        tab2 = runtime.ttk.Frame(tab_control)

        tab_control.add(tab1, text=runtime.SETTINGS_GUIDE_TEXT)
        tab_control.add(tab2, text=runtime.SECONDARY_MODEL_TEXT)

        tab1.grid_rowconfigure(0, weight=1)
        tab1.grid_columnconfigure(0, weight=1)
        tab2.grid_rowconfigure(0, weight=1)
        tab2.grid_columnconfigure(0, weight=1)

        if is_demucs or is_mdxnet:
            tab3 = runtime.ttk.Frame(tab_control)
            tab_control.add(
                tab3,
                text=runtime.PREPROCESS_MODEL_CHOOSE_TEXT if is_demucs else runtime.MDX23C_ONLY_OPTIONS_TEXT,
            )
            tab3.grid_rowconfigure(0, weight=1)
            tab3.grid_columnconfigure(0, weight=1)

        tab_control.pack(expand=1, fill=runtime.tk.BOTH)

        self.ui.tab2_loaded = False
        self.ui.tab3_loaded = False

        def on_tab_selected(event: Any) -> None:
            load_screen = False
            if event.widget.tab("current", option="text") == "Secondary Model" and not self.ui.tab2_loaded:
                tab = tab2
                self.ui.tab2_loaded = True
                tab_load = lambda: self.ui.menu_secondary_model(tab, ai_network_vars)
                load_screen = True
            elif (
                event.widget.tab("current", option="text") == runtime.PREPROCESS_MODEL_CHOOSE_TEXT
                and not self.ui.tab3_loaded
            ):
                tab = tab3
                self.ui.tab3_loaded = True
                tab_load = lambda: self.ui.menu_preproc_model(tab)
                load_screen = True
            else:
                return

            loading_label = runtime.ttk.Label(
                tab,
                text="Updating model lists...",
                font=runtime.Font(family=runtime.MAIN_FONT_NAME, size=14),
            )
            loading_label.place(relx=0.5, rely=0.5, anchor=runtime.tk.CENTER)
            tab.update_idletasks()
            tab_load()
            loading_label.destroy()

        tab_control.bind("<<NotebookTabChanged>>", on_tab_selected)

        if is_demucs or is_mdxnet:
            return tab1, tab3
        return tab1
