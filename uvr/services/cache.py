"""Source-cache service for the framework-neutral backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gui_data.constants import DEMUCS_ARCH_TYPE, MDX_ARCH_TYPE, VR_ARCH_TYPE


@dataclass
class SourceCache:
    """Store per-process-method cached sources by model name."""

    _cache: dict[str, dict[str, object]] = field(
        default_factory=lambda: {
            VR_ARCH_TYPE: {},
            MDX_ARCH_TYPE: {},
            DEMUCS_ARCH_TYPE: {},
        }
    )

    def clear(self) -> None:
        for process_method in self._cache:
            self._cache[process_method] = {}

    def get(self, process_method: str, model_name: str | None = None) -> tuple[str | None, Any]:
        mapper = self._cache.get(process_method, {})
        for key, value in mapper.items():
            if model_name and model_name in key:
                return key, value
        return None, None

    def put(self, process_method: str, sources: object, model_name: str | None = None) -> None:
        if model_name is None:
            return
        self._cache.setdefault(process_method, {})[model_name] = sources

    # Compatibility callbacks for the legacy separation backend.
    def cached_source_callback(self, process_method: str, model_name: str | None = None) -> tuple[str | None, Any]:
        return self.get(process_method, model_name)

    def cached_model_source_holder(self, process_method: str, sources: object, model_name: str | None = None) -> None:
        self.put(process_method, sources, model_name)
