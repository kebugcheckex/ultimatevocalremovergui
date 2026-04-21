"""Service modules for UVR."""

from uvr.services.cache import SourceCache
from uvr.services.catalog import InstalledModel, ModelCatalog, discover_models, list_installed_models, load_model_catalog
from uvr.services.downloads import (
    DownloadCatalog,
    DownloadPlan,
    DownloadResult,
    DownloadTask,
    ModelSettingsBundle,
    build_download_catalog,
    ensure_mdx23_configs,
    execute_download_plan,
    fetch_bulletin,
    fetch_online_data,
    fetch_online_state,
    list_downloadable_items,
    load_or_fetch_model_settings,
    refresh_model_settings,
    resolve_download_plan,
    validate_vip_code,
)

__all__ = [
    "DownloadCatalog",
    "DownloadPlan",
    "DownloadResult",
    "DownloadTask",
    "InstalledModel",
    "ModelSettingsBundle",
    "ModelCatalog",
    "SourceCache",
    "build_download_catalog",
    "discover_models",
    "ensure_mdx23_configs",
    "execute_download_plan",
    "fetch_bulletin",
    "fetch_online_data",
    "fetch_online_state",
    "list_downloadable_items",
    "list_installed_models",
    "load_or_fetch_model_settings",
    "load_model_catalog",
    "refresh_model_settings",
    "resolve_download_plan",
    "validate_vip_code",
]
