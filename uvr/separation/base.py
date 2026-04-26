"""Shared base class for all separation backends."""

from __future__ import annotations

import os
import warnings
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import soundfile as sf
import torch

from gui_data.constants import (
    ALL_STEMS,
    BV_VOCAL_STEM,
    BV_VOCAL_STEM_I,
    BV_VOCAL_STEM_LABEL,
    CUDA_DEVICE,
    DEMUCS_ARCH_TYPE,
    DEMUCS_V3,
    DEMUCS_V4,
    DEFAULT,
    DONE,
    INFERENCE_STEP_1,
    INFERENCE_STEP_1_PRE,
    INFERENCE_STEP_1_SEC,
    INFERENCE_STEP_1_VOC_S,
    INFERENCE_STEP_2_PRE,
    INFERENCE_STEP_2_PRE_CACHED_MODOEL,
    INFERENCE_STEP_2_PRIMARY_CACHED,
    INFERENCE_STEP_2_SEC,
    INFERENCE_STEP_2_SEC_CACHED_MODOEL,
    INFERENCE_STEP_2_VOC_S,
    INFERENCE_STEP_DEVERBING,
    INST_STEM,
    LEAD_VOCAL_STEM,
    LEAD_VOCAL_STEM_I,
    LEAD_VOCAL_STEM_LABEL,
    MDX_ARCH_TYPE,
    SAVING_STEM,
    VR_ARCH_TYPE,
    VOCAL_STEM,
    secondary_stem,
)
from lib_v5 import spec_utils
from uvr.separation.audio_io import save_format
from uvr.separation.device import cpu, cuda_available, mps_available
from uvr.separation.vr_denoiser import vr_denoiser

if TYPE_CHECKING:
    from uvr.domain.model_data import ModelData

warnings.filterwarnings("ignore")


class SeperateAttributes:
    """Shared initialisation and output helpers for VR / MDX / Demucs backends."""

    def __init__(
        self,
        model_data: ModelData,
        process_data: dict[str, Any],
        main_model_primary_stem_4_stem: str | None = None,
        main_process_method: str | None = None,
        is_return_dual: bool = True,
        main_model_primary: str | None = None,
        vocal_stem_path: tuple[Any, str] | None = None,
        master_inst_source: np.ndarray | None = None,
        master_vocal_source: np.ndarray | None = None,
    ) -> None:
        self.list_all_models: list[str]
        self.process_data = process_data
        self.progress_value = 0
        self.set_progress_bar: Callable[..., None] = process_data["set_progress_bar"]
        self.write_to_console: Callable[..., None] = process_data["write_to_console"]

        if vocal_stem_path:
            self.audio_file, self.audio_file_base = vocal_stem_path
            self.audio_file_base_voc_split: Callable[[str, str], str] | None = (
                lambda stem, split: os.path.join(
                    self.export_path,
                    f'{self.audio_file_base.replace("_(Vocals)", "")}_({stem}_{split}).wav',
                )
            )
        else:
            self.audio_file = process_data["audio_file"]
            self.audio_file_base: str = process_data["audio_file_base"]
            self.audio_file_base_voc_split = None

        self.export_path: str = process_data["export_path"]
        self.cached_source_callback: Callable[..., Any] = process_data["cached_source_callback"]
        self.cached_model_source_holder: Callable[..., None] = process_data["cached_model_source_holder"]
        self.is_4_stem_ensemble: bool = process_data["is_4_stem_ensemble"]
        self.list_all_models = process_data["list_all_models"]
        self.process_iteration: Callable[[], None] = process_data["process_iteration"]
        self.is_return_dual = is_return_dual

        self.is_pitch_change: bool = model_data.is_pitch_change
        self.semitone_shift: float = model_data.semitone_shift
        self.is_match_frequency_pitch: bool = model_data.is_match_frequency_pitch
        self.overlap: str = model_data.overlap
        self.overlap_mdx: str = model_data.overlap_mdx
        self.overlap_mdx23: str = model_data.overlap_mdx23
        self.is_mdx_combine_stems: bool = model_data.is_mdx_combine_stems
        self.is_mdx_c: bool = model_data.is_mdx_c
        self.mdx_c_configs = model_data.mdx_c_configs
        self.mdxnet_stem_select: str = model_data.mdxnet_stem_select
        self.mixer_path = model_data.mixer_path
        self.model_samplerate: int = model_data.model_samplerate
        self.model_capacity = model_data.model_capacity
        self.is_vr_51_model: bool = model_data.is_vr_51_model
        self.is_pre_proc_model: bool = model_data.is_pre_proc_model
        self.is_secondary_model_activated: bool = model_data.is_secondary_model_activated if not self.is_pre_proc_model else False
        self.is_secondary_model: bool = model_data.is_secondary_model if not self.is_pre_proc_model else True
        self.process_method: str = model_data.process_method
        self.model_path: str = model_data.model_path
        self.model_name: str = model_data.model_name
        self.model_basename: str = model_data.model_basename
        self.wav_type_set: str = model_data.wav_type_set
        self.mp3_bit_set: str = model_data.mp3_bit_set
        self.save_format: str = model_data.save_format
        self.is_gpu_conversion: int = model_data.is_gpu_conversion
        self.is_normalization: bool = model_data.is_normalization
        self.is_primary_stem_only: bool = (
            model_data.is_primary_stem_only if not self.is_secondary_model else model_data.is_primary_model_primary_stem_only
        )
        self.is_secondary_stem_only: bool = (
            model_data.is_secondary_stem_only if not self.is_secondary_model else model_data.is_primary_model_secondary_stem_only
        )
        self.is_ensemble_mode: bool = model_data.is_ensemble_mode
        self.secondary_model = model_data.secondary_model
        self.primary_model_primary_stem: str = model_data.primary_model_primary_stem
        self.primary_stem_native: str = model_data.primary_stem_native
        self.primary_stem: str = model_data.primary_stem
        self.secondary_stem: str = model_data.secondary_stem
        self.is_invert_spec: bool = model_data.is_invert_spec
        self.is_deverb_vocals: bool = model_data.is_deverb_vocals
        self.is_mixer_mode: bool = model_data.is_mixer_mode
        self.secondary_model_scale: float = model_data.secondary_model_scale
        self.is_demucs_pre_proc_model_inst_mix: bool = model_data.is_demucs_pre_proc_model_inst_mix
        self.primary_source_map: dict[str, np.ndarray] = {}
        self.secondary_source_map: dict[str, np.ndarray] = {}
        self.primary_source: np.ndarray | None = None
        self.secondary_source: np.ndarray | None = None
        self.secondary_source_primary: np.ndarray | None = None
        self.secondary_source_secondary: np.ndarray | None = None
        self.main_model_primary_stem_4_stem = main_model_primary_stem_4_stem
        self.main_model_primary = main_model_primary
        self.ensemble_primary_stem: str = model_data.ensemble_primary_stem
        self.is_multi_stem_ensemble: bool = model_data.is_multi_stem_ensemble
        self.is_other_gpu = False
        self.is_deverb = True
        self.DENOISER_MODEL = model_data.DENOISER_MODEL
        self.DEVERBER_MODEL = model_data.DEVERBER_MODEL
        self.is_source_swap = False
        self.vocal_split_model = model_data.vocal_split_model
        self.is_vocal_split_model: bool = model_data.is_vocal_split_model
        self.master_vocal_path: str | None = None
        self.set_master_inst_source = None
        self.master_inst_source = master_inst_source
        self.master_vocal_source = master_vocal_source
        self.is_save_inst_vocal_splitter: bool = (
            isinstance(master_inst_source, np.ndarray) and model_data.is_save_inst_vocal_splitter
        )
        self.is_inst_only_voc_splitter: bool = model_data.is_inst_only_voc_splitter
        self.is_karaoke: bool = model_data.is_karaoke
        self.is_bv_model: bool = model_data.is_bv_model
        self.is_bv_model_rebalenced: bool = model_data.bv_model_rebalance and self.is_vocal_split_model
        self.is_sec_bv_rebalance: bool = model_data.is_sec_bv_rebalance
        self.stem_path_init: str = os.path.join(self.export_path, f"{self.audio_file_base}_({self.secondary_stem}).wav")
        self.deverb_vocal_opt: str = model_data.deverb_vocal_opt
        self.is_save_vocal_only: bool = model_data.is_save_vocal_only
        self.device: torch.device | str = cpu
        self.run_type: list[str] = ["CPUExecutionProvider"]
        self.is_opencl = False
        self.device_set = model_data.device_set
        self.is_use_opencl: bool = model_data.is_use_opencl

        if self.is_inst_only_voc_splitter or self.is_sec_bv_rebalance:
            self.is_primary_stem_only = False
            self.is_secondary_stem_only = False

        if main_model_primary and self.is_multi_stem_ensemble:
            self.primary_stem, self.secondary_stem = main_model_primary, secondary_stem(main_model_primary)

        if self.is_gpu_conversion >= 0:
            if mps_available:
                self.device, self.is_other_gpu = "mps", True
            else:
                device_prefix: str | None = None
                if self.device_set != DEFAULT:
                    device_prefix = CUDA_DEVICE
                if cuda_available:
                    self.device = CUDA_DEVICE if not device_prefix else f"{device_prefix}:{self.device_set}"
                    self.run_type = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        if model_data.process_method == MDX_ARCH_TYPE:
            self.is_mdx_ckpt: bool = model_data.is_mdx_ckpt
            self.primary_model_name, self.primary_sources = self.cached_source_callback(MDX_ARCH_TYPE, model_name=self.model_basename)
            self.is_denoise: bool = model_data.is_denoise
            self.is_denoise_model: bool = model_data.is_denoise_model
            self.is_mdx_c_seg_def: bool = model_data.is_mdx_c_seg_def
            self.mdx_batch_size = model_data.mdx_batch_size
            self.compensate = model_data.compensate
            self.mdx_segment_size: int = model_data.mdx_segment_size

            if self.is_mdx_c:
                if not self.is_4_stem_ensemble:
                    self.primary_stem = model_data.ensemble_primary_stem if process_data["is_ensemble_master"] else model_data.primary_stem
                    self.secondary_stem = model_data.ensemble_secondary_stem if process_data["is_ensemble_master"] else model_data.secondary_stem
            else:
                self.dim_f: int = model_data.mdx_dim_f_set
                self.dim_t: int = 2 ** model_data.mdx_dim_t_set

            self.check_label_secondary_stem_runs()
            self.n_fft: int = model_data.mdx_n_fft_scale_set
            self.chunks = model_data.chunks
            self.margin: int = model_data.margin
            self.adjust = 1
            self.dim_c = 4
            self.hop = 1024

        if model_data.process_method == DEMUCS_ARCH_TYPE:
            self.demucs_stems = model_data.demucs_stems if main_process_method not in (MDX_ARCH_TYPE, VR_ARCH_TYPE) else None
            self.secondary_model_4_stem = model_data.secondary_model_4_stem
            self.secondary_model_4_stem_scale = model_data.secondary_model_4_stem_scale
            self.is_chunk_demucs: bool = model_data.is_chunk_demucs
            self.segment = model_data.segment
            self.demucs_version: str = model_data.demucs_version
            self.demucs_source_list = model_data.demucs_source_list
            self.demucs_source_map: dict[str, int] = model_data.demucs_source_map
            self.is_demucs_combine_stems: bool = model_data.is_demucs_combine_stems
            self.demucs_stem_count: int = model_data.demucs_stem_count
            self.pre_proc_model = model_data.pre_proc_model
            self.device = cpu if self.is_other_gpu and self.demucs_version not in (DEMUCS_V3, DEMUCS_V4) else self.device

            self.primary_stem = model_data.ensemble_primary_stem if process_data["is_ensemble_master"] else model_data.primary_stem
            self.secondary_stem = model_data.ensemble_secondary_stem if process_data["is_ensemble_master"] else model_data.secondary_stem

            if (self.is_multi_stem_ensemble or self.is_4_stem_ensemble) and not self.is_secondary_model:
                self.is_return_dual = False

            if self.is_multi_stem_ensemble and main_model_primary:
                self.is_4_stem_ensemble = False
                if main_model_primary in self.demucs_source_map:
                    self.primary_stem = main_model_primary
                    self.secondary_stem = secondary_stem(main_model_primary)
                elif secondary_stem(main_model_primary) in self.demucs_source_map:
                    self.primary_stem = secondary_stem(main_model_primary)
                    self.secondary_stem = main_model_primary

            if self.is_secondary_model and not process_data["is_ensemble_master"]:
                if self.demucs_stem_count != 2 and model_data.primary_model_primary_stem == INST_STEM:
                    self.primary_stem = VOCAL_STEM
                    self.secondary_stem = INST_STEM
                else:
                    self.primary_stem = model_data.primary_model_primary_stem
                    self.secondary_stem = secondary_stem(self.primary_stem)

            self.shifts: int = model_data.shifts
            self.is_split_mode: bool = model_data.is_split_mode if self.demucs_version != DEMUCS_V4 else True
            self.primary_model_name, self.primary_sources = self.cached_source_callback(DEMUCS_ARCH_TYPE, model_name=self.model_basename)

        if model_data.process_method == VR_ARCH_TYPE:
            self.check_label_secondary_stem_runs()
            self.primary_model_name, self.primary_sources = self.cached_source_callback(VR_ARCH_TYPE, model_name=self.model_basename)
            self.mp = model_data.vr_model_param
            self.high_end_process: str = model_data.is_high_end_process
            self.is_tta: bool = model_data.is_tta
            self.is_post_process: bool = model_data.is_post_process
            self.batch_size: int = model_data.batch_size
            self.window_size: int = model_data.window_size
            self.input_high_end_h: int | None = None
            self.input_high_end: np.ndarray | None = None
            self.post_process_threshold: float = model_data.post_process_threshold
            self.aggressiveness: dict[str, Any] = {
                "value": model_data.aggression_setting,
                "split_bin": self.mp.param["band"][1]["crop_stop"],
                "aggr_correction": self.mp.param.get("aggr_correction"),
            }

    # ------------------------------------------------------------------
    # Console / progress helpers
    # ------------------------------------------------------------------

    def check_label_secondary_stem_runs(self) -> None:
        if self.process_data["is_ensemble_master"] and not self.is_4_stem_ensemble and not self.is_mdx_c:
            if self.ensemble_primary_stem != self.primary_stem:
                self.is_primary_stem_only, self.is_secondary_stem_only = self.is_secondary_stem_only, self.is_primary_stem_only
        if self.is_pre_proc_model or self.is_secondary_model:
            self.is_primary_stem_only = False
            self.is_secondary_stem_only = False

    def start_inference_console_write(self) -> None:
        if self.is_secondary_model and not self.is_pre_proc_model and not self.is_vocal_split_model:
            self.write_to_console(INFERENCE_STEP_2_SEC(self.process_method, self.model_basename))
        if self.is_pre_proc_model:
            self.write_to_console(INFERENCE_STEP_2_PRE(self.process_method, self.model_basename))
        if self.is_vocal_split_model:
            self.write_to_console(INFERENCE_STEP_2_VOC_S(self.process_method, self.model_basename))

    def running_inference_console_write(self, is_no_write: bool = False) -> None:
        if not is_no_write:
            self.write_to_console(DONE, base_text="")
            self.set_progress_bar(0.05)
        if self.is_secondary_model and not self.is_pre_proc_model and not self.is_vocal_split_model:
            self.write_to_console(INFERENCE_STEP_1_SEC)
        elif self.is_pre_proc_model:
            self.write_to_console(INFERENCE_STEP_1_PRE)
        elif self.is_vocal_split_model:
            self.write_to_console(INFERENCE_STEP_1_VOC_S)
        else:
            self.write_to_console(INFERENCE_STEP_1)

    def running_inference_progress_bar(self, length: int, is_match_mix: bool = False) -> None:
        if not is_match_mix:
            self.progress_value += 1
            if (0.8 / length * self.progress_value) >= 0.8:
                length = self.progress_value + 1
            self.set_progress_bar(0.1, 0.8 / length * self.progress_value)

    def load_cached_sources(self) -> None:
        if self.is_secondary_model and not self.is_pre_proc_model:
            self.write_to_console(INFERENCE_STEP_2_SEC_CACHED_MODOEL(self.process_method, self.model_basename))
        elif self.is_pre_proc_model:
            self.write_to_console(INFERENCE_STEP_2_PRE_CACHED_MODOEL(self.process_method, self.model_basename))
        else:
            self.write_to_console(INFERENCE_STEP_2_PRIMARY_CACHED, "")

    # ------------------------------------------------------------------
    # Source caching
    # ------------------------------------------------------------------

    def cache_source(self, secondary_sources: Any) -> None:
        if self.list_all_models.count(self.model_basename) > 1:
            self.cached_model_source_holder(self.process_method, secondary_sources, self.model_basename)

    # ------------------------------------------------------------------
    # Vocal split chain
    # ------------------------------------------------------------------

    def process_vocal_split_chain(self, sources: dict[str, Any]) -> None:
        master_inst_source = sources.get(INST_STEM)
        master_vocal_source = sources.get(VOCAL_STEM)

        if (
            isinstance(master_vocal_source, np.ndarray)
            and self.vocal_split_model
            and not self.is_ensemble_mode
            and not self.is_karaoke
            and not self.is_bv_model
        ):
            from uvr.separation.chain import process_chain_model  # deferred — chain imports the subclasses

            process_chain_model(
                self.vocal_split_model,
                self.process_data,
                vocal_stem_path=self.master_vocal_path,
                master_vocal_source=master_vocal_source,
                master_inst_source=master_inst_source,
            )

    # ------------------------------------------------------------------
    # Stem processing and output
    # ------------------------------------------------------------------

    def process_secondary_stem(
        self,
        stem_source: np.ndarray,
        secondary_model_source: np.ndarray | None = None,
        model_scale: float | None = None,
    ) -> np.ndarray:
        if not self.is_secondary_model and self.is_secondary_model_activated and isinstance(secondary_model_source, np.ndarray):
            scale = model_scale if model_scale is not None else self.secondary_model_scale
            stem_source = spec_utils.average_dual_sources(stem_source, secondary_model_source, scale)
        return stem_source

    def final_process(
        self,
        stem_path: str,
        source: np.ndarray,
        secondary_source: np.ndarray | None,
        stem_name: str,
        samplerate: int,
    ) -> dict[str, np.ndarray]:
        source = self.process_secondary_stem(source, secondary_source)
        self.write_audio(stem_path, source, samplerate, stem_name=stem_name)
        return {stem_name: source}

    def write_audio(self, stem_path: str, stem_source: np.ndarray, samplerate: int, stem_name: str | None = None) -> None:
        is_not_ensemble = not self.is_ensemble_mode or self.is_vocal_split_model

        def _save_audio(path: str, source: np.ndarray) -> None:
            source = spec_utils.normalize(source, self.is_normalization)
            sf.write(path, source, samplerate, subtype=self.wav_type_set)
            if is_not_ensemble:
                save_format(path, self.save_format, self.mp3_bit_set)

        def _save_with_message(path: str, name: str, source: np.ndarray) -> None:
            is_deverb = self.is_deverb_vocals and (
                self.deverb_vocal_opt == name
                or (self.deverb_vocal_opt == "ALL" and name in (VOCAL_STEM, LEAD_VOCAL_STEM_LABEL, BV_VOCAL_STEM_LABEL))
            )
            self.write_to_console(f"{SAVING_STEM[0]}{name}{SAVING_STEM[1]}")
            if is_deverb and is_not_ensemble:
                self.write_to_console(INFERENCE_STEP_DEVERBING, base_text="")
                src_deverbed, src_reverb = vr_denoiser(source, self.device, is_deverber=True, model_path=self.DEVERBER_MODEL)
                _save_audio(path.replace(".wav", "_deverbed.wav"), src_deverbed)
                _save_audio(path.replace(".wav", "_reverb_only.wav"), src_reverb)
            _save_audio(path, source)
            self.write_to_console(DONE, base_text="")

        def _save_voc_split_vocal(name: str, source: np.ndarray) -> None:
            label = LEAD_VOCAL_STEM_LABEL if name == LEAD_VOCAL_STEM else BV_VOCAL_STEM_LABEL
            _save_with_message(self.audio_file_base_voc_split(VOCAL_STEM, name), label, source)

        def _save_voc_split_instrumental(name: str, source: np.ndarray, is_inst_invert: bool = False) -> None:
            inst_label = "Instrumental (With Lead Vocals)" if name == LEAD_VOCAL_STEM else "Instrumental (With Backing Vocals)"
            inst_path_name = LEAD_VOCAL_STEM_I if name == LEAD_VOCAL_STEM else BV_VOCAL_STEM_I
            inst_src = -source if is_inst_invert else source
            combined = spec_utils.combine_arrarys([self.master_inst_source, inst_src], is_swap=True)
            _save_with_message(self.audio_file_base_voc_split(INST_STEM, inst_path_name), inst_label, combined)

        is_bv_model_lead = self.is_bv_model_rebalenced and self.is_vocal_split_model and stem_name == LEAD_VOCAL_STEM
        is_bv_rebalance_lead = self.is_bv_model_rebalenced and self.is_vocal_split_model and stem_name == BV_VOCAL_STEM
        is_no_vocal_save = (self.is_inst_only_voc_splitter and stem_name in (VOCAL_STEM, BV_VOCAL_STEM, LEAD_VOCAL_STEM)) or is_bv_model_lead
        is_do_not_save_inst = self.is_save_vocal_only and self.is_sec_bv_rebalance and stem_name == INST_STEM

        bv_rebalance_lead_source: np.ndarray | None = None
        if is_bv_rebalance_lead:
            master_voc = spec_utils.match_array_shapes(self.master_vocal_source, stem_source, is_swap=True)
            bv_rebalance_lead_source = stem_source - master_voc

        if not is_bv_model_lead and not is_do_not_save_inst:
            if self.is_vocal_split_model or not self.is_secondary_model:
                if self.is_vocal_split_model and not self.is_inst_only_voc_splitter:
                    _save_voc_split_vocal(stem_name, stem_source)
                    if is_bv_rebalance_lead and bv_rebalance_lead_source is not None:
                        _save_voc_split_vocal(LEAD_VOCAL_STEM, bv_rebalance_lead_source)
                else:
                    if not is_no_vocal_save:
                        _save_with_message(stem_path, stem_name, stem_source)

                if self.is_save_inst_vocal_splitter and not self.is_save_vocal_only:
                    _save_voc_split_instrumental(stem_name, stem_source)
                    if is_bv_rebalance_lead and bv_rebalance_lead_source is not None:
                        _save_voc_split_instrumental(LEAD_VOCAL_STEM, bv_rebalance_lead_source, is_inst_invert=True)

                self.set_progress_bar(0.95)

        if stem_name == VOCAL_STEM:
            self.master_vocal_path = stem_path

    # ------------------------------------------------------------------
    # Pitch helpers
    # ------------------------------------------------------------------

    def pitch_fix(self, source: np.ndarray, sr_pitched: int, org_mix: np.ndarray) -> np.ndarray:
        source = spec_utils.change_pitch_semitones(source, sr_pitched, semitone_shift=self.semitone_shift)[0]
        return spec_utils.match_array_shapes(source, org_mix)

    def match_frequency_pitch(self, mix: np.ndarray) -> np.ndarray:
        if self.is_match_frequency_pitch and self.is_pitch_change:
            source, sr_pitched = spec_utils.change_pitch_semitones(mix, 44100, semitone_shift=-self.semitone_shift)
            return self.pitch_fix(source, sr_pitched, mix)
        return mix
