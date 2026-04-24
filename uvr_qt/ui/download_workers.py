"""Background workers for the download manager window."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal

from uvr_core.jobs import CatalogRefreshResult, DownloadJobResult
from uvr_core.requests import DownloadRequest
from uvr_qt.services import DownloadFacade


class CatalogRefreshWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, facade: DownloadFacade, *, vip_code: str) -> None:
        super().__init__()
        self.facade = facade
        self.vip_code = vip_code

    def run(self) -> None:
        try:
            result = self.facade.refresh_catalog(vip_code=self.vip_code)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)


class DownloadWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: DownloadFacade, *, request: DownloadRequest) -> None:
        super().__init__()
        self.facade = facade
        self.request = request

    def run(self) -> None:
        try:
            result = self.facade.download(
                self.request,
                log=self.log_emitted.emit,
                progress=lambda value: self.progress_emitted.emit(int(max(0, min(value, 100)))),
                status=self.status_emitted.emit,
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)
