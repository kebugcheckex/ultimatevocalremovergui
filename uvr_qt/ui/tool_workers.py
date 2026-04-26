"""Background workers for ensemble and audio-tool windows."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal

from uvr_core.jobs import AudioToolJobResult, EnsembleJobResult
from uvr_core.requests import AudioToolRequest, EnsembleRequest
from uvr_qt.services.tool_facades import AudioToolFacade, EnsembleFacade


class EnsembleWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: EnsembleFacade, request: EnsembleRequest) -> None:
        super().__init__()
        self.facade = facade
        self.request = request

    def run(self) -> None:
        try:
            result = self.facade.run(
                self.request,
                log=self.log_emitted.emit,
                progress=lambda v: self.progress_emitted.emit(int(max(0, min(v, 100)))),
                status=self.status_emitted.emit,
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)


class AudioToolWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: AudioToolFacade, request: AudioToolRequest) -> None:
        super().__init__()
        self.facade = facade
        self.request = request

    def run(self) -> None:
        try:
            result = self.facade.run(
                self.request,
                log=self.log_emitted.emit,
                progress=lambda v: self.progress_emitted.emit(int(max(0, min(v, 100)))),
                status=self.status_emitted.emit,
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)
