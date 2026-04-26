"""ONNX Runtime import guard and compatibility patch.

Imported at package init time.  Callers access ``ort`` from here so they all
see the same (possibly None) reference after patching.
"""

from __future__ import annotations

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class _UnavailableInferenceSession:
    """Placeholder that raises on instantiation when ONNX Runtime is missing."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise ImportError("ONNX Runtime Python API is unavailable.")


# Some broken installs leave an empty namespace package.  Patch the missing
# symbols so callers can do a safe hasattr check rather than a try/except.
if ort is not None and not hasattr(ort, "InferenceSession"):
    ort.InferenceSession = _UnavailableInferenceSession
if ort is not None and not hasattr(ort, "get_available_providers"):
    ort.get_available_providers = lambda: []
