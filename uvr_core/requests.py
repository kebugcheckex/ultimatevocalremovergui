"""Framework-neutral request models for backend jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings


@dataclass(frozen=True)
class ModelSelectionRequest:
    vr_model: str
    mdx_net_model: str
    demucs_model: str
    demucs_pre_proc_model: str
    vocal_splitter_model: str
    demucs_stems: str
    mdx_stems: str
    secondary_models: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OutputSettingsRequest:
    save_format: str
    wav_type: str
    mp3_bitrate: str
    add_model_name: bool
    create_model_folder: bool


@dataclass(frozen=True)
class ProcessingOptionsRequest:
    process_method: str
    audio_tool: str
    algorithm: str
    device: str
    use_gpu: bool
    primary_stem_only: bool
    secondary_stem_only: bool
    normalize_output: bool
    wav_ensemble: bool
    testing_audio: bool
    model_sample_mode: bool
    model_sample_duration: int


@dataclass(frozen=True)
class AdvancedModelControlsRequest:
    aggression_setting: int
    window_size: int
    batch_size: str
    crop_size: int
    is_tta: bool
    is_post_process: bool
    is_high_end_process: bool
    post_process_threshold: float
    margin: int
    mdx_segment_size: int
    overlap: str
    overlap_mdx: str
    shifts: int
    margin_demucs: int
    compensate: str
    mdx_batch_size: str
    segment: str


@dataclass(frozen=True)
class SeparationRequest:
    input_paths: tuple[str, ...]
    export_path: str
    models: ModelSelectionRequest
    output: OutputSettingsRequest
    options: ProcessingOptionsRequest
    advanced: AdvancedModelControlsRequest
    extra_settings: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "SeparationRequest":
        values = settings.to_legacy_dict()
        mapped_keys = {
            "input_paths",
            "export_path",
            "vr_model",
            "mdx_net_model",
            "demucs_model",
            "demucs_pre_proc_model",
            "set_vocal_splitter",
            "demucs_stems",
            "mdx_stems",
            "vr_voc_inst_secondary_model",
            "vr_other_secondary_model",
            "vr_bass_secondary_model",
            "vr_drums_secondary_model",
            "demucs_voc_inst_secondary_model",
            "demucs_other_secondary_model",
            "demucs_bass_secondary_model",
            "demucs_drums_secondary_model",
            "mdx_voc_inst_secondary_model",
            "mdx_other_secondary_model",
            "mdx_bass_secondary_model",
            "mdx_drums_secondary_model",
            "save_format",
            "wav_type_set",
            "mp3_bit_set",
            "is_add_model_name",
            "is_create_model_folder",
            "chosen_process_method",
            "chosen_audio_tool",
            "choose_algorithm",
            "device_set",
            "is_gpu_conversion",
            "is_primary_stem_only",
            "is_secondary_stem_only",
            "is_normalization",
            "is_wav_ensemble",
            "is_testing_audio",
            "model_sample_mode",
            "model_sample_mode_duration",
        }
        return cls(
            input_paths=tuple(values.get("input_paths", ())),
            export_path=str(values.get("export_path", "")),
            models=ModelSelectionRequest(
                vr_model=str(values.get("vr_model", "")),
                mdx_net_model=str(values.get("mdx_net_model", "")),
                demucs_model=str(values.get("demucs_model", "")),
                demucs_pre_proc_model=str(values.get("demucs_pre_proc_model", "")),
                vocal_splitter_model=str(values.get("set_vocal_splitter", "")),
                demucs_stems=str(values.get("demucs_stems", "")),
                mdx_stems=str(values.get("mdx_stems", "")),
                secondary_models={
                    key: str(values.get(key, ""))
                    for key in DEFAULT_DATA
                    if key.endswith("_secondary_model")
                },
            ),
            output=OutputSettingsRequest(
                save_format=str(values.get("save_format", "")),
                wav_type=str(values.get("wav_type_set", "")),
                mp3_bitrate=str(values.get("mp3_bit_set", "")),
                add_model_name=bool(values.get("is_add_model_name", False)),
                create_model_folder=bool(values.get("is_create_model_folder", False)),
            ),
            options=ProcessingOptionsRequest(
                process_method=str(values.get("chosen_process_method", "")),
                audio_tool=str(values.get("chosen_audio_tool", "")),
                algorithm=str(values.get("choose_algorithm", "")),
                device=str(values.get("device_set", "")),
                use_gpu=bool(values.get("is_gpu_conversion", False)),
                primary_stem_only=bool(values.get("is_primary_stem_only", False)),
                secondary_stem_only=bool(values.get("is_secondary_stem_only", False)),
                normalize_output=bool(values.get("is_normalization", False)),
                wav_ensemble=bool(values.get("is_wav_ensemble", False)),
                testing_audio=bool(values.get("is_testing_audio", False)),
                model_sample_mode=bool(values.get("model_sample_mode", False)),
                model_sample_duration=int(values.get("model_sample_mode_duration", 30)),
            ),
            advanced=AdvancedModelControlsRequest(
                aggression_setting=int(values.get("aggression_setting", 5)),
                window_size=int(values.get("window_size", 512)),
                batch_size=str(values.get("batch_size", DEFAULT_DATA.get("batch_size", "Default"))),
                crop_size=int(values.get("crop_size", 256)),
                is_tta=bool(values.get("is_tta", False)),
                is_post_process=bool(values.get("is_post_process", False)),
                is_high_end_process=bool(values.get("is_high_end_process", False)),
                post_process_threshold=float(values.get("post_process_threshold", 0.2)),
                margin=int(values.get("margin", 44100)),
                mdx_segment_size=int(values.get("mdx_segment_size", 256)),
                overlap=str(values.get("overlap", DEFAULT_DATA.get("overlap", "0.25"))),
                overlap_mdx=str(values.get("overlap_mdx", DEFAULT_DATA.get("overlap_mdx", "Default"))),
                shifts=int(values.get("shifts", 2)),
                margin_demucs=int(values.get("margin_demucs", 44100)),
                compensate=str(values.get("compensate", DEFAULT_DATA.get("compensate", "Auto"))),
                mdx_batch_size=str(values.get("mdx_batch_size", DEFAULT_DATA.get("mdx_batch_size", "Default"))),
                segment=str(values.get("segment", DEFAULT_DATA.get("segment", "Default"))),
            ),
            extra_settings={key: value for key, value in values.items() if key not in mapped_keys},
        )


@dataclass(frozen=True)
class DownloadRequest:
    model_type: str
    selection: str
    vip_code: str = ""
    refresh_model_settings: bool = True


@dataclass(frozen=True)
class EnsembleRequest:
    input_paths: tuple[str, ...]
    export_path: str
    algorithm: str
    output_name: str = "Ensembled"
    save_format: str = "WAV"
    wav_type: str = "PCM_16"
    mp3_bitrate: str = "320k"
    normalize_output: bool = False
    wav_ensemble: bool = False


@dataclass(frozen=True)
class AudioToolRequest:
    audio_tool: str
    input_paths: tuple[str, ...]
    export_path: str
    save_format: str = "WAV"
    wav_type: str = "PCM_16"
    mp3_bitrate: str = "320k"
    normalize_output: bool = False
    testing_audio: bool = False
    align_window: str = "3"
    align_intro: str = "Default"
    db_analysis: str = "Medium"
    save_aligned: bool = False
    match_silence: bool = True
    spec_match: bool = False
    phase_option: str = "Automatic"
    phase_shifts: str = "None"
    time_stretch_rate: str = "2.0"
    pitch_rate: str = "2.0"
    time_correction: bool = True
