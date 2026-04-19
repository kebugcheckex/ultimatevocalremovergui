"""Tk-specific helpers extracted from UVR.py."""

from __future__ import annotations

from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


def drop(event: Any, accept_mode: str = "files") -> list[str] | None:
    path = event.data
    if accept_mode == "folder":
        path = path.replace("{", "").replace("}", "")
        if not runtime.os.path.isdir(path):
            runtime.messagebox.showerror(
                parent=runtime.root,
                title=runtime.INVALID_FOLDER_ERROR_TEXT[0],
                message=runtime.INVALID_FOLDER_ERROR_TEXT[1],
            )
            return None
        runtime.root.export_path_var.set(path)
    elif accept_mode in ["files", runtime.FILE_1, runtime.FILE_2, runtime.FILE_1_LB, runtime.FILE_2_LB]:
        path = path.replace("{", "").replace("}", "")
        for dnd_file in runtime.dnd_path_check:
            path = path.replace(f" {dnd_file}", f";{dnd_file}")
        path = path.split(";")
        path[-1] = path[-1].replace(";", "")

        if accept_mode == "files":
            runtime.root.inputPaths = tuple(path)
            runtime.root.process_input_selections()
            runtime.root.update_inputPaths()
        elif accept_mode in [runtime.FILE_1, runtime.FILE_2]:
            if len(path) == 2:
                runtime.root.select_audiofile(path[0])
                runtime.root.select_audiofile(path[1], is_primary=False)
                runtime.root.DualBatch_inputPaths = []
                runtime.root.check_dual_paths()
            elif len(path) == 1:
                if accept_mode == runtime.FILE_1:
                    runtime.root.select_audiofile(path[0])
                else:
                    runtime.root.select_audiofile(path[0], is_primary=False)
        elif accept_mode in [runtime.FILE_1_LB, runtime.FILE_2_LB]:
            return path
    else:
        return None

    return None


def read_bulliten_text_mac(path: str, data: str) -> str:
    try:
        with open(path, "w") as handle:
            handle.write(data)

        if runtime.os.path.isfile(path):
            with open(path, "r") as file_handle:
                data = file_handle.read().replace("~", "•")
    except Exception:
        data = "No information available."

    return data


def open_link(event: Any, link: str | None = None) -> None:
    runtime.webbrowser.open(link)


def auto_hyperlink(text_widget: Any) -> None:
    content = text_widget.get("1.0", runtime.tk.END)
    urls = runtime.re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        content,
    )

    for url in urls:
        start_idx = content.find(url)
        end_idx = start_idx + len(url)

        start_line = content.count("\n", 0, start_idx) + 1
        start_char = start_idx - content.rfind("\n", 0, start_idx) - 1
        end_line = content.count("\n", 0, end_idx) + 1
        end_char = end_idx - content.rfind("\n", 0, end_idx) - 1

        start_tag = f"{start_line}.{start_char}"
        end_tag = f"{end_line}.{end_char}"

        text_widget.tag_add(url, start_tag, end_tag)
        text_widget.tag_configure(url, foreground=runtime.FG_COLOR, underline=True)
        text_widget.tag_bind(url, "<Button-1>", lambda e, link=url: open_link(e, link))
        text_widget.tag_bind(url, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
        text_widget.tag_bind(url, "<Leave>", lambda e: text_widget.config(cursor="arrow"))


def vip_downloads(password: str, link_type: tuple[bytes, bytes] | Any = None) -> str:
    """Attempts to decrypt VIP model link with given input code."""
    link_type = link_type or runtime.VIP_REPO

    try:
        kdf = runtime.PBKDF2HMAC(
            algorithm=runtime.hashes.SHA256(),
            length=32,
            salt=link_type[0],
            iterations=390000,
        )

        key = runtime.base64.urlsafe_b64encode(kdf.derive(bytes(password, "utf-8")))
        fernet = runtime.Fernet(key)

        return str(fernet.decrypt(link_type[1]), "UTF-8")
    except Exception:
        return runtime.NO_CODE
