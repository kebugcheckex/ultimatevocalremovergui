"""Named settings profile helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from uvr.config.models import AppSettings


DEFAULT_PROFILES_DIR = Path("gui_data") / "saved_settings"
PROFILE_NAME_PATTERN = re.compile(r"\b^([a-zA-Z0-9 -]{0,25})$\b")


class ProfileError(ValueError):
    """Raised when a profile operation fails validation."""


@dataclass(frozen=True)
class SettingsProfileStore:
    """Read and write saved workflow profiles using the legacy JSON layout."""

    default_data: Mapping[str, Any]
    profiles_dir: Path = DEFAULT_PROFILES_DIR

    def list_profiles(self) -> tuple[str, ...]:
        if not self.profiles_dir.exists():
            return ()
        names = [
            path.stem.replace("_", " ")
            for path in self.profiles_dir.glob("*.json")
            if path.is_file()
        ]
        return tuple(sorted(names, key=str.casefold))

    def save_profile(self, name: str, settings: Mapping[str, Any]) -> str:
        normalized_name = self._normalize_name(name)
        normalized_settings = AppSettings.from_legacy_dict(settings, self.default_data).to_legacy_dict()
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profile_path(normalized_name).write_text(
            json.dumps(normalized_settings, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return normalized_name

    def load_profile(self, name: str) -> dict[str, Any]:
        path = self._profile_path(name)
        if not path.is_file():
            raise FileNotFoundError(f'Profile "{name}" was not found.')
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ProfileError(f'Profile "{name}" did not contain a JSON object.')
        return AppSettings.from_legacy_dict(payload, self.default_data).to_legacy_dict()

    def delete_profile(self, name: str) -> None:
        path = self._profile_path(name)
        if not path.is_file():
            raise FileNotFoundError(f'Profile "{name}" was not found.')
        path.unlink()

    def _profile_path(self, name: str) -> Path:
        normalized_name = self._normalize_name(name)
        filename = normalized_name.replace(" ", "_")
        return self.profiles_dir / f"{filename}.json"

    def _normalize_name(self, name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise ProfileError("Profile name cannot be empty.")
        if PROFILE_NAME_PATTERN.fullmatch(normalized) is None:
            raise ProfileError("Profile names may only use letters, numbers, spaces, and hyphens (max 25 characters).")
        return normalized
