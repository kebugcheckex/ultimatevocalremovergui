# Python 3.13 Upgrade Plan

## Goal

Upgrade the project from Python 3.9 to Python 3.13 one version at a time, while:

- keeping the Tk app, CLI, and in-progress Qt app working
- replacing or upgrading dependencies that block newer Python versions
- modernizing syntax and typing as each minimum version increases
- avoiding a large, untestable "all at once" migration

## Current Baseline

Repository findings from this codebase review:

- `mise.toml` pins Python `3.9`.
- The local shell environment is currently running Python `3.9.25`.
- The README still documents Python 3.9 on Windows and Python 3.10 on macOS.
- There is no committed `pyproject.toml`, `setup.cfg`, `setup.py`, or `requirements.txt`.
- The only committed requirements file is `requirements-refactor.txt`, and it currently contains only `pytest`.
- The codebase already mixes modern and legacy typing styles:
  - newer modules under `uvr/`, `uvr_core/`, and `uvr_qt/` use `X | Y`
  - legacy and vendored code under `UVR.py`, `demucs/`, and `lib_v5/` still uses `typing.List`, `Optional`, `Union`, and `typing as tp`
- Persistence is partially modernized:
  - default config path is now YAML-backed `data/config.yaml`
  - legacy pickle compatibility still exists through `data.pkl`
- Runtime bootstrapping still depends on legacy global behavior:
  - `UVR.py` calls `os.chdir(BASE_PATH)`
  - `uvr/runtime.py` calls `os.chdir(DEFAULT_PATHS.base_path)` and builds a `SimpleNamespace`
- The main compatibility risk is not syntax. It is the native and ML stack used by:
  - `torch`
  - `onnxruntime`
  - `PySide6`
  - `librosa` / `soundfile` / `audioread`
  - `onnx2pytorch`
  - vendored `demucs/`
  - older helper libraries such as `kthread`, `ml_collections`, `pyglet`, `pyperclip`, and bundled `tkinterdnd2`

## Migration Principles

1. Move the supported Python version one minor release at a time: `3.10`, then `3.11`, then `3.12`, then `3.13`.
2. At each step, upgrade dependencies first, then refactor code to use the new minimum version, then run the full smoke test suite.
3. Do not apply broad syntax rewrites to vendored code blindly. Treat `demucs/` and `lib_v5/` as compatibility islands until their dependency story is stable.
4. Introduce proper packaging metadata before the first version bump so interpreter constraints and dependency pins live in source control.
5. Keep YAML persistence as the default path and continue reducing reliance on raw pickle.

## Phase 0: Prep Before Python 3.10

This prep work should happen before any interpreter bump.

### 0.1 Add real packaging metadata

Create a committed `pyproject.toml` and move environment definition out of README-only instructions.

Minimum contents:

- `requires-python = ">=3.9,<3.10"` initially, then raise it each phase
- core runtime dependencies
- optional dependency groups for:
  - `dev`
  - `qt`
  - `cli`
  - possibly `gpu` if the project wants to split CPU and CUDA guidance

Why this is first:

- today the repo has no authoritative dependency manifest
- version-gated dependency pinning is almost impossible to manage cleanly without it
- CI and local reproduction both depend on this

### 0.2 Build a dependency inventory

Capture all direct runtime imports in the new metadata, then classify them into:

- first-party code
- vendored code
- heavy native/runtime packages
- likely replaceable utilities

Initial high-risk list from the repo:

- `torch`
- `onnx`
- `onnxruntime`
- `onnx2pytorch`
- `pytorch_lightning`
- `PySide6`
- `librosa`
- `soundfile`
- `audioread`
- `scipy`
- `numpy`
- `pydub`
- `matchering`
- `cryptography`
- `click`
- `yaml` / `PyYAML`
- `ml_collections`
- `kthread`
- `pyglet`
- `pyperclip`
- `natsort`
- `psutil`
- `playsound` / `playsound3`
- vendored `tkinterdnd2`

### 0.3 Separate supported code from vendored code

Define three buckets explicitly:

- actively maintained project code:
  - `uvr/`
  - `uvr_core/`
  - `uvr_qt/`
  - `uvr_cli/`
  - tests
- legacy project code:
  - `UVR.py`
  - `separate.py`
- vendored or near-vendored code:
  - `demucs/`
  - `lib_v5/`
  - bundled `gui_data/tkinterdnd2/`

Rule for the upgrade:

- modernize project-owned code aggressively
- touch vendored code only when required for compatibility or bug fixes

### 0.4 Expand the test gate

Current tests are concentrated in `tests/test_phase1_sanity.py`. Before the first interpreter bump, add at least:

- CLI smoke tests for `python -m uvr_cli --help`
- config round-trip tests for YAML and legacy pickle migration
- lightweight import tests for:
  - `UVR.py`
  - `uvr_cli.__main__`
  - `uvr_qt.app`
  - `separate.py`
- one backend smoke path for:
  - separation request creation
  - download catalog loading
  - model discovery

The goal is not deep model execution in CI. The goal is early failure on import-time and compatibility regressions.

### 0.5 Remove README as the source of truth for dependencies

Keep install docs, but point them at the new package metadata and tested install commands.

## Version-by-Version Plan

## Phase 1: Python 3.10

### Objective

Reach a clean, tested Python 3.10 baseline with no behavioral changes other than compatibility work.

### Code refactors to do in this phase

- Replace remaining project-owned `typing.Union[X, Y]` with `X | Y`.
- Replace project-owned `Optional[X]` with `X | None`.
- Replace project-owned `List[X]`, `Dict[K, V]`, `Tuple[...]`, and `Set[X]` with built-in generics.
- Remove `from __future__ import annotations` only where it is no longer needed and doing so does not create churn. Keeping it temporarily is fine.
- Standardize on `pathlib.Path` for new code and reduce stringly-typed path plumbing where touched.

Scope note:

- Apply those rewrites first to `uvr/`, `uvr_core/`, `uvr_qt/`, `uvr_cli/`, and tests.
- Defer broad style rewrites in `UVR.py`, `demucs/`, and `lib_v5/` unless the file must change for compatibility.

### Dependency work in this phase

- Upgrade all direct dependencies to versions that support Python 3.10.
- Verify wheel availability and import stability for:
  - `torch`
  - `onnxruntime`
  - `PySide6`
  - `cryptography`
  - `numpy`
  - `scipy`
  - `librosa`
- Reduce reliance on `audioread` as an implicit audio backend. Prefer `soundfile` or an explicit ffmpeg-backed path where possible.
- Audit `playsound` versus `playsound3` fallback behavior and decide on one supported package.

### Cleanup targets

- Replace `SimpleNamespace` runtime state in `uvr/runtime.py` with a typed runtime object or dataclass-backed container.
- Start removing `os.chdir(...)` as an application-wide assumption and pass explicit paths instead.
- Convert `subprocess.Popen(f'python ...', shell=True)` style process relaunches to `sys.executable` plus argument lists.

### Exit criteria

- `mise.toml` and package metadata point to Python 3.10.
- Tests pass under Python 3.10.
- README install instructions no longer claim Python 3.9/3.10 inconsistently.
- Project-owned type syntax is 3.10-native in the actively maintained packages.

## Phase 2: Python 3.11

### Objective

Reach Python 3.11 with the runtime architecture more explicit and less dependent on legacy globals.

### Code refactors to do in this phase

- Continue typing cleanup in `UVR.py` where edits are already required.
- Replace project-owned `typing.Any` heavy dict plumbing with typed dataclasses or typed mappings where the interfaces are stable.
- Keep moving state creation out of Tk widgets and into typed request/state objects.

### Dependency work in this phase

- Upgrade all direct dependencies to versions verified for Python 3.11.
- Re-check native stack support:
  - `torch`
  - `onnxruntime`
  - `PySide6`
  - `soundfile`
  - `numpy`
  - `scipy`
- Decide whether these dependencies should stay or be replaced:
  - `kthread`
  - `ml_collections`
  - `pyglet`
  - `pyperclip`

Recommended direction:

- replace `kthread` with standard library threading/cancellation primitives if possible
- limit `ml_collections.ConfigDict` to compatibility boundaries or replace with dataclasses/plain dicts
- keep `pyperclip` and `pyglet` only if they remain necessary for the Tk app

### Cleanup targets

- Remove remaining path and runtime behavior that depends on mutating process-global state.
- Make backend entry points importable without side effects beyond constant initialization.
- Reduce import-time coupling between `UVR.py`, `separate.py`, and the extracted backend packages.

### Exit criteria

- Clean test pass on Python 3.11.
- Import-time side effects are reduced enough that backend modules can be exercised without depending on global cwd changes.
- At least one legacy utility dependency is removed or isolated behind a small adapter.

## Phase 3: Python 3.12

### Objective

Reach Python 3.12 after paying down the dependencies most likely to lag interpreter support.

### Code refactors to do in this phase

- Modernize project-owned remaining legacy typing syntax outside vendored code.
- Replace ad hoc data carrier dicts in hot paths with typed request/result objects where the structure is already known.
- Continue shrinking `UVR.py` and `separate.py` integration surfaces.

### Dependency work in this phase

This is the phase where dependency replacement may be required rather than simple upgrades.

Likely candidates:

- `audioread`
  - treat as optional or remove from the default path
  - prefer `soundfile` plus explicit ffmpeg handling
- `onnx2pytorch`
  - verify it is still required in the main path
  - if only used in limited conversion flows, isolate it behind an optional feature gate
- `pytorch_lightning`
  - verify whether `lib_v5/mdxnet.py` truly needs it at runtime
  - if not, replace with direct `torch.nn.Module` usage or isolate behind a compatibility wrapper
- vendored `tkinterdnd2`
  - keep it disabled by default if maintenance remains poor
  - document it as optional until verified on newer Python/Tk combinations

### Cleanup targets

- Finish converting the default persistence story to YAML-centric docs and code paths.
- Keep pickle strictly as legacy import compatibility, not as a preferred save format.
- Remove stale README instructions that hardcode site-package file copying paths for old Python installs.

### Exit criteria

- Clean test pass on Python 3.12.
- Dependency list is split into required versus optional integrations.
- At least the actively maintained packages no longer depend on deprecated or weakly maintained libraries for core workflows.

## Phase 4: Python 3.13

### Objective

Reach Python 3.13 with a smaller, more explicit runtime surface and a dependency set that is intentionally maintained.

### Code refactors to do in this phase

- Finish any remaining project-owned syntax modernization.
- Keep vendored typing rewrites minimal unless required for compatibility.
- Review warnings and deprecations under Python 3.13 and fix them in owned code before they become future breaks.

### Dependency work in this phase

- Upgrade all remaining required dependencies to Python 3.13-compatible versions.
- Re-verify the critical wheel/install matrix for:
  - CPU-only environments
  - CUDA-enabled environments
  - macOS arm64
  - Linux desktop installs
- If a dependency still blocks Python 3.13, choose one of three paths explicitly:
  - replace it
  - isolate it behind an optional feature flag
  - pin that feature to an older interpreter in a clearly documented compatibility mode

The preferred outcome for core workflows is not to keep a hard Python-version fork. If a dependency blocks 3.13 for a niche feature, isolate the feature instead of blocking the entire project.

### Cleanup targets

- Raise `requires-python` to `>=3.13`.
- Update `mise.toml`, docs, CI, and local developer instructions.
- Re-run import and smoke tests for Tk, CLI, and Qt entry points.
- Document any features that remain optional or partially supported on 3.13.

### Exit criteria

- Clean test pass on Python 3.13.
- README and docs consistently target Python 3.13.
- Core separation, config, catalog, and download flows work on the supported platforms.

## Dependency Replacement Candidates

These are the most likely libraries to need replacement, isolation, or stricter optionalization during the migration.

### `audioread`

Reason:

- older backend-style library
- often used as a fallback rather than a preferred path
- worth removing from the default execution path if `soundfile` plus ffmpeg is sufficient

Recommended action:

- make audio loading explicit
- prefer `soundfile`
- keep `audioread` only as an optional fallback if still required

### `kthread`

Reason:

- niche dependency
- standard library threading plus cooperative cancellation is usually enough

Recommended action:

- replace with `threading.Thread`, `threading.Event`, and explicit job cancellation plumbing

### `ml_collections`

Reason:

- extra dependency for config-shaped data that the project is already refactoring into typed objects

Recommended action:

- replace project-owned uses with dataclasses or normal dict structures
- keep only if required by vendored model code

### `onnx2pytorch`

Reason:

- specialized bridge dependency
- may lag behind newer Python and PyTorch releases

Recommended action:

- verify whether it is needed for common workflows
- isolate or replace if it blocks later interpreter bumps

### `pytorch_lightning`

Reason:

- large dependency surface for a likely narrow usage area

Recommended action:

- confirm whether runtime usage is real and necessary
- replace with direct `torch` abstractions if practical

### vendored `demucs/` and `lib_v5/`

Reason:

- these directories contain older style typing and compatibility assumptions
- broad formatting or syntax rewrites can introduce subtle behavioral regressions

Recommended action:

- update only as needed for interpreter compatibility
- avoid unnecessary cleanup-only churn in these trees during the version bump

## Recommended Execution Order

For each version step, use the same order:

1. Freeze the current state with tests.
2. Add or update dependency metadata and pins for the next Python version.
3. Upgrade dependencies in a branch dedicated to that version step.
4. Fix import-time and install-time breakages first.
5. Apply owned-code refactors enabled by that new minimum version.
6. Run tests and smoke checks.
7. Update docs only after the code and dependency set are stable.

## Suggested Deliverables Per Step

Each version bump should land as a small series of PRs, not a single giant one.

Suggested split:

1. packaging and CI
2. dependency upgrades
3. owned-code syntax and typing refactors
4. runtime/bootstrap cleanup
5. docs and installation updates

## Minimum Verification Matrix

Run this matrix at each version step:

- unit tests
- import tests for Tk, CLI, Qt entry points
- `python -m uvr_cli --help`
- one non-GUI config load/save smoke test
- one model catalog/discovery smoke test

Run this matrix at least for the final Python 3.13 target:

- Linux CPU install
- Windows install path
- macOS arm64 install path
- one GPU-enabled environment if GPU support remains a supported workflow

## Recommended First PR

Before touching Python versions, make one prep PR with only:

- `pyproject.toml`
- a real dependency manifest
- CI or local test commands tied to that manifest
- doc updates describing the supported Python baseline as 3.9
- no behavior changes except packaging and reproducibility fixes

That PR creates the control point needed for the actual `3.10 -> 3.13` migration.
