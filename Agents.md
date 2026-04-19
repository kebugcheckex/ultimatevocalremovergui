# Agent Notes

## Purpose

This repository is a desktop audio source-separation application built around a Tkinter GUI. It combines:

- a large GUI/controller entry point in `UVR.py`
- model execution pipelines in `separate.py`
- bundled model/inference implementations in `lib_v5/` and `demucs/`
- bundled assets, settings, and helper modules under `gui_data/`

The application is not structured as a reusable package. It is an app-first codebase with substantial logic concentrated in a few large files.

## Top-Level Structure

- `UVR.py`
  - Main application entry point.
  - Owns GUI construction, persisted settings, model discovery, download/update logic, process orchestration, and app startup/shutdown.
  - Defines the global `root = MainWindow()` in `__main__`.
- `separate.py`
  - Runtime separation engine.
  - Contains shared separation state plus architecture-specific executors:
    - `SeperateVR`
    - `SeperateMDX`
    - `SeperateMDXC`
    - `SeperateDemucs`
- `lib_v5/`
  - UVR-specific signal-processing and model support code.
  - `spec_utils.py` is the main audio utility layer.
  - `vr_network/` contains VR model definitions and params.
  - `mdxnet.py`, `tfc_tdf_v3.py`, `modules.py`, `results.py` support MDX/MDX-C execution.
- `demucs/`
  - Bundled Demucs codebase used directly by the app.
  - `apply.py` is the main Demucs inference/chunking entry.
- `gui_data/`
  - GUI constants, sizing, themes, DnD support, images, fonts, audio cues, saved settings/ensembles placeholders, and error helpers.
- `models/`
  - Local model store and metadata:
    - `VR_Models/`
    - `MDX_Net_Models/`
    - `Demucs_Models/`
- `README.md`
  - End-user install/run instructions.
- `requirements.txt`
  - Runtime dependencies; no separate dev/test dependency set.

## Runtime Architecture

### 1. Startup

Application startup is in `UVR.py`.

- Resolves `BASE_PATH` and `chdir`s into it.
- Loads persisted app data from `data.pkl`, falling back to `DEFAULT_DATA` from `gui_data/constants.py`.
- Creates `MainWindow`, which:
  - builds the Tkinter UI
  - loads model hash/name metadata from JSON
  - scans model directories
  - starts a periodic `update_loop()`
  - starts online refresh/update checks

The GUI class is both view and controller. There is no separate application/service layer.

### 2. User Configuration -> `ModelData`

`ModelData` in `UVR.py` is the central configuration object for a single selected model run.

It reads directly from Tkinter variables on the global `root` object and computes:

- chosen architecture (`VR`, `MDX-Net`, `Demucs`, or ensemble-expanded variants)
- model path and hash
- stem mappings
- secondary model selections
- Demucs pre-proc model
- vocal split model
- device flags
- inference settings such as segment size, overlap, denoise, save format, etc.

This means model configuration is tightly coupled to live GUI state.

### 3. Process Orchestration

Main processing begins in `MainWindow.process_initialize()` and dispatches into:

- `process_start()` for separation
- `process_tool_start()` for non-separation audio tools

Processing runs on `KThread`, not the Tkinter main thread.

For each input file:

1. GUI validates input/output and storage.
2. `assemble_model_data()` creates one or more `ModelData` objects.
3. `process_start()` builds a `process_data` dict with callbacks and run context.
4. The code instantiates one separator class from `separate.py`.
5. The separator writes outputs directly to disk and reports progress back via callbacks.
6. Ensemble mode optionally post-processes outputs with `Ensembler`.

### 4. Separation Layer

`separate.py` uses `SeperateAttributes` as a shared base state object.

Each separator implementation:

- reads model settings from `ModelData`
- receives callbacks from `process_data`
- performs inference
- optionally invokes secondary models
- optionally invokes vocal split chaining
- writes stems to disk

Architecture-specific responsibilities:

- `SeperateVR`
  - spectrogram-based VR pipeline using `lib_v5.vr_network`
- `SeperateMDX`
  - ONNX or checkpoint-based MDX-Net pipeline
- `SeperateMDXC`
  - YAML/config-driven MDX-C multi-stem pipeline using `TFC_TDF_net`
- `SeperateDemucs`
  - Demucs v1/v2/v3/v4 execution, plus multi-stem handling and pre-proc chaining

### 5. Audio Utility Layer

`lib_v5/spec_utils.py` is the main shared DSP/helper module. It handles things like:

- spectrogram conversion
- inversion and recombination
- ensemble averaging
- alignment/matching helpers
- audio normalization
- save/export helpers used by higher layers

This file is effectively an internal utility library for most nontrivial audio math in the app.

## Main Functional Areas

### Separation

Primary separation paths are selected by process method:

- `VR Architecture`
- `MDX-Net`
- `Demucs`
- `Ensemble Mode`

Ensemble mode is orchestrated in `UVR.py` and combines outputs after multiple per-model runs.

### Audio Tools

`AudioTools` and `Ensembler` in `UVR.py` implement non-model features:

- manual ensemble
- align inputs
- matchering-based matching
- time stretch
- pitch shift
- file combination

### Model Discovery and Updates

`MainWindow.update_available_models()` scans local model folders repeatedly.

Online update/download logic in `UVR.py`:

- refreshes remote metadata
- updates local JSON metadata caches
- downloads models and app patches

This logic is mixed into the GUI controller rather than isolated in a service module.

### Persistence

Persistence is file-based:

- `data.pkl` for current app state
- `gui_data/saved_settings/*.json` for named settings presets
- `gui_data/saved_ensembles/*.json` for named ensemble presets

There is no database or formal config schema layer.

## Important Coupling and Design Characteristics

### Global `root` Dependency

A large amount of code depends on the module-level global `root`.

Examples:

- `ModelData` reads current UI variables directly from `root`
- many helper methods assume a live GUI instance
- separator configuration is shaped by callbacks originating from `root`

This makes reuse, testing, and headless execution difficult.

### Large Monolithic GUI File

`UVR.py` is the dominant controller and contains:

- app bootstrap
- config/state defaults
- widget creation
- widget state transitions
- download/update workflows
- process orchestration
- settings persistence
- popup/menu logic
- utility actions

This file is the main architectural hotspot.

### Callback Dictionary Instead of Typed Interface

`process_start()` passes a `process_data` dict into separator classes. That dict contains:

- progress callbacks
- console callbacks
- cached-source callbacks
- file/export metadata
- ensemble flags

This is flexible, but weakly typed and easy to break when keys change.

### Bundled Third-Party Model Code

The repo vendors Demucs code under `demucs/` and custom/support code under `lib_v5/`. Changes in inference behavior may require careful coordination across:

- GUI option semantics
- `ModelData`
- separator classes
- `spec_utils.py`
- local model metadata JSON

## Notable Findings

- There are no obvious automated tests in the repository.
- There is no package layout, CLI layer, or API boundary separate from the GUI.
- The codebase assumes local writable state and writes outputs/settings directly into the repo/app directory structure.
- Model metadata is partly local and partly remote-updated.
- Threading is used extensively for processing and download flows, while UI state remains centralized in Tkinter.
- Caching exists for repeated model usage within a run, but it is managed via shared callback/state plumbing rather than a dedicated cache object.
- The project bundles many binary/model assets directly in-tree, so repository size and startup assumptions are asset-driven.

## Practical Navigation Guide

If you need to modify behavior, these are the highest-value entry points:

- `UVR.py`
  - startup, UI, settings, orchestration, downloads, ensemble logic
- `separate.py`
  - per-architecture inference flow and output writing
- `lib_v5/spec_utils.py`
  - shared DSP/audio transforms
- `gui_data/constants.py`
  - app-wide constants and defaults
- `models/*/model_data/*.json`
  - model metadata and name mapping

## Suggested Refactor Boundaries

If this codebase is going to be extended, the cleanest future seams are:

1. Extract `ModelData` creation away from direct `root` access.
2. Replace `process_data` dict passing with a typed runtime context object.
3. Split `UVR.py` into:
   - app bootstrap
   - GUI widgets/views
   - processing controller
   - download/update service
   - persistence service
4. Isolate filesystem and network side effects behind dedicated helpers.
5. Add a headless processing entry point that can run without Tkinter.

## Current State Summary

This is a mature but highly centralized desktop application. The main architecture is:

- Tkinter GUI/controller in `UVR.py`
- per-model execution engines in `separate.py`
- DSP/model helpers in `lib_v5/`
- vendored Demucs runtime in `demucs/`
- local asset/config/model stores in `gui_data/` and `models/`

The main strengths are broad functionality and directness. The main maintenance risks are monolithic control flow, global GUI coupling, weakly typed runtime context passing, and the absence of obvious automated tests.
