"""Framework-neutral job API shared by all adapters.

This package is the stable boundary between the backend (uvr/) and adapters
(uvr_qt/, uvr_cli/).  Nothing below this line requires PySide6, Tk, or Click.

Public surface (stable as of Phase 6)
--------------------------------------

Events — uvr_core.events
  Event               discriminated union of all event types below
  LogEvent            free-form log line emitted during a running job
  StatusEvent         one-line status string; replaces the previous value
  ProgressEvent       numeric progress in [0, 100] with optional file counters
  ResultEvent         separation completed; carries processed paths and model info
  EnsembleResultEvent ensemble completed; carries output path and algorithm
  DownloadResultEvent download completed; carries counts and model type
  AudioToolResultEvent audio-tool completed; carries output paths and tool name

All events are frozen dataclasses with a ``to_dict()`` method that returns a
JSON-serializable dict (suitable for SSE / WebSocket serialization).

Requests — uvr_core.requests
  SeparationRequest         inputs + model + output + advanced controls
  DownloadRequest           model type, selection name, optional VIP code
  EnsembleRequest           input files, algorithm, output settings
  AudioToolRequest          tool name, inputs, tool-specific parameters
  ModelSelectionRequest     sub-request: which models and stems
  OutputSettingsRequest     sub-request: format, bitrate, naming flags
  ProcessingOptionsRequest  sub-request: method, device, stem-only flags

All requests are frozen dataclasses. Build them directly, or derive a
SeparationRequest from persisted settings via ``SeparationRequest.from_settings()``.

Jobs — uvr_core.jobs
  SeparationJob   run / cancel separation; query installed models and stems
  DownloadJob     run / list / refresh the download catalog
  EnsembleJob     run a manual ensemble over pre-separated stems
  AudioToolJob    run an audio tool (align, pitch-shift, time-stretch, matchering)

Every job's ``run()`` accepts an optional ``subscriber: Callable[[Event], None]``
and emits typed events in real time.  Jobs are single-threaded by design; callers
are responsible for running them on a worker thread and forwarding events to UI.

``SeparationJob`` is not safe to share across threads.  Create one per job run.
``DownloadJob``, ``EnsembleJob``, and ``AudioToolJob`` are stateless and may be
reused, but concurrent calls are not supported.
"""

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
