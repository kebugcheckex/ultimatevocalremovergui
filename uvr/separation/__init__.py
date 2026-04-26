"""Audio separation backends for UVR.

Public surface:
    SeperateVR      — VR-Net backend
    SeperateMDX     — MDX-Net (ONNX / ckpt) backend
    SeperateMDXC    — MDX-C (TFC-TDF-net) backend
    SeperateDemucs  — Demucs v1–v4 backend
    save_format     — post-process WAV → FLAC/MP3
"""

from uvr.separation.vr import SeperateVR
from uvr.separation.mdx import SeperateMDX
from uvr.separation.mdxc import SeperateMDXC
from uvr.separation.demucs import SeperateDemucs
from uvr.separation.audio_io import save_format

__all__ = [
    "SeperateVR",
    "SeperateMDX",
    "SeperateMDXC",
    "SeperateDemucs",
    "save_format",
]
