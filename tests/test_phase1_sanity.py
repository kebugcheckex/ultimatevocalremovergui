from __future__ import annotations

import json
import io
import os
import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml
from click.testing import CliRunner
from gui_data.constants import ALIGN_INPUTS, CHANGE_PITCH, DEFAULT_DATA, MATCH_INPUTS, TIME_STRETCH, VR_ARCH_PM
from uvr.config.models import AppSettings
from uvr.config.persistence import DEFAULT_DATA_FILE, load_settings, save_settings
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
from uvr_core.events import AudioToolResultEvent, DownloadResultEvent, EnsembleResultEvent, LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import (
    AudioToolJob,
    AvailableDownloads,
    AudioToolJobResult,
    CatalogRefreshResult,
    DownloadJob,
    DownloadJobResult,
    EnsembleJob,
    JobCancelledError,
    ResolvedModel,
    SeparationJob,
)
from uvr_core.requests import AudioToolRequest, DownloadRequest, EnsembleRequest, SeparationRequest
from uvr_cli.__main__ import cli
from uvr_qt.state.app_state import (
    AdvancedModelControlsState,
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


class PersistenceTests(unittest.TestCase):
    def test_save_settings_writes_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_file = Path(tmp_dir) / "config.yaml"
            settings = AppSettings.from_legacy_dict(DEFAULT_DATA, DEFAULT_DATA)

            save_settings(settings, data_file=data_file)

            payload = yaml.safe_load(data_file.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload["save_format"], DEFAULT_DATA["save_format"])

    def test_load_settings_migrates_legacy_pickle_to_yaml_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            legacy_file = tmp_path / "data.pkl"
            legacy_payload = dict(DEFAULT_DATA)
            legacy_payload["save_format"] = "MP3"

            with legacy_file.open("wb") as handle:
                pickle.dump(legacy_payload, handle)

            with mock.patch("uvr.config.persistence.DEFAULT_DATA_FILE", tmp_path / "config.yaml"), mock.patch(
                "uvr.config.persistence.LEGACY_DATA_FILE",
                legacy_file,
            ):
                settings = load_settings(default_data=DEFAULT_DATA)

            self.assertEqual(settings.to_legacy_dict()["save_format"], "MP3")
            migrated_file = tmp_path / "config.yaml"
            self.assertTrue(migrated_file.is_file())
            migrated_payload = yaml.safe_load(migrated_file.read_text(encoding="utf-8"))
            self.assertEqual(migrated_payload["save_format"], "MP3")


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


class CliDownloadCommandTests(unittest.TestCase):
    def test_cli_module_imports_without_qt_or_pyside(self) -> None:
        script = """
import importlib
import sys

class BlockQtImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "uvr_qt" or fullname.startswith("uvr_qt."):
            raise RuntimeError(f"unexpected Qt adapter import: {fullname}")
        if fullname == "PySide6" or fullname.startswith("PySide6."):
            raise RuntimeError(f"unexpected PySide6 import: {fullname}")
        return None

sys.meta_path.insert(0, BlockQtImports())
module = importlib.import_module("uvr_cli.__main__")
sys.stdout.write(module.cli.help or "")
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": "."},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Ultimate Vocal Remover command-line interface.", result.stdout)

    def test_list_methods_supports_json_output(self) -> None:
        runner = CliRunner()
        job = mock.Mock()
        job.available_process_methods.return_value = ("VR Architecture", "MDX-Net")

        with mock.patch("uvr_cli.__main__.SeparationJob", return_value=job):
            result = runner.invoke(cli, ["list-methods", "--json"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(json.loads(result.output), {"methods": ["VR Architecture", "MDX-Net"]})

    def test_list_downloads_uses_download_job_output(self) -> None:
        runner = CliRunner()
        available = SimpleNamespace(
            bulletin="notice",
            vr_items=("VR One",),
            mdx_items=("MDX One",),
            demucs_items=(),
        )
        job = mock.Mock()
        job.available_downloads.return_value = available

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(cli, ["list-downloads"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Bulletin: notice", result.output)
        self.assertIn("VR:", result.output)
        self.assertIn("VR One", result.output)
        self.assertIn("MDX One", result.output)

    def test_list_downloads_supports_json_output(self) -> None:
        runner = CliRunner()
        available = SimpleNamespace(
            bulletin="notice",
            vr_items=("VR One",),
            mdx_items=(),
            demucs_items=("Demucs One",),
        )
        job = mock.Mock()
        job.available_downloads.return_value = available

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(cli, ["list-downloads", "--json"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            json.loads(result.output),
            {
                "bulletin": "notice",
                "downloads": {"vr": ["VR One"], "mdx": [], "demucs": ["Demucs One"]},
            },
        )

    def test_refresh_catalog_reports_summary(self) -> None:
        runner = CliRunner()
        refresh_result = SimpleNamespace(
            available_downloads=SimpleNamespace(
                bulletin="notice",
                vr_items=("VR One",),
                mdx_items=(),
                demucs_items=("Demucs One", "Demucs Two"),
            ),
            refreshed_settings=object(),
        )
        job = mock.Mock()
        job.refresh_catalog.return_value = refresh_result

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(cli, ["refresh-catalog"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Catalog refreshed.", result.output)
        self.assertIn("VR downloads available: 1", result.output)
        self.assertIn("Demucs downloads available: 2", result.output)
        self.assertIn("Model settings refreshed: yes", result.output)

    def test_refresh_catalog_supports_json_output(self) -> None:
        runner = CliRunner()
        refresh_result = SimpleNamespace(
            available_downloads=SimpleNamespace(
                bulletin="notice",
                vr_items=("VR One",),
                mdx_items=("MDX One",),
                demucs_items=(),
            ),
            refreshed_settings=None,
        )
        job = mock.Mock()
        job.refresh_catalog.return_value = refresh_result

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(cli, ["refresh-catalog", "--json", "--no-refresh-model-settings"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            json.loads(result.output),
            {
                "bulletin": "notice",
                "vr_downloads_available": 1,
                "mdx_downloads_available": 1,
                "demucs_downloads_available": 0,
                "model_settings_refreshed": False,
            },
        )

    def test_download_command_builds_download_request(self) -> None:
        runner = CliRunner()
        captured = {}
        job = mock.Mock()

        def fake_run(request, subscriber=None):
            captured["request"] = request
            if subscriber is not None:
                subscriber(StatusEvent(message="Downloading test model"))
                subscriber(ProgressEvent(percent=100.0, current_file=1, total_files=1))
            return SimpleNamespace(
                completed_files=("/tmp/model.pth",),
                skipped_existing=(),
            )

        job.run.side_effect = fake_run

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(
                cli,
                ["download", "--type", "vr", "--model", "VR One", "--no-refresh-model-settings"],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(captured["request"], DownloadRequest(model_type=VR_ARCH_PM, selection="VR One", vip_code="", refresh_model_settings=False))
        self.assertIn("Downloaded 1 file(s).", result.output)
        self.assertIn("/tmp/model.pth", result.output)

    def test_download_command_supports_json_progress(self) -> None:
        runner = CliRunner()
        job = mock.Mock()

        def fake_run(_request, subscriber=None):
            if subscriber is not None:
                subscriber(StatusEvent(message="Downloading test model"))
                subscriber(ProgressEvent(percent=50.0, current_file=1, total_files=1))
                subscriber(
                    DownloadResultEvent(
                        completed_files=("/tmp/model.pth",),
                        skipped_existing=(),
                        model_type="VR Architecture",
                        selection="VR One",
                    )
                )
            return SimpleNamespace(
                completed_files=("/tmp/model.pth",),
                skipped_existing=(),
            )

        job.run.side_effect = fake_run

        with mock.patch("uvr_cli.__main__.DownloadJob", return_value=job):
            result = runner.invoke(
                cli,
                ["download", "--type", "vr", "--model", "VR One", "--progress", "json", "--no-refresh-model-settings"],
            )

        self.assertEqual(result.exit_code, 0)
        output_lines = [json.loads(line) for line in result.output.strip().splitlines()]
        self.assertEqual(output_lines[0]["event_type"], "status")
        self.assertEqual(output_lines[1]["event_type"], "progress")
        self.assertEqual(output_lines[2]["event_type"], "download_result")


class CliConfigCommandTests(unittest.TestCase):
    def test_config_show_supports_json_output(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["config", "show", "vr_model", "--json", "--data-file", "config.pkl"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(json.loads(result.output), {"vr_model": DEFAULT_DATA["vr_model"]})

    def test_config_set_persists_boolean_value(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem():
            set_result = runner.invoke(
                cli,
                ["config", "set", "is_gpu_conversion", "true", "--data-file", "config.pkl"],
            )
            show_result = runner.invoke(
                cli,
                ["config", "show", "is_gpu_conversion", "--json", "--data-file", "config.pkl"],
            )

        self.assertEqual(set_result.exit_code, 0)
        self.assertEqual(show_result.exit_code, 0)
        self.assertEqual(json.loads(show_result.output), {"is_gpu_conversion": True})

    def test_config_set_persists_list_value_from_json(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem():
            set_result = runner.invoke(
                cli,
                ["config", "set", "input_paths", '["a.wav", "b.wav"]', "--json", "--data-file", "config.pkl"],
            )
            show_result = runner.invoke(
                cli,
                ["config", "show", "input_paths", "--json", "--data-file", "config.pkl"],
            )

        self.assertEqual(set_result.exit_code, 0)
        self.assertEqual(json.loads(set_result.output), {"input_paths": ["a.wav", "b.wav"]})
        self.assertEqual(json.loads(show_result.output), {"input_paths": ["a.wav", "b.wav"]})

    def test_config_set_rejects_unknown_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "not_a_key", "value"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("unknown config key", result.output)


class EnsembleJobTests(unittest.TestCase):
    def test_ensemble_job_runs_manual_ensemble(self) -> None:
        job = EnsembleJob()
        events = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            export_path = tmp_path / "out"
            input_a = tmp_path / "a.wav"
            input_b = tmp_path / "b.wav"
            input_a.write_bytes(b"a")
            input_b.write_bytes(b"b")

            called = {}

            class FakeEnsembler:
                def __init__(self, settings, is_manual_ensemble=False):
                    called["settings"] = settings
                    called["is_manual_ensemble"] = is_manual_ensemble

                def ensemble_manual(self, audio_inputs, audio_file_base):
                    called["audio_inputs"] = tuple(audio_inputs)
                    called["audio_file_base"] = audio_file_base

            with mock.patch("uvr_core.jobs.Ensembler", FakeEnsembler):
                result = job.run(
                    EnsembleRequest(
                        input_paths=(str(input_a), str(input_b)),
                        export_path=str(export_path),
                        algorithm="Average",
                        output_name="Mix",
                    ),
                    subscriber=events.append,
                )

        self.assertEqual(result.algorithm, "Average")
        self.assertTrue(result.output_path.endswith("Mix_(Average).wav"))
        self.assertEqual(called["audio_inputs"], (str(input_a), str(input_b)))
        self.assertEqual(called["audio_file_base"], "Mix")
        self.assertTrue(called["is_manual_ensemble"])
        self.assertTrue(any(isinstance(event, EnsembleResultEvent) for event in events))


class CliEnsembleCommandTests(unittest.TestCase):
    def test_ensemble_command_builds_request(self) -> None:
        runner = CliRunner()
        captured = {}
        job = mock.Mock()

        def fake_run(request, subscriber=None):
            captured["request"] = request
            if subscriber is not None:
                subscriber(StatusEvent(message="Preparing ensemble"))
                subscriber(ProgressEvent(percent=100.0, current_file=2, total_files=2))
            return SimpleNamespace(output_path="/tmp/out/Ensembled_(Average).wav")

        job.run.side_effect = fake_run

        with runner.isolated_filesystem():
            input_a = Path("a.wav")
            input_b = Path("b.wav")
            output_dir = Path("out")
            input_a.write_bytes(b"a")
            input_b.write_bytes(b"b")
            expected_input_paths = (str(input_a.resolve()), str(input_b.resolve()))
            expected_output_path = str(output_dir.resolve())
            with mock.patch("uvr_cli.__main__.EnsembleJob", return_value=job):
                result = runner.invoke(
                    cli,
                    ["ensemble", "a.wav", "b.wav", "-o", "out", "--algorithm", "Average"],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            captured["request"],
            EnsembleRequest(
                input_paths=expected_input_paths,
                export_path=expected_output_path,
                algorithm="Average",
                output_name="Ensembled",
                save_format="WAV",
                wav_type="PCM_16",
                mp3_bitrate="320k",
                normalize_output=False,
                wav_ensemble=False,
            ),
        )
        self.assertIn("Ensembled 2 input file(s).", result.output)

    def test_ensemble_command_supports_json_progress(self) -> None:
        runner = CliRunner()
        job = mock.Mock()

        def fake_run(_request, subscriber=None):
            if subscriber is not None:
                subscriber(StatusEvent(message="Preparing ensemble"))
                subscriber(ProgressEvent(percent=100.0, current_file=2, total_files=2))
                subscriber(
                    EnsembleResultEvent(
                        output_path="/tmp/out/Ensembled_(Average).wav",
                        inputs=("/tmp/a.wav", "/tmp/b.wav"),
                        algorithm="Average",
                    )
                )
            return SimpleNamespace(output_path="/tmp/out/Ensembled_(Average).wav")

        job.run.side_effect = fake_run

        with runner.isolated_filesystem():
            Path("a.wav").write_bytes(b"a")
            Path("b.wav").write_bytes(b"b")
            with mock.patch("uvr_cli.__main__.EnsembleJob", return_value=job):
                result = runner.invoke(
                    cli,
                    ["ensemble", "a.wav", "b.wav", "-o", "out", "--progress", "json"],
                )

        self.assertEqual(result.exit_code, 0)
        output_lines = [json.loads(line) for line in result.output.strip().splitlines()]
        self.assertEqual(output_lines[0]["event_type"], "status")
        self.assertEqual(output_lines[1]["event_type"], "progress")
        self.assertEqual(output_lines[2]["event_type"], "ensemble_result")


class AudioToolJobTests(unittest.TestCase):
    def test_audio_tool_job_runs_time_stretch(self) -> None:
        job = AudioToolJob()
        events = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            export_path = tmp_path / "out"
            input_a = tmp_path / "a.wav"
            input_b = tmp_path / "b.wav"
            input_a.write_bytes(b"a")
            input_b.write_bytes(b"b")
            called = []

            class FakeAudioTools:
                def __init__(self, audio_tool, settings):
                    self.audio_tool = audio_tool
                    self.settings = settings
                    self.is_testing_audio = ""

                def pitch_or_time_shift(self, audio_file, audio_file_base):
                    called.append((audio_file, audio_file_base))

            with mock.patch("uvr_core.jobs.AudioTools", FakeAudioTools):
                result = job.run(
                    AudioToolRequest(
                        audio_tool=TIME_STRETCH,
                        input_paths=(str(input_a), str(input_b)),
                        export_path=str(export_path),
                    ),
                    subscriber=events.append,
                )

        self.assertEqual(result.audio_tool, TIME_STRETCH)
        self.assertEqual(called, [(str(input_a), "a"), (str(input_b), "b")])
        self.assertEqual(
            result.output_paths,
            (
                str(export_path / "a_time_stretched.wav"),
                str(export_path / "b_time_stretched.wav"),
            ),
        )
        self.assertTrue(any(isinstance(event, AudioToolResultEvent) for event in events))

    def test_audio_tool_job_runs_align(self) -> None:
        job = AudioToolJob()
        events = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            export_path = tmp_path / "out"
            input_a = tmp_path / "a.wav"
            input_b = tmp_path / "b.wav"
            input_a.write_bytes(b"a")
            input_b.write_bytes(b"b")
            called = {}

            class FakeAudioTools:
                def __init__(self, audio_tool, settings):
                    self.audio_tool = audio_tool
                    self.settings = settings
                    self.is_testing_audio = ""

                def align_inputs(self, audio_inputs, audio_file_base, audio_file_2_base, command_text, set_progress_bar):
                    called["audio_inputs"] = tuple(audio_inputs)
                    called["audio_file_base"] = audio_file_base
                    called["audio_file_2_base"] = audio_file_2_base
                    command_text("Processing files...")
                    set_progress_bar(0.25, 0.5)

            with mock.patch("uvr_core.jobs.AudioTools", FakeAudioTools):
                result = job.run(
                    AudioToolRequest(
                        audio_tool=ALIGN_INPUTS,
                        input_paths=(str(input_a), str(input_b)),
                        export_path=str(export_path),
                        save_aligned=True,
                    ),
                    subscriber=events.append,
                )

        self.assertEqual(called["audio_inputs"], (str(input_a), str(input_b)))
        self.assertEqual(called["audio_file_base"], "a")
        self.assertEqual(called["audio_file_2_base"], "b")
        self.assertEqual(
            result.output_paths,
            (
                str(export_path / "a_(Inverted).wav"),
                str(export_path / "b_(Aligned).wav"),
            ),
        )
        self.assertTrue(any(isinstance(event, ProgressEvent) and event.percent == 75.0 for event in events))


class CliAudioToolCommandTests(unittest.TestCase):
    def test_audio_tool_pitch_builds_request(self) -> None:
        runner = CliRunner()
        captured = {}
        job = mock.Mock()

        def fake_run(request, subscriber=None):
            captured["request"] = request
            if subscriber is not None:
                subscriber(StatusEvent(message="Processing 1/1"))
                subscriber(ProgressEvent(percent=100.0, current_file=1, total_files=1))
            return SimpleNamespace(output_paths=("/tmp/out/a_pitch_shifted.wav",))

        job.run.side_effect = fake_run

        with runner.isolated_filesystem():
            Path("a.wav").write_bytes(b"a")
            expected_input_paths = (str(Path("a.wav").resolve()),)
            expected_output_path = str(Path("out").resolve())
            with mock.patch("uvr_cli.__main__.AudioToolJob", return_value=job):
                result = runner.invoke(
                    cli,
                    [
                        "audio-tool",
                        "pitch",
                        "a.wav",
                        "-o",
                        "out",
                        "--rate",
                        "3.5",
                        "--no-time-correction",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            captured["request"],
            AudioToolRequest(
                audio_tool=CHANGE_PITCH,
                input_paths=expected_input_paths,
                export_path=expected_output_path,
                save_format="WAV",
                wav_type="PCM_16",
                mp3_bitrate="320k",
                normalize_output=False,
                testing_audio=False,
                align_window="3",
                align_intro="Default",
                db_analysis="Medium",
                save_aligned=False,
                match_silence=True,
                spec_match=False,
                phase_option="Automatic",
                phase_shifts="None",
                time_stretch_rate="3.5",
                pitch_rate="3.5",
                time_correction=False,
            ),
        )
        self.assertIn("Change Pitch completed.", result.output)

    def test_audio_tool_align_supports_json_progress(self) -> None:
        runner = CliRunner()
        job = mock.Mock()

        def fake_run(_request, subscriber=None):
            if subscriber is not None:
                subscriber(StatusEvent(message="Preparing align inputs"))
                subscriber(ProgressEvent(percent=60.0, current_file=2, total_files=2))
                subscriber(
                    AudioToolResultEvent(
                        audio_tool=ALIGN_INPUTS,
                        output_paths=("/tmp/out/a_(Inverted).wav",),
                        inputs=("/tmp/a.wav", "/tmp/b.wav"),
                    )
                )
            return SimpleNamespace(output_paths=("/tmp/out/a_(Inverted).wav",))

        job.run.side_effect = fake_run

        with runner.isolated_filesystem():
            Path("a.wav").write_bytes(b"a")
            Path("b.wav").write_bytes(b"b")
            with mock.patch("uvr_cli.__main__.AudioToolJob", return_value=job):
                result = runner.invoke(
                    cli,
                    ["audio-tool", "align", "a.wav", "b.wav", "-o", "out", "--progress", "json"],
                )

        self.assertEqual(result.exit_code, 0)
        output_lines = [json.loads(line) for line in result.output.strip().splitlines()]
        self.assertEqual(output_lines[0]["event_type"], "status")
        self.assertEqual(output_lines[1]["event_type"], "progress")
        self.assertEqual(output_lines[2]["event_type"], "audio_tool_result")

    def test_audio_tool_match_builds_request(self) -> None:
        runner = CliRunner()
        captured = {}
        job = mock.Mock()

        def fake_run(request, subscriber=None):
            captured["request"] = request
            return SimpleNamespace(output_paths=("/tmp/out/a_(Matched).wav",))

        job.run.side_effect = fake_run

        with runner.isolated_filesystem():
            Path("a.wav").write_bytes(b"a")
            Path("b.wav").write_bytes(b"b")
            expected_input_paths = (str(Path("a.wav").resolve()), str(Path("b.wav").resolve()))
            with mock.patch("uvr_cli.__main__.AudioToolJob", return_value=job):
                result = runner.invoke(cli, ["audio-tool", "match", "a.wav", "b.wav", "-o", "out"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(captured["request"].audio_tool, MATCH_INPUTS)
        self.assertEqual(captured["request"].input_paths, expected_input_paths)


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
            advanced=AdvancedModelControlsState(
                aggression_setting=7,
                window_size=1024,
                batch_size="3",
                crop_size=512,
                is_tta=True,
                is_post_process=True,
                is_high_end_process=True,
                post_process_threshold=0.35,
                margin=22050,
                mdx_segment_size=512,
                overlap="0.5",
                overlap_mdx="0.75",
                shifts=3,
                margin_demucs=11025,
                compensate="1.08",
                mdx_batch_size="4",
                segment="10",
            ),
            extra_settings={"custom": "value"},
        )

        request = state.to_separation_request()

        self.assertEqual(request.input_paths, ("input.wav",))
        self.assertEqual(request.export_path, "out")
        self.assertEqual(request.models.vr_model, "vr model")
        self.assertEqual(request.output.save_format, "WAV")
        self.assertTrue(request.options.use_gpu)
        self.assertEqual(request.advanced.window_size, 1024)
        self.assertEqual(request.advanced.compensate, "1.08")
        self.assertEqual(request.extra_settings["custom"], "value")

    def test_app_state_round_trips_output_and_sampling_fields(self) -> None:
        state = AppState(
            paths=PathsState(),
            models=ModelSelectionState(
                vr_model="",
                mdx_net_model="",
                demucs_model="",
                demucs_pre_proc_model="",
                vocal_splitter_model="",
                demucs_stems="All Stems",
                mdx_stems="All Stems",
            ),
            output=OutputSettingsState(
                save_format="MP3",
                wav_type="PCM_16",
                mp3_bitrate="224k",
                add_model_name=False,
                create_model_folder=True,
            ),
            processing=ProcessingSettingsState(
                process_method="VR Architecture",
                audio_tool="",
                algorithm="",
                device="DEFAULT",
                use_gpu=False,
                primary_stem_only=False,
                secondary_stem_only=False,
                normalize_output=False,
                wav_ensemble=False,
                testing_audio=True,
                model_sample_mode=True,
                model_sample_duration=45,
            ),
            advanced=AdvancedModelControlsState(
                aggression_setting=12,
                window_size=320,
                batch_size="2",
                crop_size=384,
                is_tta=False,
                is_post_process=True,
                is_high_end_process=False,
                post_process_threshold=0.4,
                margin=12345,
                mdx_segment_size=768,
                overlap="0.25",
                overlap_mdx="0.5",
                shifts=6,
                margin_demucs=54321,
                compensate="1.035",
                mdx_batch_size="5",
                segment="15",
            ),
        )

        payload = state.to_legacy_dict()

        self.assertEqual(payload["save_format"], "MP3")
        self.assertEqual(payload["mp3_bit_set"], "224k")
        self.assertTrue(payload["is_create_model_folder"])
        self.assertTrue(payload["is_testing_audio"])
        self.assertTrue(payload["model_sample_mode"])
        self.assertEqual(payload["model_sample_mode_duration"], 45)
        self.assertEqual(payload["window_size"], 320)
        self.assertEqual(payload["mdx_segment_size"], 768)
        self.assertEqual(payload["margin_demucs"], 54321)
        self.assertEqual(payload["compensate"], "1.035")

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
        self.assertEqual(request.advanced.window_size, 512)
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
                advanced=SimpleNamespace(
                    aggression_setting=5,
                    window_size=512,
                    batch_size="Default",
                    crop_size=256,
                    is_tta=False,
                    is_post_process=False,
                    is_high_end_process=False,
                    post_process_threshold=0.2,
                    margin=44100,
                    mdx_segment_size=256,
                    overlap="0.25",
                    overlap_mdx="Default",
                    shifts=2,
                    margin_demucs=44100,
                    compensate="Automatic",
                    mdx_batch_size="Default",
                    segment="Default",
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

    def test_run_can_be_cancelled(self) -> None:
        job = SeparationJob()
        events = []

        class FakeSeparator:
            def __init__(self, process_data: dict[str, object]):
                self.process_data = process_data

            def seperate(self) -> None:
                self.process_data["set_progress_bar"](0.1)
                self.process_data["set_progress_bar"](0.2)

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
                advanced=SimpleNamespace(
                    aggression_setting=5,
                    window_size=512,
                    batch_size="Default",
                    crop_size=256,
                    is_tta=False,
                    is_post_process=False,
                    is_high_end_process=False,
                    post_process_threshold=0.2,
                    margin=44100,
                    mdx_segment_size=256,
                    overlap="0.25",
                    overlap_mdx="Default",
                    shifts=2,
                    margin_demucs=44100,
                    compensate="Automatic",
                    mdx_batch_size="Default",
                    segment="Default",
                ),
                extra_settings={},
            )

            fake_model = SimpleNamespace(
                model_status=True,
                model_basename="fake_model",
                process_method="VR Architecture",
                is_mdx_c=False,
            )

            def subscriber(event):
                events.append(event)
                if isinstance(event, ProgressEvent):
                    job.cancel()

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
                with self.assertRaises(JobCancelledError):
                    job.run(request, subscriber=subscriber)

        self.assertTrue(any(isinstance(event, StatusEvent) and event.message == "Cancelled" for event in events))
        self.assertTrue(any(isinstance(event, LogEvent) and event.message == "Processing cancelled." for event in events))


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _make_state(self) -> AppState:
        return AppState(
            paths=PathsState(
                input_paths=("input.wav",),
                export_path="out",
            ),
            models=ModelSelectionState(
                vr_model="Model A",
                mdx_net_model="",
                demucs_model="",
                demucs_pre_proc_model="",
                vocal_splitter_model="",
                demucs_stems="All Stems",
                mdx_stems="All Stems",
            ),
            output=OutputSettingsState(
                save_format="WAV",
                wav_type="PCM_16",
                mp3_bitrate="320k",
                add_model_name=False,
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
                normalize_output=False,
                wav_ensemble=False,
                testing_audio=False,
                model_sample_mode=False,
                model_sample_duration=30,
            ),
            advanced=AdvancedModelControlsState(
                aggression_setting=5,
                window_size=512,
                batch_size="Default",
                crop_size=256,
                is_tta=False,
                is_post_process=False,
                is_high_end_process=False,
                post_process_threshold=0.2,
                margin=44100,
                mdx_segment_size=256,
                overlap="0.25",
                overlap_mdx="Default",
                shifts=2,
                margin_demucs=44100,
                compensate="Automatic",
                mdx_batch_size="Default",
                segment="Default",
            ),
        )

    def test_save_format_switches_output_controls(self) -> None:
        from uvr_core.jobs import ResolvedModel
        from uvr_qt.services.processing_facade import ProcessingFacade
        from uvr_qt.ui.main_window import MainWindow

        class FakeFacade(ProcessingFacade):
            def __init__(self) -> None:
                pass

            def available_process_methods(self):
                return ("VR Architecture",)

            def available_models_for_method(self, process_method: str):
                return ("Model A",)

            def available_tagged_models_for_methods(self, process_methods):
                return ("VR Architecture: Aux VR", "MDX-Net: Aux MDX")

            def resolve_model(self, state: AppState):
                return ResolvedModel("VR Architecture", state.models.vr_model, "vr")

        with mock.patch("uvr_qt.ui.main_window.save_settings"):
            window = MainWindow(state=self._make_state(), processing_facade=FakeFacade())
            try:
                self.assertFalse(window.mp3_bitrate_combo.isEnabled())
                self.assertTrue(window.wav_type_combo.isEnabled())

                window.save_format_combo.setCurrentText("MP3")

                self.assertEqual(window.state.output.save_format, "MP3")
                self.assertTrue(window.mp3_bitrate_combo.isEnabled())
                self.assertFalse(window.wav_type_combo.isEnabled())
            finally:
                window.close()

    def test_runtime_state_toggles_process_and_cancel_buttons(self) -> None:
        from uvr_core.jobs import ResolvedModel
        from uvr_qt.services.processing_facade import ProcessingFacade
        from uvr_qt.ui.main_window import MainWindow

        class FakeFacade(ProcessingFacade):
            def __init__(self) -> None:
                pass

            def available_process_methods(self):
                return ("VR Architecture",)

            def available_models_for_method(self, process_method: str):
                return ("Model A",)

            def available_tagged_models_for_methods(self, process_methods):
                return ("VR Architecture: Aux VR", "MDX-Net: Aux MDX")

            def resolve_model(self, state: AppState):
                return ResolvedModel("VR Architecture", state.models.vr_model, "vr")

        with mock.patch("uvr_qt.ui.main_window.save_settings"):
            window = MainWindow(state=self._make_state(), processing_facade=FakeFacade())
            try:
                self.assertTrue(window.process_button.isEnabled())
                self.assertFalse(window.cancel_button.isEnabled())
                self.assertEqual(window.process_button.text(), "Process with GPU")

                window._set_runtime(is_processing=True, can_cancel=True, status_text="Working")

                self.assertFalse(window.process_button.isEnabled())
                self.assertTrue(window.cancel_button.isEnabled())

                window.gpu_checkbox.setChecked(False)

                self.assertEqual(window.process_button.text(), "Process on CPU")
            finally:
                window.close()

    def test_download_button_opens_separate_window(self) -> None:
        from uvr_core.jobs import ResolvedModel
        from uvr_qt.services.processing_facade import ProcessingFacade
        from uvr_qt.ui.main_window import MainWindow

        class FakeFacade(ProcessingFacade):
            def __init__(self) -> None:
                pass

            def available_process_methods(self):
                return ("VR Architecture",)

            def available_models_for_method(self, process_method: str):
                return ("Model A",)

            def available_tagged_models_for_methods(self, process_methods):
                return ("VR Architecture: Aux VR",)

            def resolve_model(self, state: AppState):
                return ResolvedModel("VR Architecture", state.models.vr_model, "vr")

        with mock.patch("uvr_qt.ui.main_window.save_settings"):
            window = MainWindow(state=self._make_state(), processing_facade=FakeFacade())
            try:
                self.assertIsNone(window.download_manager_window)
                window._open_download_manager()
                self.assertIsNotNone(window.download_manager_window)
                self.assertEqual(window.download_manager_window.windowTitle(), "Model Downloads")
            finally:
                if window.download_manager_window is not None:
                    window.download_manager_window.close()
                window.close()

    def test_advanced_controls_are_collapsible_and_method_specific(self) -> None:
        from uvr_core.jobs import ResolvedModel
        from uvr_qt.services.processing_facade import ProcessingFacade
        from uvr_qt.ui.main_window import MainWindow

        class FakeFacade(ProcessingFacade):
            def __init__(self) -> None:
                pass

            def available_process_methods(self):
                return ("VR Architecture", "MDX-Net", "Demucs")

            def available_models_for_method(self, process_method: str):
                return ("Model A",)

            def available_tagged_models_for_methods(self, process_methods):
                return ("VR Architecture: Aux VR", "MDX-Net: Aux MDX")

            def resolve_model(self, state: AppState):
                return ResolvedModel(state.processing.process_method, state.models.vr_model or "Model A", "vr")

        with mock.patch("uvr_qt.ui.main_window.save_settings"):
            window = MainWindow(state=self._make_state(), processing_facade=FakeFacade())
            try:
                self.assertTrue(window.advanced_container.isHidden())
                self.assertFalse(window.advanced_toggle_button.isChecked())

                window.advanced_toggle_button.click()

                self.assertFalse(window.advanced_container.isHidden())
                self.assertFalse(window.vr_advanced_group.isHidden())
                self.assertTrue(window.mdx_advanced_group.isHidden())

                window.process_method_combo.setCurrentText("MDX-Net")

                self.assertEqual(window.state.processing.process_method, "MDX-Net")
                self.assertTrue(window.vr_advanced_group.isHidden())
                self.assertFalse(window.mdx_advanced_group.isHidden())
                self.assertTrue(window.demucs_advanced_group.isHidden())
            finally:
                window.close()

    def test_composition_controls_update_state(self) -> None:
        from uvr_core.jobs import ResolvedModel
        from uvr_qt.services.processing_facade import ProcessingFacade
        from uvr_qt.ui.main_window import MainWindow

        class FakeFacade(ProcessingFacade):
            def __init__(self) -> None:
                pass

            def available_process_methods(self):
                return ("VR Architecture", "MDX-Net", "Demucs")

            def available_models_for_method(self, process_method: str):
                return ("Model A",)

            def available_tagged_models_for_methods(self, process_methods):
                return ("VR Architecture: Aux VR", "MDX-Net: Aux MDX")

            def resolve_model(self, state: AppState):
                return ResolvedModel(state.processing.process_method, state.models.vr_model or "Model A", "vr")

        with mock.patch("uvr_qt.ui.main_window.save_settings"):
            window = MainWindow(state=self._make_state(), processing_facade=FakeFacade())
            try:
                window.advanced_toggle_button.click()
                window.process_method_combo.setCurrentText("Demucs")
                window.demucs_stems_combo.setCurrentText("Vocals")
                window.demucs_pre_proc_checkbox.setChecked(True)
                window.demucs_pre_proc_model_combo.setCurrentText("VR Architecture: Aux VR")
                window.vocal_splitter_checkbox.setChecked(True)
                window.vocal_splitter_model_combo.setCurrentText("MDX-Net: Aux MDX")

                self.assertEqual(window.state.models.demucs_stems, "Vocals")
                self.assertEqual(window.state.models.demucs_pre_proc_model, "VR Architecture: Aux VR")
                self.assertEqual(window.state.models.vocal_splitter_model, "MDX-Net: Aux MDX")
                self.assertTrue(window.state.extra_settings["is_demucs_pre_proc_model_activate"])
                self.assertTrue(window.state.extra_settings["is_set_vocal_splitter"])
            finally:
                window.close()


class DownloadManagerWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_refresh_finished_updates_catalog_view(self) -> None:
        from uvr_qt.ui.download_manager_window import DownloadManagerWindow

        class FakeFacade:
            def refresh_catalog(self, *, vip_code: str = "", refresh_model_settings: bool = True):
                return CatalogRefreshResult(
                    available_downloads=AvailableDownloads(
                        bulletin="hello",
                        vr_items=("VR One",),
                        mdx_items=("MDX One",),
                        demucs_items=("Demucs One",),
                        decoded_vip_link="",
                    ),
                    refreshed_settings=None,
                )

        window = DownloadManagerWindow(download_facade=FakeFacade())
        try:
            result = FakeFacade().refresh_catalog()
            window._refresh_finished(result)
            self.assertEqual(window.bulletin_field.toPlainText(), "hello")
            self.assertEqual(window.item_list.count(), 1)
            self.assertEqual(window.item_list.item(0).text(), "VR One")
        finally:
            window.close()

    def test_model_type_switch_updates_available_items(self) -> None:
        from uvr_qt.ui.download_manager_window import DownloadManagerWindow

        window = DownloadManagerWindow(download_facade=mock.Mock())
        try:
            window.current_downloads = AvailableDownloads(
                bulletin=None,
                vr_items=("VR One",),
                mdx_items=("MDX One", "MDX Two"),
                demucs_items=("Demucs One",),
                decoded_vip_link="",
            )
            window.model_type_combo.setCurrentText("MDX-Net")
            window._refresh_list()
            self.assertEqual(window.item_list.count(), 2)
            self.assertEqual(window.item_list.item(1).text(), "MDX Two")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
