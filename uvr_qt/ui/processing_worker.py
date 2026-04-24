"""Background worker for the processing pipeline."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal

from uvr_qt.services import JobCancelledError, ProcessingFacade
from uvr_qt.state import AppState


class ProcessingWorker(QObject):
    finished = Signal(object)
    cancelled = Signal()
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: ProcessingFacade, state: AppState):
        super().__init__()
        self.facade = facade
        self.state = state

    def cancel(self) -> None:
        self.facade.cancel()

    def run(self) -> None:
        try:
            result = self.facade.process(
                self.state,
                log=self.log_emitted.emit,
                progress=lambda value: self.progress_emitted.emit(int(max(0, min(value, 100)))),
                status=self.status_emitted.emit,
            )
        except JobCancelledError:
            self.cancelled.emit()
            return
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self.failed.emit(error_message)
            return

        self.finished.emit(result)
