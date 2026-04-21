# PySide6 Testing Plan

## Goal

Define a pragmatic testing strategy for the in-progress `uvr_qt/` frontend without trying to fully test the legacy Tk application.

The current Qt implementation already includes:

- typed app state in `uvr_qt/state/`
- a processing facade in `uvr_qt/services/processing_facade.py`
- a basic `PySide6` main window in `uvr_qt/ui/main_window.py`
- end-to-end processing through the existing backend for a narrow workflow

This plan focuses on testing those pieces directly.

## Principles

1. Prefer testing the new Qt-facing boundary over testing `UVR.py`.
2. Keep most tests at the state and facade layers.
3. Use a small number of real processing smoke tests.
4. Add widget tests only where UI state transitions are important.
5. Avoid making most test runs depend on GPU hardware or full model inference.

## Test Layers

### 1. State Tests

Primary target:

- `uvr_qt/state/app_state.py`

These tests should be fast and deterministic.

What to verify:

- loading persisted settings into `AppState`
- round-tripping `AppState` back to legacy settings format
- preserving expected keys like `chosen_process_method`, `save_format`, and `input_paths`
- updating process/model/output selections without dropping unrelated legacy values

Suggested cases:

- default settings load
- saved settings load from a temp `data.pkl`
- `to_legacy_dict()` emits lists where legacy code expects lists
- output settings and model selections survive a round-trip

### 2. Facade Unit Tests

Primary target:

- `uvr_qt/services/processing_facade.py`

These tests should verify backend selection and settings mapping without requiring a full run each time.

What to verify:

- `available_process_methods()` reflects installed model types
- `available_models_for_method()` is scoped correctly
- `resolve_model()` respects the selected process method and selected model
- generic tuning flags map into `ModelDataSettings` / built model state
- output settings affect naming and folder behavior

Suggested cases:

- resolve VR model when `VR Architecture` is selected
- resolve MDX model when `MDX-Net` is selected
- resolve Demucs model when `Demucs` is selected
- `use_gpu=False` produces CPU-oriented model configuration
- `normalize_output=True` reaches the built model
- `primary_stem_only` and `secondary_stem_only` map correctly
- `add_model_name=True` updates output basename
- `create_model_folder=True` updates output directory layout

Important note:

- Most facade tests should stop before calling real separator inference.
- Real inference should be covered separately by smoke tests.

### 3. Processing Smoke Tests

Primary target:

- narrow end-to-end processing path through `ProcessingFacade.process()`

These tests are slower and should be limited in number.

What to verify:

- one input file can be processed into a temp directory
- expected output stems are created
- processing completes for each supported installed method where practical

Suggested initial smoke cases:

1. VR smoke test using `gui_data/complete_chime.wav`
2. MDX smoke test using the same sample file if an MDX model is installed
3. Demucs smoke test if a Demucs model is installed locally

Checks should include:

- output files exist
- output files are written to the expected directory
- model-name and model-folder toggles affect the output path

These tests should default to CPU-friendly settings unless the test is explicitly about GPU preference wiring.

### 4. Qt Widget Tests

Primary target:

- `uvr_qt/ui/main_window.py`

These tests are useful, but they should come after state and facade coverage.

Recommended tool:

- `pytest-qt`

What to verify:

- process-method selection updates the model list
- selecting a model updates persisted state
- output controls update state
- tuning controls update state
- `Primary stem only` and `Secondary stem only` remain mutually exclusive
- process button enablement depends on input paths, output path, and a runnable model selection
- `Reload Models` refreshes available model data

Do not start with deep visual assertions. Focus on state transitions and enabled/disabled behavior.

## Recommended Test Layout

Suggested directory structure:

```text
tests/
  test_qt_state.py
  test_processing_facade.py
  test_processing_integration.py
  test_main_window.py
```

Suggested scope for each file:

- `test_qt_state.py`
  state loading, persistence, round-trip checks
- `test_processing_facade.py`
  model discovery, resolution, and settings mapping
- `test_processing_integration.py`
  smoke tests with real sample input and temp output directories
- `test_main_window.py`
  widget state transitions using `pytest-qt`

## Recommended Tooling

There is no established repo-wide test harness yet for this new frontend, so the recommended starting point is:

- `pytest`
- `pytest-qt` for widget tests

If tests are added, the minimal dependency direction should likely be a separate Qt/frontend test dependency set rather than folding immediately into the legacy runtime install path.

## Priority Order

Recommended order of implementation:

1. state round-trip tests
2. processing facade selection and settings tests
3. one VR smoke test
4. one MDX smoke test if model is installed
5. Qt widget tests for selector/toggle behavior
6. Demucs smoke test if model is installed and runtime is stable

This order gives the highest value first while keeping failures easy to diagnose.

## What Not To Test Yet

Do not spend time early on:

- pixel-perfect UI rendering tests
- full parity with Tk widget behavior
- every legacy popup flow
- exhaustive model-parameter combinations
- GPU-required assertions that fail on CPU-only environments
- broad tests that import and drive all of `UVR.py`

Those will slow down the test suite and make failures harder to interpret.

## Stability Notes

Current backend integration still depends on adapter behavior and runtime bridging around legacy modules.

That means tests should prefer:

- verifying explicit inputs and outputs
- checking resolved model selections
- checking emitted files and state transitions

over:

- asserting deep internal implementation details of legacy modules

As the Qt-facing backend boundary gets cleaner, tests can move lower into backend services with less reliance on legacy runtime assumptions.

## Success Criteria

The first useful test suite for the Qt frontend should give confidence that:

- settings persist correctly
- model discovery and selection behave predictably
- the selected output options change real processing behavior
- one-file processing works for installed backend model types
- the new window reflects and mutates state correctly

That is enough to support continued iteration on the new frontend without trying to freeze the full application behavior too early.
