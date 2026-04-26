"""MDX-Net (non-C) separation backend."""

from __future__ import annotations

import os

import numpy as np
import torch

import lib_v5.mdxnet as MdxnetSet
from lib_v5 import spec_utils
from lib_v5.tfc_tdf_v3 import STFT
from onnx import load as onnx_load
from onnx2pytorch import ConvertModel

from gui_data.constants import DEFAULT, INST_STEM, MDX_NET_FREQ_CUT, NO_STEM, DONE
from uvr.separation._onnx_patch import ort
from uvr.separation.audio_io import prepare_mix
from uvr.separation.base import SeperateAttributes
from uvr.separation.device import clear_gpu_cache, mdx_should_use_onnxruntime
from uvr.separation.vr_denoiser import vr_denoiser


class SeperateMDX(SeperateAttributes):
    """MDX-Net inference backend (ONNX and ckpt variants)."""

    def seperate(self) -> dict[str, np.ndarray] | None:
        samplerate = 44100

        if self.primary_model_name == self.model_basename and isinstance(self.primary_sources, tuple):
            mix, source = self.primary_sources
            self.load_cached_sources()
        else:
            self.start_inference_console_write()

            if self.is_mdx_ckpt:
                model_params = torch.load(self.model_path, map_location=lambda storage, loc: storage)["hyper_parameters"]
                self.dim_c, self.hop = model_params["dim_c"], model_params["hop_length"]
                separator = MdxnetSet.ConvTDFNet(**model_params)
                self.model_run = separator.load_from_checkpoint(self.model_path).to(self.device).eval()
            else:
                if mdx_should_use_onnxruntime(self.mdx_segment_size, self.dim_t, self.is_other_gpu, self.device, self.run_type):
                    ort_session = ort.InferenceSession(self.model_path, providers=self.run_type)
                    self.model_run = lambda spek: ort_session.run(None, {"input": spek.cpu().numpy()})[0]
                else:
                    self.model_run = ConvertModel(onnx_load(self.model_path))
                    self.model_run.to(self.device).eval()

            self.running_inference_console_write()
            mix = prepare_mix(self.audio_file)
            source = self.demix(mix)

            if not self.is_vocal_split_model:
                self.cache_source((mix, source))
            self.write_to_console(DONE, base_text="")

        mdx_net_cut = self.primary_stem in MDX_NET_FREQ_CUT and self.is_match_frequency_pitch

        if self.is_secondary_model_activated and self.secondary_model:
            from uvr.separation.chain import process_secondary_model  # deferred — chain imports subclasses

            self.secondary_source_primary, self.secondary_source_secondary = process_secondary_model(
                self.secondary_model, self.process_data,
                main_process_method=self.process_method, main_model_primary=self.primary_stem,
            )

        if not self.is_primary_stem_only:
            secondary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.secondary_stem}).wav")
            if not isinstance(self.secondary_source, np.ndarray):
                raw_mix = self.demix(self.match_frequency_pitch(mix), is_match_mix=True) if mdx_net_cut else self.match_frequency_pitch(mix)
                self.secondary_source = spec_utils.invert_stem(raw_mix, source) if self.is_invert_spec else mix.T - source.T
            self.secondary_source_map = self.final_process(secondary_stem_path, self.secondary_source, self.secondary_source_secondary, self.secondary_stem, samplerate)

        if not self.is_secondary_stem_only:
            primary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.primary_stem}).wav")
            if not isinstance(self.primary_source, np.ndarray):
                self.primary_source = source.T
            self.primary_source_map = self.final_process(primary_stem_path, self.primary_source, self.secondary_source_primary, self.primary_stem, samplerate)

        clear_gpu_cache()
        secondary_sources = {**self.primary_source_map, **self.secondary_source_map}
        self.process_vocal_split_chain(secondary_sources)

        if self.is_secondary_model or self.is_pre_proc_model:
            return secondary_sources
        return None

    def initialize_model_settings(self) -> None:
        self.n_bins = self.n_fft // 2 + 1
        self.trim = self.n_fft // 2
        self.chunk_size = self.hop * (self.mdx_segment_size - 1)
        self.gen_size = self.chunk_size - 2 * self.trim
        self.stft = STFT(self.n_fft, self.hop, self.dim_f, self.device)

    def demix(self, mix: np.ndarray, is_match_mix: bool = False) -> np.ndarray:
        self.initialize_model_settings()
        org_mix = mix
        sr_pitched: int | None = None

        if is_match_mix:
            chunk_size = self.hop * (256 - 1)
            overlap = 0.02
        else:
            chunk_size = self.chunk_size
            overlap = self.overlap_mdx
            if self.is_pitch_change:
                mix, sr_pitched = spec_utils.change_pitch_semitones(mix, 44100, semitone_shift=-self.semitone_shift)

        gen_size = chunk_size - 2 * self.trim
        pad = gen_size + self.trim - (mix.shape[-1] % gen_size)
        mixture = np.concatenate(
            (np.zeros((2, self.trim), dtype="float32"), mix, np.zeros((2, pad), dtype="float32")), axis=1
        )

        step = self.chunk_size - self.n_fft if overlap == DEFAULT else int((1 - overlap) * chunk_size)
        result = np.zeros((1, 2, mixture.shape[-1]), dtype=np.float32)
        divider = np.zeros((1, 2, mixture.shape[-1]), dtype=np.float32)
        total = 0
        total_chunks = (mixture.shape[-1] + step - 1) // step

        for i in range(0, mixture.shape[-1], step):
            total += 1
            start = i
            end = min(i + chunk_size, mixture.shape[-1])
            chunk_size_actual = end - start

            window = None if overlap == 0 else np.tile(np.hanning(chunk_size_actual)[None, None, :], (1, 2, 1))

            mix_part_ = mixture[:, start:end]
            if end != i + chunk_size:
                mix_part_ = np.concatenate((mix_part_, np.zeros((2, (i + chunk_size) - end), dtype="float32")), axis=-1)

            mix_part = torch.tensor([mix_part_], dtype=torch.float32).to(self.device)
            with torch.no_grad():
                for mix_wave in mix_part.split(self.mdx_batch_size):
                    self.running_inference_progress_bar(total_chunks, is_match_mix=is_match_mix)
                    tar_waves = self.run_model(mix_wave, is_match_mix=is_match_mix)
                    if window is not None:
                        tar_waves[..., :chunk_size_actual] *= window
                        divider[..., start:end] += window
                    else:
                        divider[..., start:end] += 1
                    result[..., start:end] += tar_waves[..., : end - start]

        tar_waves = result / divider
        tar_waves = np.concatenate(tar_waves[:, :, self.trim : -self.trim], axis=-1)[:, : mix.shape[-1]]
        source = tar_waves[:, 0:None]

        if self.is_pitch_change and not is_match_mix and sr_pitched is not None:
            source = self.pitch_fix(source, sr_pitched, org_mix)

        source = source if is_match_mix else source * self.compensate

        if self.is_denoise_model and not is_match_mix:
            if NO_STEM in self.primary_stem_native or self.primary_stem_native == INST_STEM:
                if org_mix.shape[1] != source.shape[1]:
                    source = spec_utils.match_array_shapes(source, org_mix)
                source = org_mix - vr_denoiser(org_mix - source, self.device, model_path=self.DENOISER_MODEL)
            else:
                source = vr_denoiser(source, self.device, model_path=self.DENOISER_MODEL)

        return source

    def run_model(self, mix: torch.Tensor, is_match_mix: bool = False) -> np.ndarray:
        spek = self.stft(mix.to(self.device)) * self.adjust
        spek[:, :, :3, :] *= 0

        if is_match_mix:
            spec_pred = spek.cpu().numpy()
        else:
            spec_pred = (
                -self.model_run(-spek) * 0.5 + self.model_run(spek) * 0.5
                if self.is_denoise
                else self.model_run(spek)
            )

        return self.stft.inverse(torch.tensor(spec_pred).to(self.device)).cpu().detach().numpy()
