"""VR-model denoiser and deverber helpers."""

from __future__ import annotations

import os

import librosa
import numpy as np
import torch

from gui_data.constants import ARM, OPERATING_SYSTEM, SYSTEM_ARCH, SYSTEM_PROC
from lib_v5 import spec_utils
from lib_v5.vr_network import nets_new
from lib_v5.vr_network.model_param_init import ModelParameters
from uvr.separation.device import cpu


def vr_denoiser(
    X: np.ndarray,
    device: torch.device | str,
    *,
    hop_length: int = 1024,
    n_fft: int = 2048,
    cropsize: int = 256,
    is_deverber: bool = False,
    model_path: str | None = None,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Run the VR denoiser or deverber on *X*.

    Returns a single denoised array, or a ``(deverbed, reverb_only)`` tuple
    when *is_deverber* is True.
    """
    batchsize = 4
    mp: ModelParameters | None = None

    if is_deverber:
        nout, nout_lstm = 64, 128
        mp = ModelParameters(os.path.join("lib_v5", "vr_network", "modelparams", "4band_v3.json"))
        n_fft = mp.param["bins"] * 2
    else:
        hop_length = 1024
        nout, nout_lstm = 16, 128

    model = nets_new.CascadedNet(n_fft, nout=nout, nout_lstm=nout_lstm)
    model.load_state_dict(torch.load(model_path, map_location=cpu))
    model.to(device)

    X_spec = _load_mix_for_deverb(X.T, mp) if mp is not None else spec_utils.wave_to_spectrogram_old(X, hop_length, n_fft)
    X_mag = np.abs(X_spec)
    X_phase = np.angle(X_spec)

    n_frame = X_mag.shape[2]
    pad_l, pad_r, roi_size = spec_utils.make_padding(n_frame, cropsize, model.offset)
    X_mag_pad = np.pad(X_mag, ((0, 0), (0, 0), (pad_l, pad_r)), mode="constant")
    X_mag_pad /= X_mag_pad.max()

    patches = (X_mag_pad.shape[2] - 2 * model.offset) // roi_size
    X_dataset = np.asarray([X_mag_pad[:, :, i * roi_size : i * roi_size + cropsize] for i in range(patches)])

    model.eval()
    with torch.no_grad():
        mask_parts: list[np.ndarray] = []
        for i in range(0, patches, batchsize):
            pred = model.predict_mask(torch.from_numpy(X_dataset[i : i + batchsize]).to(device))
            mask_parts.append(np.concatenate(pred.detach().cpu().numpy(), axis=2))

    mask = np.concatenate(mask_parts, axis=2)[:, :, :n_frame]

    if is_deverber:
        assert mp is not None
        v_spec = mask * X_mag * np.exp(1.j * X_phase)
        y_spec = (1 - mask) * X_mag * np.exp(1.j * X_phase)
        wave = spec_utils.match_array_shapes(spec_utils.cmb_spectrogram_to_wave(v_spec, mp, is_v51_model=True).T, X)
        wave_2 = spec_utils.match_array_shapes(spec_utils.cmb_spectrogram_to_wave(y_spec, mp, is_v51_model=True).T, X)
        return wave, wave_2

    v_spec = (1 - mask) * X_mag * np.exp(1.j * X_phase)
    if mp is None:
        wave = spec_utils.spectrogram_to_wave_old(v_spec, hop_length=1024)
    else:
        wave = spec_utils.cmb_spectrogram_to_wave(v_spec, mp, is_v51_model=True).T

    return spec_utils.match_array_shapes(wave, X)


def _load_mix_for_deverb(X: np.ndarray, mp: ModelParameters) -> np.ndarray:
    """Build a multi-band spectrogram from raw audio *X* using model params *mp*."""
    X_wave: dict[int, np.ndarray] = {}
    X_spec_s: dict[int, np.ndarray] = {}
    bands_n = len(mp.param["band"])

    for d in range(bands_n, 0, -1):
        bp = mp.param["band"][d]
        wav_resolution = "polyphase" if OPERATING_SYSTEM == "Darwin" and (SYSTEM_PROC == ARM or ARM in SYSTEM_ARCH) else "polyphase"

        if d == bands_n:
            X_wave[d] = X
        else:
            X_wave[d] = librosa.resample(X_wave[d + 1], mp.param["band"][d + 1]["sr"], bp["sr"], res_type=wav_resolution)

        X_spec_s[d] = spec_utils.wave_to_spectrogram(X_wave[d], bp["hl"], bp["n_fft"], mp, band=d, is_v51_model=True)

    return spec_utils.combine_spectrograms(X_spec_s, mp)
