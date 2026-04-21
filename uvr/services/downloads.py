"""Download and online-refresh services for the framework-neutral backend."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, BinaryIO
from urllib.request import urlopen

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from gui_data.constants import (
    BULLETIN_CHECK,
    DEMUCS_ARCH_TYPE,
    DEMUCS_MODEL_NAME_DATA_LINK,
    DEMUCS_NEWER_ARCH_TYPES,
    DOWNLOAD_CHECKS,
    MDX23_CONFIG_CHECKS,
    MDX_ARCH_TYPE,
    MDX_MODEL_DATA_LINK,
    MDX_MODEL_NAME_DATA_LINK,
    NO_CODE,
    NORMAL_REPO,
    VIP_REPO,
    VIP_SELECTION,
    VR_ARCH_TYPE,
    VR_MODEL_DATA_LINK,
)
from uvr.runtime import DEFAULT_PATHS, RuntimePaths
from uvr.services.catalog import ModelCatalog, load_model_catalog


OpenUrl = Callable[[str], BinaryIO]
ProgressCallback = Callable[[int, int, int, int, "DownloadTask"], None]


@dataclass(frozen=True)
class OnlineData:
    payload: dict[str, Any]
    bulletin: str | None = None


@dataclass(frozen=True)
class DownloadCatalog:
    vr_download_list: dict[str, Any]
    mdx_download_list: dict[str, Any]
    demucs_download_list: dict[str, dict[str, str]]


@dataclass(frozen=True)
class DownloadTask:
    name: str
    url: str
    destination: Path


@dataclass(frozen=True)
class DownloadPlan:
    selection: str
    model_type: str
    tasks: tuple[DownloadTask, ...]


@dataclass(frozen=True)
class DownloadResult:
    completed: tuple[Path, ...]
    skipped_existing: tuple[Path, ...]


@dataclass(frozen=True)
class ModelSettingsBundle:
    vr_hash_mapper: dict[str, Any]
    mdx_hash_mapper: dict[str, Any]
    mdx_name_select_mapper: dict[str, Any]
    demucs_name_select_mapper: dict[str, Any]

    def write_to_disk(self, paths: RuntimePaths = DEFAULT_PATHS) -> None:
        paths.vr_hash_json.write_text(json.dumps(self.vr_hash_mapper, indent=4))
        paths.mdx_hash_json.write_text(json.dumps(self.mdx_hash_mapper, indent=4))
        paths.mdx_model_name_select.write_text(json.dumps(self.mdx_name_select_mapper, indent=4))
        paths.demucs_model_name_select.write_text(json.dumps(self.demucs_name_select_mapper, indent=4))

    def to_model_catalog(self) -> ModelCatalog:
        return ModelCatalog(
            vr_hash_mapper=self.vr_hash_mapper,
            mdx_hash_mapper=self.mdx_hash_mapper,
            mdx_name_select_mapper=self.mdx_name_select_mapper,
            demucs_name_select_mapper=self.demucs_name_select_mapper,
        )


def _read_json(url: str, *, opener: OpenUrl = urlopen) -> dict[str, Any]:
    with opener(url) as response:
        return json.load(response)


def _read_text(url: str, *, opener: OpenUrl = urlopen) -> str:
    with opener(url) as response:
        return response.read().decode("utf-8")


def fetch_online_data(*, opener: OpenUrl = urlopen) -> dict[str, Any]:
    return _read_json(DOWNLOAD_CHECKS, opener=opener)


def fetch_bulletin(*, opener: OpenUrl = urlopen) -> str:
    return _read_text(BULLETIN_CHECK, opener=opener)


def fetch_online_state(*, opener: OpenUrl = urlopen) -> OnlineData:
    return OnlineData(
        payload=fetch_online_data(opener=opener),
        bulletin=fetch_bulletin(opener=opener),
    )


def validate_vip_code(password: str, link_type: tuple[bytes, bytes] | Any = VIP_REPO) -> str:
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=link_type[0],
            iterations=390000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(bytes(password, "utf-8")))
        fernet = Fernet(key)
        return str(fernet.decrypt(link_type[1]), "UTF-8")
    except Exception:
        return NO_CODE


def build_download_catalog(
    online_data: dict[str, Any],
    *,
    decoded_vip_link: str = NO_CODE,
) -> DownloadCatalog:
    vr_download_list = dict(online_data["vr_download_list"])
    mdx_download_list = dict(online_data["mdx_download_list"])
    demucs_download_list = dict(online_data["demucs_download_list"])
    mdx_download_list.update(online_data.get("mdx23c_download_list", {}))

    if decoded_vip_link != NO_CODE:
        vr_download_list.update(online_data.get("vr_download_vip_list", {}))
        mdx_download_list.update(online_data.get("mdx_download_vip_list", {}))
        mdx_download_list.update(online_data.get("mdx23c_download_vip_list", {}))

    return DownloadCatalog(
        vr_download_list=vr_download_list,
        mdx_download_list=mdx_download_list,
        demucs_download_list=demucs_download_list,
    )


def ensure_mdx23_configs(
    catalog: DownloadCatalog,
    *,
    paths: RuntimePaths = DEFAULT_PATHS,
    opener: OpenUrl = urlopen,
) -> None:
    paths.mdx_c_config_path.mkdir(parents=True, exist_ok=True)
    for model in catalog.mdx_download_list.values():
        if not isinstance(model, dict):
            continue
        model_name, config_name = list(model.items())[0]
        del model_name
        config_local = paths.mdx_c_config_path / config_name
        if config_local.is_file():
            continue
        with opener(f"{MDX23_CONFIG_CHECKS}{config_name}") as response:
            config_local.write_bytes(response.read())


def list_downloadable_items(
    catalog: DownloadCatalog,
    model_type: str,
    *,
    paths: RuntimePaths = DEFAULT_PATHS,
    opener: OpenUrl = urlopen,
) -> list[str]:
    if model_type == VR_ARCH_TYPE:
        return [
            selectable
            for selectable, model_name in catalog.vr_download_list.items()
            if not (paths.vr_models_dir / model_name).is_file()
        ]

    if model_type == MDX_ARCH_TYPE:
        ensure_mdx23_configs(catalog, paths=paths, opener=opener)
        missing = []
        for selectable, model in catalog.mdx_download_list.items():
            model_name = list(model.keys())[0] if isinstance(model, dict) else str(model)
            if not (paths.mdx_models_dir / model_name).is_file():
                missing.append(selectable)
        return missing

    if model_type == DEMUCS_ARCH_TYPE:
        missing: list[str] = []
        for selectable, model_group in catalog.demucs_download_list.items():
            is_newer = any(arch in selectable for arch in DEMUCS_NEWER_ARCH_TYPES)
            for file_name in model_group:
                destination = paths.demucs_newer_repo_dir / file_name if is_newer else paths.demucs_models_dir / file_name
                if not destination.is_file():
                    missing.append(selectable)
                    break
        return list(dict.fromkeys(missing))

    return []


def resolve_download_plan(
    selection: str,
    model_type: str,
    catalog: DownloadCatalog,
    *,
    decoded_vip_link: str = NO_CODE,
    paths: RuntimePaths = DEFAULT_PATHS,
) -> DownloadPlan:
    model_repo = decoded_vip_link if VIP_SELECTION in selection and decoded_vip_link != NO_CODE else NORMAL_REPO

    if model_type == VR_ARCH_TYPE:
        for selectable, model_name in catalog.vr_download_list.items():
            if selection == selectable:
                return DownloadPlan(
                    selection=selection,
                    model_type=model_type,
                    tasks=(DownloadTask(selection, f"{model_repo}{model_name}", paths.vr_models_dir / model_name),),
                )

    if model_type == MDX_ARCH_TYPE:
        for selectable, model in catalog.mdx_download_list.items():
            if selection != selectable:
                continue
            model_name = list(model.keys())[0] if isinstance(model, dict) else str(model)
            return DownloadPlan(
                selection=selection,
                model_type=model_type,
                tasks=(DownloadTask(selection, f"{model_repo}{model_name}", paths.mdx_models_dir / model_name),),
            )

    if model_type == DEMUCS_ARCH_TYPE:
        for selectable, model_group in catalog.demucs_download_list.items():
            if selection != selectable:
                continue
            is_newer = any(arch in selection for arch in DEMUCS_NEWER_ARCH_TYPES)
            tasks = tuple(
                DownloadTask(
                    name=file_name,
                    url=url,
                    destination=paths.demucs_newer_repo_dir / file_name if is_newer else paths.demucs_models_dir / file_name,
                )
                for file_name, url in model_group.items()
            )
            return DownloadPlan(selection=selection, model_type=model_type, tasks=tasks)

    raise KeyError(f"Unknown download selection: {selection}")


def refresh_model_settings(
    *,
    paths: RuntimePaths = DEFAULT_PATHS,
    opener: OpenUrl = urlopen,
) -> ModelSettingsBundle:
    bundle = ModelSettingsBundle(
        vr_hash_mapper=_read_json(VR_MODEL_DATA_LINK, opener=opener),
        mdx_hash_mapper=_read_json(MDX_MODEL_DATA_LINK, opener=opener),
        mdx_name_select_mapper=_read_json(MDX_MODEL_NAME_DATA_LINK, opener=opener),
        demucs_name_select_mapper=_read_json(DEMUCS_MODEL_NAME_DATA_LINK, opener=opener),
    )
    bundle.write_to_disk(paths)
    return bundle


def load_or_fetch_model_settings(
    *,
    paths: RuntimePaths = DEFAULT_PATHS,
    opener: OpenUrl = urlopen,
) -> ModelSettingsBundle:
    try:
        return refresh_model_settings(paths=paths, opener=opener)
    except Exception:
        catalog = load_model_catalog(paths)
        return ModelSettingsBundle(
            vr_hash_mapper=catalog.vr_hash_mapper,
            mdx_hash_mapper=catalog.mdx_hash_mapper,
            mdx_name_select_mapper=catalog.mdx_name_select_mapper,
            demucs_name_select_mapper=catalog.demucs_name_select_mapper,
        )


def execute_download_plan(
    plan: DownloadPlan,
    *,
    opener: OpenUrl = urlopen,
    progress: ProgressCallback | None = None,
    chunk_size: int = 1024 * 128,
) -> DownloadResult:
    completed: list[Path] = []
    skipped_existing: list[Path] = []
    total_items = len(plan.tasks)

    for item_index, task in enumerate(plan.tasks, start=1):
        task.destination.parent.mkdir(parents=True, exist_ok=True)
        if task.destination.is_file():
            skipped_existing.append(task.destination)
            continue

        with opener(task.url) as response, task.destination.open("wb") as handle:
            total_bytes = _content_length(response)
            written = 0
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                if progress is not None:
                    progress(item_index, total_items, written, total_bytes, task)

        completed.append(task.destination)

    return DownloadResult(
        completed=tuple(completed),
        skipped_existing=tuple(skipped_existing),
    )


def _content_length(response: BinaryIO) -> int:
    headers = getattr(response, "headers", None)
    if headers is not None:
        content_length = headers.get("Content-Length")
        if content_length is not None:
            try:
                return int(content_length)
            except (TypeError, ValueError):
                return 0
    length = getattr(response, "length", None)
    if isinstance(length, int):
        return length
    return 0
