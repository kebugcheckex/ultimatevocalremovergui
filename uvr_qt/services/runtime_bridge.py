"""Minimal runtime bridge for extracted backend modules."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from gui_data import constants
from lib_v5.vr_network.model_param_init import ModelParameters


BASE_PATH = Path(__file__).resolve().parents[2]
MODELS_DIR = BASE_PATH / "models"
VR_MODELS_DIR = MODELS_DIR / "VR_Models"
MDX_MODELS_DIR = MODELS_DIR / "MDX_Net_Models"
DEMUCS_MODELS_DIR = MODELS_DIR / "Demucs_Models"
DEMUCS_NEWER_REPO_DIR = DEMUCS_MODELS_DIR / "v3_v4_repo"
VR_HASH_DIR = VR_MODELS_DIR / "model_data"
MDX_HASH_DIR = MDX_MODELS_DIR / "model_data"
MDX_C_CONFIG_PATH = MDX_HASH_DIR / "mdx_c_configs"
VR_PARAM_DIR = BASE_PATH / "lib_v5" / "vr_network" / "modelparams"
MDX_MIXER_PATH = BASE_PATH / "lib_v5" / "mixer.ckpt"
DENOISER_MODEL_PATH = VR_MODELS_DIR / "UVR-DeNoise-Lite.pth"
DEVERBER_MODEL_PATH = VR_MODELS_DIR / "UVR-DeEcho-DeReverb.pth"
VR_HASH_JSON = VR_HASH_DIR / "model_data.json"
MDX_HASH_JSON = MDX_HASH_DIR / "model_data.json"
MDX_MODEL_NAME_SELECT = MDX_MODELS_DIR / "model_data" / "model_name_mapper.json"
DEMUCS_MODEL_NAME_SELECT = DEMUCS_MODELS_DIR / "model_data" / "model_name_mapper.json"


def create_runtime() -> Any:
    runtime = SimpleNamespace()
    for name in dir(constants):
        if name.startswith("_"):
            continue
        setattr(runtime, name, getattr(constants, name))

    runtime.BASE_PATH = str(BASE_PATH)
    runtime.MODELS_DIR = str(MODELS_DIR)
    runtime.VR_MODELS_DIR = str(VR_MODELS_DIR)
    runtime.MDX_MODELS_DIR = str(MDX_MODELS_DIR)
    runtime.DEMUCS_MODELS_DIR = str(DEMUCS_MODELS_DIR)
    runtime.DEMUCS_NEWER_REPO_DIR = str(DEMUCS_NEWER_REPO_DIR)
    runtime.VR_HASH_DIR = str(VR_HASH_DIR)
    runtime.MDX_HASH_DIR = str(MDX_HASH_DIR)
    runtime.MDX_C_CONFIG_PATH = str(MDX_C_CONFIG_PATH)
    runtime.VR_PARAM_DIR = str(VR_PARAM_DIR)
    runtime.MDX_MIXER_PATH = str(MDX_MIXER_PATH)
    runtime.DENOISER_MODEL_PATH = str(DENOISER_MODEL_PATH)
    runtime.DEVERBER_MODEL_PATH = str(DEVERBER_MODEL_PATH)
    runtime.model_hash_table = {}
    runtime.ModelParameters = ModelParameters
    return runtime


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r") as handle:
        return json.load(handle)


def discover_models(directory: str | Path, ext: str | tuple[str, ...], *, is_mdxnet: bool = False) -> tuple[str, ...]:
    return tuple(
        item if is_mdxnet and item.endswith(constants.CKPT) else os.path.splitext(item)[0]
        for item in os.listdir(directory)
        if item.endswith(ext)
    )


def configure_backend_runtime() -> Any:
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba")
    os.chdir(BASE_PATH)

    runtime = create_runtime()

    from uvr.domain import model_data as model_data_module

    model_data_module.configure_runtime(runtime)
    return runtime


def read_model_catalog() -> dict[str, dict[str, Any]]:
    return {
        "vr_hash_mapper": load_json(VR_HASH_JSON),
        "mdx_hash_mapper": load_json(MDX_HASH_JSON),
        "mdx_name_select_mapper": load_json(MDX_MODEL_NAME_SELECT),
        "demucs_name_select_mapper": load_json(DEMUCS_MODEL_NAME_SELECT),
    }

