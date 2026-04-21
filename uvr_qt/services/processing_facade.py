"""Qt-facing adapter over the shared processing job API."""

from __future__ import annotations

from typing import Callable

from uvr_core.events import LogEvent, ProgressEvent, StatusEvent
from uvr_core.jobs import ProcessResult, ResolvedModel, SeparationJob
from uvr_core.requests import (
    ModelSelectionRequest,
    OutputSettingsRequest,
    ProcessingOptionsRequest,
    SeparationRequest,
)
from uvr_qt.state import AppState


class ProcessingFacade:
    """Qt adapter that converts AppState into a shared backend request."""

    def __init__(self) -> None:
        self.job = SeparationJob()

    def available_process_methods(self) -> tuple[str, ...]:
        return self.job.available_process_methods()

    def available_models_for_method(self, process_method: str) -> tuple[str, ...]:
        return self.job.available_models_for_method(process_method)

    def resolve_model(self, state: AppState) -> ResolvedModel | None:
        return self.job.resolve_model(_request_from_state(state))

    def process(
        self,
        state: AppState,
        *,
        log: Callable[[str], None],
        progress: Callable[[float], None],
        status: Callable[[str], None],
    ) -> ProcessResult:
        def subscriber(event: LogEvent | ProgressEvent | StatusEvent) -> None:
            if isinstance(event, LogEvent):
                log(event.message)
            elif isinstance(event, ProgressEvent):
                progress(event.percent)
            elif isinstance(event, StatusEvent):
                status(event.message)

        return self.job.run(_request_from_state(state), subscriber=subscriber)


def _request_from_state(state: AppState) -> SeparationRequest:
    return SeparationRequest(
        input_paths=state.paths.input_paths,
        export_path=state.paths.export_path,
        models=ModelSelectionRequest(
            vr_model=state.models.vr_model,
            mdx_net_model=state.models.mdx_net_model,
            demucs_model=state.models.demucs_model,
            demucs_pre_proc_model=state.models.demucs_pre_proc_model,
            vocal_splitter_model=state.models.vocal_splitter_model,
            demucs_stems=state.models.demucs_stems,
            mdx_stems=state.models.mdx_stems,
            secondary_models=dict(state.models.secondary_models),
        ),
        output=OutputSettingsRequest(
            save_format=state.output.save_format,
            wav_type=state.output.wav_type,
            mp3_bitrate=state.output.mp3_bitrate,
            add_model_name=state.output.add_model_name,
            create_model_folder=state.output.create_model_folder,
        ),
        options=ProcessingOptionsRequest(
            process_method=state.processing.process_method,
            audio_tool=state.processing.audio_tool,
            algorithm=state.processing.algorithm,
            device=state.processing.device,
            use_gpu=state.processing.use_gpu,
            primary_stem_only=state.processing.primary_stem_only,
            secondary_stem_only=state.processing.secondary_stem_only,
            normalize_output=state.processing.normalize_output,
            wav_ensemble=state.processing.wav_ensemble,
            testing_audio=state.processing.testing_audio,
            model_sample_mode=state.processing.model_sample_mode,
            model_sample_duration=state.processing.model_sample_duration,
        ),
        extra_settings=dict(state.extra_settings),
    )
