"""Typed application state for the PySide6 frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings
from uvr.config.persistence import load_settings


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
class AppState:
    """Single source of truth for the Qt application."""

    paths: PathsState
    models: ModelSelectionState
    output: OutputSettingsState
    processing: ProcessingSettingsState
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
        }

        return cls(
            paths=paths,
            models=models,
            output=output,
            processing=processing,
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
            }
        )
        payload.update(self.models.secondary_models)
        return payload


@dataclass(frozen=True)
class ProcessingRequest:
    """Typed processing request consumed by the future Qt processing facade."""

    process_method: str
    audio_tool: str
    algorithm: str
    input_paths: tuple[str, ...]
    export_path: str
    models: ModelSelectionState
    output: OutputSettingsState
    options: ProcessingSettingsState
    extra_settings: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_app_state(cls, state: AppState) -> ProcessingRequest:
        return cls(
            process_method=state.processing.process_method,
            audio_tool=state.processing.audio_tool,
            algorithm=state.processing.algorithm,
            input_paths=state.paths.input_paths,
            export_path=state.paths.export_path,
            models=state.models,
            output=state.output,
            options=state.processing,
            extra_settings=dict(state.extra_settings),
        )


def load_app_state(data_file: str | Path = "data.pkl") -> AppState:
    """Load persisted settings into the new Qt state model."""
    settings = load_settings(default_data=DEFAULT_DATA, data_file=data_file)
    return AppState.from_settings(settings)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
