from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gui_data.constants import DEFAULT_DATA, VR_ARCH_PM
from uvr.config.models import AppSettings
from uvr.runtime import RuntimePaths, build_runtime_paths
from uvr.services.cache import SourceCache
from uvr.services.catalog import ModelCatalog, discover_models, list_installed_models
from uvr.services.downloads import (
    build_download_catalog,
    execute_download_plan,
    load_or_fetch_model_settings,
    resolve_download_plan,
    validate_vip_code,
)
from uvr_core.events import DownloadResultEvent, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import DownloadJob, ResolvedModel, SeparationJob
from uvr_core.requests import DownloadRequest, SeparationRequest
from uvr_qt.state.app_state import (
    AppState,
    ModelSelectionState,
    OutputSettingsState,
    PathsState,
    ProcessingSettingsState,
)


class RuntimePathsTests(unittest.TestCase):
    def test_build_runtime_paths_respects_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            custom_base = tmp_path / "repo"
            custom_models = tmp_path / "alt-models"

            with mock.patch.dict(
                os.environ,
                {"UVR_BASE_PATH": str(custom_base), "UVR_MODELS_DIR": str(custom_models)},
                clear=False,
            ):
                paths = build_runtime_paths()

            self.assertEqual(paths.base_path, custom_base.resolve())
            self.assertEqual(paths.models_dir, custom_models.resolve())
            self.assertEqual(paths.vr_models_dir, custom_models.resolve() / "VR_Models")
            self.assertEqual(paths.mdx_model_name_select, custom_models.resolve() / "MDX_Net_Models" / "model_data" / "model_name_mapper.json")


class CatalogServiceTests(unittest.TestCase):
    def test_discover_models_handles_ckpt_names_and_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "alpha.onnx").write_bytes(b"")
            (tmp_path / "beta.ckpt").write_bytes(b"")
            (tmp_path / "ignore.txt").write_text("x")

            self.assertEqual(discover_models(tmp_path, (".onnx", ".ckpt")), ("alpha", "beta"))
            self.assertEqual(discover_models(tmp_path, (".onnx", ".ckpt"), is_mdxnet=True), ("alpha", "beta.ckpt"))

    def test_list_installed_models_uses_catalog_remapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            models_dir = tmp_path / "models"
            vr_dir = models_dir / "VR_Models"
            mdx_dir = models_dir / "MDX_Net_Models"
            demucs_dir = models_dir / "Demucs_Models"
            newer_demucs_dir = demucs_dir / "v3_v4_repo"
            vr_hash_dir = vr_dir / "model_data"
            mdx_hash_dir = mdx_dir / "model_data"

            for path in (vr_dir, mdx_dir, demucs_dir, newer_demucs_dir, vr_hash_dir, mdx_hash_dir):
                path.mkdir(parents=True, exist_ok=True)

            (vr_dir / "vr_a.pth").write_bytes(b"")
            (mdx_dir / "mapped_mdx.onnx").write_bytes(b"")
            (demucs_dir / "legacy.th").write_bytes(b"")
            (newer_demucs_dir / "repo_model.yaml").write_text("name: repo")

            paths = RuntimePaths(
                base_path=tmp_path,
                models_dir=models_dir,
                vr_models_dir=vr_dir,
                mdx_models_dir=mdx_dir,
                demucs_models_dir=demucs_dir,
                demucs_newer_repo_dir=newer_demucs_dir,
                vr_hash_dir=vr_hash_dir,
                mdx_hash_dir=mdx_hash_dir,
                mdx_c_config_path=mdx_hash_dir / "mdx_c_configs",
                vr_param_dir=tmp_path / "lib_v5" / "vr_network" / "modelparams",
                mdx_mixer_path=tmp_path / "lib_v5" / "mixer.ckpt",
                denoiser_model_path=vr_dir / "UVR-DeNoise-Lite.pth",
                deverber_model_path=vr_dir / "UVR-DeEcho-DeReverb.pth",
                vr_hash_json=vr_hash_dir / "model_data.json",
                mdx_hash_json=mdx_hash_dir / "model_data.json",
                mdx_model_name_select=mdx_dir / "model_data" / "model_name_mapper.json",
                demucs_model_name_select=demucs_dir / "model_data" / "model_name_mapper.json",
            )
            catalog = ModelCatalog(
                vr_hash_mapper={},
                mdx_hash_mapper={},
                mdx_name_select_mapper={"mapped_mdx": "Pretty MDX"},
                demucs_name_select_mapper={"repo_model": "Pretty Demucs"},
            )

            models = list_installed_models(catalog, paths)
            summary = {(model.process_method, model.model_name, model.source) for model in models}

            self.assertIn(("VR Architecture", "vr_a", "vr"), summary)
            self.assertIn(("MDX-Net", "Pretty MDX", "mdx"), summary)
            self.assertIn(("Demucs", "legacy", "demucs"), summary)
            self.assertIn(("Demucs", "Pretty Demucs", "demucs"), summary)


class CacheServiceTests(unittest.TestCase):
    def test_source_cache_put_get_and_clear(self) -> None:
        cache = SourceCache()

        cache.put("VR Architecture", ("mix", "sources"), "Model A")
        model_name, sources = cache.get("VR Architecture", "Model A")

        self.assertEqual(model_name, "Model A")
        self.assertEqual(sources, ("mix", "sources"))

        cache.clear()
        self.assertEqual(cache.get("VR Architecture", "Model A"), (None, None))

    def test_source_cache_compatibility_callbacks_match_substring_lookup(self) -> None:
        cache = SourceCache()

        cache.cached_model_source_holder("MDX-Net", {"vocals": [1]}, "UVR-MDX-NET Main")

        model_name, sources = cache.cached_source_callback("MDX-Net", "MDX-NET Main")

        self.assertEqual(model_name, "UVR-MDX-NET Main")
        self.assertEqual(sources, {"vocals": [1]})


class DownloadServiceTests(unittest.TestCase):
    def test_validate_vip_code_rejects_invalid_code(self) -> None:
        self.assertEqual(validate_vip_code("definitely-wrong"), "incorrect_code")

    def test_resolve_download_plan_handles_mdx_and_multi_file_demucs(self) -> None:
        catalog = build_download_catalog(
            {
                "vr_download_list": {"VR One": "vr_one.pth"},
                "mdx_download_list": {"MDX One": "mdx_one.onnx"},
                "mdx23c_download_list": {"MDX23 One": {"mdx23.ckpt": "model.yaml"}},
                "demucs_download_list": {
                    "Demucs v4: htdemucs": {
                        "a.th": "https://example.invalid/a.th",
                        "b.yaml": "https://example.invalid/b.yaml",
                    }
                },
            }
        )

        mdx_plan = resolve_download_plan("MDX23 One", "MDX-Net", catalog)
        demucs_plan = resolve_download_plan("Demucs v4: htdemucs", "Demucs", catalog)

        self.assertEqual(mdx_plan.tasks[0].destination.name, "mdx23.ckpt")
        self.assertEqual(len(demucs_plan.tasks), 2)
        self.assertTrue(all(task.destination.name in {"a.th", "b.yaml"} for task in demucs_plan.tasks))

    def test_execute_download_plan_and_model_settings_fallback(self) -> None:
        class FakeResponse(io.BytesIO):
            def __init__(self, payload: bytes):
                super().__init__(payload)
                self.headers = {"Content-Length": str(len(payload))}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()
                return False

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            models_dir = tmp_path / "models"
            vr_dir = models_dir / "VR_Models"
            mdx_dir = models_dir / "MDX_Net_Models"
            demucs_dir = models_dir / "Demucs_Models"
            newer_demucs_dir = demucs_dir / "v3_v4_repo"
            vr_hash_dir = vr_dir / "model_data"
            mdx_hash_dir = mdx_dir / "model_data"

            for path in (vr_dir, mdx_dir, demucs_dir, newer_demucs_dir, vr_hash_dir, mdx_hash_dir, mdx_dir / "model_data", demucs_dir / "model_data"):
                path.mkdir(parents=True, exist_ok=True)

            (vr_hash_dir / "model_data.json").write_text("{}")
            (mdx_hash_dir / "model_data.json").write_text("{}")
            (mdx_dir / "model_data" / "model_name_mapper.json").write_text("{}")
            (demucs_dir / "model_data" / "model_name_mapper.json").write_text("{}")

            paths = RuntimePaths(
                base_path=tmp_path,
                models_dir=models_dir,
                vr_models_dir=vr_dir,
                mdx_models_dir=mdx_dir,
                demucs_models_dir=demucs_dir,
                demucs_newer_repo_dir=newer_demucs_dir,
                vr_hash_dir=vr_hash_dir,
                mdx_hash_dir=mdx_hash_dir,
                mdx_c_config_path=mdx_hash_dir / "mdx_c_configs",
                vr_param_dir=tmp_path / "lib_v5" / "vr_network" / "modelparams",
                mdx_mixer_path=tmp_path / "lib_v5" / "mixer.ckpt",
                denoiser_model_path=vr_dir / "UVR-DeNoise-Lite.pth",
                deverber_model_path=vr_dir / "UVR-DeEcho-DeReverb.pth",
                vr_hash_json=vr_hash_dir / "model_data.json",
                mdx_hash_json=mdx_hash_dir / "model_data.json",
                mdx_model_name_select=mdx_dir / "model_data" / "model_name_mapper.json",
                demucs_model_name_select=demucs_dir / "model_data" / "model_name_mapper.json",
            )

            plan = SimpleNamespace(
                tasks=(SimpleNamespace(name="file", url="https://example.invalid/file.bin", destination=tmp_path / "file.bin"),)
            )

            progress_calls = []
            result = execute_download_plan(
                plan,
                opener=lambda _url: FakeResponse(b"payload"),
                progress=lambda *args: progress_calls.append(args),
            )
            self.assertEqual(result.completed, (tmp_path / "file.bin",))
            self.assertTrue(progress_calls)
            self.assertEqual((tmp_path / "file.bin").read_bytes(), b"payload")

            bundle = load_or_fetch_model_settings(
                paths=paths,
                opener=lambda _url: (_ for _ in ()).throw(RuntimeError("offline")),
            )
            self.assertEqual(bundle.vr_hash_mapper, {})
            self.assertEqual(bundle.mdx_name_select_mapper, {})

    def test_download_job_exposes_headless_catalog_and_execution(self) -> None:
        class FakeResponse(io.BytesIO):
            def __init__(self, payload: bytes):
                super().__init__(payload)
                self.headers = {"Content-Length": str(len(payload))}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()
                return False

        def json_bytes(payload: object) -> bytes:
            return json.dumps(payload).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            models_dir = tmp_path / "models"
            vr_dir = models_dir / "VR_Models"
            mdx_dir = models_dir / "MDX_Net_Models"
            demucs_dir = models_dir / "Demucs_Models"
            newer_demucs_dir = demucs_dir / "v3_v4_repo"
            vr_hash_dir = vr_dir / "model_data"
            mdx_hash_dir = mdx_dir / "model_data"
            demucs_hash_dir = demucs_dir / "model_data"

            for path in (
                vr_dir,
                mdx_dir,
                demucs_dir,
                newer_demucs_dir,
                vr_hash_dir,
                mdx_hash_dir,
                demucs_hash_dir,
                mdx_hash_dir / "mdx_c_configs",
            ):
                path.mkdir(parents=True, exist_ok=True)

            (vr_hash_dir / "model_data.json").write_text("{}")
            (mdx_hash_dir / "model_data.json").write_text("{}")
            (mdx_dir / "model_data" / "model_name_mapper.json").write_text("{}")
            (demucs_dir / "model_data" / "model_name_mapper.json").write_text("{}")

            paths = RuntimePaths(
                base_path=tmp_path,
                models_dir=models_dir,
                vr_models_dir=vr_dir,
                mdx_models_dir=mdx_dir,
                demucs_models_dir=demucs_dir,
                demucs_newer_repo_dir=newer_demucs_dir,
                vr_hash_dir=vr_hash_dir,
                mdx_hash_dir=mdx_hash_dir,
                mdx_c_config_path=mdx_hash_dir / "mdx_c_configs",
                vr_param_dir=tmp_path / "lib_v5" / "vr_network" / "modelparams",
                mdx_mixer_path=tmp_path / "lib_v5" / "mixer.ckpt",
                denoiser_model_path=vr_dir / "UVR-DeNoise-Lite.pth",
                deverber_model_path=vr_dir / "UVR-DeEcho-DeReverb.pth",
                vr_hash_json=vr_hash_dir / "model_data.json",
                mdx_hash_json=mdx_hash_dir / "model_data.json",
                mdx_model_name_select=mdx_dir / "model_data" / "model_name_mapper.json",
                demucs_model_name_select=demucs_dir / "model_data" / "model_name_mapper.json",
            )

            online_payload = {
                "vr_download_list": {"VR One": "vr_one.pth"},
                "mdx_download_list": {},
                "mdx23c_download_list": {},
                "demucs_download_list": {},
            }

            def opener(url: str):
                if url.endswith("download_checks.json"):
                    return FakeResponse(json_bytes(online_payload))
                if url.endswith("bulletin.txt"):
                    return FakeResponse(b"bulletin")
                if url.endswith("vr_one.pth"):
                    return FakeResponse(b"model")
                raise AssertionError(f"unexpected url {url}")

            job = DownloadJob(paths=paths, opener=opener)
            available = job.available_downloads()

            self.assertEqual(available.bulletin, "bulletin")
            self.assertEqual(available.vr_items, ("VR One",))

            events = []
            result = job.run(
                DownloadRequest(model_type=VR_ARCH_PM, selection="VR One", refresh_model_settings=False),
                subscriber=events.append,
            )

            self.assertEqual(result.completed_files, (str(vr_dir / "vr_one.pth"),))
            self.assertTrue((vr_dir / "vr_one.pth").is_file())
            self.assertTrue(any(isinstance(event, ProgressEvent) for event in events))
            self.assertTrue(any(isinstance(event, DownloadResultEvent) for event in events))


class AppStateConversionTests(unittest.TestCase):
    def test_app_state_converts_to_separation_request(self) -> None:
        state = AppState(
            paths=PathsState(
                input_paths=("input.wav",),
                export_path="out",
                last_directory="/tmp",
            ),
            models=ModelSelectionState(
                vr_model="vr model",
                mdx_net_model="mdx model",
                demucs_model="demucs model",
                demucs_pre_proc_model="pre",
                vocal_splitter_model="splitter",
                demucs_stems="All Stems",
                mdx_stems="All Stems",
                secondary_models={"vr_voc_inst_secondary_model": "secondary"},
            ),
            output=OutputSettingsState(
                save_format="WAV",
                wav_type="PCM_16",
                mp3_bitrate="320k",
                add_model_name=True,
                create_model_folder=False,
            ),
            processing=ProcessingSettingsState(
                process_method="VR Architecture",
                audio_tool="",
                algorithm="",
                device="DEFAULT",
                use_gpu=True,
                primary_stem_only=False,
                secondary_stem_only=False,
                normalize_output=True,
                wav_ensemble=False,
                testing_audio=False,
                model_sample_mode=False,
                model_sample_duration=30,
            ),
            extra_settings={"custom": "value"},
        )

        request = state.to_separation_request()

        self.assertEqual(request.input_paths, ("input.wav",))
        self.assertEqual(request.export_path, "out")
        self.assertEqual(request.models.vr_model, "vr model")
        self.assertEqual(request.output.save_format, "WAV")
        self.assertTrue(request.options.use_gpu)
        self.assertEqual(request.extra_settings["custom"], "value")

    def test_separation_request_from_settings_preserves_extra_values(self) -> None:
        data = dict(DEFAULT_DATA)
        data.update(
            {
                "input_paths": ["track.wav"],
                "export_path": "exports",
                "vr_model": "vr model",
                "custom_flag": "present",
            }
        )
        settings = AppSettings.from_legacy_dict(data, DEFAULT_DATA)

        request = SeparationRequest.from_settings(settings)

        self.assertEqual(request.input_paths, ("track.wav",))
        self.assertEqual(request.export_path, "exports")
        self.assertEqual(request.models.vr_model, "vr model")
        self.assertEqual(request.extra_settings["custom_flag"], "present")


class EventTests(unittest.TestCase):
    def test_events_are_serializable_dicts(self) -> None:
        self.assertEqual(LogEvent(message="hello").to_dict()["event_type"], "log")
        self.assertEqual(StatusEvent(message="working").to_dict()["message"], "working")
        self.assertEqual(ProgressEvent(percent=50.0, current_file=1, total_files=2).to_dict()["percent"], 50.0)
        self.assertEqual(ResultEvent((), "out", "VR", "model", "vr").to_dict()["source"], "vr")


class SeparationJobTests(unittest.TestCase):
    def test_run_emits_expected_sanity_events(self) -> None:
        job = SeparationJob()
        events = []

        class FakeSeparator:
            def __init__(self, process_data: dict[str, object]):
                self.process_data = process_data

            def seperate(self) -> None:
                self.process_data["write_to_console"]("inner log")
                self.process_data["set_progress_bar"](0.5)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.wav"
            output_path = tmp_path / "out"
            input_path.write_bytes(b"fake")

            request = SeparationRequest(
                input_paths=(str(input_path),),
                export_path=str(output_path),
                models=SimpleNamespace(
                    vr_model="Fake Model",
                    mdx_net_model="",
                    demucs_model="",
                    demucs_pre_proc_model="",
                    vocal_splitter_model="",
                    demucs_stems="All Stems",
                    mdx_stems="All Stems",
                    secondary_models={},
                ),
                output=SimpleNamespace(
                    save_format="WAV",
                    wav_type="PCM_16",
                    mp3_bitrate="320k",
                    add_model_name=False,
                    create_model_folder=False,
                ),
                options=SimpleNamespace(
                    process_method="VR Architecture",
                    audio_tool="",
                    algorithm="",
                    device="DEFAULT",
                    use_gpu=False,
                    primary_stem_only=False,
                    secondary_stem_only=False,
                    normalize_output=False,
                    wav_ensemble=False,
                    testing_audio=False,
                    model_sample_mode=False,
                    model_sample_duration=30,
                ),
                extra_settings={},
            )

            fake_model = SimpleNamespace(
                model_status=True,
                model_basename="fake_model",
                process_method="VR Architecture",
                is_mdx_c=False,
            )

            with mock.patch.object(
                job,
                "resolve_model",
                return_value=ResolvedModel("VR Architecture", "Fake Model", "vr"),
            ), mock.patch.object(
                job,
                "_build_model",
                return_value=fake_model,
            ), mock.patch.object(
                job,
                "_create_separator",
                side_effect=lambda _model, process_data: FakeSeparator(process_data),
            ), mock.patch(
                "uvr_core.jobs.clear_gpu_cache"
            ):
                result = job.run(request, subscriber=events.append)

        self.assertEqual(result.processed_files, (str(input_path),))
        self.assertTrue(any(isinstance(event, StatusEvent) and event.message == "Completed" for event in events))
        self.assertTrue(any(isinstance(event, LogEvent) and event.message == "inner log" for event in events))
        self.assertTrue(any(isinstance(event, ProgressEvent) and event.percent == 50.0 for event in events))
        self.assertIsInstance(events[-1], ResultEvent)


if __name__ == "__main__":
    unittest.main()
