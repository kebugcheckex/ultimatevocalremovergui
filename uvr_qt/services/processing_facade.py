"""Qt-facing processing facade for the first end-to-end workflow."""

from __future__ import annotations

import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gui_data.constants import (
    ALL_STEMS,
    AUTO_PHASE,
    AUTO_SELECT,
    CHOOSE_MODEL,
    DEFAULT,
    DENOISE_NONE,
    DEMUCS_ARCH_TYPE,
    DEMUCS_OVERLAP,
    DEF_OPT,
    MDX23_OVERLAP,
    MDX_ARCH_TYPE,
    MDX_OVERLAP,
    VR_ARCH_PM,
    VR_ARCH_TYPE,
    WAV,
)
from uvr.domain.model_data import ModelData, ModelDataResolvers, ModelDataSettings
from uvr_qt.state import AppState

from uvr_qt.services.runtime_bridge import (
    DEMUCS_MODELS_DIR,
    DEMUCS_NEWER_REPO_DIR,
    MDX_MODELS_DIR,
    VR_MODELS_DIR,
    configure_backend_runtime,
    discover_models,
    read_model_catalog,
)

configure_backend_runtime()
from separate import SeperateDemucs, SeperateMDX, SeperateMDXC, SeperateVR, clear_gpu_cache  # noqa: E402


@dataclass(frozen=True)
class ResolvedModel:
    process_method: str
    model_name: str
    source: str


@dataclass(frozen=True)
class ProcessResult:
    processed_files: tuple[str, ...]
    output_path: str
    model: ResolvedModel


class ProcessingFacade:
    """Minimal bridge from Qt app state to the existing separation backend."""

    def __init__(self) -> None:
        self.catalog = read_model_catalog()

    def resolve_model(self, state: AppState) -> ResolvedModel | None:
        available = self._available_models()
        preferred_method = state.processing.process_method

        preferred_name_map = {
            VR_ARCH_PM: state.models.vr_model,
            VR_ARCH_TYPE: state.models.vr_model,
            MDX_ARCH_TYPE: state.models.mdx_net_model,
            DEMUCS_ARCH_TYPE: state.models.demucs_model,
        }

        preferred_name = preferred_name_map.get(preferred_method, CHOOSE_MODEL)
        if preferred_name != CHOOSE_MODEL:
            for candidate in available:
                if candidate.process_method == preferred_method and candidate.model_name == preferred_name:
                    return candidate

        preferred_order = [preferred_method, MDX_ARCH_TYPE, VR_ARCH_PM, DEMUCS_ARCH_TYPE]
        seen: set[str] = set()
        for method in preferred_order:
            if method in seen:
                continue
            seen.add(method)
            for candidate in available:
                if candidate.process_method == method:
                    return candidate

        return available[0] if available else None

    def process(
        self,
        state: AppState,
        *,
        log: Callable[[str], None],
        progress: Callable[[float], None],
        status: Callable[[str], None],
    ) -> ProcessResult:
        resolved_model = self.resolve_model(state)
        if resolved_model is None:
            raise RuntimeError("No compatible backend models were found in the local models directories.")

        input_paths = tuple(path for path in state.paths.input_paths if path)
        if not input_paths:
            raise RuntimeError("No input files selected.")

        export_path = state.paths.export_path
        if not export_path:
            raise RuntimeError("No output folder selected.")

        os.makedirs(export_path, exist_ok=True)

        model = self._build_model(resolved_model)
        if not model.model_status:
            raise RuntimeError(f'The selected backend model "{resolved_model.model_name}" is not available.')

        cache = _CacheState()
        processed: list[str] = []

        try:
            for index, audio_file in enumerate(input_paths, start=1):
                if not Path(audio_file).is_file():
                    raise RuntimeError(f'Input file does not exist: "{audio_file}"')

                status(f"Processing {index}/{len(input_paths)}")
                log(f'Input {index}/{len(input_paths)}: "{os.path.basename(audio_file)}"')
                log(f"Model: {resolved_model.process_method} / {resolved_model.model_name}")
                progress(((index - 1) / len(input_paths)) * 100.0)

                audio_file_base = f"{index}_{Path(audio_file).stem}"
                process_data = self._build_process_data(
                    model=model,
                    audio_file=audio_file,
                    audio_file_base=audio_file_base,
                    export_path=export_path,
                    cache=cache,
                    log=log,
                    progress=progress,
                    file_index=index,
                    total_files=len(input_paths),
                )

                separator = self._create_separator(model, process_data)
                separator.seperate()
                clear_gpu_cache()
                processed.append(audio_file)
                progress((index / len(input_paths)) * 100.0)
                log("Done.")

            status("Completed")
            return ProcessResult(
                processed_files=tuple(processed),
                output_path=export_path,
                model=resolved_model,
            )
        except Exception:
            clear_gpu_cache()
            raise

    def _available_models(self) -> list[ResolvedModel]:
        mdx_raw = discover_models(MDX_MODELS_DIR, (".onnx", ".ckpt"), is_mdxnet=True)
        demucs_raw = discover_models(DEMUCS_MODELS_DIR, (".ckpt", ".gz", ".th")) + discover_models(
            DEMUCS_NEWER_REPO_DIR,
            ".yaml",
        )
        vr_raw = discover_models(VR_MODELS_DIR, ".pth")

        def remap(name: str, mapper: dict[str, str]) -> str:
            for old_name, new_name in mapper.items():
                if name in old_name:
                    return new_name
            return name

        resolved = [ResolvedModel(process_method=VR_ARCH_PM, model_name=name, source="vr") for name in sorted(vr_raw)]
        resolved.extend(
            ResolvedModel(
                process_method=MDX_ARCH_TYPE,
                model_name=remap(name, self.catalog["mdx_name_select_mapper"]),
                source="mdx",
            )
            for name in sorted(mdx_raw)
        )
        resolved.extend(
            ResolvedModel(
                process_method=DEMUCS_ARCH_TYPE,
                model_name=remap(name, self.catalog["demucs_name_select_mapper"]),
                source="demucs",
            )
            for name in sorted(demucs_raw)
        )
        return resolved

    def _build_model(self, resolved_model: ResolvedModel) -> ModelData:
        return ModelData(
            resolved_model.model_name,
            selected_process_method=VR_ARCH_TYPE if resolved_model.process_method == VR_ARCH_PM else resolved_model.process_method,
            settings=self._build_settings(resolved_model.process_method),
            resolvers=self._build_resolvers(),
        )

    def _build_settings(self, process_method: str) -> ModelDataSettings:
        return ModelDataSettings(
            device_set=DEFAULT,
            is_deverb_vocals=False,
            deverb_vocal_opt="Vocals",
            is_denoise_model=False,
            is_gpu_conversion=True,
            is_normalization=False,
            is_use_opencl=False,
            is_primary_stem_only=False,
            is_secondary_stem_only=False,
            is_primary_stem_only_demucs=False,
            is_secondary_stem_only_demucs=False,
            denoise_option=DENOISE_NONE,
            is_mdx_c_seg_def=False,
            mdx_batch_size=DEF_OPT,
            mdxnet_stems=ALL_STEMS,
            overlap=str(DEMUCS_OVERLAP[0]),
            overlap_mdx=str(MDX_OVERLAP[0]),
            overlap_mdx23=str(MDX23_OVERLAP[6]),
            semitone_shift="0",
            is_match_frequency_pitch=True,
            is_mdx23_combine_stems=True,
            wav_type_set="PCM_16",
            mp3_bit_set="320k",
            save_format=WAV,
            is_invert_spec=False,
            demucs_stems=ALL_STEMS,
            is_demucs_combine_stems=True,
            chosen_process_method=VR_ARCH_TYPE if process_method == VR_ARCH_PM else process_method,
            is_save_inst_set_vocal_splitter=False,
            ensemble_main_stem="",
            vr_is_secondary_model_activate=False,
            aggression_setting=5,
            is_tta=False,
            is_post_process=False,
            window_size=512,
            batch_size=DEF_OPT,
            crop_size=256,
            is_high_end_process=False,
            post_process_threshold=0.2,
            vr_hash_mapper=self.catalog["vr_hash_mapper"],
            mdx_is_secondary_model_activate=False,
            margin=44100,
            mdx_segment_size=256,
            mdx_hash_mapper=self.catalog["mdx_hash_mapper"],
            compensate=AUTO_SELECT,
            demucs_is_secondary_model_activate=False,
            is_demucs_pre_proc_model_activate=False,
            is_demucs_pre_proc_model_inst_mix=False,
            margin_demucs=44100,
            shifts=2,
            is_split_mode=True,
            segment=DEF_OPT,
            is_chunk_demucs=False,
            mdx_name_select_mapper=self.catalog["mdx_name_select_mapper"],
            demucs_name_select_mapper=self.catalog["demucs_name_select_mapper"],
        )

    def _build_resolvers(self) -> ModelDataResolvers:
        return ModelDataResolvers(
            return_ensemble_stems=lambda: ("", ""),
            check_only_selection_stem=lambda _check_type: False,
            determine_secondary_model=lambda *_args: (None, None),
            determine_demucs_pre_proc_model=lambda _primary_stem=None: None,
            determine_vocal_split_model=lambda: None,
            resolve_popup_model_data=lambda *_args: None,
        )

    def _build_process_data(
        self,
        *,
        model: ModelData,
        audio_file: str,
        audio_file_base: str,
        export_path: str,
        cache: "_CacheState",
        log: Callable[[str], None],
        progress: Callable[[float], None],
        file_index: int,
        total_files: int,
    ) -> dict[str, object]:
        progress_step = {"count": 0}

        def write_to_console(text: str, base_text: str = "") -> None:
            message = f"{base_text}{text}".rstrip()
            if message:
                log(message)

        def process_iteration() -> None:
            progress_step["count"] += 1
            fractional = min(progress_step["count"] * 10.0, 90.0)
            progress((((file_index - 1) + fractional / 100.0) / total_files) * 100.0)

        def set_progress_bar(step: float, inference_iterations: float = 0.0) -> None:
            partial = min(max(float(step + inference_iterations), 0.0), 1.0)
            progress((((file_index - 1) + partial) / total_files) * 100.0)

        return {
            "model_data": model,
            "export_path": export_path,
            "audio_file_base": audio_file_base,
            "audio_file": audio_file,
            "set_progress_bar": set_progress_bar,
            "write_to_console": write_to_console,
            "process_iteration": process_iteration,
            "cached_source_callback": cache.cached_source_callback,
            "cached_model_source_holder": cache.cached_model_source_holder,
            "list_all_models": [model.model_basename],
            "is_ensemble_master": False,
            "is_4_stem_ensemble": False,
        }

    def _create_separator(self, model: ModelData, process_data: dict[str, object]):
        if model.process_method == VR_ARCH_TYPE:
            return SeperateVR(model, process_data)
        if model.process_method == MDX_ARCH_TYPE:
            return SeperateMDXC(model, process_data) if model.is_mdx_c else SeperateMDX(model, process_data)
        if model.process_method == DEMUCS_ARCH_TYPE:
            return SeperateDemucs(model, process_data)
        raise RuntimeError(f"Unsupported process method: {model.process_method}")


class _CacheState:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, object]] = {
            VR_ARCH_TYPE: {},
            MDX_ARCH_TYPE: {},
            DEMUCS_ARCH_TYPE: {},
        }

    def cached_source_callback(self, process_method: str, model_name: str | None = None):
        mapper = self._cache.get(process_method, {})
        for key, value in mapper.items():
            if model_name and model_name in key:
                return key, value
        return None, None

    def cached_model_source_holder(self, process_method: str, sources, model_name: str | None = None) -> None:
        if model_name is None:
            return
        self._cache.setdefault(process_method, {})[model_name] = sources
