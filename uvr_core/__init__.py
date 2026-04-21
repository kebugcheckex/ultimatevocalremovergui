"""Framework-neutral job API shared by all adapters."""

from uvr_core.events import DownloadResultEvent, Event, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import AvailableDownloads, DownloadJob, DownloadJobResult, ProcessResult, ResolvedModel, SeparationJob
from uvr_core.requests import (
    DownloadRequest,
    ModelSelectionRequest,
    OutputSettingsRequest,
    ProcessingOptionsRequest,
    SeparationRequest,
)

__all__ = [
    "Event",
    "DownloadResultEvent",
    "LogEvent",
    "ProgressEvent",
    "ResultEvent",
    "StatusEvent",
    "DownloadRequest",
    "ModelSelectionRequest",
    "OutputSettingsRequest",
    "ProcessingOptionsRequest",
    "SeparationRequest",
    "AvailableDownloads",
    "DownloadJob",
    "DownloadJobResult",
    "ProcessResult",
    "ResolvedModel",
    "SeparationJob",
]
