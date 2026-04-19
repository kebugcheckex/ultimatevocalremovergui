# UVR.py Refactor Plan

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

The two most important architectural issues are:

1. `MainWindow` owns too much behavior.
2. `ModelData` is UI-coupled because it reads directly from global `root` and Tk variables.

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

This structure should be introduced incrementally. It does not need to exist all at once in the first PR.

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

### `uvr/domain/model_data.py`

- extracted and refactored `ModelData`
- no direct access to Tk variables
- accepts typed configuration objects instead of reading from global `root`

This is the most important architectural seam in the whole refactor.

### `uvr/domain/ensemble.py`

- extracted `Ensembler`
- typed methods and arguments
- no Tk dependencies

### `uvr/domain/audio_tools.py`

- extracted `AudioTools`
- typed method signatures
- no Tk dependencies

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

### `uvr/services/cache.py`

- source caching and lookup logic
- cache clearing and update rules

### `uvr/services/downloads.py`

- online refresh
- download validation
- download queue/state handling
- download post-actions

### `uvr/ui/widgets.py`

- `ToolTip`
- `ListboxBatchFrame`
- `ComboBoxEditableMenu`
- `ComboBoxMenu`
- `ThreadSafeConsole`

### `uvr/ui/main_window.py`

- composition root for the Tk UI
- widget/frame creation
- delegates business logic to service modules

The long-term goal is for this module to become thin.

### `uvr/ui/actions.py`

- selection handlers
- widget state updates
- UI event responses

This should own logic such as:

- `selection_action_*`
- `update_*`
- widget enable/disable transitions

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

### `uvr/utils/system.py`

- OS-specific helper functions
- splash helpers
- process close helpers
- notification sound helpers
- generic non-UI utility functions

### `uvr/utils/tk_helpers.py`

- Tk hyperlink helpers
- drag-and-drop helper functions
- other small Tk-specific standalone functions

## First-Cut Extraction Plan

The first step should be low-risk and high-signal. Extract the parts with the clearest boundaries first.

### Phase 1: Zero-Risk Extractions

Move these first:

- top-level helper functions
- persistence helpers
- `Ensembler`
- `AudioTools`
- custom widget classes

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
   - `play_notification_sound`
   - `get_execution_time`
   - `right_click_release_linux`
   - `close_process`
   - `extract_stems`

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

Outcome of phase 5:

- `MainWindow` becomes a thin composition shell

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

### Major Risk: `ModelData`

This is the main blocker to a clean architecture because it reads directly from Tk/global state.

### Major Risk: Shared Mutable State

`MainWindow` currently owns and mutates a large amount of shared state. Extractions must be careful not to create circular imports or hidden side effects.

### Major Risk: Popup/Menu Coupling

Many popup methods likely depend on widget state that is only implicit in `MainWindow`.

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

- evaluate PySide6 or web UI migration after the backend/config boundaries are stable

## Recommendation

Do not begin with a GUI rewrite.

First:

1. establish typed config models
2. isolate persistence
3. decouple domain logic from Tk
4. move process orchestration out of `MainWindow`

After those steps, the codebase will be in a position where replacing Tk is a strategic choice instead of a full rewrite.
