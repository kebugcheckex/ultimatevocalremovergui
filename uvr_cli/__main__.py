"""UVR CLI entrypoint.

Thin wrapper around :class:`uvr_core.jobs.SeparationJob`.
Builds a framework-neutral request from CLI flags (seeded with persisted
defaults when ``data.pkl`` is present) and runs a single-model separation pass
over one or more input files.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import traceback

import click

from gui_data.constants import DEFAULT_DATA
from gui_data.constants import (
    DEMUCS_ARCH_TYPE,
    FLAC,
    MDX_ARCH_TYPE,
    MP3,
    VR_ARCH_PM,
    WAV,
)
from uvr.config.models import AppSettings
from uvr.config.persistence import load_settings
from uvr_core.events import LogEvent, ProgressEvent, StatusEvent
from uvr_core.jobs import SeparationJob
from uvr_core.requests import SeparationRequest


METHOD_CHOICES = {
    "vr": VR_ARCH_PM,
    "mdx": MDX_ARCH_TYPE,
    "demucs": DEMUCS_ARCH_TYPE,
}
FORMAT_CHOICES = {"wav": WAV, "flac": FLAC, "mp3": MP3}


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


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Ultimate Vocal Remover command-line interface."""


@cli.command("list-methods")
def list_methods() -> None:
    """List processing methods backed by locally installed models."""
    job = SeparationJob()
    methods = job.available_process_methods()
    if not methods:
        print("No local models found. Install models under ./models/.")
        sys.exit(1)
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
def list_models(method_key: str) -> None:
    """List local models for a given --method."""
    job = SeparationJob()
    method = METHOD_CHOICES[method_key]
    names = job.available_models_for_method(method)
    if not names:
        print(f"No local {method_key} models found.")
        sys.exit(1)
    for name in names:
        print(name)


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
    default="data.pkl",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Persisted settings file used for defaults. Missing files are ignored.",
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
        progress_reporter = _make_progress_reporter()

        def subscriber(event: LogEvent | ProgressEvent | StatusEvent) -> None:
            if isinstance(event, LogEvent):
                _log(event.message)
            elif isinstance(event, ProgressEvent):
                progress_reporter(event.percent)
            elif isinstance(event, StatusEvent):
                _status(event.message)

        result = job.run(state, subscriber=subscriber)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print(f"Wrote {len(result.processed_files)} file(s) to {result.output_path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
