# UVR CLI Guide

`uvr_cli` is the command-line interface for Ultimate Vocal Remover's shared backend.

It is intended to run standalone from the Qt rewrite:

- it does not import `uvr_qt`
- it does not require `PySide6`
- it runs directly against `uvr/` and `uvr_core/`

## What It Covers

The CLI covers the mainstream headless workflows from Phase 3:

- single-model separation
- manual ensemble
- audio tools: time stretch, pitch shift, align, and matchering
- download catalog refresh and model downloads
- persisted config inspection and updates
- machine-readable JSON output for listing commands and job progress

Advanced popup-driven Tk workflows are still out of scope.

## Run It

From the repository root:

```bash
python -m uvr_cli --help
```

This repo does not yet ship a dedicated packaging manifest for the CLI, so the supported standalone invocation in Phase 3 is `python -m uvr_cli` from a Python environment with the project's backend dependencies installed.

## Standalone Deployment Notes

For a CLI-only deployment:

1. Create a Python 3.9 environment.
2. Install the backend/runtime dependencies used by this repository.
3. Deploy the repository contents needed by the backend:
   `uvr/`, `uvr_core/`, `uvr_cli/`, `gui_data/`, `lib_v5/`, `demucs/`, `separate.py`, and `models/` as needed.
4. Run the CLI with `python -m uvr_cli ...`.

The CLI does not depend on any Phase 4 Qt code path. If `PySide6` is absent, the CLI still runs.

## Paths And Models

By default, the backend resolves paths relative to the repo root. Two environment variables are supported:

- `UVR_BASE_PATH`: override the backend base directory
- `UVR_MODELS_DIR`: override the models directory

Model discovery expects the usual UVR layout under `models/`, including:

- `models/VR_Models`
- `models/MDX_Net_Models`
- `models/Demucs_Models`

## Common Commands

List installed processing methods:

```bash
python -m uvr_cli list-methods
python -m uvr_cli list-methods --json
```

List installed models:

```bash
python -m uvr_cli list-models --method vr
python -m uvr_cli list-models --method mdx --json
```

Run separation:

```bash
python -m uvr_cli separate song.wav -o out --method vr --model "My VR Model"
python -m uvr_cli separate song.wav -o out --progress json
```

Run manual ensemble:

```bash
python -m uvr_cli ensemble stem_a.wav stem_b.wav -o out --algorithm Average
```

Run audio tools:

```bash
python -m uvr_cli audio-tool time-stretch take.wav -o out --rate 1.15
python -m uvr_cli audio-tool pitch vocal.wav -o out --rate -2 --time-correction
python -m uvr_cli audio-tool align mix.wav instrumental.wav -o out --save-aligned
python -m uvr_cli audio-tool match target.wav reference.wav -o out
```

Refresh the online catalog and download a model:

```bash
python -m uvr_cli refresh-catalog
python -m uvr_cli list-downloads --type vr
python -m uvr_cli download --type vr --model "UVR Model Name"
```

Inspect and update persisted config:

```bash
python -m uvr_cli config show
python -m uvr_cli config show vr_model --json
python -m uvr_cli config set is_gpu_conversion true
```

## JSON Output

Listing commands support `--json`.

Long-running jobs support:

- `--progress text`
- `--progress json`

When `--progress json` is used, each line is a JSON event object from `uvr_core.events`.

## Persistence

The CLI reads legacy persisted settings from `data.pkl` by default and can be pointed at another file with `--data-file` on supported commands.

That compatibility is intentional for Phase 3. The persistence migration away from pickle is Phase 6 work and is not required for CLI use today.

## Limitations

- Cancellation is still best-effort `Ctrl+C`; structured job cancellation is later work.
- The CLI targets mainstream workflows, not every Tk popup or corner-case tool.
- The repo does not yet expose a wheel/sdist packaging flow for the CLI.
