"""Framework-neutral job API shared by all adapters."""

from uvr_core.events import AudioToolResultEvent, DownloadResultEvent, EnsembleResultEvent, Event, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import AudioToolJob, AudioToolJobResult, AvailableDownloads, CatalogRefreshResult, DownloadJob, DownloadJobResult, EnsembleJob, EnsembleJobResult, ProcessResult, ResolvedModel, SeparationJob
from uvr_core.requests import (
    AudioToolRequest,
    DownloadRequest,
    EnsembleRequest,
    ModelSelectionRequest,
    OutputSettingsRequest,
    ProcessingOptionsRequest,
    SeparationRequest,
)

__all__ = [
    "Event",
    "AudioToolResultEvent",
    "DownloadResultEvent",
    "EnsembleResultEvent",
    "LogEvent",
    "ProgressEvent",
    "ResultEvent",
    "StatusEvent",
    "AudioToolRequest",
    "DownloadRequest",
    "EnsembleRequest",
    "ModelSelectionRequest",
    "OutputSettingsRequest",
    "ProcessingOptionsRequest",
    "SeparationRequest",
    "AudioToolJob",
    "AudioToolJobResult",
    "AvailableDownloads",
    "CatalogRefreshResult",
    "DownloadJob",
    "DownloadJobResult",
    "EnsembleJob",
    "EnsembleJobResult",
    "ProcessResult",
    "ResolvedModel",
    "SeparationJob",
]
