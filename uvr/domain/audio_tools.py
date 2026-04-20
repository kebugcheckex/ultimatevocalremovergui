"""Audio tool helpers extracted from UVR.py."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


@dataclass(frozen=True)
class AudioToolSettings:
    export_path: str
    wav_type_set: Any
    is_normalization: bool
    is_testing_audio: bool
    save_format: str
    mp3_bit_set: str
    align_window: int
    align_intro_val: Any
    db_analysis_val: Any
    is_save_align: bool
    is_match_silence: bool
    is_spec_match: bool
    phase_option: str
    phase_shifts: Any
    time_stretch_rate: str
    pitch_rate: str
    is_time_correction: bool


class AudioTools:
    def __init__(self, audio_tool: str, settings: AudioToolSettings):
        time_stamp = round(runtime.time.time())
        self.audio_tool = audio_tool
        self.main_export_path = Path(settings.export_path)
        self.wav_type_set = settings.wav_type_set
        self.is_normalization = settings.is_normalization
        self.is_testing_audio = f"{time_stamp}_" if settings.is_testing_audio else ""
        self.save_format: Callable[[str], None] = lambda save_path: runtime.save_format(
            save_path,
            settings.save_format,
            settings.mp3_bit_set,
        )
        self.align_window = settings.align_window
        self.align_intro_val = settings.align_intro_val
        self.db_analysis_val = settings.db_analysis_val
        self.is_save_align = settings.is_save_align
        self.is_match_silence = settings.is_match_silence
        self.is_spec_match = settings.is_spec_match
        self.phase_option = settings.phase_option
        self.phase_shifts = settings.phase_shifts
        self.time_stretch_rate = float(settings.time_stretch_rate)
        self.pitch_rate = float(settings.pitch_rate)
        self.is_time_correction = settings.is_time_correction

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
        rate = self.time_stretch_rate if self.audio_tool == runtime.TIME_STRETCH else self.pitch_rate
        is_pitch = self.audio_tool != runtime.TIME_STRETCH
        if is_pitch:
            is_time_correction = self.is_time_correction
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
