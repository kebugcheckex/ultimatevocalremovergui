"""Typed ModelData extraction without direct Tk/root access."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

import yaml
from ml_collections import ConfigDict

runtime: Any | None = None


def configure_runtime(module: Any) -> None:
    global runtime
    runtime = module


@dataclass(frozen=True)
class ModelDataSettings:
    device_set: str
    is_deverb_vocals: bool
    deverb_vocal_opt: Any
    is_denoise_model: bool
    is_gpu_conversion: bool
    is_normalization: bool
    is_use_opencl: bool
    is_primary_stem_only: bool
    is_secondary_stem_only: bool
    is_primary_stem_only_demucs: bool
    is_secondary_stem_only_demucs: bool
    denoise_option: str
    is_mdx_c_seg_def: bool
    mdx_batch_size: str
    mdxnet_stems: str
    overlap: str
    overlap_mdx: str
    overlap_mdx23: str
    semitone_shift: str
    is_match_frequency_pitch: bool
    is_mdx23_combine_stems: bool
    wav_type_set: Any
    mp3_bit_set: str
    save_format: str
    is_invert_spec: bool
    demucs_stems: str
    is_demucs_combine_stems: bool
    chosen_process_method: str
    is_save_inst_set_vocal_splitter: bool
    ensemble_main_stem: str
    vr_is_secondary_model_activate: bool
    aggression_setting: Any
    is_tta: bool
    is_post_process: bool
    window_size: Any
    batch_size: str
    crop_size: Any
    is_high_end_process: bool
    post_process_threshold: Any
    vr_hash_mapper: dict[str, Any]
    mdx_is_secondary_model_activate: bool
    margin: Any
    mdx_segment_size: Any
    mdx_hash_mapper: dict[str, Any]
    compensate: str
    demucs_is_secondary_model_activate: bool
    is_demucs_pre_proc_model_activate: bool
    is_demucs_pre_proc_model_inst_mix: bool
    margin_demucs: Any
    shifts: Any
    is_split_mode: bool
    segment: str
    is_chunk_demucs: bool
    mdx_name_select_mapper: dict[str, Any]
    demucs_name_select_mapper: dict[str, Any]


@dataclass(frozen=True)
class ModelDataResolvers:
    return_ensemble_stems: Callable[[], tuple[str, str]]
    check_only_selection_stem: Callable[[str], bool]
    determine_secondary_model: Callable[[str, str, bool, bool], tuple[Any, Any]]
    determine_demucs_pre_proc_model: Callable[[str | None], Any]
    determine_vocal_split_model: Callable[[], Any]
    resolve_popup_model_data: Callable[[str, str, str, str, bool], dict[str, Any] | None]


class ModelData:
    def __init__(
        self,
        model_name: str,
        selected_process_method: str = None,
        is_secondary_model: bool = False,
        primary_model_primary_stem: str | None = None,
        is_primary_model_primary_stem_only: bool = False,
        is_primary_model_secondary_stem_only: bool = False,
        is_pre_proc_model: bool = False,
        is_dry_check: bool = False,
        is_change_def: bool = False,
        is_get_hash_dir_only: bool = False,
        is_vocal_split_model: bool = False,
        *,
        settings: ModelDataSettings,
        resolvers: ModelDataResolvers,
    ):
        self.settings = settings
        self.resolvers = resolvers
        selected_process_method = selected_process_method or runtime.ENSEMBLE_MODE

        device_set = settings.device_set
        self.DENOISER_MODEL = runtime.DENOISER_MODEL_PATH
        self.DEVERBER_MODEL = runtime.DEVERBER_MODEL_PATH
        self.is_deverb_vocals = settings.is_deverb_vocals if os.path.isfile(runtime.DEVERBER_MODEL_PATH) else False
        self.deverb_vocal_opt = settings.deverb_vocal_opt
        self.is_denoise_model = settings.is_denoise_model if os.path.isfile(runtime.DENOISER_MODEL_PATH) else False
        self.is_gpu_conversion = 0 if settings.is_gpu_conversion else -1
        self.is_normalization = settings.is_normalization
        self.is_use_opencl = settings.is_use_opencl
        self.is_primary_stem_only = settings.is_primary_stem_only
        self.is_secondary_stem_only = settings.is_secondary_stem_only
        self.is_denoise = settings.denoise_option != runtime.DENOISE_NONE
        self.is_mdx_c_seg_def = settings.is_mdx_c_seg_def
        self.mdx_batch_size = 1 if settings.mdx_batch_size == runtime.DEF_OPT else int(settings.mdx_batch_size)
        self.mdxnet_stem_select = settings.mdxnet_stems
        self.overlap = float(settings.overlap) if settings.overlap != runtime.DEFAULT else 0.25
        self.overlap_mdx = (
            float(settings.overlap_mdx) if settings.overlap_mdx != runtime.DEFAULT else settings.overlap_mdx
        )
        self.overlap_mdx23 = int(float(settings.overlap_mdx23))
        self.semitone_shift = float(settings.semitone_shift)
        self.is_pitch_change = self.semitone_shift != 0
        self.is_match_frequency_pitch = settings.is_match_frequency_pitch
        self.is_mdx_ckpt = False
        self.is_mdx_c = False
        self.is_mdx_combine_stems = settings.is_mdx23_combine_stems
        self.mdx_c_configs = None
        self.mdx_model_stems: list[str] = []
        self.mdx_dim_f_set = None
        self.mdx_dim_t_set = None
        self.mdx_stem_count = 1
        self.compensate = None
        self.mdx_n_fft_scale_set = None
        self.wav_type_set = settings.wav_type_set
        self.device_set = device_set.split(":")[-1].strip() if ":" in device_set else device_set
        self.mp3_bit_set = settings.mp3_bit_set
        self.save_format = settings.save_format
        self.is_invert_spec = settings.is_invert_spec
        self.is_mixer_mode = False
        self.demucs_stems = settings.demucs_stems
        self.is_demucs_combine_stems = settings.is_demucs_combine_stems
        self.demucs_source_list: list[str] = []
        self.demucs_stem_count = 0
        self.mixer_path = runtime.MDX_MIXER_PATH
        self.model_name = model_name
        self.process_method = selected_process_method
        self.model_status = False if self.model_name in (runtime.CHOOSE_MODEL, runtime.NO_MODEL) else True
        self.primary_stem = None
        self.secondary_stem = None
        self.primary_stem_native = None
        self.is_ensemble_mode = False
        self.ensemble_primary_stem = None
        self.ensemble_secondary_stem = None
        self.primary_model_primary_stem = primary_model_primary_stem
        self.is_secondary_model = True if is_vocal_split_model else is_secondary_model
        self.secondary_model = None
        self.secondary_model_scale = None
        self.demucs_4_stem_added_count = 0
        self.is_demucs_4_stem_secondaries = False
        self.is_4_stem_ensemble = False
        self.pre_proc_model = None
        self.pre_proc_model_activated = False
        self.is_pre_proc_model = is_pre_proc_model
        self.is_dry_check = is_dry_check
        self.model_samplerate = 44100
        self.model_capacity = 32, 128
        self.is_vr_51_model = False
        self.is_demucs_pre_proc_model_inst_mix = False
        self.manual_download_Button = None
        self.secondary_model_4_stem: list[Any] = []
        self.secondary_model_4_stem_scale: list[Any] = []
        self.secondary_model_4_stem_names: list[str] = []
        self.secondary_model_4_stem_model_names_list: list[str | None] = []
        self.all_models: list[Any] = []
        self.secondary_model_other = None
        self.secondary_model_scale_other = None
        self.secondary_model_bass = None
        self.secondary_model_scale_bass = None
        self.secondary_model_drums = None
        self.secondary_model_scale_drums = None
        self.is_multi_stem_ensemble = False
        self.is_karaoke = False
        self.is_bv_model = False
        self.bv_model_rebalance = 0
        self.is_sec_bv_rebalance = False
        self.is_change_def = is_change_def
        self.model_hash_dir = None
        self.is_get_hash_dir_only = is_get_hash_dir_only
        self.is_secondary_model_activated = False
        self.vocal_split_model = None
        self.is_vocal_split_model = is_vocal_split_model
        self.is_vocal_split_model_activated = False
        self.is_save_inst_vocal_splitter = settings.is_save_inst_set_vocal_splitter
        self.is_inst_only_voc_splitter = resolvers.check_only_selection_stem(runtime.INST_STEM_ONLY)
        self.is_save_vocal_only = resolvers.check_only_selection_stem(runtime.IS_SAVE_VOC_ONLY)

        if selected_process_method == runtime.ENSEMBLE_MODE:
            self.process_method, _, self.model_name = model_name.partition(runtime.ENSEMBLE_PARTITION)
            self.model_and_process_tag = model_name
            self.ensemble_primary_stem, self.ensemble_secondary_stem = resolvers.return_ensemble_stems()

            is_not_secondary_or_pre_proc = not is_secondary_model and not is_pre_proc_model
            self.is_ensemble_mode = is_not_secondary_or_pre_proc

            if settings.ensemble_main_stem == runtime.FOUR_STEM_ENSEMBLE:
                self.is_4_stem_ensemble = self.is_ensemble_mode
            elif (
                settings.ensemble_main_stem == runtime.MULTI_STEM_ENSEMBLE
                and settings.chosen_process_method == runtime.ENSEMBLE_MODE
            ):
                self.is_multi_stem_ensemble = True

            is_not_vocal_stem = self.ensemble_primary_stem != runtime.VOCAL_STEM
            self.pre_proc_model_activated = settings.is_demucs_pre_proc_model_activate if is_not_vocal_stem else False

        if self.process_method == runtime.VR_ARCH_TYPE:
            self.is_secondary_model_activated = settings.vr_is_secondary_model_activate if not is_secondary_model else False
            self.aggression_setting = float(int(settings.aggression_setting) / 100)
            self.is_tta = settings.is_tta
            self.is_post_process = settings.is_post_process
            self.window_size = int(settings.window_size)
            self.batch_size = 1 if settings.batch_size == runtime.DEF_OPT else int(settings.batch_size)
            self.crop_size = int(settings.crop_size)
            self.is_high_end_process = "mirroring" if settings.is_high_end_process else "None"
            self.post_process_threshold = float(settings.post_process_threshold)
            self.model_capacity = 32, 128
            self.model_path = os.path.join(runtime.VR_MODELS_DIR, f"{self.model_name}.pth")
            self.get_model_hash()
            if self.model_hash:
                self.model_hash_dir = os.path.join(runtime.VR_HASH_DIR, f"{self.model_hash}.json")
                if is_change_def:
                    self.model_data = self.change_model_data()
                else:
                    self.model_data = (
                        self.get_model_data(runtime.VR_HASH_DIR, settings.vr_hash_mapper)
                        if self.model_hash != runtime.WOOD_INST_MODEL_HASH
                        else runtime.WOOD_INST_PARAMS
                    )
                if self.model_data:
                    vr_model_param = os.path.join(
                        runtime.VR_PARAM_DIR,
                        f"{self.model_data['vr_model_param']}.json",
                    )
                    self.primary_stem = self.model_data["primary_stem"]
                    self.secondary_stem = runtime.secondary_stem(self.primary_stem)
                    self.vr_model_param = runtime.ModelParameters(vr_model_param)
                    self.model_samplerate = self.vr_model_param.param["sr"]
                    self.primary_stem_native = self.primary_stem
                    if "nout" in self.model_data and "nout_lstm" in self.model_data:
                        self.model_capacity = self.model_data["nout"], self.model_data["nout_lstm"]
                        self.is_vr_51_model = True
                    self.check_if_karaokee_model()
                else:
                    self.model_status = False

        if self.process_method == runtime.MDX_ARCH_TYPE:
            self.is_secondary_model_activated = settings.mdx_is_secondary_model_activate if not is_secondary_model else False
            self.margin = int(settings.margin)
            self.chunks = 0
            self.mdx_segment_size = int(settings.mdx_segment_size)
            self.get_mdx_model_path()
            self.get_model_hash()
            if self.model_hash:
                self.model_hash_dir = os.path.join(runtime.MDX_HASH_DIR, f"{self.model_hash}.json")
                if is_change_def:
                    self.model_data = self.change_model_data()
                else:
                    self.model_data = self.get_model_data(runtime.MDX_HASH_DIR, settings.mdx_hash_mapper)
                if self.model_data:
                    if "config_yaml" in self.model_data:
                        self.is_mdx_c = True
                        config_path = os.path.join(runtime.MDX_C_CONFIG_PATH, self.model_data["config_yaml"])
                        if os.path.isfile(config_path):
                            with open(config_path) as handle:
                                config = ConfigDict(yaml.load(handle, Loader=yaml.FullLoader))

                            self.mdx_c_configs = config
                            if self.mdx_c_configs.training.target_instrument:
                                target = self.mdx_c_configs.training.target_instrument
                                self.mdx_model_stems = [target]
                                self.primary_stem = target
                            else:
                                self.mdx_model_stems = self.mdx_c_configs.training.instruments
                                self.mdx_stem_count = len(self.mdx_model_stems)
                                self.primary_stem = (
                                    self.mdx_model_stems[0]
                                    if self.mdx_stem_count == 2
                                    else self.mdxnet_stem_select
                                )
                                if self.is_ensemble_mode:
                                    self.mdxnet_stem_select = self.ensemble_primary_stem
                        else:
                            self.model_status = False
                    else:
                        self.compensate = (
                            self.model_data["compensate"]
                            if settings.compensate == runtime.AUTO_SELECT
                            else float(settings.compensate)
                        )
                        self.mdx_dim_f_set = self.model_data["mdx_dim_f_set"]
                        self.mdx_dim_t_set = self.model_data["mdx_dim_t_set"]
                        self.mdx_n_fft_scale_set = self.model_data["mdx_n_fft_scale_set"]
                        self.primary_stem = self.model_data["primary_stem"]
                        self.primary_stem_native = self.model_data["primary_stem"]
                        self.check_if_karaokee_model()

                    self.secondary_stem = runtime.secondary_stem(self.primary_stem)
                else:
                    self.model_status = False

        if self.process_method == runtime.DEMUCS_ARCH_TYPE:
            self.is_secondary_model_activated = settings.demucs_is_secondary_model_activate if not is_secondary_model else False
            if not self.is_ensemble_mode:
                self.pre_proc_model_activated = (
                    settings.is_demucs_pre_proc_model_activate
                    if settings.demucs_stems not in [runtime.VOCAL_STEM, runtime.INST_STEM]
                    else False
                )
            self.margin_demucs = int(settings.margin_demucs)
            self.chunks_demucs = 0
            self.shifts = int(settings.shifts)
            self.is_split_mode = settings.is_split_mode
            self.segment = settings.segment
            self.is_chunk_demucs = settings.is_chunk_demucs
            self.is_primary_stem_only = (
                settings.is_primary_stem_only if self.is_ensemble_mode else settings.is_primary_stem_only_demucs
            )
            self.is_secondary_stem_only = (
                settings.is_secondary_stem_only if self.is_ensemble_mode else settings.is_secondary_stem_only_demucs
            )
            self.get_demucs_model_data()
            self.get_demucs_model_path()

        if self.model_status:
            self.model_basename = os.path.splitext(os.path.basename(self.model_path))[0]
        else:
            self.model_basename = None

        self.pre_proc_model_activated = self.pre_proc_model_activated if not self.is_secondary_model else False
        self.is_primary_model_primary_stem_only = is_primary_model_primary_stem_only
        self.is_primary_model_secondary_stem_only = is_primary_model_secondary_stem_only

        is_secondary_activated_and_status = self.is_secondary_model_activated and self.model_status
        is_demucs = self.process_method == runtime.DEMUCS_ARCH_TYPE
        is_all_stems = settings.demucs_stems == runtime.ALL_STEMS
        is_valid_ensemble = not self.is_ensemble_mode and is_all_stems and is_demucs
        is_multi_stem_ensemble_demucs = self.is_multi_stem_ensemble and is_demucs

        if is_secondary_activated_and_status:
            if is_valid_ensemble or self.is_4_stem_ensemble or is_multi_stem_ensemble_demucs:
                for key in runtime.DEMUCS_4_SOURCE_LIST:
                    self.secondary_model_data(key)
                    self.secondary_model_4_stem.append(self.secondary_model)
                    self.secondary_model_4_stem_scale.append(self.secondary_model_scale)
                    self.secondary_model_4_stem_names.append(key)

                self.demucs_4_stem_added_count = sum(item is not None for item in self.secondary_model_4_stem)
                self.is_secondary_model_activated = any(item is not None for item in self.secondary_model_4_stem)
                self.demucs_4_stem_added_count -= 1 if self.is_secondary_model_activated else 0

                if self.is_secondary_model_activated:
                    self.secondary_model_4_stem_model_names_list = [
                        item.model_basename if item is not None else None for item in self.secondary_model_4_stem
                    ]
                    self.is_demucs_4_stem_secondaries = True
            else:
                primary_stem = self.ensemble_primary_stem if self.is_ensemble_mode and is_demucs else self.primary_stem
                self.secondary_model_data(primary_stem)

        if self.process_method == runtime.DEMUCS_ARCH_TYPE and not is_secondary_model:
            if self.demucs_stem_count >= 3 and self.pre_proc_model_activated:
                self.pre_proc_model = resolvers.determine_demucs_pre_proc_model(self.primary_stem)
                self.pre_proc_model_activated = True if self.pre_proc_model else False
                self.is_demucs_pre_proc_model_inst_mix = (
                    settings.is_demucs_pre_proc_model_inst_mix if self.pre_proc_model else False
                )

        if self.is_vocal_split_model and self.model_status:
            self.is_secondary_model_activated = False
            if self.is_bv_model:
                primary = (
                    runtime.BV_VOCAL_STEM
                    if self.primary_stem_native == runtime.VOCAL_STEM
                    else runtime.LEAD_VOCAL_STEM
                )
            else:
                primary = (
                    runtime.LEAD_VOCAL_STEM
                    if self.primary_stem_native == runtime.VOCAL_STEM
                    else runtime.BV_VOCAL_STEM
                )
            self.primary_stem, self.secondary_stem = primary, runtime.secondary_stem(primary)

        self.vocal_splitter_model_data()

    def vocal_splitter_model_data(self) -> None:
        if not self.is_secondary_model and self.model_status:
            self.vocal_split_model = self.resolvers.determine_vocal_split_model()
            self.is_vocal_split_model_activated = True if self.vocal_split_model else False
            if self.vocal_split_model and self.vocal_split_model.bv_model_rebalance:
                self.is_sec_bv_rebalance = True

    def secondary_model_data(self, primary_stem: str) -> None:
        secondary_model_data = self.resolvers.determine_secondary_model(
            self.process_method,
            primary_stem,
            self.is_primary_stem_only,
            self.is_secondary_stem_only,
        )
        self.secondary_model = secondary_model_data[0]
        self.secondary_model_scale = secondary_model_data[1]
        self.is_secondary_model_activated = False if not self.secondary_model else True
        if self.secondary_model:
            self.is_secondary_model_activated = self.secondary_model.model_basename != self.model_basename

    def check_if_karaokee_model(self) -> None:
        if runtime.IS_KARAOKEE in self.model_data.keys():
            self.is_karaoke = self.model_data[runtime.IS_KARAOKEE]
        if runtime.IS_BV_MODEL in self.model_data.keys():
            self.is_bv_model = self.model_data[runtime.IS_BV_MODEL]
        if runtime.IS_BV_MODEL_REBAL in self.model_data.keys() and self.is_bv_model:
            self.bv_model_rebalance = self.model_data[runtime.IS_BV_MODEL_REBAL]

    def get_mdx_model_path(self) -> None:
        if self.model_name.endswith(runtime.CKPT):
            self.is_mdx_ckpt = True

        ext = "" if self.is_mdx_ckpt else runtime.ONNX
        for file_name, chosen_mdx_model in self.settings.mdx_name_select_mapper.items():
            if self.model_name in chosen_mdx_model:
                if file_name.endswith(runtime.CKPT):
                    ext = ""
                self.model_path = os.path.join(runtime.MDX_MODELS_DIR, f"{file_name}{ext}")
                break
        else:
            self.model_path = os.path.join(runtime.MDX_MODELS_DIR, f"{self.model_name}{ext}")

        self.mixer_path = os.path.join(runtime.MDX_MODELS_DIR, "mixer_val.ckpt")

    def get_demucs_model_path(self) -> None:
        demucs_newer = self.demucs_version in {runtime.DEMUCS_V3, runtime.DEMUCS_V4}
        demucs_model_dir = runtime.DEMUCS_NEWER_REPO_DIR if demucs_newer else runtime.DEMUCS_MODELS_DIR
        for file_name, chosen_model in self.settings.demucs_name_select_mapper.items():
            if self.model_name == chosen_model:
                self.model_path = os.path.join(demucs_model_dir, file_name)
                break
        else:
            self.model_path = os.path.join(runtime.DEMUCS_NEWER_REPO_DIR, f"{self.model_name}.yaml")

    def get_demucs_model_data(self) -> None:
        self.demucs_version = runtime.DEMUCS_V4
        for key, value in runtime.DEMUCS_VERSION_MAPPER.items():
            if value in self.model_name:
                self.demucs_version = key

        if runtime.DEMUCS_UVR_MODEL in self.model_name:
            self.demucs_source_list, self.demucs_source_map, self.demucs_stem_count = (
                runtime.DEMUCS_2_SOURCE,
                runtime.DEMUCS_2_SOURCE_MAPPER,
                2,
            )
        else:
            self.demucs_source_list, self.demucs_source_map, self.demucs_stem_count = (
                runtime.DEMUCS_4_SOURCE,
                runtime.DEMUCS_4_SOURCE_MAPPER,
                4,
            )

        if not self.is_ensemble_mode:
            self.primary_stem = runtime.PRIMARY_STEM if self.demucs_stems == runtime.ALL_STEMS else self.demucs_stems
            self.secondary_stem = runtime.secondary_stem(self.primary_stem)

    def get_model_data(self, model_hash_dir: str, hash_mapper: dict[str, Any]) -> dict[str, Any] | None:
        model_settings_json = os.path.join(model_hash_dir, f"{self.model_hash}.json")
        if os.path.isfile(model_settings_json):
            with open(model_settings_json, "r") as json_file:
                return json.load(json_file)
        for hash_value, settings in hash_mapper.items():
            if self.model_hash in hash_value:
                return settings
        return self.get_model_data_from_popup()

    def change_model_data(self) -> dict[str, Any] | None:
        if self.is_get_hash_dir_only:
            return None
        return self.get_model_data_from_popup()

    def get_model_data_from_popup(self) -> dict[str, Any] | None:
        if self.is_dry_check:
            return None
        return self.resolvers.resolve_popup_model_data(
            self.process_method,
            self.model_name,
            self.model_hash,
            self.model_path,
            self.is_change_def,
        )

    def get_model_hash(self) -> None:
        self.model_hash = None
        if not os.path.isfile(self.model_path):
            self.model_status = False
            self.model_hash = None
        else:
            if runtime.model_hash_table:
                for key, value in runtime.model_hash_table.items():
                    if self.model_path == key:
                        self.model_hash = value
                        break

            if not self.model_hash:
                try:
                    with open(self.model_path, "rb") as handle:
                        handle.seek(-10000 * 1024, 2)
                        self.model_hash = hashlib.md5(handle.read()).hexdigest()
                except Exception:
                    self.model_hash = hashlib.md5(open(self.model_path, "rb").read()).hexdigest()

                runtime.model_hash_table.update({self.model_path: self.model_hash})
