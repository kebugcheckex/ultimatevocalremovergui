"""MDX-C (TFC-TDF) separation backend."""

from __future__ import annotations

import os

import numpy as np
import torch

from lib_v5 import spec_utils
from lib_v5.tfc_tdf_v3 import TFC_TDF_net

from gui_data.constants import ALL_STEMS, DONE, INST_STEM, VOCAL_STEM
from uvr.separation.audio_io import prepare_mix
from uvr.separation.base import SeperateAttributes
from uvr.separation.device import clear_gpu_cache, cpu
from uvr.separation.vr_denoiser import vr_denoiser


class SeperateMDXC(SeperateAttributes):
    """MDX-C (TFC-TDF-net) inference backend."""

    def seperate(self) -> dict[str, np.ndarray] | None:
        samplerate = 44100
        sources = None

        if self.primary_model_name == self.model_basename and isinstance(self.primary_sources, tuple):
            mix, sources = self.primary_sources
            self.load_cached_sources()
        else:
            self.start_inference_console_write()
            self.running_inference_console_write()
            mix = prepare_mix(self.audio_file)
            sources = self.demix(mix)
            if not self.is_vocal_split_model:
                self.cache_source((mix, sources))
            self.write_to_console(DONE, base_text="")

        stem_list = (
            [self.mdx_c_configs.training.target_instrument]
            if self.mdx_c_configs.training.target_instrument
            else list(self.mdx_c_configs.training.instruments)
        )

        if self.is_secondary_model:
            if self.is_pre_proc_model:
                self.mdxnet_stem_select = stem_list[0]
            else:
                self.mdxnet_stem_select = self.main_model_primary_stem_4_stem or self.primary_model_primary_stem
            self.primary_stem = self.mdxnet_stem_select
            self.secondary_stem = _secondary_stem(self.mdxnet_stem_select)
            self.is_primary_stem_only, self.is_secondary_stem_only = False, False

        is_all_stems = self.mdxnet_stem_select == ALL_STEMS
        is_not_ensemble_master = not self.process_data["is_ensemble_master"]
        is_multi_stem = len(stem_list) > 2
        is_not_secondary_model = not self.is_secondary_model
        is_ensemble_4_stem = self.is_4_stem_ensemble and is_multi_stem

        if (is_all_stems and is_not_ensemble_master and is_multi_stem and is_not_secondary_model) or (
            is_ensemble_4_stem and not self.is_pre_proc_model
        ):
            for stem in stem_list:
                primary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({stem}).wav")
                self.primary_source = sources[stem].T
                self.write_audio(primary_stem_path, self.primary_source, samplerate, stem_name=stem)
                if stem == VOCAL_STEM and not self.is_sec_bv_rebalance:
                    self.process_vocal_split_chain({VOCAL_STEM: stem})
        else:
            source_primary = sources if len(stem_list) == 1 else (
                sources[stem_list[0]] if self.is_multi_stem_ensemble and len(stem_list) == 2 else sources[self.mdxnet_stem_select]
            )

            if self.is_secondary_model_activated and self.secondary_model:
                from uvr.separation.chain import process_secondary_model  # deferred — chain imports subclasses

                self.secondary_source_primary, self.secondary_source_secondary = process_secondary_model(
                    self.secondary_model, self.process_data,
                    main_process_method=self.process_method, main_model_primary=self.primary_stem,
                )

            if not self.is_primary_stem_only:
                secondary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.secondary_stem}).wav")
                if not isinstance(self.secondary_source, np.ndarray):
                    if self.is_mdx_combine_stems and len(stem_list) >= 2:
                        if len(stem_list) == 2:
                            secondary_source = sources[self.secondary_stem]
                        else:
                            remaining = {k: v for k, v in sources.items() if k != self.primary_stem}
                            next_stem = next(iter(remaining))
                            secondary_source = np.zeros_like(remaining[next_stem])
                            for v in remaining.values():
                                secondary_source += v
                        self.secondary_source = secondary_source.T
                    else:
                        self.secondary_source = source_primary
                        raw_mix = self.match_frequency_pitch(mix)
                        self.secondary_source = spec_utils.to_shape(self.secondary_source, raw_mix.shape)
                        if self.is_invert_spec:
                            self.secondary_source = spec_utils.invert_stem(raw_mix, self.secondary_source)
                        else:
                            self.secondary_source = -self.secondary_source.T + raw_mix.T

                self.secondary_source_map = self.final_process(
                    secondary_stem_path, self.secondary_source, self.secondary_source_secondary, self.secondary_stem, samplerate
                )

            if not self.is_secondary_stem_only:
                primary_stem_path = os.path.join(self.export_path, f"{self.audio_file_base}_({self.primary_stem}).wav")
                if not isinstance(self.primary_source, np.ndarray):
                    self.primary_source = source_primary.T
                self.primary_source_map = self.final_process(
                    primary_stem_path, self.primary_source, self.secondary_source_primary, self.primary_stem, samplerate
                )

        clear_gpu_cache()
        secondary_sources = {**self.primary_source_map, **self.secondary_source_map}
        self.process_vocal_split_chain(secondary_sources)

        if self.is_secondary_model or self.is_pre_proc_model:
            return secondary_sources
        return None

    def demix(self, mix: np.ndarray) -> dict[str, np.ndarray] | np.ndarray:
        sr_pitched = 44100
        org_mix = mix
        if self.is_pitch_change:
            mix, sr_pitched = spec_utils.change_pitch_semitones(mix, 44100, semitone_shift=-self.semitone_shift)

        model = TFC_TDF_net(self.mdx_c_configs, device=self.device)
        model.load_state_dict(torch.load(self.model_path, map_location=cpu))
        model.to(self.device).eval()

        mix_t = torch.tensor(mix, dtype=torch.float32)

        try:
            S = model.num_target_instruments
        except AttributeError:
            S = model.module.num_target_instruments

        mdx_segment_size = self.mdx_c_configs.inference.dim_t if self.is_mdx_c_seg_def else self.mdx_segment_size
        chunk_size = self.mdx_c_configs.audio.hop_length * (mdx_segment_size - 1)
        overlap = self.overlap_mdx23
        hop_size = chunk_size // overlap
        mix_shape = mix_t.shape[1]
        pad_size = hop_size - (mix_shape - chunk_size) % hop_size
        mix_t = torch.cat(
            [torch.zeros(2, chunk_size - hop_size), mix_t, torch.zeros(2, pad_size + chunk_size - hop_size)], dim=1
        )

        chunks = mix_t.unfold(1, chunk_size, hop_size).transpose(0, 1)
        batches = [chunks[i : i + self.mdx_batch_size] for i in range(0, len(chunks), self.mdx_batch_size)]

        X = (torch.zeros(S, *mix_t.shape) if S > 1 else torch.zeros_like(mix_t)).to(self.device)
        with torch.no_grad():
            cnt = 0
            for batch in batches:
                self.running_inference_progress_bar(len(batches))
                x = model(batch.to(self.device))
                for w in x:
                    X[..., cnt * hop_size : cnt * hop_size + chunk_size] += w
                    cnt += 1

        estimated = X[..., chunk_size - hop_size : -(pad_size + chunk_size - hop_size)] / overlap
        del X

        def _pitch_fix(s: np.ndarray) -> np.ndarray:
            return self.pitch_fix(s, sr_pitched, org_mix)

        if S > 1:
            sources = {
                k: (_pitch_fix(v) if self.is_pitch_change else v)
                for k, v in zip(self.mdx_c_configs.training.instruments, estimated.cpu().detach().numpy())
            }
            del estimated
            if self.is_denoise_model and VOCAL_STEM in sources and INST_STEM in sources:
                sources[VOCAL_STEM] = vr_denoiser(sources[VOCAL_STEM], self.device, model_path=self.DENOISER_MODEL)
                if sources[VOCAL_STEM].shape[1] != org_mix.shape[1]:
                    sources[VOCAL_STEM] = spec_utils.match_array_shapes(sources[VOCAL_STEM], org_mix)
                sources[INST_STEM] = org_mix - sources[VOCAL_STEM]
            return sources

        est_s = estimated.cpu().detach().numpy()
        del estimated
        return _pitch_fix(est_s) if self.is_pitch_change else est_s


def _secondary_stem(stem: str) -> str:
    """Return the complementary stem name (thin local alias)."""
    from gui_data.constants import secondary_stem as _ss
    return _ss(stem)
