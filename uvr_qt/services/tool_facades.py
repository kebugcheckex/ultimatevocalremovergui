"""Qt-facing adapters for ensemble and audio-tool jobs."""

from __future__ import annotations

from typing import Callable

from uvr_core.events import AudioToolResultEvent, EnsembleResultEvent, LogEvent, ProgressEvent, StatusEvent
from uvr_core.jobs import AudioToolJob, AudioToolJobResult, EnsembleJob, EnsembleJobResult
from uvr_core.requests import AudioToolRequest, EnsembleRequest


class EnsembleFacade:
    """Qt adapter over the shared EnsembleJob."""

    def __init__(self, job: EnsembleJob | None = None) -> None:
        self.job = job or EnsembleJob()

    def run(
        self,
        request: EnsembleRequest,
        *,
        log: Callable[[str], None],
        progress: Callable[[float], None],
        status: Callable[[str], None],
    ) -> EnsembleJobResult:
        def subscriber(event: object) -> None:
            if isinstance(event, LogEvent):
                log(event.message)
            elif isinstance(event, ProgressEvent):
                progress(event.percent)
            elif isinstance(event, StatusEvent):
                status(event.message)

        return self.job.run(request, subscriber=subscriber)


class AudioToolFacade:
    """Qt adapter over the shared AudioToolJob."""

    def __init__(self, job: AudioToolJob | None = None) -> None:
        self.job = job or AudioToolJob()

    def run(
        self,
        request: AudioToolRequest,
        *,
        log: Callable[[str], None],
        progress: Callable[[float], None],
        status: Callable[[str], None],
    ) -> AudioToolJobResult:
        def subscriber(event: object) -> None:
            if isinstance(event, LogEvent):
                log(event.message)
            elif isinstance(event, ProgressEvent):
                progress(event.percent)
            elif isinstance(event, StatusEvent):
                status(event.message)

        return self.job.run(request, subscriber=subscriber)
