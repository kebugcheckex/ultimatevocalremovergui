"""Pure helper functions for model selection and state normalization."""

from __future__ import annotations

from dataclasses import replace

from gui_data.constants import ALL_STEMS, INST_STEM, NO_MODEL, VOCAL_STEM
from uvr_qt.services import ProcessingFacade
from uvr_qt.state import AppState


SECONDARY_MODEL_SLOTS = (
    ("voc_inst", "Vocals / Instrumental"),
    ("other", "Other / No Other"),
    ("bass", "Bass / No Bass"),
    ("drums", "Drums / No Drums"),
)


def available_aux_models(facade: ProcessingFacade) -> tuple[str, ...]:
    models = facade.available_tagged_models_for_methods(("VR Architecture", "MDX-Net"))
    return (NO_MODEL, *models)


def available_stem_targets(
    facade: ProcessingFacade,
    state: AppState,
    process_method: str,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    try:
        targets = facade.available_stem_targets(state, process_method)
    except Exception:
        targets = ()
    return targets or fallback


def coerce_model_stem_selection(
    state: AppState, process_method: str, available_targets: tuple[str, ...]
) -> AppState:
    if process_method == "MDX-Net":
        current_value = state.models.mdx_stems
        field_name = "mdx_stems"
    elif process_method == "Demucs":
        current_value = state.models.demucs_stems
        field_name = "demucs_stems"
    else:
        return state
    if not available_targets or current_value in available_targets:
        return state
    return replace(state, models=replace(state.models, **{field_name: available_targets[0]}))


def normalize_common_workflow_state(state: AppState) -> AppState:
    extra = dict(state.extra_settings)
    process_method = state.processing.process_method
    demucs_stem = state.models.demucs_stems

    if process_method != "Demucs":
        extra["is_demucs_pre_proc_model_activate"] = False
        extra["is_demucs_pre_proc_model_inst_mix"] = False

    if demucs_stem in {VOCAL_STEM, INST_STEM}:
        extra["is_demucs_pre_proc_model_activate"] = False
        extra["is_demucs_pre_proc_model_inst_mix"] = False

    if not extra.get("is_set_vocal_splitter", False):
        extra["is_save_inst_set_vocal_splitter"] = False

    return replace(state, extra_settings=extra)


def workflow_validation_issue(state: AppState) -> str | None:
    def flag(key: str) -> bool:
        return bool(state.extra_settings.get(key, False))

    if flag("is_demucs_pre_proc_model_activate"):
        if state.processing.process_method != "Demucs":
            return "Demucs pre-proc is only available for Demucs workflows."
        if state.models.demucs_stems in {VOCAL_STEM, INST_STEM}:
            return "Demucs pre-proc requires All Stems or a non-vocal Demucs stem target."
        if state.models.demucs_pre_proc_model == NO_MODEL:
            return "Select an installed pre-proc model before starting."

    if flag("is_demucs_pre_proc_model_inst_mix") and not flag("is_demucs_pre_proc_model_activate"):
        return "Save Instrumental Mixture requires Demucs pre-proc to be enabled."

    if flag("is_set_vocal_splitter") and state.models.vocal_splitter_model == NO_MODEL:
        return "Select an installed vocal splitter model before starting."

    if flag("is_save_inst_set_vocal_splitter") and not flag("is_set_vocal_splitter"):
        return "Save Split Instrumentals requires the vocal splitter workflow to be enabled."

    return None


def secondary_prefix(process_method: str) -> str | None:
    if process_method == "VR Architecture":
        return "vr"
    if process_method == "MDX-Net":
        return "mdx"
    if process_method == "Demucs":
        return "demucs"
    return None


def secondary_activation_key(process_method: str) -> str | None:
    prefix = secondary_prefix(process_method)
    return f"{prefix}_is_secondary_model_activate" if prefix else None


def secondary_model_key(slot: str, process_method: str) -> str | None:
    prefix = secondary_prefix(process_method)
    return f"{prefix}_{slot}_secondary_model" if prefix else None


def selected_model_name(state: AppState) -> str:
    return selected_model_name_for_method(state, state.processing.process_method)


def selected_model_name_for_method(state: AppState, process_method: str) -> str:
    if process_method == "VR Architecture":
        return state.models.vr_model
    if process_method == "MDX-Net":
        return state.models.mdx_net_model
    if process_method == "Demucs":
        return state.models.demucs_model
    return ""


def state_with_selected_model(state: AppState, process_method: str, model_name: str) -> AppState:
    if process_method == "VR Architecture":
        return replace(state, models=replace(state.models, vr_model=model_name))
    if process_method == "MDX-Net":
        return replace(state, models=replace(state.models, mdx_net_model=model_name))
    if process_method == "Demucs":
        return replace(state, models=replace(state.models, demucs_model=model_name))
    return state
