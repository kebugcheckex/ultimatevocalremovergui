"""Framework-neutral runtime bootstrap for the legacy separation backend."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from gui_data import constants
from lib_v5.vr_network.model_param_init import ModelParameters


@dataclass(frozen=True)
class RuntimePaths:
    base_path: Path
    models_dir: Path
    vr_models_dir: Path
    mdx_models_dir: Path
    demucs_models_dir: Path
    demucs_newer_repo_dir: Path
    vr_hash_dir: Path
    mdx_hash_dir: Path
    mdx_c_config_path: Path
    vr_param_dir: Path
    mdx_mixer_path: Path
    denoiser_model_path: Path
    deverber_model_path: Path
    vr_hash_json: Path
    mdx_hash_json: Path
    mdx_model_name_select: Path
    demucs_model_name_select: Path


def build_runtime_paths(
    *,
    base_path: str | Path | None = None,
    models_dir: str | Path | None = None,
) -> RuntimePaths:
    resolved_base = Path(base_path or os.environ.get("UVR_BASE_PATH") or Path(__file__).resolve().parents[1]).resolve()
    resolved_models = Path(models_dir or os.environ.get("UVR_MODELS_DIR") or (resolved_base / "models")).resolve()
    vr_models_dir = resolved_models / "VR_Models"
    mdx_models_dir = resolved_models / "MDX_Net_Models"
    demucs_models_dir = resolved_models / "Demucs_Models"
    vr_hash_dir = vr_models_dir / "model_data"
    mdx_hash_dir = mdx_models_dir / "model_data"
    return RuntimePaths(
        base_path=resolved_base,
        models_dir=resolved_models,
        vr_models_dir=vr_models_dir,
        mdx_models_dir=mdx_models_dir,
        demucs_models_dir=demucs_models_dir,
        demucs_newer_repo_dir=demucs_models_dir / "v3_v4_repo",
        vr_hash_dir=vr_hash_dir,
        mdx_hash_dir=mdx_hash_dir,
        mdx_c_config_path=mdx_hash_dir / "mdx_c_configs",
        vr_param_dir=resolved_base / "lib_v5" / "vr_network" / "modelparams",
        mdx_mixer_path=resolved_base / "lib_v5" / "mixer.ckpt",
        denoiser_model_path=vr_models_dir / "UVR-DeNoise-Lite.pth",
        deverber_model_path=vr_models_dir / "UVR-DeEcho-DeReverb.pth",
        vr_hash_json=vr_hash_dir / "model_data.json",
        mdx_hash_json=mdx_hash_dir / "model_data.json",
        mdx_model_name_select=mdx_models_dir / "model_data" / "model_name_mapper.json",
        demucs_model_name_select=demucs_models_dir / "model_data" / "model_name_mapper.json",
    )


DEFAULT_PATHS = build_runtime_paths()
BASE_PATH = DEFAULT_PATHS.base_path
MODELS_DIR = DEFAULT_PATHS.models_dir
VR_MODELS_DIR = DEFAULT_PATHS.vr_models_dir
MDX_MODELS_DIR = DEFAULT_PATHS.mdx_models_dir
DEMUCS_MODELS_DIR = DEFAULT_PATHS.demucs_models_dir
DEMUCS_NEWER_REPO_DIR = DEFAULT_PATHS.demucs_newer_repo_dir
VR_HASH_DIR = DEFAULT_PATHS.vr_hash_dir
MDX_HASH_DIR = DEFAULT_PATHS.mdx_hash_dir
MDX_C_CONFIG_PATH = DEFAULT_PATHS.mdx_c_config_path
VR_PARAM_DIR = DEFAULT_PATHS.vr_param_dir
MDX_MIXER_PATH = DEFAULT_PATHS.mdx_mixer_path
DENOISER_MODEL_PATH = DEFAULT_PATHS.denoiser_model_path
DEVERBER_MODEL_PATH = DEFAULT_PATHS.deverber_model_path
VR_HASH_JSON = DEFAULT_PATHS.vr_hash_json
MDX_HASH_JSON = DEFAULT_PATHS.mdx_hash_json
MDX_MODEL_NAME_SELECT = DEFAULT_PATHS.mdx_model_name_select
DEMUCS_MODEL_NAME_SELECT = DEFAULT_PATHS.demucs_model_name_select


def create_runtime(paths: RuntimePaths = DEFAULT_PATHS) -> Any:
    runtime = SimpleNamespace()
    for name in dir(constants):
        if name.startswith("_"):
            continue
        setattr(runtime, name, getattr(constants, name))

    runtime.BASE_PATH = str(paths.base_path)
    runtime.MODELS_DIR = str(paths.models_dir)
    runtime.VR_MODELS_DIR = str(paths.vr_models_dir)
    runtime.MDX_MODELS_DIR = str(paths.mdx_models_dir)
    runtime.DEMUCS_MODELS_DIR = str(paths.demucs_models_dir)
    runtime.DEMUCS_NEWER_REPO_DIR = str(paths.demucs_newer_repo_dir)
    runtime.VR_HASH_DIR = str(paths.vr_hash_dir)
    runtime.MDX_HASH_DIR = str(paths.mdx_hash_dir)
    runtime.MDX_C_CONFIG_PATH = str(paths.mdx_c_config_path)
    runtime.VR_PARAM_DIR = str(paths.vr_param_dir)
    runtime.MDX_MIXER_PATH = str(paths.mdx_mixer_path)
    runtime.DENOISER_MODEL_PATH = str(paths.denoiser_model_path)
    runtime.DEVERBER_MODEL_PATH = str(paths.deverber_model_path)
    runtime.model_hash_table = {}
    runtime.ModelParameters = ModelParameters
    return runtime


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r") as handle:
        return json.load(handle)


def configure_backend_runtime() -> Any:
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba")
    os.chdir(DEFAULT_PATHS.base_path)

    runtime = create_runtime(DEFAULT_PATHS)
    runtime.os = os

    import time as time_module
    from lib_v5 import spec_utils
    import matchering as match
    from separate import save_format
    from uvr.domain import audio_tools as audio_tools_module
    from uvr.domain import ensemble as ensemble_module

    runtime.time = time_module
    runtime.spec_utils = spec_utils
    runtime.save_format = save_format
    runtime.match = match
    runtime.ENSEMBLE_TEMP_PATH = str(DEFAULT_PATHS.base_path / "ensemble_temps")
    Path(runtime.ENSEMBLE_TEMP_PATH).mkdir(parents=True, exist_ok=True)

    from uvr.domain import model_data as model_data_module

    model_data_module.configure_runtime(runtime)
    audio_tools_module.configure_runtime(runtime)
    ensemble_module.configure_runtime(runtime)
    return runtime


def read_model_catalog() -> dict[str, dict[str, Any]]:
    from uvr.services.catalog import load_model_catalog

    return load_model_catalog(DEFAULT_PATHS).to_dict()


def discover_models(
    directory: str | Path,
    ext: str | tuple[str, ...],
    *,
    is_mdxnet: bool = False,
) -> tuple[str, ...]:
    from uvr.services.catalog import discover_models as discover_catalog_models

    return discover_catalog_models(directory, ext, is_mdxnet=is_mdxnet)
