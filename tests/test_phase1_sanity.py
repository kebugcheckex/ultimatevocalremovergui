from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings
from uvr.runtime import build_runtime_paths
from uvr_core.events import LogEvent, ProgressEvent, ResultEvent, StatusEvent
from uvr_core.jobs import ResolvedModel, SeparationJob
from uvr_core.requests import SeparationRequest
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
