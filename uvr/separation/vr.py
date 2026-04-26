"""VR-Net separation backend."""

from __future__ import annotations

import math
import os

import librosa
import numpy as np
import torch

from lib_v5 import spec_utils
from lib_v5.vr_network import nets, nets_new

from gui_data.constants import ARM, DONE, NON_ACCOM_STEMS, OPERATING_SYSTEM, SYSTEM_ARCH, SYSTEM_PROC
from gui_data.error_handling import ERROR_MAPPER, WINDOW_SIZE_ERROR
from uvr.separation.audio_io import prepare_mix, rerun_mp3
from uvr.separation.base import SeperateAttributes
from uvr.separation.device import clear_gpu_cache, cpu
from uvr.separation.vr_denoiser import vr_denoiser


class SeperateVR(SeperateAttributes):
    """VR-Net inference backend."""

    def seperate(self) -> dict[str, np.ndarray] | None:
        if self.primary_model_name == self.model_basename and isinstance(self.primary_sources, tuple):
            y_spec, v_spec = self.primary_sources
            self.load_cached_sources()
        else:
            self.start_inference_console_write()

            nn_arch_sizes = [31191, 33966, 56817, 123821, 123812, 129605, 218409, 537238, 537227]
            vr_5_1_models = [56817, 218409]
            model_size = math.ceil(os.stat(self.model_path).st_size / 1024)
            nn_arch_size = min(nn_arch_sizes, key=lambda x: abs(x - model_size))

            if nn_arch_size in vr_5_1_models or self.is_vr_51_model:
                self.model_run = nets_new.CascadedNet(
                    self.mp.param["bins"] * 2,
                    nn_arch_size,
                    nout=self.model_capacity[0],
                    nout_lstm=self.model_capacity[1],
                )
                self.is_vr_51_model = True
            else:
                self.model_run = nets.determine_model_capacity(self.mp.param["bins"] * 2, nn_arch_size)

            self.model_run.load_state_dict(torch.load(self.model_path, map_location=cpu))
            self.model_run.to(self.device)
            self.running_inference_console_write()

            y_spec, v_spec = self.inference_vr(self.loading_mix(), self.device, self.aggressiveness)
            if not self.is_vocal_split_model:
                self.cache_source((y_spec, v_spec))
            self.write_to_console(DONE, base_text="")

        if self.is_secondary_model_activated and self.secondary_model:
            from uvr.separation.chain import process_secondary_model  # deferred — chain imports subclasses

            self.secondary_source_primary, self.secondary_source_secondary = process_secondary_model(
                self.secondary_model, self.process_data,
                main_process_method=self.process_method, main_model_primary=self.primary_stem,
            )

        if not self.is_secondary_stem_only:
            primary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.primary_stem}).wav")
            if not isinstance(self.primary_source, np.ndarray):
                self.primary_source = self.spec_to_wav(y_spec).T
                if self.model_samplerate != 44100:
                    self.primary_source = librosa.resample(self.primary_source.T, orig_sr=self.model_samplerate, target_sr=44100).T
            self.primary_source_map = self.final_process(primary_stem_path, self.primary_source, self.secondary_source_primary, self.primary_stem, 44100)

        if not self.is_primary_stem_only:
            secondary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.secondary_stem}).wav")
            if not isinstance(self.secondary_source, np.ndarray):
                self.secondary_source = self.spec_to_wav(v_spec).T
                if self.model_samplerate != 44100:
                    self.secondary_source = librosa.resample(self.secondary_source.T, orig_sr=self.model_samplerate, target_sr=44100).T
            self.secondary_source_map = self.final_process(secondary_stem_path, self.secondary_source, self.secondary_source_secondary, self.secondary_stem, 44100)

        clear_gpu_cache()
        secondary_sources = {**self.primary_source_map, **self.secondary_source_map}
        self.process_vocal_split_chain(secondary_sources)

        if self.is_secondary_model:
            return secondary_sources
        return None

    def loading_mix(self) -> np.ndarray:
        X_wave: dict[int, np.ndarray] = {}
        X_spec_s: dict[int, np.ndarray] = {}
        bands_n = len(self.mp.param["band"])

        audio_file = spec_utils.write_array_to_mem(self.audio_file, subtype=self.wav_type_set)
        is_mp3 = audio_file.endswith(".mp3") if isinstance(audio_file, str) else False

        for d in range(bands_n, 0, -1):
            bp = self.mp.param["band"][d]
            if OPERATING_SYSTEM == "Darwin":
                wav_resolution = "polyphase" if SYSTEM_PROC == ARM or ARM in SYSTEM_ARCH else bp["res_type"]
            else:
                wav_resolution = bp["res_type"]

            if d == bands_n:
                X_wave[d], _ = librosa.load(audio_file, bp["sr"], False, dtype=np.float32, res_type=wav_resolution)
                X_spec_s[d] = spec_utils.wave_to_spectrogram(X_wave[d], bp["hl"], bp["n_fft"], self.mp, band=d, is_v51_model=self.is_vr_51_model)
                if not np.any(X_wave[d]) and is_mp3:
                    X_wave[d] = rerun_mp3(audio_file, bp["sr"])
                if X_wave[d].ndim == 1:
                    X_wave[d] = np.asarray([X_wave[d], X_wave[d]])
            else:
                X_wave[d] = librosa.resample(X_wave[d + 1], self.mp.param["band"][d + 1]["sr"], bp["sr"], res_type=wav_resolution)
                X_spec_s[d] = spec_utils.wave_to_spectrogram(X_wave[d], bp["hl"], bp["n_fft"], self.mp, band=d, is_v51_model=self.is_vr_51_model)

            if d == bands_n and self.high_end_process != "none":
                self.input_high_end_h = (bp["n_fft"] // 2 - bp["crop_stop"]) + (self.mp.param["pre_filter_stop"] - self.mp.param["pre_filter_start"])
                self.input_high_end = X_spec_s[d][:, bp["n_fft"] // 2 - self.input_high_end_h : bp["n_fft"] // 2, :]

        X_spec = spec_utils.combine_spectrograms(X_spec_s, self.mp, is_v51_model=self.is_vr_51_model)
        del X_wave, X_spec_s, audio_file
        return X_spec

    def inference_vr(
        self,
        X_spec: np.ndarray,
        device: torch.device | str,
        aggressiveness: dict,
    ) -> tuple[np.ndarray, np.ndarray]:
        def _execute(X_mag_pad: np.ndarray, roi_size: int) -> np.ndarray:
            patches = (X_mag_pad.shape[2] - 2 * self.model_run.offset) // roi_size
            total_iterations = patches // self.batch_size if not self.is_tta else (patches // self.batch_size) * 2
            X_dataset = np.asarray([X_mag_pad[:, :, i * roi_size : i * roi_size + self.window_size] for i in range(patches)])

            self.model_run.eval()
            with torch.no_grad():
                mask: list[np.ndarray] = []
                for i in range(0, patches, self.batch_size):
                    self.progress_value += 1
                    if self.progress_value >= total_iterations:
                        self.progress_value = total_iterations
                    self.set_progress_bar(0.1, 0.8 / total_iterations * self.progress_value)
                    X_batch = torch.from_numpy(X_dataset[i : i + self.batch_size]).to(device)
                    pred = self.model_run.predict_mask(X_batch)
                    if not pred.size()[3] > 0:
                        raise Exception(ERROR_MAPPER[WINDOW_SIZE_ERROR])
                    mask.append(np.concatenate(pred.detach().cpu().numpy(), axis=2))
                if not mask:
                    raise Exception(ERROR_MAPPER[WINDOW_SIZE_ERROR])
            return np.concatenate(mask, axis=2)

        def _postprocess(mask: np.ndarray, X_mag: np.ndarray, X_phase: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            is_non_accom = any(stem == self.primary_stem for stem in NON_ACCOM_STEMS)
            mask = spec_utils.adjust_aggr(mask, is_non_accom, aggressiveness)
            if self.is_post_process:
                mask = spec_utils.merge_artifacts(mask, thres=self.post_process_threshold)
            y_spec = mask * X_mag * np.exp(1.j * X_phase)
            v_spec = (1 - mask) * X_mag * np.exp(1.j * X_phase)
            return y_spec, v_spec

        X_mag, X_phase = spec_utils.preprocess(X_spec)
        n_frame = X_mag.shape[2]
        pad_l, pad_r, roi_size = spec_utils.make_padding(n_frame, self.window_size, self.model_run.offset)
        X_mag_pad = np.pad(X_mag, ((0, 0), (0, 0), (pad_l, pad_r)), mode="constant")
        X_mag_pad /= X_mag_pad.max()
        mask = _execute(X_mag_pad, roi_size)

        if self.is_tta:
            pad_l += roi_size // 2
            pad_r += roi_size // 2
            X_mag_pad = np.pad(X_mag, ((0, 0), (0, 0), (pad_l, pad_r)), mode="constant")
            X_mag_pad /= X_mag_pad.max()
            mask_tta = _execute(X_mag_pad, roi_size)
            mask_tta = mask_tta[:, :, roi_size // 2 :]
            mask = (mask[:, :, :n_frame] + mask_tta[:, :, :n_frame]) * 0.5
        else:
            mask = mask[:, :, :n_frame]

        return _postprocess(mask, X_mag, X_phase)

    def spec_to_wav(self, spec: np.ndarray) -> np.ndarray:
        if self.high_end_process.startswith("mirroring") and isinstance(self.input_high_end, np.ndarray) and self.input_high_end_h:
            input_high_end_ = spec_utils.mirroring(self.high_end_process, spec, self.input_high_end, self.mp)
            return spec_utils.cmb_spectrogram_to_wave(spec, self.mp, self.input_high_end_h, input_high_end_, is_v51_model=self.is_vr_51_model)
        return spec_utils.cmb_spectrogram_to_wave(spec, self.mp, is_v51_model=self.is_vr_51_model)
