"""Qt-facing adapter over the shared processing job API."""

from __future__ import annotations

from typing import Callable

from uvr_core.events import LogEvent, ProgressEvent, StatusEvent
from uvr_core.jobs import ProcessResult, ResolvedModel, SeparationJob
from uvr_qt.state import AppState


class ProcessingFacade:
    """Qt adapter that converts AppState into a shared backend request."""

    def __init__(self, job: SeparationJob | None = None) -> None:
        self.job = job or SeparationJob()

    def cancel(self) -> None:
        self.job.cancel()

    def available_process_methods(self) -> tuple[str, ...]:
        return self.job.available_process_methods()

    def available_models_for_method(self, process_method: str) -> tuple[str, ...]:
        return self.job.available_models_for_method(process_method)

    def available_tagged_models_for_methods(self, process_methods: tuple[str, ...]) -> tuple[str, ...]:
        return self.job.available_tagged_models_for_methods(process_methods)

    def available_stem_targets(self, state: AppState, process_method: str) -> tuple[str, ...]:
        return self.job.available_stem_targets(state.to_separation_request(), process_method)

    def resolve_model(self, state: AppState) -> ResolvedModel | None:
        return self.job.resolve_model(state.to_separation_request())

    def save_model_defaults(self, state: AppState) -> str:
        return self.job.save_model_defaults(state.to_separation_request())

    def delete_model_defaults(self, state: AppState) -> str:
        return self.job.delete_model_defaults(state.to_separation_request())

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

        return self.job.run(state.to_separation_request(), subscriber=subscriber)
