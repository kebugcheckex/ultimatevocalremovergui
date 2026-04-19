"""System helpers extracted from UVR.py."""

from __future__ import annotations

import os
import queue
import time
from collections.abc import Callable
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


def get_execution_time(function: Callable[[], Any], name: str) -> None:
    start = time.time()
    function()
    end = time.time()
    print(f"{name} Execution Time: ", end - start)


def right_click_release_linux(window: Any, top_win: Any | None = None) -> None:
    if runtime.OPERATING_SYSTEM == "Linux":
        runtime.root.bind("<Button-1>", lambda e: window.destroy())
        if top_win:
            top_win.bind("<Button-1>", lambda e: window.destroy())


def close_process(q: queue.Queue) -> None:
    def close_splash() -> None:
        name = "UVR_Launcher.exe"
        for process in runtime.psutil.process_iter(attrs=["name"]):
            process_name = process.info.get("name")

            if process_name == name:
                try:
                    process.terminate()
                    q.put(f"{name} terminated.")
                    break
                except runtime.psutil.NoSuchProcess as exc:
                    q.put(f"Error terminating {name}: {exc}")

                    try:
                        with open(runtime.SPLASH_DOC, "w") as handle:
                            handle.write("1")
                    except Exception:
                        print("No splash screen.")

    thread = runtime.KThread(target=close_splash)
    thread.start()


def extract_stems(audio_file_base: str, export_path: str) -> list[str]:
    filenames = [file for file in os.listdir(export_path) if file.startswith(audio_file_base)]

    pattern = r"\(([^()]+)\)(?=[^()]*\.wav)"
    stem_list: list[str] = []

    for filename in filenames:
        match = runtime.re.search(pattern, filename)
        if match:
            stem_list.append(match.group(1))

    counter = runtime.Counter(stem_list)
    filtered_list = [item for item in stem_list if counter[item] > 1]

    return list(set(filtered_list))
