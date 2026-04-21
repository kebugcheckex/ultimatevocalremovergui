"""Framework-neutral job API shared by all adapters."""

from uvr_core.events import Event, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import ProcessResult, ResolvedModel, SeparationJob
from uvr_core.requests import (
    ModelSelectionRequest,
    OutputSettingsRequest,
    ProcessingOptionsRequest,
    SeparationRequest,
)

__all__ = [
    "Event",
    "LogEvent",
    "ProgressEvent",
    "ResultEvent",
    "StatusEvent",
    "ModelSelectionRequest",
    "OutputSettingsRequest",
    "ProcessingOptionsRequest",
    "SeparationRequest",
    "ProcessResult",
    "ResolvedModel",
    "SeparationJob",
]
