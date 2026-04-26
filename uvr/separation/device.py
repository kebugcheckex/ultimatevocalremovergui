"""GPU / device selection utilities shared by all separation backends."""

from __future__ import annotations

import gc

import torch

from gui_data.constants import CUDA_DEVICE, is_macos
from uvr.separation._onnx_patch import ort

cpu = torch.device("cpu")
mps_available: bool = torch.backends.mps.is_available() if is_macos else False
cuda_available: bool = torch.cuda.is_available()


def clear_gpu_cache() -> None:
    """Release GPU memory after a job completes."""
    gc.collect()
    if is_macos:
        torch.mps.empty_cache()
    else:
        torch.cuda.empty_cache()


def is_cuda_device(device: object) -> bool:
    """Return True if *device* is a CUDA device string."""
    return isinstance(device, str) and device.startswith(CUDA_DEVICE)


def mdx_should_use_onnxruntime(
    mdx_segment_size: int,
    dim_t: int,
    is_other_gpu: bool,
    device: object,
    run_type: list[str],
) -> bool:
    """Return True when ONNX Runtime should be preferred over onnx2pytorch."""
    if ort is None or not hasattr(ort, "InferenceSession") or not hasattr(ort, "get_available_providers"):
        return False
    if mdx_segment_size != dim_t or is_other_gpu:
        return False
    if is_cuda_device(device) and "CUDAExecutionProvider" not in ort.get_available_providers():
        return False
    return bool(run_type)
