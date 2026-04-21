"""Model discovery and catalog loading for the framework-neutral backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gui_data.constants import DEMUCS_ARCH_TYPE, MDX_ARCH_TYPE, VR_ARCH_PM
from uvr.runtime import DEFAULT_PATHS, RuntimePaths, load_json


@dataclass(frozen=True)
class InstalledModel:
    process_method: str
    model_name: str
    source: str


@dataclass(frozen=True)
class ModelCatalog:
    vr_hash_mapper: dict[str, Any]
    mdx_hash_mapper: dict[str, Any]
    mdx_name_select_mapper: dict[str, str]
    demucs_name_select_mapper: dict[str, str]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "vr_hash_mapper": dict(self.vr_hash_mapper),
            "mdx_hash_mapper": dict(self.mdx_hash_mapper),
            "mdx_name_select_mapper": dict(self.mdx_name_select_mapper),
            "demucs_name_select_mapper": dict(self.demucs_name_select_mapper),
        }


def load_model_catalog(paths: RuntimePaths = DEFAULT_PATHS) -> ModelCatalog:
    return ModelCatalog(
        vr_hash_mapper=load_json(paths.vr_hash_json),
        mdx_hash_mapper=load_json(paths.mdx_hash_json),
        mdx_name_select_mapper=load_json(paths.mdx_model_name_select),
        demucs_name_select_mapper=load_json(paths.demucs_model_name_select),
    )


def discover_models(
    directory: str | Path,
    ext: str | tuple[str, ...],
    *,
    is_mdxnet: bool = False,
) -> tuple[str, ...]:
    directory_path = Path(directory)
    return tuple(
        item.name if is_mdxnet and item.name.endswith(".ckpt") else item.stem
        for item in sorted(directory_path.iterdir(), key=lambda candidate: candidate.name)
        if item.is_file() and item.name.endswith(ext)
    )


def remap_model_name(name: str, mapper: dict[str, str]) -> str:
    for old_name, new_name in mapper.items():
        if name in old_name:
            return new_name
    return name


def list_installed_models(
    catalog: ModelCatalog,
    paths: RuntimePaths = DEFAULT_PATHS,
) -> list[InstalledModel]:
    mdx_raw = discover_models(paths.mdx_models_dir, (".onnx", ".ckpt"), is_mdxnet=True)
    demucs_raw = discover_models(paths.demucs_models_dir, (".ckpt", ".gz", ".th")) + discover_models(
        paths.demucs_newer_repo_dir,
        ".yaml",
    )
    vr_raw = discover_models(paths.vr_models_dir, ".pth")

    resolved = [InstalledModel(process_method=VR_ARCH_PM, model_name=name, source="vr") for name in vr_raw]
    resolved.extend(
        InstalledModel(
            process_method=MDX_ARCH_TYPE,
            model_name=remap_model_name(name, catalog.mdx_name_select_mapper),
            source="mdx",
        )
        for name in mdx_raw
    )
    resolved.extend(
        InstalledModel(
            process_method=DEMUCS_ARCH_TYPE,
            model_name=remap_model_name(name, catalog.demucs_name_select_mapper),
            source="demucs",
        )
        for name in demucs_raw
    )
    return resolved
