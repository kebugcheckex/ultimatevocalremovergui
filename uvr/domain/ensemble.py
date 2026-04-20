"""Ensemble helpers extracted from UVR.py."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


@dataclass(frozen=True)
class EnsemblerSettings:
    is_save_all_outputs_ensemble: bool
    chosen_ensemble_name: str
    ensemble_type: str
    ensemble_main_stem_pair: tuple[str, str]
    export_path: str
    is_append_ensemble_name: bool
    is_testing_audio: bool
    is_normalization: bool
    is_wav_ensemble: bool
    wav_type_set: Any
    mp3_bit_set: str
    save_format: str
    choose_algorithm: str


class Ensembler:
    def __init__(self, settings: EnsemblerSettings, is_manual_ensemble: bool = False):
        self.is_save_all_outputs_ensemble = settings.is_save_all_outputs_ensemble
        time_stamp = round(runtime.time.time())
        self.audio_tool = runtime.MANUAL_ENSEMBLE
        self.main_export_path = Path(settings.export_path)
        self.chosen_ensemble = f"_{settings.chosen_ensemble_name}" if settings.is_append_ensemble_name else ""
        ensemble_folder_name = (
            self.main_export_path if self.is_save_all_outputs_ensemble else runtime.ENSEMBLE_TEMP_PATH
        )
        self.ensemble_folder_name = runtime.os.path.join(
            ensemble_folder_name,
            f"{settings.chosen_ensemble_name}_Outputs_{time_stamp}",
        )
        self.is_testing_audio = f"{time_stamp}_" if settings.is_testing_audio else ""
        ensemble_algorithm = settings.ensemble_type.partition("/")
        self.primary_algorithm = ensemble_algorithm[0]
        self.secondary_algorithm = ensemble_algorithm[2]
        self.full_ensemble_algorithm = settings.ensemble_type
        self.ensemble_primary_stem = settings.ensemble_main_stem_pair[0]
        self.ensemble_secondary_stem = settings.ensemble_main_stem_pair[1]
        self.is_normalization = settings.is_normalization
        self.is_wav_ensemble = settings.is_wav_ensemble
        self.wav_type_set = settings.wav_type_set
        self.mp3_bit_set = settings.mp3_bit_set
        self.save_format = settings.save_format
        self.choose_algorithm = settings.choose_algorithm
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
            algorithm = self.full_ensemble_algorithm
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
        algorithm = self.choose_algorithm
        algorithm_text = "" if is_bulk else f"_({self.choose_algorithm})"
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
                self.save_format,
                self.mp3_bit_set,
            )
        )
        runtime.spec_utils.combine_audio(
            audio_inputs,
            runtime.os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}"),
            self.wav_type_set,
            save_format=save_format_,
        )
