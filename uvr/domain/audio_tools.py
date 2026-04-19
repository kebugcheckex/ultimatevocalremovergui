"""Audio tool helpers extracted from UVR.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


class AudioTools:
    def __init__(self, audio_tool: str):
        time_stamp = round(runtime.time.time())
        self.audio_tool = audio_tool
        self.main_export_path = Path(runtime.root.export_path_var.get())
        self.wav_type_set = runtime.root.wav_type_set
        self.is_normalization = runtime.root.is_normalization_var.get()
        self.is_testing_audio = f"{time_stamp}_" if runtime.root.is_testing_audio_var.get() else ""
        self.save_format = (
            lambda save_path: runtime.save_format(
                save_path,
                runtime.root.save_format_var.get(),
                runtime.root.mp3_bit_set_var.get(),
            )
        )
        self.align_window = runtime.TIME_WINDOW_MAPPER[runtime.root.time_window_var.get()]
        self.align_intro_val = runtime.INTRO_MAPPER[runtime.root.intro_analysis_var.get()]
        self.db_analysis_val = runtime.VOLUME_MAPPER[runtime.root.db_analysis_var.get()]
        self.is_save_align = runtime.root.is_save_align_var.get()
        self.is_match_silence = runtime.root.is_match_silence_var.get()
        self.is_spec_match = runtime.root.is_spec_match_var.get()
        self.phase_option = runtime.root.phase_option_var.get()
        self.phase_shifts = runtime.PHASE_SHIFTS_OPT[runtime.root.phase_shifts_var.get()]

    def align_inputs(
        self,
        audio_inputs: list[str],
        audio_file_base: str,
        audio_file_2_base: str,
        command_Text: Any,
        set_progress_bar: Any,
    ) -> None:
        audio_file_base = f"{self.is_testing_audio}{audio_file_base}"
        audio_file_2_base = f"{self.is_testing_audio}{audio_file_2_base}"

        aligned_path = runtime.os.path.join(f"{self.main_export_path}", f"{audio_file_2_base}_(Aligned).wav")
        inverted_path = runtime.os.path.join(f"{self.main_export_path}", f"{audio_file_base}_(Inverted).wav")

        runtime.spec_utils.align_audio(
            audio_inputs[0],
            audio_inputs[1],
            aligned_path,
            inverted_path,
            self.wav_type_set,
            self.is_save_align,
            command_Text,
            self.save_format,
            align_window=self.align_window,
            align_intro_val=self.align_intro_val,
            db_analysis=self.db_analysis_val,
            set_progress_bar=set_progress_bar,
            phase_option=self.phase_option,
            phase_shifts=self.phase_shifts,
            is_match_silence=self.is_match_silence,
            is_spec_match=self.is_spec_match,
        )

    def match_inputs(self, audio_inputs: list[str], audio_file_base: str, command_Text: Any) -> None:
        target = audio_inputs[0]
        reference = audio_inputs[1]

        command_Text("Processing... ")

        save_path = runtime.os.path.join(
            f"{self.main_export_path}",
            f"{self.is_testing_audio}{audio_file_base}_(Matched).wav",
        )

        runtime.match.process(
            target=target,
            reference=reference,
            results=[runtime.match.save_audiofile(save_path, wav_set=self.wav_type_set)],
        )

        self.save_format(save_path)

    def combine_audio(self, audio_inputs: list[str], audio_file_base: str) -> None:
        runtime.spec_utils.combine_audio(
            audio_inputs,
            runtime.os.path.join(self.main_export_path, f"{self.is_testing_audio}{audio_file_base}"),
            self.wav_type_set,
            save_format=self.save_format,
        )

    def pitch_or_time_shift(self, audio_file: str, audio_file_base: str) -> None:
        is_time_correction = True
        rate = (
            float(runtime.root.time_stretch_rate_var.get())
            if self.audio_tool == runtime.TIME_STRETCH
            else float(runtime.root.pitch_rate_var.get())
        )
        is_pitch = self.audio_tool != runtime.TIME_STRETCH
        if is_pitch:
            is_time_correction = True if runtime.root.is_time_correction_var.get() else False
        file_text = runtime.TIME_TEXT if self.audio_tool == runtime.TIME_STRETCH else runtime.PITCH_TEXT
        save_path = runtime.os.path.join(
            self.main_export_path,
            f"{self.is_testing_audio}{audio_file_base}{file_text}.wav",
        )
        runtime.spec_utils.augment_audio(
            save_path,
            audio_file,
            rate,
            self.is_normalization,
            self.wav_type_set,
            self.save_format,
            is_pitch=is_pitch,
            is_time_correction=is_time_correction,
        )
