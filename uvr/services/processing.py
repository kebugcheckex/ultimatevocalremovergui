"""Processing orchestration extracted from UVR.py."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class ProcessingController:
    def __init__(self, ui: Any):
        self.ui = ui

    def process_initialize(self) -> None:
        if not (
            self.ui.chosen_process_method_var.get() == runtime.AUDIO_TOOLS
            and self.ui.chosen_audio_tool_var.get() in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]
            and self.ui.fileOneEntry_var.get()
            and self.ui.fileTwoEntry_var.get()
        ) and not (self.ui.inputPaths and os.path.isfile(self.ui.inputPaths[0])):
            self.ui.error_dialoge(runtime.INVALID_INPUT)
            return

        if not os.path.isdir(self.ui.export_path_var.get()):
            self.ui.error_dialoge(runtime.INVALID_EXPORT)
            return

        if not self.ui.process_storage_check():
            return

        if self.ui.chosen_process_method_var.get() != runtime.AUDIO_TOOLS:
            if not self.ui.process_preliminary_checks():
                error_msg = (
                    runtime.INVALID_ENSEMBLE
                    if self.ui.chosen_process_method_var.get() == runtime.ENSEMBLE_MODE
                    else runtime.INVALID_MODEL
                )
                self.ui.error_dialoge(error_msg)
                return
            target_function = self.process_start
        else:
            target_function = self.process_tool_start

        self.ui.active_processing_thread = runtime.KThread(target=target_function)
        self.ui.active_processing_thread.start()

    def process_button_init(self) -> None:
        self.ui.auto_save()
        self.ui.conversion_Button_Text_var.set(runtime.WAIT_PROCESSING)
        self.ui.conversion_Button.configure(state=runtime.tk.DISABLED)
        self.ui.command_Text.clear()

    def process_get_base_text(self, total_files: int, file_num: int, is_dual: bool = False) -> str:
        init_text = "Files" if is_dual else "File"
        return f"{init_text} {file_num}/{total_files} "

    def process_update_progress(self, total_files: int, step: float = 1) -> None:
        total_count = self.ui.true_model_count * total_files
        base = 100 / total_count
        progress = base * self.ui.iteration - base
        progress += base * step
        self.ui.progress_bar_main_var.set(progress)
        self.ui.conversion_Button_Text_var.set(f"Process Progress: {int(progress)}%")

    def confirm_stop_process(self) -> None:
        self.ui.auto_save()
        if self.ui.thread_check(self.ui.active_processing_thread):
            confirm = runtime.messagebox.askyesno(
                parent=runtime.root,
                title=runtime.STOP_PROCESS_CONFIRM[0],
                message=runtime.STOP_PROCESS_CONFIRM[1],
            )
            if confirm:
                try:
                    self.ui.active_processing_thread.terminate()
                finally:
                    self.ui.is_process_stopped = True
                    self.ui.command_Text.write(runtime.PROCESS_STOPPED_BY_USER)
        else:
            self.ui.clear_cache_torch = True

    def process_end(self, error: Exception | None = None) -> None:
        self.ui.auto_save()
        self.ui.cached_sources_clear()
        self.ui.clear_cache_torch = True
        self.ui.conversion_Button_Text_var.set(runtime.START_PROCESSING)
        self.ui.conversion_Button.configure(state=runtime.tk.NORMAL)
        self.ui.progress_bar_main_var.set(0)

        if error:
            error_message_box_text = f"{runtime.error_dialouge(error)}{runtime.ERROR_OCCURED[1]}"
            confirm = runtime.messagebox.askyesno(
                parent=runtime.root,
                title=runtime.ERROR_OCCURED[0],
                message=error_message_box_text,
            )
            if confirm:
                self.ui.is_confirm_error_var.set(True)
                self.ui.clear_cache_torch = True

            self.ui.clear_cache_torch = True
            if runtime.MODEL_MISSING_CHECK in error_message_box_text:
                self.ui.update_checkbox_text()

    def process_tool_start(self) -> None:
        def time_elapsed() -> str:
            return f'Time Elapsed: {time.strftime("%H:%M:%S", time.gmtime(int(time.perf_counter() - stime)))}'

        def get_audio_file_base(audio_file: Any) -> str:
            if audio_tool.audio_tool == runtime.MANUAL_ENSEMBLE:
                return f"{os.path.splitext(os.path.basename(input_paths[0]))[0]}"
            if audio_tool.audio_tool in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
                return f"{os.path.splitext(os.path.basename(audio_file[0]))[0]}"
            return f"{os.path.splitext(os.path.basename(audio_file))[0]}"

        def handle_ensemble(audio_inputs: Any, audio_file_base: str) -> None:
            self.ui.progress_bar_main_var.set(50)
            if self.ui.choose_algorithm_var.get() == runtime.COMBINE_INPUTS:
                audio_tool.combine_audio(audio_inputs, audio_file_base)
            else:
                audio_tool.ensemble_manual(audio_inputs, audio_file_base)
            self.ui.progress_bar_main_var.set(100)
            self.ui.command_Text.write(runtime.DONE)

        def handle_alignment_match(audio_file: Any, audio_file_base: str, command_text: Any, set_progress_bar: Any) -> None:
            audio_file_2_base = f"{os.path.splitext(os.path.basename(audio_file[1]))[0]}"
            if audio_tool.audio_tool == runtime.MATCH_INPUTS:
                audio_tool.match_inputs(audio_file, audio_file_base, command_text)
            else:
                command_text(f"{runtime.PROCESS_STARTING_TEXT}\n")
                audio_tool.align_inputs(audio_file, audio_file_base, audio_file_2_base, command_text, set_progress_bar)
            self.ui.progress_bar_main_var.set(base * file_num)
            self.ui.command_Text.write(f"{runtime.DONE}\n")

        def handle_pitch_time_shift(audio_file: str, audio_file_base: str) -> None:
            audio_tool.pitch_or_time_shift(audio_file, audio_file_base)
            self.ui.progress_bar_main_var.set(base * file_num)
            self.ui.command_Text.write(runtime.DONE)

        multiple_files = False
        stime = time.perf_counter()
        self.process_button_init()
        input_paths = self.ui.inputPaths
        is_verified_audio = True
        is_dual = False
        is_model_sample_mode = self.ui.model_sample_mode_var.get()
        self.ui.iteration = 0
        self.ui.true_model_count = 1
        self.ui.process_check_wav_type()
        process_complete_text = runtime.PROCESS_COMPLETE

        if self.ui.chosen_audio_tool_var.get() in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
            if self.ui.DualBatch_inputPaths:
                input_paths = tuple(self.ui.DualBatch_inputPaths)
            else:
                if not self.ui.fileOneEntry_Full_var.get() or not self.ui.fileTwoEntry_Full_var.get():
                    self.ui.command_Text.write(runtime.NOT_ENOUGH_ERROR_TEXT)
                    self.process_end()
                    return
                input_paths = [(self.ui.fileOneEntry_Full_var.get(), self.ui.fileTwoEntry_Full_var.get())]

        try:
            total_files = len(input_paths)
            if self.ui.chosen_audio_tool_var.get() == runtime.TIME_STRETCH:
                audio_tool = runtime.AudioTools(runtime.TIME_STRETCH)
                self.ui.progress_bar_main_var.set(2)
            elif self.ui.chosen_audio_tool_var.get() == runtime.CHANGE_PITCH:
                audio_tool = runtime.AudioTools(runtime.CHANGE_PITCH)
                self.ui.progress_bar_main_var.set(2)
            elif self.ui.chosen_audio_tool_var.get() == runtime.MANUAL_ENSEMBLE:
                audio_tool = runtime.Ensembler(is_manual_ensemble=True)
                multiple_files = True
                if total_files <= 1:
                    self.ui.command_Text.write(runtime.NOT_ENOUGH_ERROR_TEXT)
                    self.process_end()
                    return
            else:
                audio_tool = runtime.AudioTools(self.ui.chosen_audio_tool_var.get())
                self.ui.progress_bar_main_var.set(2)
                is_dual = True

            for file_num, audio_file in enumerate(input_paths, start=1):
                self.ui.iteration += 1
                base = 100 / total_files
                audio_file_base = get_audio_file_base(audio_file)
                self.ui.base_text = self.process_get_base_text(
                    total_files=total_files,
                    file_num=total_files if multiple_files else file_num,
                    is_dual=is_dual,
                )
                command_text = lambda text: self.ui.command_Text.write(self.ui.base_text + text)
                set_progress_bar = lambda step, inference_iterations=0: self.process_update_progress(
                    total_files=total_files,
                    step=(step + inference_iterations),
                )

                if not self.ui.verify_audio(audio_file):
                    error_text_console = f'{self.ui.base_text}"{os.path.basename(audio_file)}\\" {runtime.MISSING_MESS_TEXT}\n'
                    if total_files >= 2:
                        self.ui.command_Text.write(f"\n{error_text_console}")
                    is_verified_audio = False
                    continue

                audio_tool_action = audio_tool.audio_tool
                if audio_tool_action not in [runtime.MANUAL_ENSEMBLE, runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
                    audio_file = self.ui.create_sample(audio_file) if is_model_sample_mode else audio_file
                    self.ui.command_Text.write(
                        f'{runtime.NEW_LINE if file_num != 1 else runtime.NO_LINE}{self.ui.base_text}"{os.path.basename(audio_file)}\\".{runtime.NEW_LINES}'
                    )
                elif audio_tool_action in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
                    text_write = ("File 1", "File 2") if audio_tool_action == runtime.ALIGN_INPUTS else ("Target", "Reference")
                    if audio_file[0] != audio_file[1]:
                        self.ui.command_Text.write(f'{self.ui.base_text}{text_write[0]}:  "{os.path.basename(audio_file[0])}"{runtime.NEW_LINE}')
                        self.ui.command_Text.write(f'{self.ui.base_text}{text_write[1]}:  "{os.path.basename(audio_file[1])}"{runtime.NEW_LINES}')
                    else:
                        self.ui.command_Text.write(
                            f"{self.ui.base_text}{text_write[0]} & {text_write[1]} {runtime.SIMILAR_TEXT}{runtime.NEW_LINES}"
                        )
                        continue
                else:
                    for index, item in enumerate(input_paths):
                        self.ui.command_Text.write(f'File {index + 1} "{os.path.basename(item)}"{runtime.NEW_LINE}')
                    self.ui.command_Text.write(runtime.NEW_LINE)

                is_verified_audio = True
                if audio_tool_action not in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
                    command_text(runtime.PROCESS_STARTING_TEXT)

                if audio_tool_action == runtime.MANUAL_ENSEMBLE:
                    handle_ensemble(input_paths, audio_file_base)
                    break
                if audio_tool_action in [runtime.ALIGN_INPUTS, runtime.MATCH_INPUTS]:
                    process_complete_text = runtime.PROCESS_COMPLETE_2
                    handle_alignment_match(audio_file, audio_file_base, command_text, set_progress_bar)
                if audio_tool_action in [runtime.TIME_STRETCH, runtime.CHANGE_PITCH]:
                    handle_pitch_time_shift(audio_file, audio_file_base)

            if total_files == 1 and not is_verified_audio:
                self.ui.command_Text.write(f"{error_text_console}\n{runtime.PROCESS_FAILED}")
                self.ui.command_Text.write(time_elapsed())
                runtime.playsound(runtime.FAIL_CHIME) if self.ui.is_task_complete_var.get() else None
            else:
                self.ui.command_Text.write(f"{process_complete_text}{time_elapsed()}")
                runtime.playsound(runtime.COMPLETE_CHIME) if self.ui.is_task_complete_var.get() else None

            self.process_end()
        except Exception as exc:
            self.ui.error_log_var.set(runtime.error_text(self.ui.chosen_audio_tool_var.get(), exc))
            self.ui.command_Text.write(f"\n\n{runtime.PROCESS_FAILED}")
            self.ui.command_Text.write(time_elapsed())
            runtime.playsound(runtime.FAIL_CHIME) if self.ui.is_task_complete_var.get() else None
            self.process_end(error=exc)

    def process_determine_secondary_model(
        self,
        process_method: str,
        main_model_primary_stem: str,
        is_primary_stem_only: bool = False,
        is_secondary_stem_only: bool = False,
    ) -> tuple[Any, Any]:
        secondary_model_scale = None
        secondary_model = runtime.tk.StringVar(value=runtime.NO_MODEL)

        if process_method == runtime.VR_ARCH_TYPE:
            secondary_model_vars = self.ui.vr_secondary_model_vars
        if process_method == runtime.MDX_ARCH_TYPE:
            secondary_model_vars = self.ui.mdx_secondary_model_vars
        if process_method == runtime.DEMUCS_ARCH_TYPE:
            secondary_model_vars = self.ui.demucs_secondary_model_vars

        if main_model_primary_stem in [runtime.VOCAL_STEM, runtime.INST_STEM]:
            secondary_model = secondary_model_vars["voc_inst_secondary_model"]
            secondary_model_scale = secondary_model_vars["voc_inst_secondary_model_scale"].get()
        if main_model_primary_stem in [runtime.OTHER_STEM, runtime.NO_OTHER_STEM]:
            secondary_model = secondary_model_vars["other_secondary_model"]
            secondary_model_scale = secondary_model_vars["other_secondary_model_scale"].get()
        if main_model_primary_stem in [runtime.DRUM_STEM, runtime.NO_DRUM_STEM]:
            secondary_model = secondary_model_vars["drums_secondary_model"]
            secondary_model_scale = secondary_model_vars["drums_secondary_model_scale"].get()
        if main_model_primary_stem in [runtime.BASS_STEM, runtime.NO_BASS_STEM]:
            secondary_model = secondary_model_vars["bass_secondary_model"]
            secondary_model_scale = secondary_model_vars["bass_secondary_model_scale"].get()

        if secondary_model_scale:
            secondary_model_scale = float(secondary_model_scale)

        if secondary_model.get() != runtime.NO_MODEL:
            secondary_model = runtime.ModelData(
                secondary_model.get(),
                is_secondary_model=True,
                primary_model_primary_stem=main_model_primary_stem,
                is_primary_model_primary_stem_only=is_primary_stem_only,
                is_primary_model_secondary_stem_only=is_secondary_stem_only,
            )
            if not secondary_model.model_status:
                secondary_model = None
        else:
            secondary_model = None

        return secondary_model, secondary_model_scale

    def process_determine_demucs_pre_proc_model(self, primary_stem: str | None = None) -> Any:
        if self.ui.demucs_pre_proc_model_var.get() != runtime.NO_MODEL and self.ui.is_demucs_pre_proc_model_activate_var.get():
            pre_proc_model = runtime.ModelData(
                self.ui.demucs_pre_proc_model_var.get(),
                primary_model_primary_stem=primary_stem,
                is_pre_proc_model=True,
            )
            if pre_proc_model.model_status:
                return pre_proc_model
        return None

    def process_determine_vocal_split_model(self) -> Any:
        if self.ui.set_vocal_splitter_var.get() != runtime.NO_MODEL and self.ui.is_set_vocal_splitter_var.get():
            vocal_splitter_model = runtime.ModelData(self.ui.set_vocal_splitter_var.get(), is_vocal_split_model=True)
            if vocal_splitter_model.model_status:
                return vocal_splitter_model
        return None

    def check_only_selection_stem(self, checktype: str) -> bool:
        chosen_method = self.ui.chosen_process_method_var.get()
        is_demucs = chosen_method == runtime.DEMUCS_ARCH_TYPE

        stem_primary_label = (
            self.ui.is_primary_stem_only_Demucs_Text_var.get() if is_demucs else self.ui.is_primary_stem_only_Text_var.get()
        )
        stem_primary_bool = self.ui.is_primary_stem_only_Demucs_var.get() if is_demucs else self.ui.is_primary_stem_only_var.get()
        stem_secondary_label = (
            self.ui.is_secondary_stem_only_Demucs_Text_var.get() if is_demucs else self.ui.is_secondary_stem_only_Text_var.get()
        )
        stem_secondary_bool = (
            self.ui.is_secondary_stem_only_Demucs_var.get() if is_demucs else self.ui.is_secondary_stem_only_var.get()
        )

        if checktype == runtime.VOCAL_STEM_ONLY:
            return not (
                (runtime.VOCAL_STEM_ONLY != stem_primary_label and stem_primary_bool)
                or (runtime.VOCAL_STEM_ONLY not in stem_secondary_label and stem_secondary_bool)
            )
        if checktype == runtime.INST_STEM_ONLY:
            return (
                (
                    runtime.INST_STEM_ONLY == stem_primary_label
                    and stem_primary_bool
                    and self.ui.is_save_inst_set_vocal_splitter_var.get()
                    and self.ui.set_vocal_splitter_var.get() != runtime.NO_MODEL
                )
                or (
                    runtime.INST_STEM_ONLY == stem_secondary_label
                    and stem_secondary_bool
                    and self.ui.is_save_inst_set_vocal_splitter_var.get()
                    and self.ui.set_vocal_splitter_var.get() != runtime.NO_MODEL
                )
            )
        if checktype == runtime.IS_SAVE_VOC_ONLY:
            return (
                (runtime.VOCAL_STEM_ONLY == stem_primary_label and stem_primary_bool)
                or (runtime.VOCAL_STEM_ONLY == stem_secondary_label and stem_secondary_bool)
            )
        return (
            (runtime.INST_STEM_ONLY == stem_primary_label and stem_primary_bool)
            or (runtime.INST_STEM_ONLY == stem_secondary_label and stem_secondary_bool)
        )

    def determine_voc_split(self, models: list[Any]) -> int:
        is_vocal_active = self.check_only_selection_stem(runtime.VOCAL_STEM_ONLY) or self.check_only_selection_stem(
            runtime.INST_STEM_ONLY
        )
        if (
            self.ui.set_vocal_splitter_var.get() != runtime.NO_MODEL
            and self.ui.is_set_vocal_splitter_var.get()
            and is_vocal_active
        ):
            model_stems_list = self.ui.model_list(
                runtime.VOCAL_STEM,
                runtime.INST_STEM,
                is_dry_check=True,
                is_check_vocal_split=True,
            )
            if any(model.model_basename in model_stems_list for model in models):
                return 1
        return 0

    def process_start(self) -> None:
        stime = time.perf_counter()
        time_elapsed = lambda: f'Time Elapsed: {time.strftime("%H:%M:%S", time.gmtime(int(time.perf_counter() - stime)))}'
        export_path = self.ui.export_path_var.get()
        is_ensemble = False
        self.ui.true_model_count = 0
        self.ui.iteration = 0
        is_verified_audio = True
        self.process_button_init()
        input_paths = self.ui.inputPaths
        input_path_total_len = len(input_paths)
        is_model_sample_mode = self.ui.model_sample_mode_var.get()

        try:
            if self.ui.chosen_process_method_var.get() == runtime.ENSEMBLE_MODE:
                model, ensemble = self.ui.assemble_model_data(), runtime.Ensembler()
                export_path, is_ensemble = ensemble.ensemble_folder_name, True
            if self.ui.chosen_process_method_var.get() == runtime.VR_ARCH_PM:
                model = self.ui.assemble_model_data(self.ui.vr_model_var.get(), runtime.VR_ARCH_TYPE)
            if self.ui.chosen_process_method_var.get() == runtime.MDX_ARCH_TYPE:
                model = self.ui.assemble_model_data(self.ui.mdx_net_model_var.get(), runtime.MDX_ARCH_TYPE)
            if self.ui.chosen_process_method_var.get() == runtime.DEMUCS_ARCH_TYPE:
                model = self.ui.assemble_model_data(self.ui.demucs_model_var.get(), runtime.DEMUCS_ARCH_TYPE)

            self.ui.cached_source_model_list_check(model)
            true_model_4_stem_count = sum(
                item.demucs_4_stem_added_count if item.process_method == runtime.DEMUCS_ARCH_TYPE else 0 for item in model
            )
            true_model_pre_proc_model_count = sum(2 if item.pre_proc_model_activated else 0 for item in model)
            self.ui.true_model_count = (
                sum(2 if item.is_secondary_model_activated else 1 for item in model)
                + true_model_4_stem_count
                + true_model_pre_proc_model_count
                + self.determine_voc_split(model)
            )

            for file_num, audio_file in enumerate(input_paths, start=1):
                self.ui.cached_sources_clear()
                base_text = self.process_get_base_text(total_files=input_path_total_len, file_num=file_num)

                if self.ui.verify_audio(audio_file):
                    audio_file = self.ui.create_sample(audio_file) if is_model_sample_mode else audio_file
                    self.ui.command_Text.write(
                        f'{runtime.NEW_LINE if file_num != 1 else runtime.NO_LINE}{base_text}"{os.path.basename(audio_file)}\\".{runtime.NEW_LINES}'
                    )
                    is_verified_audio = True
                else:
                    error_text_console = f'{base_text}"{os.path.basename(audio_file)}\\" {runtime.MISSING_MESS_TEXT}\n'
                    if input_path_total_len >= 2:
                        self.ui.command_Text.write(f"\n{error_text_console}")
                    self.ui.iteration += self.ui.true_model_count
                    is_verified_audio = False
                    continue

                for current_model_num, current_model in enumerate(model, start=1):
                    self.ui.iteration += 1
                    if is_ensemble:
                        self.ui.command_Text.write(
                            f"Ensemble Mode - {current_model.model_basename} - Model {current_model_num}/{len(model)}{runtime.NEW_LINES}"
                        )

                    model_name_text = f"({current_model.model_basename})" if not is_ensemble else ""
                    self.ui.command_Text.write(base_text + f"{runtime.LOADING_MODEL_TEXT} {model_name_text}...")

                    set_progress_bar = lambda step, inference_iterations=0: self.process_update_progress(
                        total_files=input_path_total_len,
                        step=(step + inference_iterations),
                    )
                    write_to_console = lambda progress_text, base_text=base_text: self.ui.command_Text.write(
                        base_text + progress_text
                    )

                    audio_file_base = f"{file_num}_{os.path.splitext(os.path.basename(audio_file))[0]}"
                    if self.ui.is_testing_audio_var.get() and not is_ensemble:
                        audio_file_base = f"{round(time.time())}_{audio_file_base}"
                    if is_ensemble:
                        audio_file_base = f"{audio_file_base}_{current_model.model_basename}"
                    elif self.ui.is_add_model_name_var.get():
                        audio_file_base = f"{audio_file_base}_{current_model.model_basename}"

                    if self.ui.is_create_model_folder_var.get() and not is_ensemble:
                        export_path = os.path.join(
                            Path(self.ui.export_path_var.get()),
                            current_model.model_basename,
                            os.path.splitext(os.path.basename(audio_file))[0],
                        )
                        if not os.path.isdir(export_path):
                            os.makedirs(export_path)

                    process_data = {
                        "model_data": current_model,
                        "export_path": export_path,
                        "audio_file_base": audio_file_base,
                        "audio_file": audio_file,
                        "set_progress_bar": set_progress_bar,
                        "write_to_console": write_to_console,
                        "process_iteration": self.ui.process_iteration,
                        "cached_source_callback": self.ui.cached_source_callback,
                        "cached_model_source_holder": self.ui.cached_model_source_holder,
                        "list_all_models": self.ui.all_models,
                        "is_ensemble_master": is_ensemble,
                        "is_4_stem_ensemble": True
                        if self.ui.ensemble_main_stem_var.get() in [runtime.FOUR_STEM_ENSEMBLE, runtime.MULTI_STEM_ENSEMBLE]
                        and is_ensemble
                        else False,
                    }

                    if current_model.process_method == runtime.VR_ARCH_TYPE:
                        seperator = runtime.SeperateVR(current_model, process_data)
                    if current_model.process_method == runtime.MDX_ARCH_TYPE:
                        seperator = (
                            runtime.SeperateMDXC(current_model, process_data)
                            if current_model.is_mdx_c
                            else runtime.SeperateMDX(current_model, process_data)
                        )
                    if current_model.process_method == runtime.DEMUCS_ARCH_TYPE:
                        seperator = runtime.SeperateDemucs(current_model, process_data)

                    seperator.seperate()
                    if is_ensemble:
                        self.ui.command_Text.write("\n")

                if is_ensemble:
                    audio_file_base = audio_file_base.replace(f"_{current_model.model_basename}", "")
                    self.ui.command_Text.write(base_text + runtime.ENSEMBLING_OUTPUTS)
                    if self.ui.ensemble_main_stem_var.get() in [runtime.FOUR_STEM_ENSEMBLE, runtime.MULTI_STEM_ENSEMBLE]:
                        stem_list = runtime.extract_stems(audio_file_base, export_path)
                        for output_stem in stem_list:
                            ensemble.ensemble_outputs(audio_file_base, export_path, output_stem, is_4_stem=True)
                    else:
                        if not self.ui.is_secondary_stem_only_var.get():
                            ensemble.ensemble_outputs(audio_file_base, export_path, runtime.PRIMARY_STEM)
                        if not self.ui.is_primary_stem_only_var.get():
                            ensemble.ensemble_outputs(audio_file_base, export_path, runtime.SECONDARY_STEM)
                            ensemble.ensemble_outputs(
                                audio_file_base,
                                export_path,
                                runtime.SECONDARY_STEM,
                                is_inst_mix=True,
                            )
                    self.ui.command_Text.write(runtime.DONE)

                if is_model_sample_mode and os.path.isfile(audio_file):
                    os.remove(audio_file)
                runtime.clear_gpu_cache()

            if is_ensemble and len(os.listdir(export_path)) == 0:
                shutil.rmtree(export_path)

            if input_path_total_len == 1 and not is_verified_audio:
                self.ui.command_Text.write(f"{error_text_console}\n{runtime.PROCESS_FAILED}")
                self.ui.command_Text.write(time_elapsed())
                runtime.playsound(runtime.FAIL_CHIME) if self.ui.is_task_complete_var.get() else None
            else:
                set_progress_bar(1.0)
                self.ui.command_Text.write(runtime.PROCESS_COMPLETE)
                self.ui.command_Text.write(time_elapsed())
                runtime.playsound(runtime.COMPLETE_CHIME) if self.ui.is_task_complete_var.get() else None

            self.process_end()
        except Exception as exc:
            self.ui.error_log_var.set(
                f"{runtime.error_text(self.ui.chosen_process_method_var.get(), exc)}{self.ui.get_settings_list()}"
            )
            self.ui.command_Text.write(f"\n\n{runtime.PROCESS_FAILED}")
            self.ui.command_Text.write(time_elapsed())
            runtime.playsound(runtime.FAIL_CHIME) if self.ui.is_task_complete_var.get() else None
            self.process_end(error=exc)
