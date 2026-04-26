"""Compatibility shim — all logic has moved to uvr/separation/."""

from uvr.separation import SeperateDemucs, SeperateMDX, SeperateMDXC, SeperateVR, save_format
from uvr.separation.device import clear_gpu_cache, mdx_should_use_onnxruntime
from uvr.separation.chain import gather_sources, process_chain_model, process_secondary_model

__all__ = [
    "SeperateDemucs",
    "SeperateMDX",
    "SeperateMDXC",
    "SeperateVR",
    "save_format",
    "clear_gpu_cache",
    "mdx_should_use_onnxruntime",
    "gather_sources",
    "process_chain_model",
    "process_secondary_model",
]
