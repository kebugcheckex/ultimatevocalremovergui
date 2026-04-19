"""Ensemble helpers extracted from UVR.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class Ensembler:
    def __init__(self, is_manual_ensemble: bool = False):
        self.is_save_all_outputs_ensemble = runtime.root.is_save_all_outputs_ensemble_var.get()
        chosen_ensemble_name = (
            f"{runtime.root.chosen_ensemble_var.get().replace(' ', '_')}"
            if runtime.root.chosen_ensemble_var.get() != runtime.CHOOSE_ENSEMBLE_OPTION
            else "Ensembled"
        )
        ensemble_algorithm = runtime.root.ensemble_type_var.get().partition("/")
        ensemble_main_stem_pair = runtime.root.ensemble_main_stem_var.get().partition("/")
        time_stamp = round(runtime.time.time())
        self.audio_tool = runtime.MANUAL_ENSEMBLE
        self.main_export_path = Path(runtime.root.export_path_var.get())
        self.chosen_ensemble = (
            f"_{chosen_ensemble_name}" if runtime.root.is_append_ensemble_name_var.get() else ""
        )
        ensemble_folder_name = (
            self.main_export_path if self.is_save_all_outputs_ensemble else runtime.ENSEMBLE_TEMP_PATH
        )
        self.ensemble_folder_name = runtime.os.path.join(
            ensemble_folder_name,
            f"{chosen_ensemble_name}_Outputs_{time_stamp}",
        )
        self.is_testing_audio = f"{time_stamp}_" if runtime.root.is_testing_audio_var.get() else ""
        self.primary_algorithm = ensemble_algorithm[0]
        self.secondary_algorithm = ensemble_algorithm[2]
        self.ensemble_primary_stem = ensemble_main_stem_pair[0]
        self.ensemble_secondary_stem = ensemble_main_stem_pair[2]
        self.is_normalization = runtime.root.is_normalization_var.get()
        self.is_wav_ensemble = runtime.root.is_wav_ensemble_var.get()
        self.wav_type_set = runtime.root.wav_type_set
        self.mp3_bit_set = runtime.root.mp3_bit_set_var.get()
        self.save_format = runtime.root.save_format_var.get()
        if not is_manual_ensemble:
            runtime.os.mkdir(self.ensemble_folder_name)

    def ensemble_outputs(
        self,
        audio_file_base: str,
        export_path: str,
        stem: str,
        is_4_stem: bool = False,
        is_inst_mix: bool = False,
    ) -> None:
        if is_4_stem:
            algorithm = runtime.root.ensemble_type_var.get()
            stem_tag = stem
        else:
            if is_inst_mix:
                algorithm = self.secondary_algorithm
                stem_tag = f"{self.ensemble_secondary_stem} {runtime.INST_STEM}"
            else:
                algorithm = self.primary_algorithm if stem == runtime.PRIMARY_STEM else self.secondary_algorithm
                stem_tag = (
                    self.ensemble_primary_stem
                    if stem == runtime.PRIMARY_STEM
                    else self.ensemble_secondary_stem
                )

        stem_outputs = self.get_files_to_ensemble(
            folder=export_path,
            prefix=audio_file_base,
            suffix=f"_({stem_tag}).wav",
        )
        audio_file_output = f"{self.is_testing_audio}{audio_file_base}{self.chosen_ensemble}_({stem_tag})"
        stem_save_path = runtime.os.path.join(f"{self.main_export_path}", f"{audio_file_output}.wav")

        if len(stem_outputs) > 1:
            runtime.spec_utils.ensemble_inputs(
                stem_outputs,
                algorithm,
                self.is_normalization,
                self.wav_type_set,
                stem_save_path,
                is_wave=self.is_wav_ensemble,
            )
            runtime.save_format(stem_save_path, self.save_format, self.mp3_bit_set)

        if self.is_save_all_outputs_ensemble:
            for item in stem_outputs:
                runtime.save_format(item, self.save_format, self.mp3_bit_set)
        else:
            for item in stem_outputs:
                try:
                    runtime.os.remove(item)
                except Exception as exc:
                    print(exc)

    def ensemble_manual(self, audio_inputs: list[str], audio_file_base: str, is_bulk: bool = False) -> None:
        is_mv_sep = True

        if is_bulk:
            number_list = list(set([runtime.os.path.basename(i).split("_")[0] for i in audio_inputs]))
            for number in number_list:
                current_list = [i for i in audio_inputs if runtime.os.path.basename(i).startswith(number)]
                audio_file_base = runtime.os.path.basename(current_list[0]).split(".wav")[0]
                stem_testing = "instrum" if "Instrumental" in audio_file_base else "vocals"
                if is_mv_sep:
                    audio_file_base_parts = audio_file_base.split("_")
                    audio_file_base = (
                        f"{audio_file_base_parts[1]}_{audio_file_base_parts[2]}_{stem_testing}"
                    )
                self.ensemble_manual_process(current_list, audio_file_base, is_bulk)
        else:
            self.ensemble_manual_process(audio_inputs, audio_file_base, is_bulk)

    def ensemble_manual_process(
        self,
        audio_inputs: list[str],
        audio_file_base: str,
        is_bulk: bool,
    ) -> None:
        algorithm = runtime.root.choose_algorithm_var.get()
        algorithm_text = "" if is_bulk else f"_({runtime.root.choose_algorithm_var.get()})"
        stem_save_path = runtime.os.path.join(
            f"{self.main_export_path}",
            f"{self.is_testing_audio}{audio_file_base}{algorithm_text}.wav",
        )
        runtime.spec_utils.ensemble_inputs(
            audio_inputs,
            algorithm,
            self.is_normalization,
            self.wav_type_set,
            stem_save_path,
            is_wave=self.is_wav_ensemble,
        )
        runtime.save_format(stem_save_path, self.save_format, self.mp3_bit_set)

    def get_files_to_ensemble(self, folder: str = "", prefix: str = "", suffix: str = "") -> list[str]:
        return [
            runtime.os.path.join(folder, item)
            for item in runtime.os.listdir(folder)
            if item.startswith(prefix) and item.endswith(suffix)
        ]

    def combine_audio(self, audio_inputs: list[str], audio_file_base: str) -> None:
        save_format_ = (
            lambda save_path: runtime.save_format(
                save_path,
                runtime.root.save_format_var.get(),
                runtime.root.mp3_bit_set_var.get(),
            )
        )
        runtime.spec_utils.combine_audio(
            audio_inputs,
            runtime.os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}"),
            self.wav_type_set,
            save_format=save_format_,
        )
