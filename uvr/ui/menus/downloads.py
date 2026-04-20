"""Download-related menu and popup flows extracted from UVR.py."""

from __future__ import annotations

import json
import os
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class DownloadMenus:
    def __init__(self, ui: Any):
        self.ui = ui

    def pop_up_update_confirmation(self) -> None:
        """Ask the user whether they want to update."""

        is_new_update = self.ui.online_data_refresh(confirmation_box=True)
        is_download_in_app_var = runtime.tk.BooleanVar(value=False)

        def update_type() -> None:
            if is_download_in_app_var.get():
                self.ui.download_item(is_update_app=True)
            else:
                runtime.webbrowser.open_new_tab(self.ui.download_update_link_var.get())

            update_confirmation_win.destroy()

        if is_new_update:
            update_confirmation_win = runtime.tk.Toplevel()

            update_confirmation_Frame = self.ui.menu_FRAME_SET(update_confirmation_win)
            update_confirmation_Frame.grid(row=0)

            self.ui.menu_title_LABEL_SET(update_confirmation_Frame, runtime.UPDATE_FOUND_TEXT, width=15).grid(
                row=0, column=0, padx=0, pady=runtime.MENU_PADDING_2
            )

            self.ui.menu_sub_LABEL_SET(
                update_confirmation_Frame,
                runtime.UPDATE_CONFIRMATION_TEXT,
                font_size=runtime.FONT_SIZE_3,
            ).grid(row=1, column=0, padx=0, pady=runtime.MENU_PADDING_1)

            runtime.ttk.Button(
                update_confirmation_Frame,
                text=runtime.YES_TEXT,
                command=update_type,
            ).grid(row=2, column=0, padx=0, pady=runtime.MENU_PADDING_1)

            runtime.ttk.Button(
                update_confirmation_Frame,
                text=runtime.NO_TEXT,
                command=lambda: update_confirmation_win.destroy(),
            ).grid(row=3, column=0, padx=0, pady=runtime.MENU_PADDING_1)

            if runtime.is_windows:
                runtime.ttk.Checkbutton(
                    update_confirmation_Frame,
                    variable=is_download_in_app_var,
                    text="Download Update in Application",
                ).grid(row=4, column=0, padx=0, pady=runtime.MENU_PADDING_1)

            self.ui.menu_placement(update_confirmation_win, runtime.CONFIRM_UPDATE_TEXT, pop_up=True)

    def menu_manual_downloads(self) -> None:
        manual_downloads_menu = runtime.tk.Toplevel()
        model_selection_var = runtime.tk.StringVar(value=runtime.SELECT_MODEL_TEXT)

        model_data: dict[str, Any] | None = None

        if self.ui.is_online:
            model_data = self.ui.online_data
            with open(runtime.DOWNLOAD_MODEL_CACHE, "w") as json_file:
                json.dump(model_data, json_file)
        elif os.path.isfile(runtime.DOWNLOAD_MODEL_CACHE):
            with open(runtime.DOWNLOAD_MODEL_CACHE, "r") as json_file:
                model_data = json.load(json_file)

        if not model_data:
            model_data = {
                "vr_download_list": {},
                "mdx_download_list": {},
                "mdx23c_download_list": {},
                "demucs_download_list": {},
            }

        vr_download_list = dict(model_data["vr_download_list"])
        mdx_download_list = dict(model_data["mdx_download_list"])
        demucs_download_list = dict(model_data["demucs_download_list"])
        mdx_download_list.update(model_data["mdx23c_download_list"])

        def create_link(link: str):
            return lambda: runtime.webbrowser.open_new_tab(link)

        def get_links() -> None:
            for widget in manual_downloads_link_Frame.winfo_children():
                widget.destroy()

            main_selection = model_selection_var.get()
            main_row = 0

            self.ui.menu_sub_LABEL_SET(manual_downloads_link_Frame, "Download Link(s)").grid(
                row=0, column=0, padx=0, pady=runtime.MENU_PADDING_4
            )

            if runtime.VR_ARCH_TYPE in main_selection:
                main_selection = vr_download_list[main_selection]
                model_dir = runtime.VR_MODELS_DIR
            elif runtime.MDX_ARCH_TYPE in main_selection or runtime.MDX_23_NAME in main_selection:
                if isinstance(mdx_download_list[main_selection], dict):
                    main_selection = mdx_download_list[main_selection]
                    main_selection = list(main_selection.keys())[0]
                else:
                    main_selection = mdx_download_list[main_selection]

                model_dir = runtime.MDX_MODELS_DIR
            else:
                model_dir = (
                    runtime.DEMUCS_NEWER_REPO_DIR
                    if "v3" in main_selection or "v4" in main_selection
                    else runtime.DEMUCS_MODELS_DIR
                )
                main_selection = demucs_download_list[main_selection]

            if isinstance(main_selection, dict):
                for link_target in main_selection.values():
                    main_row += 1
                    button_text = f" - Item {main_row}" if len(main_selection.keys()) >= 2 else ""
                    runtime.ttk.Button(
                        manual_downloads_link_Frame,
                        text=f"Open Link to Model{button_text}",
                        command=create_link(link_target),
                    ).grid(row=main_row, column=0, padx=0, pady=runtime.MENU_PADDING_1)
            else:
                link = f"{runtime.NORMAL_REPO}{main_selection}"
                runtime.ttk.Button(
                    manual_downloads_link_Frame,
                    text=runtime.OPEN_LINK_TO_MODEL_TEXT,
                    command=lambda: runtime.webbrowser.open_new_tab(link),
                ).grid(row=1, column=0, padx=0, pady=runtime.MENU_PADDING_2)

            self.ui.menu_sub_LABEL_SET(manual_downloads_link_Frame, runtime.SELECTED_MODEL_PLACE_PATH_TEXT).grid(
                row=main_row + 2, column=0, padx=0, pady=runtime.MENU_PADDING_4
            )
            runtime.ttk.Button(
                manual_downloads_link_Frame,
                text=runtime.OPEN_MODEL_DIRECTORY_TEXT,
                command=lambda: runtime.OPEN_FILE_func(model_dir),
            ).grid(row=main_row + 3, column=0, padx=0, pady=runtime.MENU_PADDING_1)

        manual_downloads_menu_Frame = self.ui.menu_FRAME_SET(manual_downloads_menu)
        manual_downloads_menu_Frame.grid(row=0)

        manual_downloads_link_Frame = self.ui.menu_FRAME_SET(manual_downloads_menu, thickness=5)
        manual_downloads_link_Frame.grid(row=1)

        self.ui.menu_title_LABEL_SET(
            manual_downloads_menu_Frame,
            runtime.MANUAL_DOWNLOADS_TEXT,
            width=45,
        ).grid(row=0, column=0, padx=0, pady=runtime.MENU_PADDING_3)

        self.ui.menu_sub_LABEL_SET(manual_downloads_menu_Frame, runtime.SELECT_MODEL_TEXT).grid(
            row=1, column=0, padx=0, pady=runtime.MENU_PADDING_1
        )

        manual_downloads_menu_select_Option = runtime.ttk.OptionMenu(manual_downloads_menu_Frame, model_selection_var)
        manual_downloads_menu_select_VR_Option = runtime.tk.Menu(manual_downloads_menu_select_Option["menu"])
        manual_downloads_menu_select_MDX_Option = runtime.tk.Menu(manual_downloads_menu_select_Option["menu"])
        manual_downloads_menu_select_DEMUCS_Option = runtime.tk.Menu(manual_downloads_menu_select_Option["menu"])
        manual_downloads_menu_select_Option["menu"].add_cascade(
            label="VR Models", menu=manual_downloads_menu_select_VR_Option
        )
        manual_downloads_menu_select_Option["menu"].add_cascade(
            label="MDX-Net Models", menu=manual_downloads_menu_select_MDX_Option
        )
        manual_downloads_menu_select_Option["menu"].add_cascade(
            label="Demucs Models", menu=manual_downloads_menu_select_DEMUCS_Option
        )

        for model_selection_vr, model_name in vr_download_list.items():
            if not os.path.isfile(os.path.join(runtime.VR_MODELS_DIR, model_name)):
                manual_downloads_menu_select_VR_Option.add_radiobutton(
                    label=model_selection_vr,
                    variable=model_selection_var,
                    command=get_links,
                )

        for model_selection_mdx, model_name in mdx_download_list.items():
            if isinstance(model_name, dict):
                items_list = list(model_name.items())
                model_name, config = items_list[0]
                config_link = f"{runtime.MDX23_CONFIG_CHECKS}{config}"
                config_local = os.path.join(runtime.MDX_C_CONFIG_PATH, config)
                if not os.path.isfile(config_local):
                    try:
                        with runtime.urllib.request.urlopen(config_link) as response:
                            with open(config_local, "wb") as out_file:
                                out_file.write(response.read())
                    except Exception:
                        model_name = None

            if model_name and not os.path.isfile(os.path.join(runtime.MDX_MODELS_DIR, model_name)):
                manual_downloads_menu_select_MDX_Option.add_radiobutton(
                    label=model_selection_mdx,
                    variable=model_selection_var,
                    command=get_links,
                )

        for model_selection_demucs in demucs_download_list.keys():
            manual_downloads_menu_select_DEMUCS_Option.add_radiobutton(
                label=model_selection_demucs,
                variable=model_selection_var,
                command=get_links,
            )

        manual_downloads_menu_select_Option.grid(row=2, column=0, padx=0, pady=runtime.MENU_PADDING_1)

        self.ui.menu_placement(
            manual_downloads_menu,
            runtime.MANUAL_DOWNLOADS_TEXT,
            pop_up=True,
            close_function=lambda: manual_downloads_menu.destroy(),
        )

    def pop_up_user_code_input(self) -> None:
        """Input VIP Code."""

        self.ui.user_code_validation_var.set("")
        self.ui.user_code = runtime.tk.Toplevel()

        user_code_Frame = self.ui.menu_FRAME_SET(self.ui.user_code)
        user_code_Frame.grid(row=0)

        self.ui.menu_title_LABEL_SET(
            user_code_Frame,
            runtime.USER_DOWNLOAD_CODES_TEXT,
            width=20,
        ).grid(row=0, column=0, padx=0, pady=runtime.MENU_PADDING_1)

        self.ui.menu_sub_LABEL_SET(user_code_Frame, runtime.DOWNLOAD_CODE_TEXT).grid(pady=runtime.MENU_PADDING_1)

        self.ui.user_code_Entry = runtime.ttk.Entry(
            user_code_Frame,
            textvariable=self.ui.user_code_var,
            justify="center",
        )
        self.ui.user_code_Entry.grid(pady=runtime.MENU_PADDING_1)
        self.ui.user_code_Entry.bind(runtime.right_click_button, self.ui.right_click_menu_popup)
        self.ui.current_text_box = self.ui.user_code_Entry

        tooltip = runtime.ToolTip(self.ui.user_code_Entry)

        def invalid_message_(text: str, is_success_message: bool) -> None:
            tooltip.hidetip()
            tooltip.showtip(text, True, is_success_message)

        self.ui.spacer_label(user_code_Frame)

        runtime.ttk.Button(
            user_code_Frame,
            text=runtime.CONFIRM_TEXT,
            command=lambda: self.ui.download_validate_code(confirm=True, code_message=invalid_message_),
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            user_code_Frame,
            text=runtime.CANCEL_TEXT,
            command=lambda: self.ui.user_code.destroy(),
        ).grid(pady=runtime.MENU_PADDING_1)

        self.ui.menu_title_LABEL_SET(user_code_Frame, text=runtime.SUPPORT_UVR_TEXT, width=20).grid(
            pady=runtime.MENU_PADDING_1
        )

        runtime.tk.Label(
            user_code_Frame,
            text=runtime.GET_DL_VIP_CODE_TEXT,
            font=(runtime.MAIN_FONT_NAME, f"{runtime.FONT_SIZE_1}"),
            foreground=runtime.FG_COLOR,
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            user_code_Frame,
            text=runtime.UVR_PATREON_LINK_TEXT,
            command=lambda: runtime.webbrowser.open_new_tab(runtime.DONATE_LINK_PATREON),
        ).grid(pady=runtime.MENU_PADDING_1)

        runtime.ttk.Button(
            user_code_Frame,
            text=runtime.BMAC_UVR_TEXT,
            command=lambda: runtime.webbrowser.open_new_tab(runtime.DONATE_LINK_BMAC),
        ).grid(pady=runtime.MENU_PADDING_1)

        self.ui.menu_placement(self.ui.user_code, runtime.INPUT_CODE_TEXT, pop_up=True)
