"""Typed application state for the PySide6 frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings
from uvr.config.persistence import load_settings
from uvr_core.requests import (
    AdvancedModelControlsRequest,
    ModelSelectionRequest,
    OutputSettingsRequest,
    ProcessingOptionsRequest,
    SeparationRequest,
)


@dataclass(frozen=True)
class PathsState:
    """File and directory selections shown in the main workflow."""

    input_paths: tuple[str, ...] = ()
    export_path: str = ""
    last_directory: str | None = None
    file_one_path: str = ""
    file_one_full_path: str = ""
    file_two_path: str = ""
    file_two_full_path: str = ""
    dual_batch_input_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelSelectionState:
    """Model selections currently surfaced by the existing backend."""

    vr_model: str
    mdx_net_model: str
    demucs_model: str
    demucs_pre_proc_model: str
    vocal_splitter_model: str
    demucs_stems: str
    mdx_stems: str
    secondary_models: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OutputSettingsState:
    """Export settings needed for the first Qt release."""

    save_format: str
    wav_type: str
    mp3_bitrate: str
    add_model_name: bool
    create_model_folder: bool


@dataclass(frozen=True)
class ProcessingSettingsState:
    """UI-facing processing settings and feature toggles."""

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
class ProcessingRuntimeState:
    """Ephemeral state owned by the Qt shell during app execution."""

    is_processing: bool = False
    can_cancel: bool = False
    progress: float = 0.0
    status_text: str = ""
    log_lines: tuple[str, ...] = ()
    last_error: str | None = None


@dataclass(frozen=True)
class AdvancedModelControlsState:
    """Typed advanced backend settings for VR, MDX, and Demucs models."""

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
class AppState:
    """Single source of truth for the Qt application."""

    paths: PathsState
    models: ModelSelectionState
    output: OutputSettingsState
    processing: ProcessingSettingsState
    advanced: AdvancedModelControlsState
    runtime: ProcessingRuntimeState = field(default_factory=ProcessingRuntimeState)
    extra_settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> AppState:
        values = settings.to_legacy_dict()

        paths = PathsState(
            input_paths=tuple(values.get("input_paths", ())),
            export_path=str(values.get("export_path", "")),
            last_directory=_optional_str(values.get("lastDir")),
            file_one_path=str(values.get("fileOneEntry", "")),
            file_one_full_path=str(values.get("fileOneEntry_Full", "")),
            file_two_path=str(values.get("fileTwoEntry", "")),
            file_two_full_path=str(values.get("fileTwoEntry_Full", "")),
            dual_batch_input_paths=tuple(values.get("DualBatch_inputPaths", ())),
        )

        models = ModelSelectionState(
            vr_model=str(values.get("vr_model", "")),
            mdx_net_model=str(values.get("mdx_net_model", "")),
            demucs_model=str(values.get("demucs_model", "")),
            demucs_pre_proc_model=str(values.get("demucs_pre_proc_model", "")),
            vocal_splitter_model=str(values.get("set_vocal_splitter", "")),
            demucs_stems=str(values.get("demucs_stems", "")),
            mdx_stems=str(values.get("mdx_stems", "")),
            secondary_models={
                key: str(values.get(key, ""))
                for key in (
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
                )
            },
        )

        output = OutputSettingsState(
            save_format=str(values.get("save_format", "")),
            wav_type=str(values.get("wav_type_set", "")),
            mp3_bitrate=str(values.get("mp3_bit_set", "")),
            add_model_name=bool(values.get("is_add_model_name", False)),
            create_model_folder=bool(values.get("is_create_model_folder", False)),
        )

        processing = ProcessingSettingsState(
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
        )

        advanced = AdvancedModelControlsState(
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
        )

        mapped_keys = {
            "input_paths",
            "export_path",
            "lastDir",
            "fileOneEntry",
            "fileOneEntry_Full",
            "fileTwoEntry",
            "fileTwoEntry_Full",
            "DualBatch_inputPaths",
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
            "aggression_setting",
            "window_size",
            "batch_size",
            "crop_size",
            "is_tta",
            "is_post_process",
            "is_high_end_process",
            "post_process_threshold",
            "margin",
            "mdx_segment_size",
            "overlap",
            "overlap_mdx",
            "shifts",
            "margin_demucs",
            "compensate",
            "mdx_batch_size",
            "segment",
        }

        return cls(
            paths=paths,
            models=models,
            output=output,
            processing=processing,
            advanced=advanced,
            extra_settings={key: value for key, value in values.items() if key not in mapped_keys},
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Round-trip state through the existing persistence format."""
        payload = dict(DEFAULT_DATA)
        payload.update(self.extra_settings)
        payload.update(
            {
                "input_paths": list(self.paths.input_paths),
                "export_path": self.paths.export_path,
                "lastDir": self.paths.last_directory,
                "fileOneEntry": self.paths.file_one_path,
                "fileOneEntry_Full": self.paths.file_one_full_path,
                "fileTwoEntry": self.paths.file_two_path,
                "fileTwoEntry_Full": self.paths.file_two_full_path,
                "DualBatch_inputPaths": list(self.paths.dual_batch_input_paths),
                "vr_model": self.models.vr_model,
                "mdx_net_model": self.models.mdx_net_model,
                "demucs_model": self.models.demucs_model,
                "demucs_pre_proc_model": self.models.demucs_pre_proc_model,
                "set_vocal_splitter": self.models.vocal_splitter_model,
                "demucs_stems": self.models.demucs_stems,
                "mdx_stems": self.models.mdx_stems,
                "save_format": self.output.save_format,
                "wav_type_set": self.output.wav_type,
                "mp3_bit_set": self.output.mp3_bitrate,
                "is_add_model_name": self.output.add_model_name,
                "is_create_model_folder": self.output.create_model_folder,
                "chosen_process_method": self.processing.process_method,
                "chosen_audio_tool": self.processing.audio_tool,
                "choose_algorithm": self.processing.algorithm,
                "device_set": self.processing.device,
                "is_gpu_conversion": self.processing.use_gpu,
                "is_primary_stem_only": self.processing.primary_stem_only,
                "is_secondary_stem_only": self.processing.secondary_stem_only,
                "is_normalization": self.processing.normalize_output,
                "is_wav_ensemble": self.processing.wav_ensemble,
                "is_testing_audio": self.processing.testing_audio,
                "model_sample_mode": self.processing.model_sample_mode,
                "model_sample_mode_duration": self.processing.model_sample_duration,
                "aggression_setting": self.advanced.aggression_setting,
                "window_size": self.advanced.window_size,
                "batch_size": self.advanced.batch_size,
                "crop_size": self.advanced.crop_size,
                "is_tta": self.advanced.is_tta,
                "is_post_process": self.advanced.is_post_process,
                "is_high_end_process": self.advanced.is_high_end_process,
                "post_process_threshold": self.advanced.post_process_threshold,
                "margin": self.advanced.margin,
                "mdx_segment_size": self.advanced.mdx_segment_size,
                "overlap": self.advanced.overlap,
                "overlap_mdx": self.advanced.overlap_mdx,
                "shifts": self.advanced.shifts,
                "margin_demucs": self.advanced.margin_demucs,
                "compensate": self.advanced.compensate,
                "mdx_batch_size": self.advanced.mdx_batch_size,
                "segment": self.advanced.segment,
            }
        )
        payload.update(self.models.secondary_models)
        return payload

    def to_separation_request(self) -> SeparationRequest:
        """Convert the Qt view model into the framework-neutral backend request."""
        return SeparationRequest(
            input_paths=self.paths.input_paths,
            export_path=self.paths.export_path,
            models=ModelSelectionRequest(
                vr_model=self.models.vr_model,
                mdx_net_model=self.models.mdx_net_model,
                demucs_model=self.models.demucs_model,
                demucs_pre_proc_model=self.models.demucs_pre_proc_model,
                vocal_splitter_model=self.models.vocal_splitter_model,
                demucs_stems=self.models.demucs_stems,
                mdx_stems=self.models.mdx_stems,
                secondary_models=dict(self.models.secondary_models),
            ),
            output=OutputSettingsRequest(
                save_format=self.output.save_format,
                wav_type=self.output.wav_type,
                mp3_bitrate=self.output.mp3_bitrate,
                add_model_name=self.output.add_model_name,
                create_model_folder=self.output.create_model_folder,
            ),
            options=ProcessingOptionsRequest(
                process_method=self.processing.process_method,
                audio_tool=self.processing.audio_tool,
                algorithm=self.processing.algorithm,
                device=self.processing.device,
                use_gpu=self.processing.use_gpu,
                primary_stem_only=self.processing.primary_stem_only,
                secondary_stem_only=self.processing.secondary_stem_only,
                normalize_output=self.processing.normalize_output,
                wav_ensemble=self.processing.wav_ensemble,
                testing_audio=self.processing.testing_audio,
                model_sample_mode=self.processing.model_sample_mode,
                model_sample_duration=self.processing.model_sample_duration,
            ),
            advanced=AdvancedModelControlsRequest(
                aggression_setting=self.advanced.aggression_setting,
                window_size=self.advanced.window_size,
                batch_size=self.advanced.batch_size,
                crop_size=self.advanced.crop_size,
                is_tta=self.advanced.is_tta,
                is_post_process=self.advanced.is_post_process,
                is_high_end_process=self.advanced.is_high_end_process,
                post_process_threshold=self.advanced.post_process_threshold,
                margin=self.advanced.margin,
                mdx_segment_size=self.advanced.mdx_segment_size,
                overlap=self.advanced.overlap,
                overlap_mdx=self.advanced.overlap_mdx,
                shifts=self.advanced.shifts,
                margin_demucs=self.advanced.margin_demucs,
                compensate=self.advanced.compensate,
                mdx_batch_size=self.advanced.mdx_batch_size,
                segment=self.advanced.segment,
            ),
            extra_settings=dict(self.extra_settings),
        )

def load_app_state(data_file: str | Path = "config.yaml") -> AppState:
    """Load persisted settings into the new Qt state model."""
    settings = load_settings(default_data=DEFAULT_DATA, data_file=data_file)
    return AppState.from_settings(settings)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
