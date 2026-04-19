"""Persistence helpers for UVR settings."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Mapping

from uvr.config.models import AppSettings


DEFAULT_DATA_FILE = Path("data.pkl")


def save_settings(
    settings: AppSettings | Mapping[str, Any],
    default_data: Mapping[str, Any] | None = None,
    data_file: str | Path = DEFAULT_DATA_FILE,
) -> None:
    """Persist normalized app settings to disk."""
    if isinstance(settings, AppSettings):
        payload = settings.to_legacy_dict()
    elif default_data is not None:
        payload = AppSettings.from_legacy_dict(settings, default_data).to_legacy_dict()
    else:
        payload = dict(settings)

    with Path(data_file).open("wb") as data_handle:
        pickle.dump(payload, data_handle)


def load_settings(
    default_data: Mapping[str, Any],
    data_file: str | Path = DEFAULT_DATA_FILE,
) -> AppSettings:
    """Load persisted settings and normalize them against defaults."""
    try:
        with Path(data_file).open("rb") as data_handle:
            data = pickle.load(data_handle)
    except (ValueError, FileNotFoundError):
        settings = AppSettings.from_legacy_dict(default_data, default_data)
        save_settings(settings=settings, data_file=data_file)
        return settings

    return AppSettings.from_legacy_dict(data, default_data)


def save_data(data: Any, data_file: str | Path = DEFAULT_DATA_FILE) -> None:
    """Persist app data to disk."""
    save_settings(settings=data, data_file=data_file)


def load_data(default_data: Any, data_file: str | Path = DEFAULT_DATA_FILE) -> dict:
    """Load persisted app data, recreating it from defaults when missing/corrupt."""
    return load_settings(default_data=default_data, data_file=data_file).to_legacy_dict()
