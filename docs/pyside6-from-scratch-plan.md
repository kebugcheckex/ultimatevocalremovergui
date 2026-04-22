# PySide6 GUI From-Scratch Plan

## Goal

Build a new `PySide6` desktop frontend for UVR instead of porting the current Tk UI widget-for-widget.

This plan assumes:

- the new GUI does **not** need strict feature parity on day one
- the existing Tk UI in `UVR.py` is **not** the source of truth for the new frontend architecture
- existing extracted modules should be reused only when they behave like backend or domain code
- Tk-specific UI code should be left behind unless it contains logic worth re-expressing elsewhere

The intended outcome is a cleaner application split:

- backend/domain/services reusable across frontends
- a fresh Qt-native presentation layer
- less coupling to Tk variables, Tk widget lifecycle, and `UVR.py` runtime globals

## Recommendation

Given the current codebase, a fresh PySide6 frontend is likely lower risk than finishing a deep Tk refactor and then porting that refactored Tk UI to Qt.

The extracted backend work already created useful seams:

- typed settings and persistence in `uvr/config/`
- non-trivial model configuration in `uvr/domain/model_data.py`
- processing orchestration in `uvr/services/processing.py`
- domain helpers in `uvr/domain/audio_tools.py` and `uvr/domain/ensemble.py`

But the remaining Tk UI still has expensive migration characteristics:

- `UVR.py` remains the composition root and state container
- Tk variables are still the effective source of truth for much of the app
- many flows depend on widget callbacks and popup behavior rather than app-level state
- the service layer still assumes a broad UI surface in several places

So the correct strategy is:

1. preserve and reuse backend logic where it is already frontend-agnostic enough
2. extract or wrap only the remaining backend pieces needed by the new UI
3. build a new PySide6 application around explicit app state and Qt-native interaction patterns

## Non-Goals

This plan does not aim to:

- preserve the exact Tk layout
- preserve every popup and menu flow before first release
- preserve old widget naming or internal UI structure
- run both frontends from the same presentation code
- spend more time extracting Tk-only helpers than is needed to unlock the new UI

## Reuse Strategy

### Reuse As-Is or Nearly As-Is

These modules are strong candidates for reuse with minimal changes:

- `uvr/config/models.py`
- `uvr/config/persistence.py`
- `uvr/domain/model_data.py`
- `uvr/domain/audio_tools.py`
- `uvr/domain/ensemble.py`
- `uvr/services/processing.py`
- parts of `uvr/utils/system.py`

These should be treated as backend-facing modules, but some still need dependency cleanup or narrower interfaces.

### Reuse After Narrow Adapters

These areas are reusable only after introducing explicit non-UI interfaces:

- `uvr/services/processing.py`
- model download/refresh flows still living in `UVR.py`
- cache/source mapping logic still living in `UVR.py`
- remaining model parameter popup logic that currently mixes UI and data assembly

For these, the goal is not to reuse Tk methods. The goal is to extract the underlying behavior into service or domain modules that Qt can call.

### Do Not Reuse

These should generally not be ported directly:

- `UVR.py` layout and widget construction
- Tk menus and popups under the old flow model
- `uvr/ui/widgets.py`
- `uvr/ui/file_inputs.py`
- `uvr/ui/actions.py`
- `uvr/ui/menus/*` as implementation code
- `uvr/utils/tk_helpers.py`

Those modules are useful as references for behavior, labels, and edge cases, but not as architectural building blocks for Qt.

## Target Architecture

Proposed new structure:

```text
uvr_qt/
  app.py
  bootstrap.py
  state/
    app_state.py
    view_models.py
  services/
    processing_facade.py
    downloads.py
    cache.py
  ui/
    main_window.py
    panels/
      process_panel.py
      input_panel.py
      output_panel.py
      settings_panel.py
      model_panel.py
      advanced_panel.py
    dialogs/
      model_params.py
      save_settings.py
      error_log.py
      about.py
    widgets/
      log_console.py
      path_list.py
      model_selector.py
```

Existing `uvr/` modules remain the backend layer. The new `uvr_qt/` package is the Qt presentation and application shell.

## Architecture Principles

1. Qt widgets must read from explicit application state, not directly from backend globals.
2. Long-running work must run through Qt-friendly worker threads or task objects.
3. The processing service should communicate via typed events/callbacks, not direct widget mutation.
4. Dialogs should edit structured data and return it; they should not own cross-application state.
5. Tk compatibility should not shape the new frontend API.

## Core Design Decision

The new source of truth should be an explicit app-state layer, not Qt widgets and not old Tk variables.

Examples of state that should live in one place:

- selected processing mode
- selected model(s)
- input paths
- export path
- processing options
- advanced settings
- download state
- queue/progress state
- error and notification state

Qt widgets should bind to that state via signals/slots or thin view-model adapters.

## Required Backend Work Before or During Qt Build

This is the minimum backend shaping needed to make the Qt implementation clean.

### 1. Narrow Processing Interface

Create a Qt-usable facade around `uvr/services/processing.py`.

Target behavior:

- accept a typed processing request
- emit progress/status/log/result events
- avoid direct dependency on `MainWindow`
- avoid direct button-state or dialog interactions

If the current `ProcessingController` still expects many UI methods, wrap it temporarily behind a thin adapter, then replace those dependencies incrementally.

### 2. Extract Download Logic

Download and online-refresh behavior should move out of `UVR.py` into a real service module.

At minimum this service should expose:

- fetch/update online metadata
- resolve downloadable model entries
- start/cancel downloads
- report download progress
- validate VIP/download codes

Qt should never call the old popup/menu methods for this behavior.

### 3. Extract Cache Logic

The cache/source helper logic still in `UVR.py` should become a backend service.

At minimum:

- source cache lookup
- cache invalidation
- model/source mapping rules

This is useful independent of UI and should not remain inside the Tk app shell.

### 4. Convert Popup-Only Data Logic Into Services

Some existing popup flows are really data-entry wrappers around backend actions.

Examples:

- model parameter discovery/default editing
- save settings as named profiles
- ensemble save/edit flows

For Qt, the data action should exist separately from the dialog.

## First Release Scope

Do not aim for all current features immediately.

Suggested Phase 1 feature set:

1. single-window main workflow
2. select input files/folders
3. select export directory
4. choose main process type
5. choose core model/configuration
6. run process
7. view progress/log output
8. cancel process
9. persist/load main settings
10. basic error presentation

Suggested Phase 1 exclusions:

- full parity for every popup
- advanced model parameter editors
- embedded download center
- every legacy audio tool
- full menu parity
- every saved settings/ensemble management edge case

That release is enough to validate the new architecture and replace the most important user workflow first.

## UI Shape Recommendation

The new Qt UI should not mimic the old menu-heavy popup style.

Prefer:

- one main window
- side panel or stacked panels for process modes
- docked or tabbed advanced settings
- modal dialogs only for secondary tasks
- persistent log/progress panel

Recommended top-level layout:

1. input/output area
2. processing mode and model selection
3. main action area with run/cancel
4. advanced settings drawer/tab
5. status/progress/log pane

This reduces popup sprawl and makes Qt state handling much simpler.

## Execution Plan

### Phase A: Backend Readiness

Deliverables:

- processing facade independent of Tk widgets
- extracted download service
- extracted cache service
- typed app-state model for the new frontend

Success criteria:

- a headless caller can create a processing request and receive progress events
- settings can load/save without touching Tk
- model resolution can run without Qt or Tk

### Phase B: Qt Shell

Deliverables:

- `PySide6` application bootstrap
- main window
- central app-state object
- signal/slot wiring

Success criteria:

- app launches
- settings load into state
- basic UI navigation works

### Phase C: Main Workflow

Deliverables:

- input selection
- export path selection
- process mode selection
- model selection
- start/cancel processing
- progress/log display

Success criteria:

- primary separation workflow works end-to-end

Current implementation status:

- done for the first Qt release slice
- `uvr_qt/` now launches, loads persisted settings, runs separation through `uvr_core`, shows progress/log output, and supports cancellation through the shared job layer
- output/tuning controls and typed state synchronization are in place

### Phase D: Advanced Controls

Deliverables:

- advanced settings panels for VR, Demucs, and MDX
- validation and state sync
- optional secondary model controls

Success criteria:

- users can run meaningful non-default workflows without old Tk menus

Current implementation status:

- partially complete
- a collapsible advanced-controls section now exists in the Qt window
- VR, MDX, and Demucs numeric/tuning controls are wired through typed Qt state into `uvr_core`
- MDX/Demucs stem targeting is surfaced in the Qt UI
- first-pass workflow-composition controls for Demucs pre-proc and vocal splitter are surfaced in the Qt UI

Still missing:

- per-stem secondary-model selection and scaling
- parity for the more complex popup-driven composition/edit flows from Tk
- stronger validation and UX around incompatible advanced combinations

### Phase E: Secondary Features

Deliverables:

- settings save/load management
- download manager
- model/default editors
- ensemble helpers
- help/about/error dialogs

Success criteria:

- old Tk frontend is no longer needed for most practical usage

## Suggested Order of Implementation

If execution starts immediately, this is the recommended order:

1. create a Qt app-state model and processing request model
2. create a Tk-free processing facade around `uvr/services/processing.py`
3. scaffold the PySide6 app and main window
4. implement input/output/model selection
5. implement run/cancel/progress/logging
6. add advanced settings panels
7. add persistence wiring
8. add download/cache/model-management features

## Risks

### 1. Hidden Tk Assumptions In Backend Paths

Some extracted backend modules still depend on runtime composition from `UVR.py`.

Mitigation:

- identify these dependencies early
- replace them with explicit constructor parameters or service adapters

### 2. Processing Service Still Too UI-Coupled

`uvr/services/processing.py` may still assume too much about UI behavior.

Mitigation:

- treat the first Qt-facing processing layer as a facade
- let the facade absorb legacy assumptions while the backend is cleaned up

### 3. Model Configuration Logic Still Mixed With Dialog Flows

Some configuration behavior is currently only reachable through popup-style flows.

Mitigation:

- extract config generation and save/load behavior first
- implement dialogs only after the underlying action is UI-independent

### 4. Scope Creep

Trying to preserve the full Tk UX will slow the rewrite significantly.

Mitigation:

- ship a smaller Qt release first
- focus on the primary workflow

## What To Keep From The Existing UI

These should be treated as reference material, not as code to port directly:

- option names and labels
- validation rules
- model-specific edge cases
- ordering/grouping of advanced settings where it still makes sense
- help text and user-facing terminology

## What Success Looks Like

A successful Qt rewrite should produce:

- a smaller, clearer frontend codebase than `UVR.py`
- backend services callable without GUI-specific globals
- a main workflow that is easier to test and reason about
- fewer popup-driven interactions
- a codebase where adding features no longer requires editing a monolithic window class

## Final Recommendation

Do not continue deep Tk refactoring as a prerequisite for Qt.

Do only the backend extraction work that directly unlocks the new frontend:

- processing facade
- downloads service
- cache service
- app-state layer

Then build the PySide6 GUI as a new application shell from scratch.

That gives the best cost/risk tradeoff for this codebase.
