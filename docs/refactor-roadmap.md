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
6. Backwards compatibility with the legacy `data.pkl` is preserved until the Qt frontend ships; after that, a migration utility can replace it.

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

Key boundary: anything a web UI would eventually need sits under `uvr/` or `uvr_core/`. Anything toolkit-specific sits under `uvr_qt/` / `uvr_cli/`. The current `uvr_qt/services/processing_facade.py` is a good first draft of `uvr_core` but needs to move out of `uvr_qt/`.

## Current Status Snapshot

- `uvr/config/`, `uvr/domain/`, and `uvr/services/processing.py` exist and are in active use from `UVR.py`.
- `ProcessingController` still depends on the `MainWindow` UI surface (see `uvr-py-refactor-plan.md` §Pre-PySide6 Stabilization Pass).
- `uvr_qt/services/processing_facade.py` provides a framework-neutral `.process(state, log, progress, status)` entry point — this is the seam both Qt and CLI currently use.
- `uvr_cli/` exists with click-based `list-methods`, `list-models`, `separate` commands driven by that facade.
- Downloads, cache, ensemble orchestration, and audio-tool flows are still `UVR.py`-bound.

## Roadmap

The phases below are ordered by dependency, not by calendar. Each phase has an explicit exit criterion so we can tell whether it's done.

### Phase 0 — Baseline (done)

- Extracted domain (`ModelData`, `Ensembler`, `AudioTools`) with typed settings.
- Typed `AppSettings` + persistence.
- `ProcessingController` extracted from `MainWindow`.
- First Qt shell + processing façade.
- CLI skeleton (`uvr_cli/`) covering single-model separation.

**Exit:** the Tk app still runs and a CLI smoke-separation works through the façade. (Current state.)

### Phase 1 — Promote the façade to `uvr_core/`

Move the framework-neutral boundary out from under `uvr_qt/` so the CLI doesn't depend on a Qt package.

- Create `uvr_core/` with `requests.py`, `events.py`, `jobs.py`.
- Relocate `ProcessingFacade` → `uvr_core.jobs.SeparationJob` (or similar), keeping the same semantics.
- Replace the ad-hoc `log/progress/status` callbacks with a typed event stream (`Iterable[Event]` or a subscriber protocol) so a later web UI can serialize them.
- Move `runtime_bridge.configure_backend_runtime()` into `uvr/runtime.py` so neither adapter owns it.
- Split `AppState` into two things: a frontend-owned view model (`uvr_qt/state/`) and a backend request (`uvr_core.requests.SeparationRequest`). The CLI constructs requests directly; the Qt app derives them from `AppState`.

**Exit:** `uvr_cli` imports nothing from `uvr_qt`; `uvr_qt` imports nothing from `uvr_cli`; both import from `uvr_core` and `uvr/`.

### Phase 2 — Extract remaining services from `UVR.py`

The Tk app still holds three capabilities the Qt/CLI adapters need:

1. **Downloads service** — online metadata refresh, VIP code validation, download queue, progress. Target: `uvr/services/downloads.py` with event-based progress.
2. **Cache service** — source-cache lookup, invalidation, model/source mapping. Target: `uvr/services/cache.py`.
3. **Model catalog service** — discovery + name mapping (currently split between `runtime_bridge.discover_models` and raw JSON loads). Target: `uvr/services/catalog.py`.

Each service gets a typed interface and no Tk imports. `UVR.py` switches to delegating into them; `uvr_core` wraps them in job types where needed (`DownloadJob`, etc.).

**Exit:** the three services are reachable from a headless Python session without importing `UVR.py`.

### Phase 3 — CLI parity with "mainstream" workflows

Grow `uvr_cli` from single-model separation to cover what most users actually do:

- `uvr-cli ensemble` — drive `uvr_core` ensemble jobs.
- `uvr-cli audio-tool <align|pitch|manual-ensemble|...>` — thin wrappers over `AudioTools`.
- `uvr-cli download <model>` / `uvr-cli refresh-catalog` — downloads service.
- `uvr-cli config show|set` — manipulate persisted settings headlessly.
- Machine-readable output: `--json` for `list-*`, `--progress=json` for jobs so it composes with other tools/CI.

**Exit:** a new user with only the CLI and `./models/` can run every job type the Tk app offers except the advanced popup-driven tweaks.

### Phase 4 — PySide6 main window (first release)

Matches the existing `pyside6-from-scratch-plan.md` Phase C/D scope, now built on `uvr_core`:

- Main workflow (input/output/method/model/run/cancel/log/progress).
- Advanced settings panels for VR, Demucs, MDX.
- Persistence wiring through `uvr/config/`.
- Cancellation routed through the job event stream, not widget state.

The advantage of doing this after Phases 1–3: the Qt frontend only consumes the same `uvr_core` that the CLI already exercises, so regressions show up earlier and cheaper.

**Exit:** Qt app replaces Tk for the primary separation workflow without reading from `UVR.py`.

### Phase 5 — PySide6 secondary features

- Download manager panel on top of `uvr/services/downloads.py`.
- Model/default editors on top of `uvr/domain/model_data.py` + settings.
- Ensemble helpers, saved settings profiles, help/about/error dialogs.
- Audio-tool panels.

**Exit:** Tk `UVR.py` is no longer needed for any supported workflow.

### Phase 6 — Retire Tk

- Delete `UVR.py` and `uvr/ui/` (Tk-only modules).
- Migrate persistence off `data.pkl` (typed JSON/TOML under `uvr/config/persistence.py`) with a one-shot migration run at first launch.
- Mark `uvr_core` as stable; document the public surface.

**Exit:** a fresh clone of the repo contains no `tkinter` imports.

### Phase 7 (out of scope, called out for shape) — Web UI readiness

Not implemented in this project, but the architecture should support it trivially:

- `uvr_core.jobs` events are already JSON-serializable.
- A FastAPI/Starlette layer under `uvr_web/` would subscribe to the event stream and push via SSE/WebSocket.
- No backend change should be required — if a web UI requires backend changes, that is a signal we broke the boundary in an earlier phase.

## Sequencing Rationale

- **Phases 1 and 2 are prerequisites for everything else.** Until the façade lives in `uvr_core/` and downloads/cache/catalog are extracted, every Qt or CLI feature accrues a backend debt.
- **Phase 3 before Phase 4.** The CLI is the cheapest way to stress the backend boundary. Bugs found while wiring the CLI are bugs the Qt frontend would have hit too, found without Qt-specific noise.
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

### 4. Pickle persistence

`data.pkl` is a raw pickle of a dict. Any change to `DEFAULT_DATA` or Python version can break it.

- **Risk:** a GUI/CLI that reads `data.pkl` may load arbitrary attacker-controlled objects if the file is shared.
- **Mitigation:** Phase 6 replaces it with a typed JSON/TOML layer; until then, treat `data.pkl` as untrusted and only read fields listed in `AppSettings`.

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
