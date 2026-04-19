"""Typed configuration models for UVR settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SettingValue = Any
LegacySettingsDict = dict[str, SettingValue]

MODEL_SELECTION_KEYS = (
    "vr_model",
    "demucs_model",
    "mdx_net_model",
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
)

PROCESS_SETTINGS_KEYS = (
    "chosen_process_method",
    "chosen_audio_tool",
    "choose_algorithm",
    "save_format",
    "wav_type_set",
    "device_set",
    "export_path",
    "input_paths",
    "lastDir",
    "time_window",
    "intro_analysis",
    "db_analysis",
    "fileOneEntry",
    "fileOneEntry_Full",
    "fileTwoEntry",
    "fileTwoEntry_Full",
    "DualBatch_inputPaths",
    "is_gpu_conversion",
    "is_primary_stem_only",
    "is_secondary_stem_only",
    "is_testing_audio",
    "is_task_complete",
    "is_normalization",
    "is_wav_ensemble",
)


@dataclass(frozen=True)
class ModelSelection:
    """Typed subset of model-selection state."""

    vr_model: str
    demucs_model: str
    mdx_net_model: str
    demucs_pre_proc_model: str
    set_vocal_splitter: str
    demucs_stems: str
    mdx_stems: str
    secondary_models: dict[str, str]


@dataclass(frozen=True)
class ProcessSettings:
    """Typed subset of runtime processing state."""

    chosen_process_method: str
    chosen_audio_tool: str
    choose_algorithm: str
    save_format: str
    wav_type_set: str
    device_set: str
    export_path: str
    input_paths: tuple[str, ...]
    dual_batch_input_paths: tuple[str, ...]
    last_directory: str
    time_window: str
    intro_analysis: str
    db_analysis: str
    file_one_entry: str
    file_one_entry_full: str
    file_two_entry: str
    file_two_entry_full: str
    is_gpu_conversion: bool
    is_primary_stem_only: bool
    is_secondary_stem_only: bool
    is_testing_audio: bool
    is_task_complete: bool
    is_normalization: bool
    is_wav_ensemble: bool


@dataclass(frozen=True)
class DownloadSettings:
    """Typed subset of download/configuration state."""

    user_code: str
    is_auto_update_model_params: bool
    is_create_model_folder: bool
    is_accept_any_input: bool


@dataclass(frozen=True)
class AppSettings:
    """Compatibility wrapper around persisted UVR settings."""

    values: LegacySettingsDict

    @classmethod
    def from_legacy_dict(
        cls,
        data: Mapping[str, SettingValue] | None,
        default_data: Mapping[str, SettingValue],
    ) -> AppSettings:
        merged: LegacySettingsDict = dict(default_data)
        if data:
            merged.update(dict(data))

        # Preserve the legacy missing-key behavior used by UVR.py today.
        if data is not None and "batch_size" not in data:
            merged["batch_size"] = default_data["batch_size"]

        return cls(values=merged)

    def to_legacy_dict(self) -> LegacySettingsDict:
        return dict(self.values)

    @property
    def model_selection(self) -> ModelSelection:
        secondary_models = {
            key: str(self.values.get(key, ""))
            for key in MODEL_SELECTION_KEYS
            if key.endswith("_secondary_model")
        }
        return ModelSelection(
            vr_model=str(self.values["vr_model"]),
            demucs_model=str(self.values["demucs_model"]),
            mdx_net_model=str(self.values["mdx_net_model"]),
            demucs_pre_proc_model=str(self.values["demucs_pre_proc_model"]),
            set_vocal_splitter=str(self.values["set_vocal_splitter"]),
            demucs_stems=str(self.values["demucs_stems"]),
            mdx_stems=str(self.values["mdx_stems"]),
            secondary_models=secondary_models,
        )

    @property
    def process_settings(self) -> ProcessSettings:
        input_paths = tuple(self.values.get("input_paths", ()))
        dual_batch_input_paths = tuple(self.values.get("DualBatch_inputPaths", ()))
        return ProcessSettings(
            chosen_process_method=str(self.values["chosen_process_method"]),
            chosen_audio_tool=str(self.values["chosen_audio_tool"]),
            choose_algorithm=str(self.values["choose_algorithm"]),
            save_format=str(self.values["save_format"]),
            wav_type_set=str(self.values["wav_type_set"]),
            device_set=str(self.values["device_set"]),
            export_path=str(self.values["export_path"]),
            input_paths=input_paths,
            dual_batch_input_paths=dual_batch_input_paths,
            last_directory=str(self.values["lastDir"]),
            time_window=str(self.values["time_window"]),
            intro_analysis=str(self.values["intro_analysis"]),
            db_analysis=str(self.values["db_analysis"]),
            file_one_entry=str(self.values["fileOneEntry"]),
            file_one_entry_full=str(self.values["fileOneEntry_Full"]),
            file_two_entry=str(self.values["fileTwoEntry"]),
            file_two_entry_full=str(self.values["fileTwoEntry_Full"]),
            is_gpu_conversion=bool(self.values["is_gpu_conversion"]),
            is_primary_stem_only=bool(self.values["is_primary_stem_only"]),
            is_secondary_stem_only=bool(self.values["is_secondary_stem_only"]),
            is_testing_audio=bool(self.values["is_testing_audio"]),
            is_task_complete=bool(self.values["is_task_complete"]),
            is_normalization=bool(self.values["is_normalization"]),
            is_wav_ensemble=bool(self.values["is_wav_ensemble"]),
        )

    @property
    def download_settings(self) -> DownloadSettings:
        return DownloadSettings(
            user_code=str(self.values["user_code"]),
            is_auto_update_model_params=bool(self.values["is_auto_update_model_params"]),
            is_create_model_folder=bool(self.values["is_create_model_folder"]),
            is_accept_any_input=bool(self.values["is_accept_any_input"]),
        )
