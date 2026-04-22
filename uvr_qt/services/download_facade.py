"""Qt-facing adapter over the shared download job API."""

from __future__ import annotations

from typing import Callable

from uvr_core.events import LogEvent, ProgressEvent, StatusEvent
from uvr_core.jobs import AvailableDownloads, CatalogRefreshResult, DownloadJob, DownloadJobResult
from uvr_core.requests import DownloadRequest


class DownloadFacade:
    """Qt adapter for catalog refresh and model downloads."""

    def __init__(self, job: DownloadJob | None = None) -> None:
        self.job = job or DownloadJob()

    def refresh_catalog(
        self,
        *,
        vip_code: str = "",
        refresh_model_settings: bool = True,
    ) -> CatalogRefreshResult:
        return self.job.refresh_catalog(
            vip_code=vip_code,
            refresh_model_settings=refresh_model_settings,
        )

    def available_downloads(self, vip_code: str = "") -> AvailableDownloads:
        return self.job.available_downloads(vip_code)

    def download(
        self,
        request: DownloadRequest,
        *,
        log: Callable[[str], None],
        progress: Callable[[float], None],
        status: Callable[[str], None],
    ) -> DownloadJobResult:
        def subscriber(event: LogEvent | ProgressEvent | StatusEvent) -> None:
            if isinstance(event, LogEvent):
                log(event.message)
            elif isinstance(event, ProgressEvent):
                progress(event.percent)
            elif isinstance(event, StatusEvent):
                status(event.message)

        return self.job.run(request, subscriber=subscriber)
