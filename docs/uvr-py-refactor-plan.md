# UVR.py Refactor Plan

## Status

Current implementation status as of this refactor pass:

- Phase 1: mostly complete
- Phase 2: complete for settings typing/persistence normalization
- Phase 3: complete via extracted `ModelData` with typed settings/resolvers
- Phase 4: complete via extracted processing controller
- Phase 5: partially complete
- PySide6 pivot readiness: not ready yet; a focused stabilization pass is still recommended before replacing Tk

The refactor is already live in `UVR.py` through compatibility imports, wrapper classes, and delegated methods. The new modules are not just planned; they are referenced by the application today.

Current extracted modules:

```text
uvr/
  config/
    models.py
    persistence.py
  domain/
    audio_tools.py
    ensemble.py
    model_data.py
  services/
    processing.py
  ui/
    actions.py
    file_inputs.py
    widgets.py
    menus/
      common.py
      inputs.py
  utils/
    system.py
    tk_helpers.py
```

Important implementation note:

- `UVR.py` still contains some legacy bodies for compatibility and incremental cleanup.
- In several places the extracted module is the active runtime implementation even if an older in-file version still exists nearby.
- This is intentional and keeps the refactor low-risk while shrinking the architectural surface of `UVR.py`.

## Goal

Break down `UVR.py` into smaller, typed modules so the application becomes:

- easier to maintain
- easier to test
- less dependent on Tk-specific global state
- easier to modernize toward PySide6 or a web-based UI later

This plan is intentionally structured to reduce risk. The first phases focus on extracting stable pieces before changing the application architecture.

## Current Problems

`UVR.py` currently mixes several unrelated responsibilities:

- app startup and shutdown
- persistence
- OS-specific helper logic
- model configuration
- audio tool logic
- ensemble logic
- Tk widget definitions
- main window layout
- menu and popup construction
- state transitions and widget enable/disable rules
- downloads and online refresh
- process orchestration and threading

The two most important architectural issues were:

1. `MainWindow` owns too much behavior.
2. `ModelData` is UI-coupled because it reads directly from global `root` and Tk variables.

Current highest-priority architectural issues are now:

1. `MainWindow` still owns too much behavior, especially layout, menus, popups, file/input flows, and shared mutable UI state.
2. `ProcessingController` and the remaining menu/popup flows still depend on Tk-era runtime state and `UVR.py` composition wiring more than they should for a clean Qt migration.

## Refactor Principles

1. Split by responsibility, not by line count.
2. Keep Tk-specific code out of domain and service modules.
3. Add type hints to every extracted module.
4. Replace raw dict-heavy interfaces with typed dataclasses where practical.
5. Preserve behavior first, then improve design.
6. Introduce compatibility layers where needed instead of rewriting everything at once.

## Target Package Structure

Proposed structure:

```text
uvr/
  app.py
  config/
    models.py
    persistence.py
  domain/
    model_data.py
    ensemble.py
    audio_tools.py
  services/
    processing.py
    cache.py
    downloads.py
  ui/
    main_window.py
    widgets.py
    actions.py
    menus/
      settings.py
      advanced_vr.py
      advanced_demucs.py
      advanced_mdx.py
      advanced_ensemble.py
      help.py
      downloads.py
      secondary_model.py
      popups.py
  utils/
    system.py
    tk_helpers.py
```

This structure has been introduced incrementally. The currently implemented subset is listed in the status section above. The remaining items are still target structure, not yet fully extracted.

## Module Responsibilities

### `uvr/app.py`

- application entrypoint
- startup sequence
- root-window creation
- shutdown/restart wiring

### `uvr/config/models.py`

- typed dataclasses for settings and runtime state
- serialized app settings model
- process/job request model
- download/config request model

Current status:

- implemented
- includes `AppSettings`
- includes typed subsets such as `ProcessSettings`, `ModelSelection`, and `DownloadSettings`
- currently acts as a compatibility layer around the legacy dict-shaped settings model

Examples:

- `AppSettings`
- `ProcessSettings`
- `ModelSelection`
- `ProcessJob`

### `uvr/config/persistence.py`

- loading and saving persisted settings
- backward compatibility for legacy `data.pkl`
- future migration away from pickle

This is the correct place to replace the current root-level `data.pkl` behavior with a safer approach later.

Current status:

- implemented
- `UVR.py` startup now loads normalized settings through this module
- includes typed `load_settings()` / `save_settings()` alongside legacy-compatible `load_data()` / `save_data()`

### `uvr/domain/model_data.py`

- extracted and refactored `ModelData`
- no direct access to Tk variables
- accepts typed configuration objects instead of reading from global `root`

This is the most important architectural seam in the whole refactor.

Current status:

- implemented
- `ModelData` now lives in this module
- direct `root` access has been replaced with explicit `ModelDataSettings` and `ModelDataResolvers`
- `UVR.py` currently exposes a compatibility wrapper class `ModelData(model_data_module.ModelData)`

### `uvr/domain/ensemble.py`

- extracted `Ensembler`
- typed methods and arguments
- target is no Tk dependencies

Current status:

- implemented
- active via alias rebinding in `UVR.py`
- now accepts explicit `EnsemblerSettings`
- no longer reads `runtime.root` state directly
- still depends on runtime-bound utility functions and composition wiring from `UVR.py`

### `uvr/domain/audio_tools.py`

- extracted `AudioTools`
- typed method signatures
- target is no Tk dependencies

Current status:

- implemented
- active via alias rebinding in `UVR.py`
- now accepts explicit `AudioToolSettings`
- no longer reads `runtime.root` state directly
- still depends on runtime-bound utility functions and composition wiring from `UVR.py`

### `uvr/services/processing.py`

- process initialization and orchestration
- conversion/tool execution flow
- progress reporting interfaces
- callback-based communication with UI

This module should own logic currently spread across:

- `process_initialize`
- `process_start`
- `process_tool_start`
- progress update helpers
- parts of validation and job dispatch

Current status:

- implemented
- `MainWindow` now delegates process lifecycle methods to `ProcessingController`
- the UI-facing method names still exist in `UVR.py`, but they are thin delegation shims
- dialog and button-state interactions are now routed through thin UI adapter methods
- no longer creates Tk variable objects internally
- still depends on the `MainWindow` UI surface and runtime composition layer

### `uvr/services/cache.py`

- source caching and lookup logic
- cache clearing and update rules

Current status:

- not extracted yet
- cache/source helpers still live in `UVR.py`

### `uvr/services/downloads.py`

- online refresh
- download validation
- download queue/state handling
- download post-actions

Current status:

- not extracted yet
- download and online-refresh logic still lives in `UVR.py`

### `uvr/ui/widgets.py`

- `ToolTip`
- `ListboxBatchFrame`
- `ComboBoxEditableMenu`
- `ComboBoxMenu`
- `ThreadSafeConsole`

Current status:

- implemented
- active via alias rebinding in `UVR.py`

### `uvr/ui/main_window.py`

- composition root for the Tk UI
- widget/frame creation
- delegates business logic to service modules

The long-term goal is for this module to become thin.

Current status:

- not created yet
- `MainWindow` still lives in `UVR.py`
- however, `MainWindow` now delegates significant logic to extracted modules

### `uvr/ui/actions.py`

- selection handlers
- widget state updates
- UI event responses

This should own logic such as:

- `selection_action_*`
- `update_*`
- widget enable/disable transitions

Current status:

- implemented
- currently owns a first extraction slice of UI state/actions:
  - `selection_action_*`
  - main widget state transitions
  - stem/ensemble state update helpers
  - saved-settings action helpers
- layout/build methods and menu/popup logic are still in `UVR.py`

### `uvr/ui/file_inputs.py`

- file dialogs
- input-path normalization
- dual-input selection helpers
- input entry text updates

Current status:

- implemented
- `MainWindow` now delegates core file/input helper flows to this module
- extracted so far:
  - `show_file_dialog`
  - `input_select_filedialog`
  - `export_select_filedialog`
  - `update_input_paths`
  - `select_audiofile`
  - `check_dual_paths`
  - `process_input_selections`

### `uvr/ui/menus/`

Split the large popup/menu methods into focused modules.

Suggested breakdown:

- `settings.py`
- `advanced_vr.py`
- `advanced_demucs.py`
- `advanced_mdx.py`
- `advanced_ensemble.py`
- `help.py`
- `downloads.py`
- `secondary_model.py`
- `popups.py`

Current status:

- started
- extracted so far:
  - `uvr/ui/menus/common.py`
  - `uvr/ui/menus/inputs.py`
- menu and popup code still largely lives in `UVR.py`, but the first menu slices now delegate through these modules

### `uvr/ui/menus/common.py`

- shared menu/popup window placement
- shared tab scaffolding
- reusable menu helper widgets/buttons

Current status:

- implemented
- currently owns:
  - `menu_placement`
  - `adjust_widget_widths`
  - `menu_tab_control`
  - shared vocal-splitter button helper

### `uvr/ui/menus/inputs.py`

- input-related right-click menus
- selected-inputs popup
- dual-input batch popup

Current status:

- implemented
- currently owns:
  - `input_right_click_menu`
  - `input_dual_right_click_menu`
  - `menu_view_inputs`
  - `menu_batch_dual`

### `uvr/utils/system.py`

- OS-specific helper functions
- splash helpers
- process close helpers
- notification sound helpers
- generic non-UI utility functions

Current status:

- partially implemented
- extracted now:
  - `get_execution_time`
  - `right_click_release_linux`
  - `close_process`
  - `extract_stems`
- planned but not yet moved:
  - `play_notification_sound`

### `uvr/utils/tk_helpers.py`

- Tk hyperlink helpers
- drag-and-drop helper functions
- other small Tk-specific standalone functions

Current status:

- implemented
- extracted now:
  - `drop`
  - `read_bulliten_text_mac`
  - `open_link`
  - `auto_hyperlink`
  - `vip_downloads`

## First-Cut Extraction Plan

The first step should be low-risk and high-signal. Extract the parts with the clearest boundaries first.

### Phase 1: Zero-Risk Extractions

Move these first:

- top-level helper functions
- persistence helpers
- `Ensembler`
- `AudioTools`
- custom widget classes

Status:

- completed in practice, with one small deviation from the original list:
  - `play_notification_sound` has not been extracted yet
- extracted modules are already referenced by `UVR.py`

Recommended initial file moves:

1. `uvr/config/persistence.py`
   Move:
   - `save_data`
   - `load_data`

2. `uvr/domain/ensemble.py`
   Move:
   - `Ensembler`

3. `uvr/domain/audio_tools.py`
   Move:
   - `AudioTools`

4. `uvr/ui/widgets.py`
   Move:
   - `ToolTip`
   - `ListboxBatchFrame`
   - `ComboBoxEditableMenu`
   - `ComboBoxMenu`
   - `ThreadSafeConsole`

5. `uvr/utils/system.py`
   Move:
   - `get_execution_time`
   - `right_click_release_linux`
   - `close_process`
   - `extract_stems`

   Deferred:
   - `play_notification_sound`

6. `uvr/utils/tk_helpers.py`
   Move:
   - `drop`
   - `read_bulliten_text_mac`
   - `open_link`
   - `auto_hyperlink`
   - `vip_downloads`

Outcome of phase 1:

- `UVR.py` gets smaller
- almost no application behavior changes
- new module structure starts to exist

Actual outcome so far:

- achieved
- `UVR.py` now uses the extracted modules through compatibility imports and aliases

### Phase 2: Typed Config Layer

Introduce typed dataclasses before rewriting orchestration.

Create:

- `AppSettings`
- `ProcessSettings`
- `ModelSelection`
- `DownloadSettings`

Then:

- stop passing raw dicts around where possible
- make persistence load/save typed models
- add a compatibility conversion layer for legacy data

Status:

- completed
- `AppSettings` is the compatibility model currently normalizing legacy dict data against `DEFAULT_DATA`
- typed persistence is active at startup and save time

Outcome of phase 2:

- stronger typing
- fewer hidden assumptions
- easier testing

### Phase 3: Decouple `ModelData`

Refactor `ModelData` so it no longer reads from global `root`.

Current problem:

- `ModelData` is effectively a UI adapter, not a domain object

Target:

- `ModelData` accepts typed settings/config objects
- no Tk imports
- no global `root` dependency

Status:

- completed
- `ModelData` now accepts typed settings and resolver callbacks instead of reading Tk variables directly
- popup-driven model metadata lookup is still supported via injected resolvers from `UVR.py`

This phase is the highest-value architectural change.

Outcome of phase 3:

- domain logic becomes reusable
- future UI replacement becomes realistic

### Phase 4: Extract Processing Controller

Move processing orchestration out of `MainWindow`.

Candidate methods:

- `process_initialize`
- `process_button_init`
- `process_get_baseText`
- `process_update_progress`
- `confirm_stop_process`
- `process_end`
- `process_tool_start`
- `process_start`
- `process_determine_secondary_model`
- `process_determine_demucs_pre_proc_model`
- `process_determine_vocal_split_model`
- `check_only_selection_stem`
- `determine_voc_split`

Target design:

- UI supplies a typed job/config object
- processing service runs work
- UI receives callbacks for:
  - console output
  - progress
  - completion
  - errors

Status:

- completed
- `uvr/services/processing.py` now contains `ProcessingController`
- `MainWindow` still exposes the old process methods, but they delegate to the controller
- follow-up stabilization work has also removed direct Tk dialogs/button constants and temporary Tk variable creation from the controller

Outcome of phase 4:

- `MainWindow` stops being the process engine
- testing becomes much easier

### Phase 5: Split `MainWindow` by UI Responsibility

Once services and config objects exist, split `MainWindow` into smaller UI modules.

Suggested groups:

1. layout/build methods
   - `fill_main_frame`
   - `fill_filePaths_Frame`
   - `fill_options_Frame`

2. menu modules
   - `menu_*`
   - `pop_up_*`

3. UI state/actions
   - `selection_action_*`
   - `update_*`
   - widget-state transitions

4. file/input helpers
   - file dialogs
   - path updates
   - sample creation
   - input validation

Status:

- partially complete
- extracted so far:
  - `uvr/ui/actions.py`
  - `uvr/ui/file_inputs.py`
  - `uvr/ui/menus/common.py`
  - `uvr/ui/menus/inputs.py`
  - selection handlers
  - widget state updates
  - saved-settings action flow
  - stem/ensemble UI transitions
  - file/input helper flows
  - shared menu infrastructure
  - input-related menu/popup flows
- still remaining in `UVR.py`:
  - layout/build methods
  - most settings/help/download/advanced menu bodies
  - most popup bodies

Outcome of phase 5:

- `MainWindow` becomes a thin composition shell

Current reality:

- `MainWindow` is thinner than before, but not yet thin
- the biggest remaining UI weight is still layout/menu construction
- file dialogs, input/path handling, and input-related popups no longer live primarily in `UVR.py`
- the biggest remaining UI weight is now the larger settings/help/download/advanced menus and popup bodies

## Pre-PySide6 Stabilization Pass

The project is closer to a GUI pivot than before, but it is not yet at the point where replacing Tk with PySide6 is the lowest-risk next step.

What is already in good shape:

- typed settings/persistence are in place
- `ModelData` has a real non-Tk seam
- processing orchestration has been extracted into a service module
- `AudioTools` and `Ensembler` now accept explicit settings objects instead of reading `root`
- core file/input helper flows and the first menu slices have been extracted from `MainWindow`

What still blocks a clean Qt rewrite:

- `MainWindow` still owns too much UI composition and state
- the remaining large menu/popup bodies still live in `UVR.py`
- `ProcessingController` still depends on the `MainWindow` UI surface rather than a narrower interface
- runtime binding through `UVR.py` is still the primary composition strategy
- drag/drop flows remain Tk-specific by design and will need a Qt replacement path later

Recommended next pass before starting PySide6:

1. continue Phase 5 by extracting the remaining settings/help/download/advanced menu bodies and popup modules out of `MainWindow`
2. keep narrowing the `ProcessingController` interface so it depends on a smaller UI adapter surface
3. introduce a framework-neutral app-state or view-model layer so Tk variables stop being the source of truth
4. leave Tk-specific drag/drop and widget behavior inside isolated UI modules so the later Qt replacement has a clear boundary

Completed stabilization work so far:

1. refactored `AudioTools` to accept `AudioToolSettings`
2. refactored `Ensembler` to accept `EnsemblerSettings`
3. removed direct Tk dialogs/button constants and temporary Tk variable creation from `ProcessingController`
4. extracted file/input helper flows into `uvr/ui/file_inputs.py`
5. extracted shared menu infrastructure and input-related menu slices into `uvr/ui/menus/common.py` and `uvr/ui/menus/inputs.py`

This is intentionally a narrow pass. The goal is not to continue refactoring indefinitely; it is to complete the remaining boundary work that will make the PySide6 migration straightforward instead of coupled to unfinished cleanup.

## Type Hint Standard

Every extracted module should meet the following standard:

1. Public functions must have full type hints.
2. Dataclasses should be preferred over untyped dicts.
3. Callback signatures should be explicitly typed.
4. Domain modules should avoid `Any` unless unavoidable.
5. Tk types should remain inside UI modules only.

Examples of useful aliases:

```python
from collections.abc import Callable

ProgressCallback = Callable[[float, float], None]
ConsoleCallback = Callable[[str], None]
```

## Risks and Constraints

### Historical Risk: `ModelData`

This was the main blocker to a clean architecture because it read directly from Tk/global state.

Current status:

- the primary coupling has been removed
- residual risk now comes from compatibility wrappers and resolver callbacks still originating in `UVR.py`

### Major Risk: Shared Mutable State

`MainWindow` currently owns and mutates a large amount of shared state. Extractions must be careful not to create circular imports or hidden side effects.

Current status:

- still relevant
- the refactor currently uses runtime binding and UI/service delegation to avoid a large rewrite
- this keeps behavior stable, but means some modules still depend on `UVR.py` as the composition/runtime source
- this runtime binding strategy is acceptable for the current incremental refactor, but it is not the ideal long-term boundary for a Qt rewrite

### Major Risk: Popup/Menu Coupling

Many popup methods likely depend on widget state that is only implicit in `MainWindow`.

Current status:

- still relevant
- this is the main reason `uvr/ui/menus/` has not been extracted yet

### Major Risk: Persistence Compatibility

The current persisted data is a raw pickle payload. If format changes are introduced, a migration or compatibility layer will be required.

## Definition of Success

The refactor is moving in the right direction if:

- `UVR.py` steadily shrinks
- new modules have clear, single responsibilities
- domain logic can run without importing Tk
- `ModelData` no longer depends on `root`
- persistence is isolated behind one module
- UI code delegates to services instead of owning business logic

## Practical Milestones

### Milestone 1

- create package structure
- extract helpers, persistence, widgets, `Ensembler`, and `AudioTools`

### Milestone 2

- add typed settings dataclasses
- wrap legacy persistence behind typed models

### Milestone 3

- refactor `ModelData` to accept typed config objects

### Milestone 4

- extract processing orchestration to a service/controller layer

### Milestone 5

- split `MainWindow` menus, actions, and layout into separate UI modules

### Milestone 6

- complete a pre-PySide6 stabilization pass
- remove remaining `runtime.root` / Tk-variable access from service and domain paths
- introduce framework-neutral UI callbacks or adapters where services still assume Tk dialogs or Tk state

### Milestone 7

- evaluate PySide6 or web UI migration after the backend/config boundaries are stable

## Recommendation

Do not begin the PySide6 rewrite yet.

First:

1. establish typed config models
2. isolate persistence
3. decouple domain logic from Tk
4. move process orchestration out of `MainWindow`
5. complete the remaining UI-boundary stabilization work around menus, popups, file/input helpers, and Tk-coupled service paths

Status against that recommendation today:

- steps 1 through 4 are substantially complete
- step 5 is still incomplete and is now the main blocker

After that stabilization pass, the codebase will be in a position where replacing Tk with PySide6 is a strategic frontend migration instead of a mixed refactor/rewrite.
