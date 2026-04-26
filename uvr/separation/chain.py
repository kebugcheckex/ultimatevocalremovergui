"""Secondary-model and vocal-split chain orchestration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from lib_v5 import spec_utils
from gui_data.constants import DEMUCS_ARCH_TYPE, MDX_ARCH_TYPE, VR_ARCH_TYPE, secondary_stem

from uvr.separation.vr import SeperateVR
from uvr.separation.mdx import SeperateMDX
from uvr.separation.mdxc import SeperateMDXC
from uvr.separation.demucs import SeperateDemucs

if TYPE_CHECKING:
    from uvr.domain.model_data import ModelData


def process_secondary_model(
    secondary_model: ModelData,
    process_data: dict,
    main_model_primary_stem_4_stem: str | None = None,
    is_source_load: bool = False,
    main_process_method: str | None = None,
    is_pre_proc_model: bool = False,
    is_return_dual: bool = True,
    main_model_primary: str | None = None,
) -> dict[str, np.ndarray] | np.ndarray | tuple | None:
    if not is_pre_proc_model:
        process_data["process_iteration"]()

    if secondary_model.process_method == VR_ARCH_TYPE:
        seperator = SeperateVR(
            secondary_model, process_data,
            main_model_primary_stem_4_stem=main_model_primary_stem_4_stem,
            main_process_method=main_process_method,
            main_model_primary=main_model_primary,
        )
    elif secondary_model.process_method == MDX_ARCH_TYPE:
        if secondary_model.is_mdx_c:
            seperator = SeperateMDXC(
                secondary_model, process_data,
                main_model_primary_stem_4_stem=main_model_primary_stem_4_stem,
                main_process_method=main_process_method,
                is_return_dual=is_return_dual,
                main_model_primary=main_model_primary,
            )
        else:
            seperator = SeperateMDX(
                secondary_model, process_data,
                main_model_primary_stem_4_stem=main_model_primary_stem_4_stem,
                main_process_method=main_process_method,
                main_model_primary=main_model_primary,
            )
    elif secondary_model.process_method == DEMUCS_ARCH_TYPE:
        seperator = SeperateDemucs(
            secondary_model, process_data,
            main_model_primary_stem_4_stem=main_model_primary_stem_4_stem,
            main_process_method=main_process_method,
            is_return_dual=is_return_dual,
            main_model_primary=main_model_primary,
        )
    else:
        raise ValueError(f"Unknown process method: {secondary_model.process_method!r}")

    secondary_sources = seperator.seperate()

    if isinstance(secondary_sources, dict) and not is_source_load and not is_pre_proc_model:
        primary_stem_name = secondary_model.primary_model_primary_stem
        return gather_sources(primary_stem_name, secondary_stem(primary_stem_name), secondary_sources)
    return secondary_sources


def process_chain_model(
    secondary_model: ModelData,
    process_data: dict,
    vocal_stem_path: str,
    master_vocal_source: np.ndarray,
    master_inst_source: np.ndarray | None = None,
) -> dict[str, np.ndarray] | None:
    process_data["process_iteration"]()

    if secondary_model.bv_model_rebalance:
        vocal_source = spec_utils.reduce_mix_bv(
            master_inst_source, master_vocal_source, reduction_rate=secondary_model.bv_model_rebalance
        )
    else:
        vocal_source = master_vocal_source

    stem_path_arg = [vocal_source, os.path.splitext(os.path.basename(vocal_stem_path))[0]]

    if secondary_model.process_method == VR_ARCH_TYPE:
        seperator = SeperateVR(
            secondary_model, process_data,
            vocal_stem_path=stem_path_arg,
            master_inst_source=master_inst_source,
            master_vocal_source=master_vocal_source,
        )
    elif secondary_model.process_method == MDX_ARCH_TYPE:
        if secondary_model.is_mdx_c:
            seperator = SeperateMDXC(
                secondary_model, process_data,
                vocal_stem_path=stem_path_arg,
                master_inst_source=master_inst_source,
                master_vocal_source=master_vocal_source,
            )
        else:
            seperator = SeperateMDX(
                secondary_model, process_data,
                vocal_stem_path=stem_path_arg,
                master_inst_source=master_inst_source,
                master_vocal_source=master_vocal_source,
            )
    elif secondary_model.process_method == DEMUCS_ARCH_TYPE:
        seperator = SeperateDemucs(
            secondary_model, process_data,
            vocal_stem_path=stem_path_arg,
            master_inst_source=master_inst_source,
            master_vocal_source=master_vocal_source,
        )
    else:
        raise ValueError(f"Unknown process method: {secondary_model.process_method!r}")

    secondary_sources = seperator.seperate()
    return secondary_sources if isinstance(secondary_sources, dict) else None


def gather_sources(
    primary_stem_name: str,
    secondary_stem_name: str,
    secondary_sources: dict[str, np.ndarray],
) -> tuple[np.ndarray | bool, np.ndarray | bool]:
    source_primary: np.ndarray | bool = False
    source_secondary: np.ndarray | bool = False

    for key, value in secondary_sources.items():
        if key in primary_stem_name:
            source_primary = value
        if key in secondary_stem_name:
            source_secondary = value

    return source_primary, source_secondary
