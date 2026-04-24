"""Persistence helpers for UVR settings."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Mapping

import yaml

from uvr.config.models import AppSettings


DEFAULT_DATA_FILE = Path("data") / "config.yaml"
LEGACY_DATA_FILE = Path("data.pkl")


def save_settings(
    settings: AppSettings | Mapping[str, Any],
    default_data: Mapping[str, Any] | None = None,
    data_file: str | Path | None = None,
) -> None:
    """Persist normalized app settings to disk."""
    if isinstance(settings, AppSettings):
        payload = settings.to_legacy_dict()
    elif default_data is not None:
        payload = AppSettings.from_legacy_dict(settings, default_data).to_legacy_dict()
    else:
        payload = dict(settings)

    path = Path(data_file) if data_file is not None else DEFAULT_DATA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".pkl":
        with path.open("wb") as data_handle:
            pickle.dump(payload, data_handle)
        return

    with path.open("w", encoding="utf-8") as data_handle:
        yaml.safe_dump(_normalize_for_yaml(payload), data_handle, sort_keys=True, allow_unicode=False)


def load_settings(
    default_data: Mapping[str, Any],
    data_file: str | Path | None = None,
) -> AppSettings:
    """Load persisted settings and normalize them against defaults."""
    path = Path(data_file) if data_file is not None else DEFAULT_DATA_FILE
    try:
        data = _load_raw_data(path)
    except (ValueError, FileNotFoundError, yaml.YAMLError, pickle.PickleError):
        settings = AppSettings.from_legacy_dict(default_data, default_data)
        save_settings(settings=settings, data_file=path)
        return settings

    if not path.exists() and path == DEFAULT_DATA_FILE:
        save_settings(settings=data, default_data=default_data, data_file=path)

    return AppSettings.from_legacy_dict(data, default_data)


def save_data(data: Any, data_file: str | Path | None = None) -> None:
    """Persist app data to disk."""
    save_settings(settings=data, data_file=data_file)


def load_data(default_data: Any, data_file: str | Path | None = None) -> dict:
    """Load persisted app data, recreating it from defaults when missing/corrupt."""
    return load_settings(default_data=default_data, data_file=data_file).to_legacy_dict()


def _load_raw_data(path: Path) -> Mapping[str, Any]:
    if path.exists():
        return _read_path(path)

    if path == DEFAULT_DATA_FILE and LEGACY_DATA_FILE.exists():
        return _read_pickle(LEGACY_DATA_FILE)

    raise FileNotFoundError(path)


def _read_path(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() == ".pkl":
        return _read_pickle(path)
    return _read_yaml(path)


def _read_yaml(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as data_handle:
        data = yaml.safe_load(data_handle) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Persisted settings must deserialize to a mapping.")
    return data


def _read_pickle(path: Path) -> Mapping[str, Any]:
    with path.open("rb") as data_handle:
        data = pickle.load(data_handle)
    if not isinstance(data, Mapping):
        raise ValueError("Persisted settings must deserialize to a mapping.")
    return data


def _normalize_for_yaml(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_for_yaml(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_normalize_for_yaml(item) for item in value]
    if isinstance(value, list):
        return [_normalize_for_yaml(item) for item in value]
    return value
