"""Framework-neutral processing jobs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gui_data.constants import (
    ALL_STEMS,
    AUTO_SELECT,
    CHOOSE_MODEL,
    DEFAULT,
    DENOISE_NONE,
    DEMUCS_ARCH_TYPE,
    DEMUCS_OVERLAP,
    DEF_OPT,
    MDX23_OVERLAP,
    MDX_ARCH_TYPE,
    NO_CODE,
    MDX_OVERLAP,
    VR_ARCH_PM,
    VR_ARCH_TYPE,
    WAV,
)
from uvr.domain.model_data import ModelData, ModelDataResolvers, ModelDataSettings
from uvr.runtime import (
    DEFAULT_PATHS,
    RuntimePaths,
    configure_backend_runtime,
)
from uvr.services.cache import SourceCache
from uvr.services.catalog import list_installed_models, load_model_catalog
from uvr.services.downloads import (
    ModelSettingsBundle,
    build_download_catalog,
    execute_download_plan,
    fetch_online_state,
    list_downloadable_items,
    load_or_fetch_model_settings,
    resolve_download_plan,
    validate_vip_code,
)
from uvr_core.events import DownloadResultEvent, Event, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.requests import DownloadRequest, SeparationRequest


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


@dataclass(frozen=True)
class AvailableDownloads:
    bulletin: str | None
    vr_items: tuple[str, ...]
    mdx_items: tuple[str, ...]
    demucs_items: tuple[str, ...]
    decoded_vip_link: str


@dataclass(frozen=True)
class DownloadJobResult:
    completed_files: tuple[str, ...]
    skipped_existing: tuple[str, ...]
    model_type: str
    selection: str
    refreshed_settings: ModelSettingsBundle | None = None


EventSubscriber = Callable[[Event], None]


class SeparationJob:
    """Thin job wrapper around the legacy separation backend."""

    def __init__(self) -> None:
        self.catalog = load_model_catalog()

    def available_process_methods(self) -> tuple[str, ...]:
        methods = []
        for model in self._available_models():
            if model.process_method not in methods:
                methods.append(model.process_method)
        return tuple(methods)

    def available_models_for_method(self, process_method: str) -> tuple[str, ...]:
        return tuple(
            model.model_name
            for model in self._available_models()
            if model.process_method == process_method
        )

    def resolve_model(self, request: SeparationRequest) -> ResolvedModel | None:
        available = self._available_models()
        preferred_method = request.options.process_method

        preferred_name_map = {
            VR_ARCH_PM: request.models.vr_model,
            VR_ARCH_TYPE: request.models.vr_model,
            MDX_ARCH_TYPE: request.models.mdx_net_model,
            DEMUCS_ARCH_TYPE: request.models.demucs_model,
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

    def run(
        self,
        request: SeparationRequest,
        *,
        subscriber: EventSubscriber | None = None,
    ) -> ProcessResult:
        resolved_model = self.resolve_model(request)
        if resolved_model is None:
            raise RuntimeError("No compatible backend models were found in the local models directories.")

        input_paths = tuple(path for path in request.input_paths if path)
        if not input_paths:
            raise RuntimeError("No input files selected.")

        export_path = request.export_path
        if not export_path:
            raise RuntimeError("No output folder selected.")

        os.makedirs(export_path, exist_ok=True)

        model = self._build_model(resolved_model, request)
        if not model.model_status:
            raise RuntimeError(f'The selected backend model "{resolved_model.model_name}" is not available.')

        cache = SourceCache()
        processed: list[str] = []

        try:
            for index, audio_file in enumerate(input_paths, start=1):
                if not Path(audio_file).is_file():
                    raise RuntimeError(f'Input file does not exist: "{audio_file}"')

                self._emit(
                    subscriber,
                    StatusEvent(
                        message=f"Processing {index}/{len(input_paths)}",
                    ),
                )
                self._emit(
                    subscriber,
                    LogEvent(message=f'Input {index}/{len(input_paths)}: "{os.path.basename(audio_file)}"'),
                )
                self._emit(
                    subscriber,
                    LogEvent(message=f"Model: {resolved_model.process_method} / {resolved_model.model_name}"),
                )
                self._emit(
                    subscriber,
                    ProgressEvent(
                        percent=((index - 1) / len(input_paths)) * 100.0,
                        current_file=index,
                        total_files=len(input_paths),
                    ),
                )

                audio_file_base = f"{index}_{Path(audio_file).stem}"
                if request.output.add_model_name:
                    audio_file_base = f"{audio_file_base}_{model.model_basename}"

                item_export_path = export_path
                if request.output.create_model_folder:
                    item_export_path = os.path.join(
                        export_path,
                        model.model_basename,
                        Path(audio_file).stem,
                    )
                    os.makedirs(item_export_path, exist_ok=True)

                process_data = self._build_process_data(
                    model=model,
                    audio_file=audio_file,
                    audio_file_base=audio_file_base,
                    export_path=item_export_path,
                    cache=cache,
                    subscriber=subscriber,
                    file_index=index,
                    total_files=len(input_paths),
                )

                separator = self._create_separator(model, process_data)
                separator.seperate()
                clear_gpu_cache()
                processed.append(audio_file)
                self._emit(
                    subscriber,
                    ProgressEvent(
                        percent=(index / len(input_paths)) * 100.0,
                        current_file=index,
                        total_files=len(input_paths),
                    ),
                )
                self._emit(subscriber, LogEvent(message="Done."))

            result = ProcessResult(
                processed_files=tuple(processed),
                output_path=export_path,
                model=resolved_model,
            )
            self._emit(subscriber, StatusEvent(message="Completed"))
            self._emit(
                subscriber,
                ResultEvent(
                    processed_files=result.processed_files,
                    output_path=result.output_path,
                    process_method=result.model.process_method,
                    model_name=result.model.model_name,
                    source=result.model.source,
                ),
            )
            return result
        except Exception:
            clear_gpu_cache()
            raise

    def _emit(self, subscriber: EventSubscriber | None, event: Event) -> None:
        if subscriber is not None:
            subscriber(event)

    def _available_models(self) -> list[ResolvedModel]:
        return [
            ResolvedModel(
                process_method=model.process_method,
                model_name=model.model_name,
                source=model.source,
            )
            for model in list_installed_models(self.catalog)
        ]

    def _build_model(self, resolved_model: ResolvedModel, request: SeparationRequest) -> ModelData:
        return ModelData(
            resolved_model.model_name,
            selected_process_method=VR_ARCH_TYPE if resolved_model.process_method == VR_ARCH_PM else resolved_model.process_method,
            settings=self._build_settings(resolved_model.process_method, request),
            resolvers=self._build_resolvers(),
        )

    def _build_settings(self, process_method: str, request: SeparationRequest) -> ModelDataSettings:
        output_settings = request.output
        processing_settings = request.options
        return ModelDataSettings(
            device_set=DEFAULT,
            is_deverb_vocals=False,
            deverb_vocal_opt="Vocals",
            is_denoise_model=False,
            is_gpu_conversion=processing_settings.use_gpu,
            is_normalization=processing_settings.normalize_output,
            is_use_opencl=False,
            is_primary_stem_only=processing_settings.primary_stem_only,
            is_secondary_stem_only=processing_settings.secondary_stem_only,
            is_primary_stem_only_demucs=processing_settings.primary_stem_only,
            is_secondary_stem_only_demucs=processing_settings.secondary_stem_only,
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
            wav_type_set=self._normalize_wav_type(output_settings.wav_type, output_settings.save_format),
            mp3_bit_set=output_settings.mp3_bitrate,
            save_format=output_settings.save_format or WAV,
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
            vr_hash_mapper=self.catalog.vr_hash_mapper,
            mdx_is_secondary_model_activate=False,
            margin=44100,
            mdx_segment_size=256,
            mdx_hash_mapper=self.catalog.mdx_hash_mapper,
            compensate=AUTO_SELECT,
            demucs_is_secondary_model_activate=False,
            is_demucs_pre_proc_model_activate=False,
            is_demucs_pre_proc_model_inst_mix=False,
            margin_demucs=44100,
            shifts=2,
            is_split_mode=True,
            segment=DEF_OPT,
            is_chunk_demucs=False,
            mdx_name_select_mapper=self.catalog.mdx_name_select_mapper,
            demucs_name_select_mapper=self.catalog.demucs_name_select_mapper,
        )

    def _normalize_wav_type(self, wav_type: str, save_format: str) -> str:
        if wav_type == "32-bit Float":
            return "FLOAT"
        if wav_type == "64-bit Float":
            return "DOUBLE" if save_format == WAV else "FLOAT"
        return wav_type or "PCM_16"

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
        cache: SourceCache,
        subscriber: EventSubscriber | None,
        file_index: int,
        total_files: int,
    ) -> dict[str, object]:
        progress_step = {"count": 0}

        def write_to_console(text: str, base_text: str = "") -> None:
            message = f"{base_text}{text}".rstrip()
            if message:
                self._emit(subscriber, LogEvent(message=message))

        def process_iteration() -> None:
            progress_step["count"] += 1
            fractional = min(progress_step["count"] * 10.0, 90.0)
            self._emit(
                subscriber,
                ProgressEvent(
                    percent=(((file_index - 1) + fractional / 100.0) / total_files) * 100.0,
                    current_file=file_index,
                    total_files=total_files,
                ),
            )

        def set_progress_bar(step: float, inference_iterations: float = 0.0) -> None:
            partial = min(max(float(step + inference_iterations), 0.0), 1.0)
            self._emit(
                subscriber,
                ProgressEvent(
                    percent=(((file_index - 1) + partial) / total_files) * 100.0,
                    current_file=file_index,
                    total_files=total_files,
                ),
            )

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


class DownloadJob:
    """Thin job wrapper around the framework-neutral download services."""

    def __init__(
        self,
        *,
        paths: RuntimePaths = DEFAULT_PATHS,
        opener=None,
    ) -> None:
        self.paths = paths
        self.opener = opener

    def available_downloads(self, vip_code: str = "") -> AvailableDownloads:
        online_state = fetch_online_state(opener=self._opener())
        decoded_vip_link = validate_vip_code(vip_code) if vip_code else NO_CODE
        catalog = build_download_catalog(online_state.payload, decoded_vip_link=decoded_vip_link)
        return AvailableDownloads(
            bulletin=online_state.bulletin,
            vr_items=tuple(list_downloadable_items(catalog, VR_ARCH_TYPE, paths=self.paths, opener=self._opener())),
            mdx_items=tuple(list_downloadable_items(catalog, MDX_ARCH_TYPE, paths=self.paths, opener=self._opener())),
            demucs_items=tuple(list_downloadable_items(catalog, DEMUCS_ARCH_TYPE, paths=self.paths, opener=self._opener())),
            decoded_vip_link=decoded_vip_link,
        )

    def run(
        self,
        request: DownloadRequest,
        *,
        subscriber: EventSubscriber | None = None,
    ) -> DownloadJobResult:
        self._emit(subscriber, StatusEvent(message="Refreshing download catalog"))
        online_state = fetch_online_state(opener=self._opener())
        decoded_vip_link = validate_vip_code(request.vip_code) if request.vip_code else NO_CODE
        catalog = build_download_catalog(online_state.payload, decoded_vip_link=decoded_vip_link)
        model_type = self._normalize_model_type(request.model_type)
        plan = resolve_download_plan(
            request.selection,
            model_type,
            catalog,
            decoded_vip_link=decoded_vip_link,
            paths=self.paths,
        )

        self._emit(subscriber, LogEvent(message=f"Preparing download: {request.selection}"))
        self._emit(subscriber, StatusEvent(message=f"Downloading {request.selection}"))

        def progress(item_index: int, total_items: int, current: int, total: int, _task) -> None:
            completed_items = item_index - 1
            item_fraction = (current / total) if total else 0.0
            percent = ((completed_items + item_fraction) / total_items) * 100.0 if total_items else 100.0
            self._emit(
                subscriber,
                ProgressEvent(percent=percent, current_file=item_index, total_files=total_items),
            )

        result = execute_download_plan(plan, opener=self._opener(), progress=progress)

        refreshed_settings = None
        if request.refresh_model_settings:
            self._emit(subscriber, StatusEvent(message="Refreshing model settings"))
            refreshed_settings = load_or_fetch_model_settings(paths=self.paths, opener=self._opener())

        job_result = DownloadJobResult(
            completed_files=tuple(str(path) for path in result.completed),
            skipped_existing=tuple(str(path) for path in result.skipped_existing),
            model_type=model_type,
            selection=request.selection,
            refreshed_settings=refreshed_settings,
        )
        self._emit(subscriber, StatusEvent(message="Completed"))
        self._emit(
            subscriber,
            DownloadResultEvent(
                completed_files=job_result.completed_files,
                skipped_existing=job_result.skipped_existing,
                model_type=job_result.model_type,
                selection=job_result.selection,
            ),
        )
        return job_result

    def _emit(self, subscriber: EventSubscriber | None, event: Event) -> None:
        if subscriber is not None:
            subscriber(event)

    def _normalize_model_type(self, model_type: str) -> str:
        return VR_ARCH_TYPE if model_type == VR_ARCH_PM else model_type

    def _opener(self):
        if self.opener is not None:
            return self.opener
        from urllib.request import urlopen

        return urlopen
