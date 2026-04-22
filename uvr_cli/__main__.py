"""UVR CLI entrypoint.

Thin wrapper around :class:`uvr_core.jobs.SeparationJob` and
:class:`uvr_core.jobs.DownloadJob`. Builds framework-neutral requests from CLI
flags (seeded with persisted defaults when ``config.yaml`` is present) and runs
backend jobs without importing UI adapters.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import traceback
from pathlib import Path

import click

from gui_data.constants import DEFAULT_DATA
from gui_data.constants import (
    ALIGN_INPUTS,
    ALIGN_PHASE_OPTIONS,
    AUTO_PHASE,
    CHANGE_PITCH,
    DEMUCS_ARCH_TYPE,
    FLAC,
    INTRO_MAPPER,
    MANUAL_ENSEMBLE_OPTIONS,
    MATCH_INPUTS,
    MDX_ARCH_TYPE,
    MP3,
    PHASE_SHIFTS_OPT,
    TIME_STRETCH,
    TIME_WINDOW_MAPPER,
    VOLUME_MAPPER,
    VR_ARCH_PM,
    WAV,
)
from uvr.config.models import AppSettings
from uvr.config.persistence import load_settings, save_settings
from uvr_core.events import AudioToolResultEvent, DownloadResultEvent, EnsembleResultEvent, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import AudioToolJob, DownloadJob, EnsembleJob, SeparationJob
from uvr_core.requests import AudioToolRequest, DownloadRequest, EnsembleRequest, SeparationRequest


METHOD_CHOICES = {
    "vr": VR_ARCH_PM,
    "mdx": MDX_ARCH_TYPE,
    "demucs": DEMUCS_ARCH_TYPE,
}
FORMAT_CHOICES = {"wav": WAV, "flac": FLAC, "mp3": MP3}
DOWNLOAD_TYPE_CHOICES = {
    "vr": VR_ARCH_PM,
    "mdx": MDX_ARCH_TYPE,
    "demucs": DEMUCS_ARCH_TYPE,
}
ENSEMBLE_ALGORITHM_CHOICES = tuple(sorted(MANUAL_ENSEMBLE_OPTIONS))


def _build_state(
    base: SeparationRequest,
    *,
    inputs: tuple[str, ...],
    output: str,
    method: str | None,
    model: str | None,
    save_format: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    use_gpu: bool | None,
    primary_only: bool,
    secondary_only: bool,
    normalize: bool | None,
    add_model_name: bool | None,
    create_model_folder: bool | None,
) -> SeparationRequest:
    models = base.models
    if model is not None and method is not None:
        if method == VR_ARCH_PM:
            models = dataclasses.replace(models, vr_model=model)
        elif method == MDX_ARCH_TYPE:
            models = dataclasses.replace(models, mdx_net_model=model)
        elif method == DEMUCS_ARCH_TYPE:
            models = dataclasses.replace(models, demucs_model=model)

    output_settings = base.output
    output_updates: dict[str, object] = {}
    if save_format is not None:
        output_updates["save_format"] = save_format
    if mp3_bitrate is not None:
        output_updates["mp3_bitrate"] = mp3_bitrate
    if wav_type is not None:
        output_updates["wav_type"] = wav_type
    if add_model_name is not None:
        output_updates["add_model_name"] = add_model_name
    if create_model_folder is not None:
        output_updates["create_model_folder"] = create_model_folder
    if output_updates:
        output_settings = dataclasses.replace(output_settings, **output_updates)

    processing = base.options
    processing_updates: dict[str, object] = {
        "primary_stem_only": primary_only,
        "secondary_stem_only": secondary_only,
    }
    if method is not None:
        processing_updates["process_method"] = method
    if use_gpu is not None:
        processing_updates["use_gpu"] = use_gpu
    if normalize is not None:
        processing_updates["normalize_output"] = normalize
    processing = dataclasses.replace(processing, **processing_updates)

    return dataclasses.replace(
        base,
        input_paths=inputs,
        export_path=output,
        models=models,
        output=output_settings,
        options=processing,
    )


def _log(message: str) -> None:
    print(message, flush=True)


def _status(message: str) -> None:
    print(f"[status] {message}", flush=True)


def _emit_json(payload: object) -> None:
    print(json.dumps(payload), flush=True)


def _make_progress_reporter():
    last = {"value": -1}

    def report(value: float) -> None:
        pct = int(max(0.0, min(100.0, value)))
        if pct != last["value"]:
            last["value"] = pct
            print(f"\r[progress] {pct:3d}%", end="", flush=True)
            if pct >= 100:
                print("", flush=True)

    return report


def _load_defaults(data_file: str) -> SeparationRequest:
    try:
        settings = load_settings(default_data=DEFAULT_DATA, data_file=data_file)
    except Exception:
        settings = AppSettings.from_legacy_dict(DEFAULT_DATA, DEFAULT_DATA)
    return SeparationRequest.from_settings(settings)


def _load_app_settings(data_file: str) -> AppSettings:
    try:
        return load_settings(default_data=DEFAULT_DATA, data_file=data_file)
    except Exception:
        return AppSettings.from_legacy_dict(DEFAULT_DATA, DEFAULT_DATA)


def _defaulted(value, fallback):
    return fallback if value is None else value


def _build_audio_tool_request(
    *,
    data_file: str,
    audio_tool: str,
    inputs: tuple[str, ...],
    output: str,
    save_format: str | None = None,
    wav_type: str | None = None,
    mp3_bitrate: str | None = None,
    normalize: bool | None = None,
    align_window: str | None = None,
    align_intro: str | None = None,
    db_analysis: str | None = None,
    save_aligned: bool | None = None,
    match_silence: bool | None = None,
    spec_match: bool | None = None,
    phase_option: str | None = None,
    phase_shifts: str | None = None,
    rate: str | None = None,
    time_correction: bool | None = None,
) -> AudioToolRequest:
    settings = _load_app_settings(data_file).to_legacy_dict()

    return AudioToolRequest(
        audio_tool=audio_tool,
        input_paths=inputs,
        export_path=output,
        save_format=_defaulted(save_format, str(settings["save_format"])),
        wav_type=_defaulted(wav_type, str(settings["wav_type_set"])),
        mp3_bitrate=_defaulted(mp3_bitrate, str(settings["mp3_bit_set"])),
        normalize_output=_defaulted(normalize, bool(settings["is_normalization"])),
        testing_audio=bool(settings["is_testing_audio"]),
        align_window=_defaulted(align_window, str(settings["time_window"])),
        align_intro=_defaulted(align_intro, str(settings["intro_analysis"])),
        db_analysis=_defaulted(db_analysis, str(settings["db_analysis"])),
        save_aligned=_defaulted(save_aligned, bool(settings["is_save_align"])),
        match_silence=_defaulted(match_silence, bool(settings["is_match_silence"])),
        spec_match=_defaulted(spec_match, bool(settings["is_spec_match"])),
        phase_option=_defaulted(phase_option, str(settings["phase_option"])),
        phase_shifts=_defaulted(phase_shifts, str(settings["phase_shifts"])),
        time_stretch_rate=_defaulted(rate, str(settings["time_stretch_rate"])),
        pitch_rate=_defaulted(rate, str(settings["pitch_rate"])),
        time_correction=_defaulted(time_correction, bool(settings["is_time_correction"])),
    )


def _print_download_listing(label: str, items: tuple[str, ...]) -> None:
    print(f"{label}:")
    if not items:
        print("  (none)")
        return
    for item in items:
        print(item)


def _make_event_subscriber(progress_mode: str):
    progress_reporter = _make_progress_reporter()

    def subscriber(
        event: LogEvent
        | ProgressEvent
        | StatusEvent
        | ResultEvent
        | DownloadResultEvent
        | EnsembleResultEvent
        | AudioToolResultEvent
    ) -> None:
        if progress_mode == "json":
            _emit_json(event.to_dict())
            return

        if isinstance(event, LogEvent):
            _log(event.message)
        elif isinstance(event, ProgressEvent):
            progress_reporter(event.percent)
        elif isinstance(event, StatusEvent):
            _status(event.message)

    return subscriber


def _coerce_setting_value(key: str, raw_value: str):
    if key not in DEFAULT_DATA:
        raise KeyError(key)

    exemplar = DEFAULT_DATA[key]
    exemplar_type = type(exemplar)

    if exemplar is None:
        if raw_value == "null":
            return None
        return raw_value

    if exemplar_type is bool:
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Expected a boolean value for {key!r}.")

    if exemplar_type is int and not isinstance(exemplar, bool):
        return int(raw_value)

    if exemplar_type is float:
        return float(raw_value)

    if exemplar_type in {list, tuple, dict}:
        parsed = json.loads(raw_value)
        if exemplar_type is tuple:
            if not isinstance(parsed, list):
                raise ValueError(f"Expected a JSON array for {key!r}.")
            return tuple(parsed)
        if not isinstance(parsed, exemplar_type):
            expected_name = "array" if exemplar_type is list else "object"
            raise ValueError(f"Expected a JSON {expected_name} for {key!r}.")
        return parsed

    return raw_value


def _run_audio_tool_command(request: AudioToolRequest, progress_mode: str) -> None:
    job = AudioToolJob()

    try:
        result = job.run(request, subscriber=_make_event_subscriber(progress_mode))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    if progress_mode == "json":
        return

    print(f"{request.audio_tool} completed.")
    for path in result.output_paths:
        print(path)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Ultimate Vocal Remover command-line interface."""


@cli.group("config")
def config_group() -> None:
    """Inspect or update persisted settings."""


@config_group.command("show")
@click.argument("key", required=False)
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file to read.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def config_show(key: str | None, data_file: str, as_json: bool) -> None:
    """Show one persisted setting or the full settings object."""
    settings = _load_app_settings(data_file)
    values = settings.to_legacy_dict()

    if key is not None:
        if key not in DEFAULT_DATA:
            print(f"Error: unknown config key {key!r}.", file=sys.stderr)
            sys.exit(2)
        payload = {key: values.get(key)}
    else:
        payload = values

    if as_json:
        _emit_json(payload)
        return

    if key is not None:
        print(payload[key])
        return

    for current_key in sorted(payload):
        print(f"{current_key}={payload[current_key]!r}")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file to update.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def config_set(key: str, value: str, data_file: str, as_json: bool) -> None:
    """Set one persisted setting by key."""
    if key not in DEFAULT_DATA:
        print(f"Error: unknown config key {key!r}.", file=sys.stderr)
        sys.exit(2)

    try:
        coerced_value = _coerce_setting_value(key, value)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    settings = _load_app_settings(data_file)
    updated_values = settings.to_legacy_dict()
    updated_values[key] = coerced_value
    updated_settings = AppSettings.from_legacy_dict(updated_values, DEFAULT_DATA)
    save_settings(updated_settings, data_file=Path(data_file))

    if as_json:
        _emit_json({key: updated_settings.to_legacy_dict()[key]})
        return

    print(f"{key}={updated_settings.to_legacy_dict()[key]!r}")


@cli.command("list-methods")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def list_methods(as_json: bool) -> None:
    """List processing methods backed by locally installed models."""
    job = SeparationJob()
    methods = job.available_process_methods()
    if not methods:
        print("No local models found. Install models under ./models/.")
        sys.exit(1)
    if as_json:
        _emit_json({"methods": list(methods)})
        return
    for method in methods:
        print(method)


@cli.command("list-models")
@click.option(
    "--method",
    "method_key",
    type=click.Choice(sorted(METHOD_CHOICES)),
    required=True,
    help="Backend family to enumerate.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def list_models(method_key: str, as_json: bool) -> None:
    """List local models for a given --method."""
    job = SeparationJob()
    method = METHOD_CHOICES[method_key]
    names = job.available_models_for_method(method)
    if not names:
        print(f"No local {method_key} models found.")
        sys.exit(1)
    if as_json:
        _emit_json({"method": method_key, "models": list(names)})
        return
    for name in names:
        print(name)


@cli.command("list-downloads")
@click.option(
    "--type",
    "download_type_key",
    type=click.Choice(sorted(DOWNLOAD_TYPE_CHOICES)),
    default=None,
    help="Limit output to one downloadable model family.",
)
@click.option(
    "--vip-code",
    default="",
    hide_input=True,
    help="Optional VIP code used to unlock VIP download listings.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def list_downloads(download_type_key: str | None, vip_code: str, as_json: bool) -> None:
    """List downloadable models available from the online catalog."""
    job = DownloadJob()

    try:
        available = job.available_downloads(vip_code=vip_code)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    download_sections = (
        ("vr", "VR", available.vr_items),
        ("mdx", "MDX", available.mdx_items),
        ("demucs", "Demucs", available.demucs_items),
    )

    selected = [section for section in download_sections if download_type_key in (None, section[0])]
    if as_json:
        _emit_json(
            {
                "bulletin": available.bulletin,
                "downloads": {key: list(items) for key, _, items in selected},
            }
        )
        return
    if available.bulletin:
        print(f"Bulletin: {available.bulletin}")
    if all(not section[2] for section in selected):
        print("No downloadable models are currently available.")
        sys.exit(0)

    for _, label, items in selected:
        _print_download_listing(label, items)


@cli.command("refresh-catalog")
@click.option(
    "--vip-code",
    default="",
    hide_input=True,
    help="Optional VIP code used to unlock VIP download listings.",
)
@click.option(
    "--refresh-model-settings/--no-refresh-model-settings",
    default=True,
    help="Refresh local model metadata JSON files as part of the catalog refresh.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def refresh_catalog(vip_code: str, refresh_model_settings: bool, as_json: bool) -> None:
    """Refresh the online download catalog and local model metadata."""
    job = DownloadJob()

    try:
        result = job.refresh_catalog(
            vip_code=vip_code,
            refresh_model_settings=refresh_model_settings,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    available = result.available_downloads
    if as_json:
        _emit_json(
            {
                "bulletin": available.bulletin,
                "vr_downloads_available": len(available.vr_items),
                "mdx_downloads_available": len(available.mdx_items),
                "demucs_downloads_available": len(available.demucs_items),
                "model_settings_refreshed": result.refreshed_settings is not None,
            }
        )
        return
    print("Catalog refreshed.")
    print(f"VR downloads available: {len(available.vr_items)}")
    print(f"MDX downloads available: {len(available.mdx_items)}")
    print(f"Demucs downloads available: {len(available.demucs_items)}")
    print(f"Model settings refreshed: {'yes' if result.refreshed_settings is not None else 'no'}")


@cli.command("download")
@click.option(
    "--type",
    "download_type_key",
    type=click.Choice(sorted(DOWNLOAD_TYPE_CHOICES)),
    required=True,
    help="Downloadable model family.",
)
@click.option(
    "--model",
    "selection",
    required=True,
    help="Downloadable model name. Use list-downloads to inspect valid values.",
)
@click.option(
    "--vip-code",
    default="",
    hide_input=True,
    help="Optional VIP code used to unlock VIP downloads.",
)
@click.option(
    "--refresh-model-settings/--no-refresh-model-settings",
    default=True,
    help="Refresh local model metadata JSON files after download.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def download_model(download_type_key: str, selection: str, vip_code: str, refresh_model_settings: bool, progress_mode: str) -> None:
    """Download one model selection from the online catalog."""
    job = DownloadJob()
    subscriber = _make_event_subscriber(progress_mode)

    try:
        result = job.run(
            DownloadRequest(
                model_type=DOWNLOAD_TYPE_CHOICES[download_type_key],
                selection=selection,
                vip_code=vip_code,
                refresh_model_settings=refresh_model_settings,
            ),
            subscriber=subscriber,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except KeyError:
        print(
            f"Error: downloadable model {selection!r} was not found for type {download_type_key!r}.",
            file=sys.stderr,
        )
        print("Run `uvr-cli list-downloads --type <vr|mdx|demucs>` to see available choices.", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    if progress_mode == "json":
        return

    print(f"Downloaded {len(result.completed_files)} file(s).")
    if result.skipped_existing:
        print(f"Skipped existing {len(result.skipped_existing)} file(s).")
    for path in result.completed_files:
        print(path)


@cli.command("ensemble")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option(
    "--algorithm",
    type=click.Choice(ENSEMBLE_ALGORITHM_CHOICES),
    default="Average",
    show_default=True,
    help="Manual ensemble algorithm.",
)
@click.option("--output-name", default="Ensembled", show_default=True, help="Base filename for the ensembled output.")
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default="wav",
    show_default=True,
    help="Output file format.",
)
@click.option("--mp3-bitrate", default="320k", show_default=True, help="MP3 bitrate when --format=mp3.")
@click.option(
    "--wav-type",
    default="PCM_16",
    show_default=True,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding.",
)
@click.option("--normalize/--no-normalize", default=False, help="Normalize ensemble output loudness.")
@click.option("--wav-ensemble/--spectral-ensemble", "wav_ensemble", default=False, help="Use waveform combination instead of spectrogram combination.")
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def ensemble(
    inputs: tuple[str, ...],
    output: str,
    algorithm: str,
    output_name: str,
    save_format_key: str,
    mp3_bitrate: str,
    wav_type: str,
    normalize: bool,
    wav_ensemble: bool,
    progress_mode: str,
) -> None:
    """Combine multiple existing audio inputs into one ensembled output."""
    if len(inputs) < 2:
        raise click.UsageError("ensemble requires at least two input files.")

    job = EnsembleJob()
    save_format = FORMAT_CHOICES[save_format_key]

    try:
        result = job.run(
            EnsembleRequest(
                input_paths=inputs,
                export_path=output,
                algorithm=algorithm,
                output_name=output_name,
                save_format=save_format,
                wav_type=wav_type,
                mp3_bitrate=mp3_bitrate,
                normalize_output=normalize,
                wav_ensemble=wav_ensemble,
            ),
            subscriber=_make_event_subscriber(progress_mode),
        )
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    if progress_mode == "json":
        return

    print(f"Ensembled {len(inputs)} input file(s).")
    print(result.output_path)


@cli.group("audio-tool")
def audio_tool_group() -> None:
    """Run one of the framework-neutral audio tools."""


@audio_tool_group.command("time-stretch")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option("--rate", type=str, default=None, help="Stretch rate. Defaults to the persisted setting.")
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default=None,
    help="Output file format. Defaults to the persisted setting.",
)
@click.option("--mp3-bitrate", default=None, help="MP3 bitrate when --format=mp3.")
@click.option(
    "--wav-type",
    default=None,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding. Defaults to the persisted setting.",
)
@click.option("--normalize/--no-normalize", default=None, help="Normalize output loudness.")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def audio_tool_time_stretch(
    inputs: tuple[str, ...],
    output: str,
    rate: str | None,
    save_format_key: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    normalize: bool | None,
    data_file: str,
    progress_mode: str,
) -> None:
    """Stretch one or more audio files in time."""
    request = _build_audio_tool_request(
        data_file=data_file,
        audio_tool=TIME_STRETCH,
        inputs=inputs,
        output=output,
        save_format=FORMAT_CHOICES[save_format_key] if save_format_key else None,
        wav_type=wav_type,
        mp3_bitrate=mp3_bitrate,
        normalize=normalize,
        rate=rate,
    )
    _run_audio_tool_command(request, progress_mode)


@audio_tool_group.command("pitch")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option("--rate", type=str, default=None, help="Pitch shift amount. Defaults to the persisted setting.")
@click.option("--time-correction/--no-time-correction", default=None, help="Preserve the input BPM after pitch shifting.")
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default=None,
    help="Output file format. Defaults to the persisted setting.",
)
@click.option("--mp3-bitrate", default=None, help="MP3 bitrate when --format=mp3.")
@click.option(
    "--wav-type",
    default=None,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding. Defaults to the persisted setting.",
)
@click.option("--normalize/--no-normalize", default=None, help="Normalize output loudness.")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def audio_tool_pitch(
    inputs: tuple[str, ...],
    output: str,
    rate: str | None,
    time_correction: bool | None,
    save_format_key: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    normalize: bool | None,
    data_file: str,
    progress_mode: str,
) -> None:
    """Pitch-shift one or more audio files."""
    request = _build_audio_tool_request(
        data_file=data_file,
        audio_tool=CHANGE_PITCH,
        inputs=inputs,
        output=output,
        save_format=FORMAT_CHOICES[save_format_key] if save_format_key else None,
        wav_type=wav_type,
        mp3_bitrate=mp3_bitrate,
        normalize=normalize,
        rate=rate,
        time_correction=time_correction,
    )
    _run_audio_tool_command(request, progress_mode)


@audio_tool_group.command("align")
@click.argument("input_a", type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True))
@click.argument("input_b", type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True))
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option("--time-window", type=click.Choice(tuple(TIME_WINDOW_MAPPER.keys())), default=None, help="Alignment time window preset.")
@click.option("--intro-analysis", type=click.Choice(tuple(INTRO_MAPPER.keys())), default=None, help="Intro analysis preset.")
@click.option("--db-analysis", type=click.Choice(tuple(VOLUME_MAPPER.keys())), default=None, help="Gain search preset.")
@click.option("--save-aligned/--no-save-aligned", default=None, help="Keep the aligned reference output.")
@click.option("--match-silence/--no-match-silence", default=None, help="Match leading silence before alignment.")
@click.option("--spec-match/--no-spec-match", default=None, help="Use spectral matching for the final aligned output.")
@click.option("--phase-option", type=click.Choice(tuple(ALIGN_PHASE_OPTIONS)), default=None, help="Phase handling mode.")
@click.option("--phase-shifts", type=click.Choice(tuple(PHASE_SHIFTS_OPT.keys())), default=None, help="Phase shift search preset.")
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default=None,
    help="Output file format. Defaults to the persisted setting.",
)
@click.option("--mp3-bitrate", default=None, help="MP3 bitrate when --format=mp3.")
@click.option(
    "--wav-type",
    default=None,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding. Defaults to the persisted setting.",
)
@click.option("--normalize/--no-normalize", default=None, help="Normalize output loudness.")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def audio_tool_align(
    input_a: str,
    input_b: str,
    output: str,
    time_window: str | None,
    intro_analysis: str | None,
    db_analysis: str | None,
    save_aligned: bool | None,
    match_silence: bool | None,
    spec_match: bool | None,
    phase_option: str | None,
    phase_shifts: str | None,
    save_format_key: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    normalize: bool | None,
    data_file: str,
    progress_mode: str,
) -> None:
    """Align two related inputs and output an inverted residual."""
    request = _build_audio_tool_request(
        data_file=data_file,
        audio_tool=ALIGN_INPUTS,
        inputs=(input_a, input_b),
        output=output,
        save_format=FORMAT_CHOICES[save_format_key] if save_format_key else None,
        wav_type=wav_type,
        mp3_bitrate=mp3_bitrate,
        normalize=normalize,
        align_window=time_window,
        align_intro=intro_analysis,
        db_analysis=db_analysis,
        save_aligned=save_aligned,
        match_silence=match_silence,
        spec_match=spec_match,
        phase_option=phase_option,
        phase_shifts=phase_shifts,
    )
    _run_audio_tool_command(request, progress_mode)


@audio_tool_group.command("match")
@click.argument("target", type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True))
@click.argument("reference", type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True))
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default=None,
    help="Output file format. Defaults to the persisted setting.",
)
@click.option("--mp3-bitrate", default=None, help="MP3 bitrate when --format=mp3.")
@click.option(
    "--wav-type",
    default=None,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding. Defaults to the persisted setting.",
)
@click.option("--normalize/--no-normalize", default=None, help="Normalize output loudness.")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def audio_tool_match(
    target: str,
    reference: str,
    output: str,
    save_format_key: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    normalize: bool | None,
    data_file: str,
    progress_mode: str,
) -> None:
    """Match one input against a reference using Matchering."""
    request = _build_audio_tool_request(
        data_file=data_file,
        audio_tool=MATCH_INPUTS,
        inputs=(target, reference),
        output=output,
        save_format=FORMAT_CHOICES[save_format_key] if save_format_key else None,
        wav_type=wav_type,
        mp3_bitrate=mp3_bitrate,
        normalize=normalize,
        phase_option=AUTO_PHASE,
    )
    _run_audio_tool_command(request, progress_mode)


@cli.command("separate")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Export directory. Created if missing.",
)
@click.option(
    "-m",
    "--method",
    "method_key",
    type=click.Choice(sorted(METHOD_CHOICES)),
    default=None,
    help="Backend family. Defaults to persisted setting, else auto-picked from available models.",
)
@click.option(
    "--model",
    default=None,
    help="Model name. Must match list-models output for the chosen method.",
)
@click.option(
    "-f",
    "--format",
    "save_format_key",
    type=click.Choice(sorted(FORMAT_CHOICES)),
    default=None,
    help="Output file format.",
)
@click.option("--mp3-bitrate", default=None, help="MP3 bitrate (e.g. 320k). Only used when --format=mp3.")
@click.option(
    "--wav-type",
    default=None,
    type=click.Choice(["PCM_16", "PCM_24", "PCM_32", "32-bit Float", "64-bit Float"]),
    help="WAV sample encoding.",
)
@click.option("--gpu/--cpu", "use_gpu", default=None, help="Force GPU or CPU. Defaults to persisted setting.")
@click.option("--primary-only", is_flag=True, help="Write only the primary stem.")
@click.option("--secondary-only", is_flag=True, help="Write only the secondary stem.")
@click.option("--normalize/--no-normalize", default=None, help="Normalize output loudness.")
@click.option("--add-model-name/--no-add-model-name", default=None, help="Append model name to filenames.")
@click.option("--model-folder/--no-model-folder", "create_model_folder", default=None, help="Group outputs in per-model subdirectories.")
@click.option(
    "--data-file",
    default="config.yaml",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
)
@click.option(
    "--progress",
    "progress_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Progress/event output format.",
)
def separate(
    inputs: tuple[str, ...],
    output: str,
    method_key: str | None,
    model: str | None,
    save_format_key: str | None,
    mp3_bitrate: str | None,
    wav_type: str | None,
    use_gpu: bool | None,
    primary_only: bool,
    secondary_only: bool,
    normalize: bool | None,
    add_model_name: bool | None,
    create_model_folder: bool | None,
    data_file: str,
    progress_mode: str,
) -> None:
    """Run separation on one or more audio INPUTS."""
    if primary_only and secondary_only:
        raise click.UsageError("--primary-only and --secondary-only are mutually exclusive.")

    method = METHOD_CHOICES[method_key] if method_key else None
    save_format = FORMAT_CHOICES[save_format_key] if save_format_key else None

    base_state = _load_defaults(data_file)
    os.makedirs(output, exist_ok=True)

    state = _build_state(
        base_state,
        inputs=inputs,
        output=output,
        method=method,
        model=model,
        save_format=save_format,
        mp3_bitrate=mp3_bitrate,
        wav_type=wav_type,
        use_gpu=use_gpu,
        primary_only=primary_only,
        secondary_only=secondary_only,
        normalize=normalize,
        add_model_name=add_model_name,
        create_model_folder=create_model_folder,
    )

    job = SeparationJob()
    resolved = job.resolve_model(state)
    if resolved is None:
        print("Error: no compatible models found under ./models/.", file=sys.stderr)
        sys.exit(2)
    if model and resolved.model_name != model:
        print(
            f"Error: model {model!r} not found for method {resolved.process_method!r}.",
            file=sys.stderr,
        )
        print("Run `uvr-cli list-models --method <vr|mdx|demucs>` to see installed models.", file=sys.stderr)
        sys.exit(2)

    try:
        result = job.run(state, subscriber=_make_event_subscriber(progress_mode))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    if progress_mode == "json":
        return

    print(f"Wrote {len(result.processed_files)} file(s) to {result.output_path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
