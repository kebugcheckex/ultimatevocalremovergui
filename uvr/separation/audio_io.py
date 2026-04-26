"""Audio file loading and format-conversion utilities."""

from __future__ import annotations

import os

import audioread
import librosa
import numpy as np
import pydub
import soundfile as sf

from gui_data.constants import FLAC, MP3, OPERATING_SYSTEM, WAV


def prepare_mix(mix: np.ndarray | str) -> np.ndarray:
    """Load *mix* from disk (if a path) and return a stereo float32 array."""
    audio_path = mix

    if not isinstance(mix, np.ndarray):
        mix, _ = librosa.load(mix, mono=False, sr=44100)
    else:
        mix = mix.T

    if isinstance(audio_path, str):
        if not np.any(mix) and audio_path.endswith(".mp3"):
            mix = rerun_mp3(audio_path)

    if mix.ndim == 1:
        mix = np.asfortranarray([mix, mix])

    return mix


def rerun_mp3(audio_file: str, sample_rate: int = 44100) -> np.ndarray:
    """Reload an MP3 via audioread to work around librosa zero-read bugs."""
    with audioread.audio_open(audio_file) as f:
        track_length = int(f.duration)
    return librosa.load(audio_file, duration=track_length, mono=False, sr=sample_rate)[0]


def save_format(audio_path: str, save_fmt: str, mp3_bit_set: str) -> None:
    """Convert a WAV file at *audio_path* to *save_fmt* in-place.

    Deletes the original WAV after a successful conversion.
    """
    if save_fmt == WAV:
        return

    if OPERATING_SYSTEM == "Darwin":
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg")
        pydub.AudioSegment.converter = ffmpeg_path

    musfile = pydub.AudioSegment.from_wav(audio_path)

    if save_fmt == FLAC:
        musfile.export(audio_path.replace(".wav", ".flac"), format="flac")
    elif save_fmt == MP3:
        mp3_path = audio_path.replace(".wav", ".mp3")
        try:
            musfile.export(mp3_path, format="mp3", bitrate=mp3_bit_set, codec="libmp3lame")
        except Exception:
            musfile.export(mp3_path, format="mp3", bitrate=mp3_bit_set)

    try:
        os.remove(audio_path)
    except Exception:
        pass
