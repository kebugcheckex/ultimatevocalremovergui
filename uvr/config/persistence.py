"""Persistence helpers for UVR settings."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any


DEFAULT_DATA_FILE = Path("data.pkl")


def save_data(data: Any, data_file: str | Path = DEFAULT_DATA_FILE) -> None:
    """Persist app data to disk."""
    with Path(data_file).open("wb") as data_handle:
        pickle.dump(data, data_handle)


def load_data(default_data: Any, data_file: str | Path = DEFAULT_DATA_FILE) -> dict:
    """Load persisted app data, recreating it from defaults when missing/corrupt."""
    try:
        with Path(data_file).open("rb") as data_handle:
            return pickle.load(data_handle)
    except (ValueError, FileNotFoundError):
        save_data(data=default_data, data_file=data_file)
        return load_data(default_data=default_data, data_file=data_file)
