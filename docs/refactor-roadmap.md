# UVR Refactor Roadmap

## Goal

Rewrite the GUI on PySide6 and ship a CLI with similar functionality, built on a shared backend that could later be exposed through a web UI without another rewrite.

"Similar functionality" here means feature coverage comparable to the existing Tk GUI's mainstream workflows (single-model separation, ensembles, secondary/pre-proc models, audio tools, model downloads). The CLI is not required to match every popup or window of the Tk app.

## Principles

1. The backend is the product. GUI and CLI are thin adapters over it.
2. Frontends consume typed state and typed requests, never Tk/Qt-specific globals.
3. Long-running work is async-friendly: progress/log/status travel over callbacks or event streams, not widget mutation.
4. Persistence lives in one place with a typed interface and a migration path off the legacy pickle.
5. No hidden Tk/Qt imports in `uvr/` (domain/services/config). If it imports a UI toolkit, it does not belong under `uvr/`.
6. Persistence changes should preserve a compatibility path from the legacy `data.pkl` long enough to migrate existing installs safely.

## Target Architecture

```text
uvr/                     # framework-neutral backend (no Tk, no Qt)
  config/                # typed settings + persistence
  domain/                # ModelData, Ensembler, AudioTools
  services/
    processing.py        # core orchestration (decoupled from MainWindow)
    downloads.py         # online refresh, validation, downloads
    cache.py             # source cache
    catalog.py           # model discovery + name mapping
  runtime.py             # replaces runtime_bridge's SimpleNamespace shim

uvr_core/                # framework-neutral façade consumed by adapters
  requests.py            # SeparationRequest, EnsembleRequest, AudioToolRequest
  events.py              # ProgressEvent, LogEvent, StatusEvent, ResultEvent
  jobs.py                # Job runner: takes a request, emits events, returns result

uvr_qt/                  # PySide6 adapter (only imports from uvr/, uvr_core/)
uvr_cli/                 # click adapter (only imports from uvr/, uvr_core/)
uvr_web/                 # future; not in scope

UVR.py                   # legacy Tk; retired after Qt parity reached
```

Key boundary: anything a web UI would eventually need sits under `uvr/` or `uvr_core/`. Anything toolkit-specific sits under `uvr_qt/` / `uvr_cli/`. That boundary now exists in code: `uvr_qt/services/processing_facade.py` is a thin Qt adapter over `uvr_core`, and `uvr_cli/` consumes `uvr_core` directly.

## Current Status Snapshot

- `uvr/config/`, `uvr/domain/`, `uvr/services/processing.py`, `uvr/services/catalog.py`, `uvr/services/cache.py`, and `uvr/services/downloads.py` exist.
- `uvr_core/` exposes typed requests, typed events, and headless jobs for separation, downloads, manual ensemble, audio tools, and per-model default management.
- `uvr/runtime.py` owns backend runtime/bootstrap and path configuration, with env-var overrides for model/base paths.
- `uvr_cli/` imports from `uvr_core`/`uvr` rather than `uvr_qt`, supports `separate`, `ensemble`, `audio-tool`, `download`, `refresh-catalog`, and `config`, and supports machine-readable JSON output for listings and progress events.
- The CLI is runnable standalone via `python -m uvr_cli` and does not require `PySide6`.
- `uvr_qt/` has a runnable PySide6 shell via `python -m uvr_qt.app` with typed app state, a main window, and a facade/worker/signal layer over `uvr_core`.
- The Qt main workflow supports input/output selection, process-method/model selection, start/cancel, progress/log display, persistence through `uvr/config`, a collapsible advanced-controls panel, MDX/Demucs stem targeting, first-pass workflow-composition for Demucs pre-proc and vocal-splitter, and per-stem secondary-model assignment/scales.
- Separate Qt windows exist for download management, manual ensemble, and audio tools; non-modal dialogs exist for advanced settings, saved profiles, and model defaults.
- Persistence defaults to YAML (`data/config.yaml`) with compatibility loading from legacy `data.pkl` and one-shot migration on first read.
- Phase 5 is complete: all mainstream secondary workflows (downloads, ensemble, audio tools, model defaults, profiles, help/error dialogs) are reachable through the Qt frontend without opening `UVR.py`.
- The remaining gap before Phase 6 is that `UVR.py` and `uvr/ui/` (Tk-only modules) have not yet been deleted, and the Tk app is still the documented entry point.

## Roadmap

The phases below are ordered by dependency, not by calendar. Each phase has an explicit exit criterion so we can tell whether it's done.

### Phase 0 — Baseline (done)

- Extracted domain (`ModelData`, `Ensembler`, `AudioTools`) with typed settings.
- Typed `AppSettings` + persistence.
- `ProcessingController` extracted from `MainWindow`.
- First Qt shell + processing façade.
- CLI skeleton (`uvr_cli/`) covering single-model separation.

**Exit:** the Tk app still runs and a CLI smoke-separation works through the façade. (Done.)

### Phase 1 — Promote the façade to `uvr_core/` (done)

Move the framework-neutral boundary out from under `uvr_qt/` so the CLI doesn't depend on a Qt package.

- Create `uvr_core/` with `requests.py`, `events.py`, `jobs.py`.
- Relocate `ProcessingFacade` → `uvr_core.jobs.SeparationJob` (or similar), keeping the same semantics.
- Replace the ad-hoc `log/progress/status` callbacks with a typed event stream (`Iterable[Event]` or a subscriber protocol) so a later web UI can serialize them.
- Move `runtime_bridge.configure_backend_runtime()` into `uvr/runtime.py` so neither adapter owns it.
- Split `AppState` into two things: a frontend-owned view model (`uvr_qt/state/`) and a backend request (`uvr_core.requests.SeparationRequest`). The CLI constructs requests directly; the Qt app derives them from `AppState`.

**Exit:** `uvr_cli` imports nothing from `uvr_qt`; `uvr_qt` imports nothing from `uvr_cli`; both import from `uvr_core` and `uvr/`. (Done.)

### Phase 2 — Extract remaining services from `UVR.py` (done)

The Tk app still holds three capabilities the Qt/CLI adapters need:

1. **Downloads service** — online metadata refresh, VIP code validation, download queue, progress. Target: `uvr/services/downloads.py` with event-based progress.
2. **Cache service** — source-cache lookup, invalidation, model/source mapping. Target: `uvr/services/cache.py`.
3. **Model catalog service** — discovery + name mapping (currently split between `runtime_bridge.discover_models` and raw JSON loads). Target: `uvr/services/catalog.py`.

Each service gets a typed interface and no Tk imports. `UVR.py` switches to delegating into them; `uvr_core` wraps them in job types where needed (`DownloadJob`, etc.).

Current progress:

- `uvr/services/catalog.py` exists and is used by `uvr_core.jobs.SeparationJob` for installed-model discovery and name mapping.
- `uvr/services/cache.py` exists and is used by `uvr_core.jobs.SeparationJob` for cached-source callbacks.
- `uvr/services/downloads.py` exists and covers online metadata refresh, VIP validation, download catalog building, download plan resolution, model-settings refresh, and file download execution.
- `uvr_core.jobs.DownloadJob` now exposes a headless download surface with typed requests/results and event-based progress, so adapters can consume downloads without importing `UVR.py`.
- `UVR.py` now delegates backend download logic into `uvr/services/downloads.py`, but still owns Tk thread management, button state, and popup/menu orchestration for downloads.

**Exit:** the three services are reachable from a headless Python session without importing `UVR.py`. (Done.)

### Phase 3 — CLI parity with "mainstream" workflows (done)

Grow `uvr_cli` from single-model separation to cover what most users actually do:

- `uvr-cli ensemble` — drive `uvr_core` ensemble jobs.
- `uvr-cli audio-tool <align|pitch|manual-ensemble|...>` — thin wrappers over `AudioTools`.
- `uvr-cli download <model>` / `uvr-cli refresh-catalog` — downloads service.
- `uvr-cli config show|set` — manipulate persisted settings headlessly.
- Machine-readable output: `--json` for `list-*`, `--progress=json` for jobs so it composes with other tools/CI.

**Exit:** a new user with only the CLI and `./models/` can run every job type the Tk app offers except the advanced popup-driven tweaks. (Done.)

### Phase 4 — PySide6 main window (first release)

Matches the existing `pyside6-from-scratch-plan.md` Phase C/D scope, now built on `uvr_core`:

- Main workflow (input/output/method/model/run/cancel/log/progress).
- Advanced settings panels for VR, Demucs, MDX.
- Persistence wiring through `uvr/config/`.
- Cancellation routed through the job event stream, not widget state.

The advantage of doing this after Phases 1–3: the Qt frontend only consumes the same `uvr_core` that the CLI already exercises, so regressions show up earlier and cheaper.

Current progress:

- `uvr_qt/state/app_state.py` now holds typed path/model/output/processing/runtime state plus typed advanced model controls.
- `uvr_qt/ui/main_window.py` now supports the primary separation shell: input/output selection, model reloading, output/tuning controls, processing progress/logs, and cancellation.
- `uvr_core.jobs.SeparationJob` now supports cancellation and auxiliary-model resolution for the Qt adapter.
- The Qt advanced panel now covers VR/MDX/Demucs numeric controls, MDX/Demucs stem selection, and first-pass workflow composition for Demucs pre-proc and vocal-splitter selection.
- The Qt advanced panel now also exposes typed per-stem secondary-model assignment and secondary scales for VR, MDX, and Demucs workflows, backed by `uvr_core` resolver hooks instead of Tk callbacks.
- The shared backend and Qt shell now validate the common Demucs/MDX composition rules needed for the first release, including model-specific stem targeting plus Demucs pre-proc/vocal-splitter guardrails.
- `uvr_qt/ui/download_manager_window.py` now provides a separate download-manager window wired to the shared download/catalog job surface.

Phase 4 exit status:

- the first-release Qt app now covers the primary separation workflow without reading from `UVR.py`
- rarer popup-era composition variants and combine-stem permutations remain deferred to later Qt phases rather than blocking the Phase 4 handoff

**Exit:** Qt app replaces Tk for the primary separation workflow without reading from `UVR.py`.

### Phase 5 — PySide6 secondary features

- Download manager panel on top of `uvr/services/downloads.py`.
- Model/default editors on top of `uvr/domain/model_data.py` + settings.
- Ensemble helpers, saved settings profiles, help/about/error dialogs.
- Audio-tool panels.

Design note: less-frequently-used features are intentionally kept out of the main window. They live in separate `QMainWindow` instances (ensemble, audio tools, downloads) or non-modal `QDialog` instances (advanced settings, profiles, model defaults), opened from the Tools menu and reused on repeated invocations.

Current progress:

- **Download manager** — done: `uvr_qt/ui/download_manager_window.py`, a separate window for catalog refresh and model downloads on top of `uvr_core.jobs.DownloadJob`.
- **Help / about / error dialogs** — done: quick-start, about, and detailed error dialogs in `uvr_qt/ui/dialogs/info_dialogs.py`; wired into the main window Help menu.
- **Saved settings profiles** — done: `uvr/config/profiles.py` (backend store) + `uvr_qt/ui/dialogs/profiles_dialog.py` (non-modal Qt dialog); reachable from Tools → Manage Profiles.
- **Manual ensemble** — done: `uvr_qt/ui/ensemble_window.py`, a separate window with input-file list, algorithm/format/flag controls, output folder, and progress/log display; backed by `EnsembleFacade` → `uvr_core.jobs.EnsembleJob`. Reachable from Tools → Manual Ensemble.
- **Audio tools** — done: `uvr_qt/ui/audio_tools_window.py`, a separate window with a top tool-selector and per-tool settings groups that show/hide (Align Inputs, Matchering, Time Stretch, Change Pitch, Manual Ensemble); backed by `AudioToolFacade` → `uvr_core.jobs.AudioToolJob`. Reachable from Tools → Audio Tools.
- **Model defaults editor** — done: `uvr_qt/ui/dialogs/model_defaults_dialog.py`, a non-modal dialog that saves or deletes per-model default parameters (VR and MDX architectures) via two new backend methods — `SeparationJob.save_model_defaults()` and `SeparationJob.delete_model_defaults()` — which write/remove the model's hash-keyed JSON file. Reachable from Tools → Model Defaults.
- **Supporting infrastructure** — `uvr_qt/services/tool_facades.py` (`EnsembleFacade`, `AudioToolFacade`) and `uvr_qt/ui/tool_workers.py` (`EnsembleWorker`, `AudioToolWorker`) follow the same facade/worker/signal pattern established in Phases 3–4.

**Exit:** Tk `UVR.py` is no longer needed for any supported workflow.

### Phase 6 — Retire Tk

- Delete `UVR.py` and `uvr/ui/` (Tk-only modules).
- Finish the persistence migration off raw pickle. The repo now defaults to YAML-backed `data/config.yaml` with compatibility loading from legacy `data.pkl`, but the Tk shell and docs still need to be fully normalized around the new format.
- Mark `uvr_core` as stable; document the public surface.

**Exit:** a fresh clone of the repo contains no `tkinter` imports.

### Phase 7 (out of scope, called out for shape) — Web UI readiness

Not implemented in this project, but the architecture should support it trivially:

- `uvr_core.jobs` events are already JSON-serializable.
- A FastAPI/Starlette layer under `uvr_web/` would subscribe to the event stream and push via SSE/WebSocket.
- No backend change should be required — if a web UI requires backend changes, that is a signal we broke the boundary in an earlier phase.

## Sequencing Rationale

- **Phases 1 and 2 are prerequisites for everything else.** Those backend boundary phases are complete enough for adapter work: the shared CLI now exercises downloads, catalog, config, ensemble, audio-tool, and separation paths without importing Qt.
- **Phase 3 before Phase 4.** That sequencing paid off: the CLI now stress-tests the shared request/event/job surface before the PySide6 main-window work begins.
- **Phases 4 and 5 can overlap** once Phase 3 has validated the event/request surface.
- **Phase 6 is gated on Phase 5.** Do not delete `UVR.py` until the Qt app covers the flows its users depend on.

## Risks and Challenges

### 1. Residual `UVR.py` composition coupling

`ProcessingController`, `Ensembler`, `AudioTools`, and `ModelData` resolvers still receive runtime-bound callbacks that originate in `UVR.py`. Moving them into `uvr_core/` means replacing those with explicit constructor parameters or registered services.

- **Risk:** silent behavior drift if a resolver happens to mutate Tk state as a side effect.
- **Mitigation:** add backend-level tests (see `pyside6-testing-plan.md`) against the façade before moving it.

### 2. `separate.py` is still monolithic

`separate.py` (1.4k lines) holds `SeperateVR/MDX/MDXC/Demucs`. It's the heaviest piece of logic and is currently imported after `configure_backend_runtime()` mutates `os.chdir` and a `SimpleNamespace`. Refactoring this later is easy to underestimate.

- **Risk:** `uvr_core` appears clean but transitively depends on `os.chdir` side effects.
- **Mitigation:** fold the runtime setup into an explicit `Backend` object passed to `separate.*`, or an `@contextmanager` scope. Do this no later than Phase 2.

### 3. Event model design lock-in

Whatever event schema `uvr_core/events.py` ships with will be what a future web UI serializes. Getting it wrong is expensive later.

- **Risk:** over-fitting the schema to current Qt/CLI needs; missing fields (e.g. structured error codes, per-stage timing) that a web UI would want.
- **Mitigation:** sketch a JSON form of the event stream before Phase 1 is locked; make events dataclasses with `to_dict()` and explicit type discriminators.

### 4. Persistence migration and compatibility

`data.pkl` is a raw pickle of a dict. Any change to `DEFAULT_DATA` or Python version can break it.

- **Risk:** a GUI/CLI that reads `data.pkl` may load arbitrary attacker-controlled objects if the file is shared.
- **Mitigation:** the codebase now defaults to YAML-backed `data/config.yaml` and can migrate legacy pickle settings on read; the remaining work is to finish normalizing the surrounding UX/docs and eventually remove pickle compatibility when it is safe to do so.

### 5. Cancellation and concurrency

Tk's current cancel path relies on `is_process_stopped` flags read from widget callbacks. A headless/CLI cancel needs the same plumbing via `uvr_core`.

- **Risk:** CLI users can't `Ctrl+C` a long Demucs run cleanly; partial outputs left behind.
- **Mitigation:** make the Job an object with a `.cancel()` method backed by a `threading.Event`; document cleanup semantics (delete partial outputs or keep them).

### 6. GPU lifecycle assumptions

`clear_gpu_cache()` is called between files in the façade. A web UI running many concurrent jobs can't share that assumption.

- **Risk:** `uvr_core` silently assumes single-job-at-a-time execution.
- **Mitigation:** document the assumption on `uvr_core.jobs`; defer multi-job support to the web phase, but do not write code that makes it impossible.

### 7. Scope creep on the Tk side

The Tk UI has many popups and legacy audio-tool corners. It's tempting to preserve every one. `pyside6-from-scratch-plan.md` already calls this out; the same applies to CLI surface.

- **Risk:** the rewrite stalls chasing Tk parity on rarely-used features.
- **Mitigation:** explicit non-goals per phase; keep the Tk app runnable until Phase 6.

### 8. Model file layout coupling

`runtime_bridge.py` hardcodes `./models/VR_Models`, `./models/MDX_Net_Models`, etc. A future web deployment (or a CLI run from elsewhere) needs this to be configurable.

- **Risk:** users assume `uvr-cli` can run from any working directory; today it `os.chdir`'s to the repo root.
- **Mitigation:** Phase 1 should introduce a `Paths` config object with sensible env-var overrides.

### 9. Tests lag behind architecture

Test coverage today is thin. Moving code without tests is how behavior drift creeps in.

- **Risk:** each phase ships "working" code that subtly regresses an edge case.
- **Mitigation:** before each phase, add the relevant tests from `pyside6-testing-plan.md` — state round-trip, façade golden-file smoke tests, then event-stream tests once Phase 1 lands.

## What "Done" Looks Like

A successful outcome of this roadmap leaves the repo with:

- a `uvr/` + `uvr_core/` backend that runs without any GUI toolkit imported;
- a PySide6 app and a click CLI that are roughly symmetric in feature coverage and share the same job/event types;
- no `tkinter` imports;
- a persistence format that isn't raw pickle;
- enough test coverage on the backend boundary that adding a web UI later is an integration task, not an architectural one.
