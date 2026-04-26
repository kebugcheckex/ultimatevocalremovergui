"""Framework-neutral processing jobs.

Import the public surface via ``uvr_core`` directly rather than this module.
"""

from __future__ import annotations

import os
from threading import Event as ThreadEvent
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gui_data.constants import (
    ALIGN_INPUTS,
    ALL_STEMS,
    AUTO_SELECT,
    CHOOSE_MODEL,
    CHANGE_PITCH,
    DEFAULT,
    DENOISE_NONE,
    DEMUCS_ARCH_TYPE,
    DEMUCS_OVERLAP,
    DEF_OPT,
    BASS_STEM,
    INTRO_MAPPER,
    ENSEMBLE_PARTITION,
    DRUM_STEM,
    INST_STEM,
    MATCH_INPUTS,
    MDX_OVERLAP,
    MDX23_OVERLAP,
    MDX_ARCH_TYPE,
    NO_BASS_STEM,
    NO_CODE,
    NO_DRUM_STEM,
    PHASE_SHIFTS_OPT,
    PITCH_TEXT,
    NO_MODEL,
    NO_OTHER_STEM,
    OTHER_STEM,
    TIME_TEXT,
    TIME_STRETCH,
    TIME_WINDOW_MAPPER,
    VOCAL_STEM,
    VOLUME_MAPPER,
    VR_ARCH_PM,
    VR_ARCH_TYPE,
    WAV,
)
from uvr.domain.audio_tools import AudioTools, AudioToolSettings
from uvr.domain.ensemble import Ensembler, EnsemblerSettings
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
from uvr_core.events import AudioToolResultEvent, DownloadResultEvent, EnsembleResultEvent, Event, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.requests import AudioToolRequest, DownloadRequest, EnsembleRequest, SeparationRequest


configure_backend_runtime()
from uvr.separation import SeperateDemucs, SeperateMDX, SeperateMDXC, SeperateVR  # noqa: E402
from uvr.separation.device import clear_gpu_cache  # noqa: E402


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


@dataclass(frozen=True)
class CatalogRefreshResult:
    available_downloads: AvailableDownloads
    refreshed_settings: ModelSettingsBundle | None = None


@dataclass(frozen=True)
class EnsembleJobResult:
    output_path: str
    inputs: tuple[str, ...]
    algorithm: str


@dataclass(frozen=True)
class AudioToolJobResult:
    audio_tool: str
    output_paths: tuple[str, ...]
    inputs: tuple[str, ...]


class JobCancelledError(RuntimeError):
    """Raised when a long-running backend job is cancelled."""


EventSubscriber = Callable[[Event], None]


class SeparationJob:
    """Thin job wrapper around the legacy separation backend.

    Not thread-safe.  Create a new instance for each job run, or reuse one
    instance sequentially.  Call ``cancel()`` from any thread to interrupt a
    running ``run()`` call.
    """

    def __init__(self) -> None:
        self.catalog = load_model_catalog()
        self._cancel_requested = ThreadEvent()

    def cancel(self) -> None:
        """Signal the running job to stop at the next cancellation checkpoint."""
        self._cancel_requested.set()

    def available_process_methods(self) -> tuple[str, ...]:
        """Return the process methods for which at least one model is installed."""
        methods = []
        for model in self._available_models():
            if model.process_method not in methods:
                methods.append(model.process_method)
        return tuple(methods)

    def available_models_for_method(self, process_method: str) -> tuple[str, ...]:
        """Return the names of installed models for a given process method."""
        return tuple(
            model.model_name
            for model in self._available_models()
            if model.process_method == process_method
        )

    def available_tagged_models_for_methods(self, process_methods: tuple[str, ...]) -> tuple[str, ...]:
        """Return ``"method//model"`` tagged strings for use in ensemble model lists."""
        return tuple(
            f"{model.process_method}{ENSEMBLE_PARTITION}{model.model_name}"
            for model in self._available_models()
            if model.process_method in process_methods
        )

    def available_stem_targets(self, request: SeparationRequest, process_method: str) -> tuple[str, ...]:
        """Return the stem names the selected model can produce for ``process_method``.

        Always includes ``ALL_STEMS`` for multi-stem models.  Falls back to
        ``(ALL_STEMS,)`` when the model cannot be loaded or resolved.
        """
        scoped_request = SeparationRequest(
            input_paths=request.input_paths,
            export_path=request.export_path,
            models=request.models,
            output=request.output,
            options=request.options.__class__(**{**request.options.__dict__, "process_method": process_method}),
            advanced=request.advanced,
            extra_settings=request.extra_settings,
        )
        resolved_model = self.resolve_model(scoped_request)
        if resolved_model is None:
            return (ALL_STEMS,)

        model = self._build_model(resolved_model, scoped_request)
        if not model.model_status:
            return (ALL_STEMS,)

        if resolved_model.process_method == DEMUCS_ARCH_TYPE:
            if model.demucs_stem_count >= 3:
                return (ALL_STEMS, *tuple(model.demucs_source_list))
            return tuple(model.demucs_source_list)

        if resolved_model.process_method == MDX_ARCH_TYPE:
            if model.mdx_model_stems:
                if len(model.mdx_model_stems) > 1:
                    return (ALL_STEMS, *tuple(model.mdx_model_stems))
                return tuple(model.mdx_model_stems)
            stems = tuple(dict.fromkeys(stem for stem in (ALL_STEMS, model.primary_stem, model.secondary_stem) if stem))
            return stems or (ALL_STEMS,)

        return (ALL_STEMS,)

    def resolve_model(self, request: SeparationRequest) -> ResolvedModel | None:
        """Return the best-matching installed model for the request, or None."""
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
        """Separate all input files and return a ProcessResult.

        Emits StatusEvent, LogEvent, and ProgressEvent to ``subscriber`` as
        each file is processed.  Emits a terminal ResultEvent on success.
        Raises JobCancelledError if cancel() was called during processing.
        Raises RuntimeError for validation failures or missing models.
        """
        self._cancel_requested.clear()
        resolved_model = self.resolve_model(request)
        if resolved_model is None:
            raise RuntimeError("No compatible backend models were found in the local models directories.")

        input_paths = tuple(path for path in request.input_paths if path)
        if not input_paths:
            raise RuntimeError("No input files selected.")

        export_path = request.export_path
        if not export_path:
            raise RuntimeError("No output folder selected.")

        model = self._build_model(resolved_model, request)
        if not model.model_status:
            raise RuntimeError(f'The selected backend model "{resolved_model.model_name}" is not available.')

        self._validate_request(request, resolved_model=resolved_model, model=model)
        os.makedirs(export_path, exist_ok=True)

        cache = SourceCache()
        processed: list[str] = []

        try:
            for index, audio_file in enumerate(input_paths, start=1):
                self._check_cancelled()
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
                self._check_cancelled()
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
        except JobCancelledError:
            clear_gpu_cache()
            self._emit(subscriber, StatusEvent(message="Cancelled"))
            self._emit(subscriber, LogEvent(message="Processing cancelled."))
            raise
        except Exception:
            clear_gpu_cache()
            raise

    def _emit(self, subscriber: EventSubscriber | None, event: Event) -> None:
        if subscriber is not None:
            subscriber(event)

    def _check_cancelled(self) -> None:
        if self._cancel_requested.is_set():
            raise JobCancelledError("Processing cancelled.")

    def _available_models(self) -> list[ResolvedModel]:
        return [
            ResolvedModel(
                process_method=model.process_method,
                model_name=model.model_name,
                source=model.source,
            )
            for model in list_installed_models(self.catalog)
        ]

    def save_model_defaults(self, request: SeparationRequest) -> str:
        """Save the current request settings as per-model defaults.

        Returns the model name whose defaults were saved.
        Supports VR and MDX architectures; Demucs does not use hash-based defaults.
        """
        resolved = self.resolve_model(request)
        if resolved is None:
            raise RuntimeError("No model could be resolved from the current selection.")
        if resolved.process_method not in (VR_ARCH_PM, VR_ARCH_TYPE, MDX_ARCH_TYPE):
            raise RuntimeError(
                f'Model defaults are only supported for VR and MDX models, not "{resolved.process_method}".'
            )
        ModelData(
            resolved.model_name,
            selected_process_method=VR_ARCH_TYPE if resolved.process_method == VR_ARCH_PM else resolved.process_method,
            settings=self._build_settings(resolved.process_method, request),
            resolvers=self._build_resolvers(request),
            is_change_def=True,
        )
        return resolved.model_name

    def delete_model_defaults(self, request: SeparationRequest) -> str:
        """Delete the stored per-model defaults for the currently resolved model.

        Returns the model name whose defaults were deleted, or raises if no
        hash file was found.
        """
        import os

        resolved = self.resolve_model(request)
        if resolved is None:
            raise RuntimeError("No model could be resolved from the current selection.")
        if resolved.process_method not in (VR_ARCH_PM, VR_ARCH_TYPE, MDX_ARCH_TYPE):
            raise RuntimeError(
                f'Model defaults are only supported for VR and MDX models, not "{resolved.process_method}".'
            )
        model_data = ModelData(
            resolved.model_name,
            selected_process_method=VR_ARCH_TYPE if resolved.process_method == VR_ARCH_PM else resolved.process_method,
            settings=self._build_settings(resolved.process_method, request),
            resolvers=self._build_resolvers(request),
            is_get_hash_dir_only=True,
        )
        hash_file = getattr(model_data, "model_hash_dir", None)
        if not hash_file or not os.path.isfile(hash_file):
            raise RuntimeError(f'No saved defaults found for "{resolved.model_name}".')
        os.remove(hash_file)
        return resolved.model_name

    def _build_model(
        self,
        resolved_model: ResolvedModel,
        request: SeparationRequest,
        *,
        is_secondary_model: bool = False,
        primary_model_primary_stem: str | None = None,
        is_primary_model_primary_stem_only: bool = False,
        is_primary_model_secondary_stem_only: bool = False,
        is_pre_proc_model: bool = False,
        is_vocal_split_model: bool = False,
    ) -> ModelData:
        return ModelData(
            resolved_model.model_name,
            selected_process_method=VR_ARCH_TYPE if resolved_model.process_method == VR_ARCH_PM else resolved_model.process_method,
            is_secondary_model=is_secondary_model,
            primary_model_primary_stem=primary_model_primary_stem,
            is_primary_model_primary_stem_only=is_primary_model_primary_stem_only,
            is_primary_model_secondary_stem_only=is_primary_model_secondary_stem_only,
            is_pre_proc_model=is_pre_proc_model,
            is_vocal_split_model=is_vocal_split_model,
            settings=self._build_settings(resolved_model.process_method, request),
            resolvers=self._build_resolvers(request),
        )

    def _build_settings(self, process_method: str, request: SeparationRequest) -> ModelDataSettings:
        output_settings = request.output
        processing_settings = request.options
        advanced = request.advanced
        extra_settings = request.extra_settings
        return ModelDataSettings(
            device_set=processing_settings.device or DEFAULT,
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
            mdx_batch_size=advanced.mdx_batch_size,
            mdxnet_stems=request.models.mdx_stems or ALL_STEMS,
            overlap=str(advanced.overlap or DEMUCS_OVERLAP[0]),
            overlap_mdx=str(advanced.overlap_mdx or MDX_OVERLAP[0]),
            overlap_mdx23=str(MDX23_OVERLAP[6]),
            semitone_shift="0",
            is_match_frequency_pitch=True,
            is_mdx23_combine_stems=True,
            wav_type_set=self._normalize_wav_type(output_settings.wav_type, output_settings.save_format),
            mp3_bit_set=output_settings.mp3_bitrate,
            save_format=output_settings.save_format or WAV,
            is_invert_spec=False,
            demucs_stems=request.models.demucs_stems or ALL_STEMS,
            is_demucs_combine_stems=True,
            chosen_process_method=VR_ARCH_TYPE if process_method == VR_ARCH_PM else process_method,
            is_save_inst_set_vocal_splitter=bool(extra_settings.get("is_save_inst_set_vocal_splitter", False)),
            ensemble_main_stem="",
            vr_is_secondary_model_activate=self._secondary_enabled(request, VR_ARCH_TYPE),
            aggression_setting=advanced.aggression_setting,
            is_tta=advanced.is_tta,
            is_post_process=advanced.is_post_process,
            window_size=advanced.window_size,
            batch_size=advanced.batch_size,
            crop_size=advanced.crop_size,
            is_high_end_process=advanced.is_high_end_process,
            post_process_threshold=advanced.post_process_threshold,
            vr_hash_mapper=self.catalog.vr_hash_mapper,
            mdx_is_secondary_model_activate=self._secondary_enabled(request, MDX_ARCH_TYPE),
            margin=advanced.margin,
            mdx_segment_size=advanced.mdx_segment_size,
            mdx_hash_mapper=self.catalog.mdx_hash_mapper,
            compensate=advanced.compensate or AUTO_SELECT,
            demucs_is_secondary_model_activate=self._secondary_enabled(request, DEMUCS_ARCH_TYPE),
            is_demucs_pre_proc_model_activate=bool(extra_settings.get("is_demucs_pre_proc_model_activate", False)),
            is_demucs_pre_proc_model_inst_mix=bool(extra_settings.get("is_demucs_pre_proc_model_inst_mix", False)),
            margin_demucs=advanced.margin_demucs,
            shifts=advanced.shifts,
            is_split_mode=True,
            segment=advanced.segment or DEF_OPT,
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

    def _build_resolvers(self, request: SeparationRequest) -> ModelDataResolvers:
        return ModelDataResolvers(
            return_ensemble_stems=lambda: ("", ""),
            check_only_selection_stem=lambda _check_type: False,
            determine_secondary_model=lambda process_method, primary_stem, primary_only, secondary_only: self._determine_secondary_model(
                request,
                process_method=process_method,
                primary_stem=primary_stem,
                is_primary_stem_only=primary_only,
                is_secondary_stem_only=secondary_only,
            ),
            determine_demucs_pre_proc_model=lambda primary_stem=None: self._determine_demucs_pre_proc_model(
                request,
                primary_stem=primary_stem,
            ),
            determine_vocal_split_model=lambda: self._determine_vocal_split_model(request),
            resolve_popup_model_data=lambda *_args: None,
        )

    def _resolve_tagged_model(self, tagged_name: str) -> ResolvedModel | None:
        process_method, separator, model_name = tagged_name.partition(ENSEMBLE_PARTITION)
        if not separator or not model_name:
            return None
        return self._resolve_model_by_method_and_name(process_method, model_name)

    def _resolve_model_by_method_and_name(self, process_method: str, model_name: str) -> ResolvedModel | None:
        for candidate in self._available_models():
            if candidate.process_method == process_method and candidate.model_name == model_name:
                return candidate
        return None

    def _resolve_model_reference(self, model_reference: str) -> ResolvedModel | None:
        if not model_reference or model_reference == NO_MODEL:
            return None

        tagged_model = self._resolve_tagged_model(model_reference)
        if tagged_model is not None:
            return tagged_model

        for candidate in self._available_models():
            if candidate.model_name == model_reference:
                return candidate
        return None

    def _secondary_enabled(self, request: SeparationRequest, process_method: str) -> bool:
        activation_key = {
            VR_ARCH_TYPE: "vr_is_secondary_model_activate",
            VR_ARCH_PM: "vr_is_secondary_model_activate",
            MDX_ARCH_TYPE: "mdx_is_secondary_model_activate",
            DEMUCS_ARCH_TYPE: "demucs_is_secondary_model_activate",
        }.get(process_method)
        activations = getattr(request.models, "secondary_model_activations", {})
        return bool(activation_key and activations.get(activation_key, False))

    def _secondary_slot_key(self, process_method: str, primary_stem: str) -> str | None:
        prefix = {
            VR_ARCH_TYPE: "vr",
            VR_ARCH_PM: "vr",
            MDX_ARCH_TYPE: "mdx",
            DEMUCS_ARCH_TYPE: "demucs",
        }.get(process_method)
        if prefix is None:
            return None

        if primary_stem in (VOCAL_STEM, INST_STEM):
            stem_key = "voc_inst"
        elif primary_stem in (OTHER_STEM, NO_OTHER_STEM):
            stem_key = "other"
        elif primary_stem in (DRUM_STEM, NO_DRUM_STEM):
            stem_key = "drums"
        elif primary_stem in (BASS_STEM, NO_BASS_STEM):
            stem_key = "bass"
        else:
            return None
        return f"{prefix}_{stem_key}_secondary_model"

    def _determine_secondary_model(
        self,
        request: SeparationRequest,
        *,
        process_method: str,
        primary_stem: str,
        is_primary_stem_only: bool = False,
        is_secondary_stem_only: bool = False,
    ) -> tuple[ModelData | None, float | None]:
        if not self._secondary_enabled(request, process_method):
            return None, None

        model_key = self._secondary_slot_key(process_method, primary_stem)
        if model_key is None:
            return None, None

        secondary_models = getattr(request.models, "secondary_models", {})
        model_reference = secondary_models.get(model_key, NO_MODEL)
        resolved_model = self._resolve_model_reference(model_reference)
        if resolved_model is None:
            return None, None

        scale_key = f"{model_key}_scale"
        secondary_scales = getattr(request.models, "secondary_model_scales", {})
        scale = float(secondary_scales.get(scale_key, 0.5))
        model = self._build_model(
            resolved_model,
            request,
            is_secondary_model=True,
            primary_model_primary_stem=primary_stem,
            is_primary_model_primary_stem_only=is_primary_stem_only,
            is_primary_model_secondary_stem_only=is_secondary_stem_only,
        )
        if not model.model_status:
            return None, None
        return model, scale

    def _validate_request(
        self,
        request: SeparationRequest,
        *,
        resolved_model: ResolvedModel | None = None,
        model: ModelData | None = None,
    ) -> None:
        if request.options.primary_stem_only and request.options.secondary_stem_only:
            raise RuntimeError("Primary stem only and secondary stem only cannot both be enabled.")

        process_method = resolved_model.process_method if resolved_model is not None else request.options.process_method
        secondary_scales = getattr(request.models, "secondary_model_scales", {})
        secondary_models = getattr(request.models, "secondary_models", {})
        for scale_key, raw_scale in secondary_scales.items():
            scale = float(raw_scale)
            if scale < 0.01 or scale > 0.99:
                raise RuntimeError(f"{scale_key} must be between 0.01 and 0.99.")

        for process_method in (VR_ARCH_TYPE, MDX_ARCH_TYPE, DEMUCS_ARCH_TYPE):
            if not self._secondary_enabled(request, process_method):
                continue
            prefix = "vr" if process_method == VR_ARCH_TYPE else process_method.lower().split("-")[0]
            for stem_key in ("voc_inst", "other", "bass", "drums"):
                model_key = f"{prefix}_{stem_key}_secondary_model"
                model_reference = secondary_models.get(model_key, NO_MODEL)
                if model_reference == NO_MODEL:
                    continue
                if self._resolve_model_reference(model_reference) is None:
                    raise RuntimeError(f'Secondary model "{model_reference}" is not installed.')

        if bool(request.extra_settings.get("is_demucs_pre_proc_model_activate", False)):
            if process_method != DEMUCS_ARCH_TYPE:
                raise RuntimeError("Demucs pre-proc is only available for Demucs workflows.")
            if request.models.demucs_stems in {VOCAL_STEM, INST_STEM}:
                raise RuntimeError("Demucs pre-proc requires All Stems or a non-vocal Demucs stem target.")
            if not self._resolve_model_reference(request.models.demucs_pre_proc_model):
                raise RuntimeError("Demucs pre-proc is enabled, but no installed pre-proc model is selected.")
            if model is not None and getattr(model, "demucs_stem_count", 0) < 3:
                raise RuntimeError("Demucs pre-proc is only supported for Demucs models with at least three stems.")

        if bool(request.extra_settings.get("is_demucs_pre_proc_model_inst_mix", False)) and not bool(
            request.extra_settings.get("is_demucs_pre_proc_model_activate", False)
        ):
            raise RuntimeError("Save Instrumental Mixture requires Demucs pre-proc to be enabled.")

        if bool(request.extra_settings.get("is_set_vocal_splitter", False)):
            if not self._resolve_model_reference(request.models.vocal_splitter_model):
                raise RuntimeError("Vocal splitter is enabled, but no installed vocal splitter model is selected.")
        elif bool(request.extra_settings.get("is_save_inst_set_vocal_splitter", False)):
            raise RuntimeError("Save Split Instrumentals requires the vocal splitter workflow to be enabled.")

        if process_method == DEMUCS_ARCH_TYPE and model is not None:
            valid_stems = set(getattr(model, "demucs_source_list", ()))
            if request.models.demucs_stems != ALL_STEMS and request.models.demucs_stems not in valid_stems:
                raise RuntimeError(
                    f'Demucs stem target "{request.models.demucs_stems}" is not supported by the selected model.'
                )

        if process_method == MDX_ARCH_TYPE and model is not None and getattr(model, "mdx_model_stems", None):
            valid_stems = set(model.mdx_model_stems)
            if request.models.mdx_stems != ALL_STEMS and request.models.mdx_stems not in valid_stems:
                raise RuntimeError(
                    f'MDX stem target "{request.models.mdx_stems}" is not supported by the selected model.'
                )

        # TODO: Ensemble-era combine-stems and popup-only composition permutations still live outside
        # the Phase 4 Qt surface. Add explicit validation here when those workflows are promoted.

    def _determine_demucs_pre_proc_model(
        self,
        request: SeparationRequest,
        *,
        primary_stem: str | None = None,
    ) -> ModelData | None:
        if not bool(request.extra_settings.get("is_demucs_pre_proc_model_activate", False)):
            return None
        resolved_model = self._resolve_model_reference(request.models.demucs_pre_proc_model)
        if resolved_model is None:
            return None
        model = self._build_model(
            resolved_model,
            request,
            primary_model_primary_stem=primary_stem,
            is_pre_proc_model=True,
        )
        return model if model.model_status else None

    def _determine_vocal_split_model(self, request: SeparationRequest) -> ModelData | None:
        if not bool(request.extra_settings.get("is_set_vocal_splitter", False)):
            return None
        resolved_model = self._resolve_model_reference(request.models.vocal_splitter_model)
        if resolved_model is None:
            return None
        model = self._build_model(
            resolved_model,
            request,
            is_vocal_split_model=True,
        )
        return model if model.model_status else None

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
            self._check_cancelled()
            message = f"{base_text}{text}".rstrip()
            if message:
                self._emit(subscriber, LogEvent(message=message))

        def process_iteration() -> None:
            self._check_cancelled()
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
            self._check_cancelled()
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
    """Thin job wrapper around the framework-neutral download services.

    Stateless after construction; safe to reuse across sequential calls.
    ``opener`` is a urllib-compatible callable used for all HTTP requests;
    leave it None to use ``urllib.request.urlopen``.
    """

    def __init__(
        self,
        *,
        paths: RuntimePaths = DEFAULT_PATHS,
        opener=None,
    ) -> None:
        self.paths = paths
        self.opener = opener

    def available_downloads(self, vip_code: str = "") -> AvailableDownloads:
        """Fetch the online catalog and return the list of downloadable items."""
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

    def refresh_catalog(
        self,
        *,
        vip_code: str = "",
        refresh_model_settings: bool = True,
    ) -> CatalogRefreshResult:
        """Fetch the online catalog and optionally refresh bundled model settings."""
        available = self.available_downloads(vip_code)
        refreshed_settings = None
        if refresh_model_settings:
            refreshed_settings = load_or_fetch_model_settings(paths=self.paths, opener=self._opener())
        return CatalogRefreshResult(
            available_downloads=available,
            refreshed_settings=refreshed_settings,
        )

    def run(
        self,
        request: DownloadRequest,
        *,
        subscriber: EventSubscriber | None = None,
    ) -> DownloadJobResult:
        """Download the requested model and return a DownloadJobResult.

        Emits StatusEvent, LogEvent, and ProgressEvent to ``subscriber``.
        Emits a terminal DownloadResultEvent on success.
        """
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


class EnsembleJob:
    """Framework-neutral wrapper around manual ensemble operations."""

    def run(
        self,
        request: EnsembleRequest,
        *,
        subscriber: EventSubscriber | None = None,
    ) -> EnsembleJobResult:
        """Ensemble the input files and return an EnsembleJobResult.

        Requires at least two input files.  Emits StatusEvent, LogEvent, and
        ProgressEvent to ``subscriber``.  Emits a terminal EnsembleResultEvent
        on success.
        """
        input_paths = tuple(path for path in request.input_paths if path)
        if len(input_paths) < 2:
            raise RuntimeError("Manual ensemble requires at least two input files.")
        if not request.export_path:
            raise RuntimeError("No output folder selected.")

        export_path = Path(request.export_path)
        export_path.mkdir(parents=True, exist_ok=True)

        for path in input_paths:
            if not Path(path).is_file():
                raise RuntimeError(f'Input file does not exist: "{path}"')

        self._emit(subscriber, StatusEvent(message="Preparing ensemble"))
        self._emit(subscriber, LogEvent(message=f"Algorithm: {request.algorithm}"))
        self._emit(
            subscriber,
            ProgressEvent(percent=0.0, current_file=0, total_files=len(input_paths)),
        )

        ensembler = Ensembler(
            settings=EnsemblerSettings(
                is_save_all_outputs_ensemble=False,
                chosen_ensemble_name=request.output_name,
                ensemble_type=f"{request.algorithm}/{request.algorithm}",
                ensemble_main_stem_pair=("", ""),
                export_path=str(export_path),
                is_append_ensemble_name=False,
                is_testing_audio=False,
                is_normalization=request.normalize_output,
                is_wav_ensemble=request.wav_ensemble,
                wav_type_set=request.wav_type,
                mp3_bit_set=request.mp3_bitrate,
                save_format=request.save_format,
                choose_algorithm=request.algorithm,
            ),
            is_manual_ensemble=True,
        )

        audio_file_base = request.output_name
        if request.algorithm == "Combine Inputs":
            ensembler.combine_audio(list(input_paths), audio_file_base)
        else:
            ensembler.ensemble_manual(list(input_paths), audio_file_base)

        output_suffix = request.save_format.lower()
        if request.algorithm == "Combine Inputs":
            output_path = export_path / f"{audio_file_base}.{output_suffix}"
        else:
            algorithm_text = f"_({request.algorithm})"
            output_path = export_path / f"{audio_file_base}{algorithm_text}.{output_suffix}"

        result = EnsembleJobResult(
            output_path=str(output_path),
            inputs=input_paths,
            algorithm=request.algorithm,
        )
        self._emit(
            subscriber,
            ProgressEvent(percent=100.0, current_file=len(input_paths), total_files=len(input_paths)),
        )
        self._emit(subscriber, StatusEvent(message="Completed"))
        self._emit(
            subscriber,
            EnsembleResultEvent(
                output_path=result.output_path,
                inputs=result.inputs,
                algorithm=result.algorithm,
            ),
        )
        return result

    def _emit(self, subscriber: EventSubscriber | None, event: Event) -> None:
        if subscriber is not None:
            subscriber(event)


class AudioToolJob:
    """Framework-neutral wrapper around legacy audio-tool operations."""

    def run(
        self,
        request: AudioToolRequest,
        *,
        subscriber: EventSubscriber | None = None,
    ) -> AudioToolJobResult:
        """Run the requested audio tool and return an AudioToolJobResult.

        Emits StatusEvent, LogEvent, and ProgressEvent to ``subscriber``.
        Emits a terminal AudioToolResultEvent on success.
        Raises RuntimeError for unsupported tool / input count combinations.
        """
        input_paths = tuple(path for path in request.input_paths if path)
        if not input_paths:
            raise RuntimeError("No input files selected.")
        if not request.export_path:
            raise RuntimeError("No output folder selected.")

        export_path = Path(request.export_path)
        export_path.mkdir(parents=True, exist_ok=True)

        for path in input_paths:
            if not Path(path).is_file():
                raise RuntimeError(f'Input file does not exist: "{path}"')

        if request.audio_tool in {ALIGN_INPUTS, MATCH_INPUTS} and len(input_paths) != 2:
            raise RuntimeError(f"{request.audio_tool} requires exactly two input files.")

        settings = AudioToolSettings(
            export_path=str(export_path),
            wav_type_set=request.wav_type,
            is_normalization=request.normalize_output,
            is_testing_audio=request.testing_audio,
            save_format=request.save_format,
            mp3_bit_set=request.mp3_bitrate,
            align_window=TIME_WINDOW_MAPPER[request.align_window],
            align_intro_val=INTRO_MAPPER[request.align_intro],
            db_analysis_val=VOLUME_MAPPER[request.db_analysis],
            is_save_align=request.save_aligned,
            is_match_silence=request.match_silence,
            is_spec_match=request.spec_match,
            phase_option=request.phase_option,
            phase_shifts=PHASE_SHIFTS_OPT[request.phase_shifts],
            time_stretch_rate=request.time_stretch_rate,
            pitch_rate=request.pitch_rate,
            is_time_correction=request.time_correction,
        )
        audio_tool = AudioTools(request.audio_tool, settings=settings)
        output_suffix = self._output_suffix(request.save_format)

        self._emit(subscriber, StatusEvent(message=f"Preparing {request.audio_tool.lower()}"))
        self._emit(subscriber, ProgressEvent(percent=0.0, current_file=0, total_files=len(input_paths)))

        if request.audio_tool in {ALIGN_INPUTS, MATCH_INPUTS}:
            output_paths = self._run_dual_input_tool(
                request=request,
                input_paths=input_paths,
                export_path=export_path,
                output_suffix=output_suffix,
                audio_tool=audio_tool,
                subscriber=subscriber,
            )
        else:
            output_paths = self._run_single_input_tool(
                request=request,
                input_paths=input_paths,
                export_path=export_path,
                output_suffix=output_suffix,
                audio_tool=audio_tool,
                subscriber=subscriber,
            )

        result = AudioToolJobResult(
            audio_tool=request.audio_tool,
            output_paths=output_paths,
            inputs=input_paths,
        )
        self._emit(subscriber, StatusEvent(message="Completed"))
        self._emit(
            subscriber,
            AudioToolResultEvent(
                audio_tool=result.audio_tool,
                output_paths=result.output_paths,
                inputs=result.inputs,
            ),
        )
        return result

    def _run_dual_input_tool(
        self,
        *,
        request: AudioToolRequest,
        input_paths: tuple[str, ...],
        export_path: Path,
        output_suffix: str,
        audio_tool: AudioTools,
        subscriber: EventSubscriber | None,
    ) -> tuple[str, ...]:
        first_base = Path(input_paths[0]).stem
        second_base = Path(input_paths[1]).stem
        prefix = audio_tool.is_testing_audio

        self._emit(subscriber, LogEvent(message=f'Input 1: "{Path(input_paths[0]).name}"'))
        self._emit(subscriber, LogEvent(message=f'Input 2: "{Path(input_paths[1]).name}"'))

        if request.audio_tool == MATCH_INPUTS:
            self._emit(subscriber, StatusEvent(message="Processing matchering"))
            audio_tool.match_inputs(
                list(input_paths),
                first_base,
                lambda message: self._emit_log(subscriber, message),
            )
            output_paths = (str(export_path / f"{prefix}{first_base}_(Matched).{output_suffix}"),)
        else:
            self._emit(subscriber, StatusEvent(message="Processing alignment"))
            audio_tool.align_inputs(
                list(input_paths),
                first_base,
                second_base,
                lambda message: self._emit_log(subscriber, message),
                lambda step, inference_iterations=0: self._emit(
                    subscriber,
                    ProgressEvent(
                        percent=min(99.0, max(0.0, (step + inference_iterations) * 100.0)),
                        current_file=2,
                        total_files=2,
                    ),
                ),
            )
            output_paths = [str(export_path / f"{prefix}{first_base}_(Inverted).{output_suffix}")]
            if request.save_aligned or request.spec_match:
                output_paths.append(str(export_path / f"{prefix}{second_base}_(Aligned).{output_suffix}"))

        self._emit(subscriber, ProgressEvent(percent=100.0, current_file=2, total_files=2))
        return tuple(output_paths)

    def _run_single_input_tool(
        self,
        *,
        request: AudioToolRequest,
        input_paths: tuple[str, ...],
        export_path: Path,
        output_suffix: str,
        audio_tool: AudioTools,
        subscriber: EventSubscriber | None,
    ) -> tuple[str, ...]:
        output_paths: list[str] = []
        total = len(input_paths)
        file_text = TIME_TEXT if request.audio_tool == TIME_STRETCH else PITCH_TEXT

        for index, path in enumerate(input_paths, start=1):
            base_name = Path(path).stem
            self._emit(subscriber, StatusEvent(message=f"Processing {index}/{total}"))
            self._emit(subscriber, LogEvent(message=f'Input {index}/{total}: "{Path(path).name}"'))
            audio_tool.pitch_or_time_shift(path, base_name)
            output_paths.append(str(export_path / f"{audio_tool.is_testing_audio}{base_name}{file_text}.{output_suffix}"))
            self._emit(
                subscriber,
                ProgressEvent(
                    percent=(index / total) * 100.0,
                    current_file=index,
                    total_files=total,
                ),
            )

        return tuple(output_paths)

    def _emit_log(self, subscriber: EventSubscriber | None, message: str) -> None:
        cleaned = message.strip()
        if cleaned:
            self._emit(subscriber, LogEvent(message=cleaned))

    def _output_suffix(self, save_format: str) -> str:
        return {
            "WAV": "wav",
            "FLAC": "flac",
            "MP3": "mp3",
        }.get(save_format.upper(), save_format.lower())

    def _emit(self, subscriber: EventSubscriber | None, event: Event) -> None:
        if subscriber is not None:
            subscriber(event)
