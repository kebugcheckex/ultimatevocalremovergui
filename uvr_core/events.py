"""Typed job events shared by the CLI and Qt adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Union


@dataclass(frozen=True)
class LogEvent:
    message: str
    event_type: str = "log"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StatusEvent:
    message: str
    event_type: str = "status"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProgressEvent:
    percent: float
    current_file: int | None = None
    total_files: int | None = None
    event_type: str = "progress"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResultEvent:
    processed_files: tuple[str, ...]
    output_path: str
    process_method: str
    model_name: str
    source: str
    event_type: str = "result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DownloadResultEvent:
    completed_files: tuple[str, ...]
    skipped_existing: tuple[str, ...]
    model_type: str
    selection: str
    event_type: str = "download_result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnsembleResultEvent:
    output_path: str
    inputs: tuple[str, ...]
    algorithm: str
    event_type: str = "ensemble_result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AudioToolResultEvent:
    audio_tool: str
    output_paths: tuple[str, ...]
    inputs: tuple[str, ...]
    event_type: str = "audio_tool_result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Event = Union[
    LogEvent,
    StatusEvent,
    ProgressEvent,
    ResultEvent,
    DownloadResultEvent,
    EnsembleResultEvent,
    AudioToolResultEvent,
]
