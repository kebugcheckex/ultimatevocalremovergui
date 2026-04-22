"""Separate download-manager window for the PySide6 frontend."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import DEMUCS_ARCH_TYPE, MDX_ARCH_TYPE, VR_ARCH_PM
from uvr_core.jobs import AvailableDownloads, CatalogRefreshResult, DownloadJobResult
from uvr_core.requests import DownloadRequest
from uvr_qt.services import DownloadFacade


class DownloadManagerWindow(QMainWindow):
    """Standalone Qt window for refreshing and downloading models."""

    def __init__(self, download_facade: DownloadFacade | None = None) -> None:
        super().__init__()
        self.download_facade = download_facade or DownloadFacade()
        self.refresh_thread: QThread | None = None
        self.refresh_worker: _CatalogRefreshWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: _DownloadWorker | None = None
        self.current_downloads = AvailableDownloads(
            bulletin=None,
            vr_items=(),
            mdx_items=(),
            demucs_items=(),
            decoded_vip_link="",
        )
        self.setWindowTitle("Model Downloads")
        self.resize(860, 640)

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._build_catalog_group())
        root_layout.addWidget(self._build_selection_group())
        root_layout.addWidget(self._build_activity_group())

        self.setCentralWidget(central_widget)
        self._set_status("Idle")
        self._refresh_list()

    def _build_catalog_group(self) -> QGroupBox:
        group = QGroupBox("Catalog")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("VIP Code"), 0, 0)
        self.vip_code_field = QLineEdit(group)
        self.vip_code_field.setPlaceholderText("Optional")
        layout.addWidget(self.vip_code_field, 0, 1)

        self.refresh_button = QPushButton("Refresh Catalog", group)
        self.refresh_button.clicked.connect(self._start_refresh)
        layout.addWidget(self.refresh_button, 0, 2)

        layout.addWidget(QLabel("Bulletin"), 1, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.bulletin_field = QPlainTextEdit(group)
        self.bulletin_field.setReadOnly(True)
        self.bulletin_field.setPlaceholderText("No bulletin loaded")
        self.bulletin_field.setMaximumHeight(120)
        layout.addWidget(self.bulletin_field, 1, 1, 1, 2)
        return group

    def _build_selection_group(self) -> QGroupBox:
        group = QGroupBox("Selection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        selector_row = QWidget(group)
        selector_layout = QHBoxLayout(selector_row)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(8)
        selector_layout.addWidget(QLabel("Model Type"))
        self.model_type_combo = QComboBox(group)
        self.model_type_combo.addItems([VR_ARCH_PM, MDX_ARCH_TYPE, DEMUCS_ARCH_TYPE])
        self.model_type_combo.currentTextChanged.connect(self._refresh_list)
        selector_layout.addWidget(self.model_type_combo)
        selector_layout.addStretch(1)

        self.item_list = QListWidget(group)
        self.item_list.itemSelectionChanged.connect(self._update_download_button)

        self.download_button = QPushButton("Download Selected", group)
        self.download_button.clicked.connect(self._start_download)

        layout.addWidget(selector_row)
        layout.addWidget(self.item_list, 1)
        layout.addWidget(self.download_button)
        return group

    def _build_activity_group(self) -> QGroupBox:
        group = QGroupBox("Activity")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)

        self.status_label = QLabel(group)
        self.status_label.setWordWrap(True)

        self.log_console = QPlainTextEdit(group)
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("Refresh and download events will appear here")
        self.log_console.setMinimumHeight(180)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_console, 1)
        return group

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _append_log(self, text: str) -> None:
        self.log_console.appendPlainText(text)

    def _refresh_list(self) -> None:
        selected_type = self.model_type_combo.currentText()
        if selected_type == VR_ARCH_PM:
            items = self.current_downloads.vr_items
        elif selected_type == MDX_ARCH_TYPE:
            items = self.current_downloads.mdx_items
        else:
            items = self.current_downloads.demucs_items

        self.item_list.clear()
        self.item_list.addItems(list(items))
        self._update_download_button()

    def _update_download_button(self) -> None:
        self.download_button.setEnabled(
            self.download_thread is None
            and self.refresh_thread is None
            and self.item_list.currentItem() is not None
        )

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy and self.download_thread is None)
        self.model_type_combo.setEnabled(not busy and self.download_thread is None)
        self.item_list.setEnabled(not busy and self.download_thread is None)
        self.vip_code_field.setEnabled(not busy and self.download_thread is None)
        self._update_download_button()

    def _start_refresh(self) -> None:
        if self.refresh_thread is not None:
            return

        self.progress_bar.setValue(0)
        self._set_status("Refreshing catalog")
        self._append_log("Refreshing catalog...")
        self._set_busy(True)

        vip_code = self.vip_code_field.text().strip()
        self.refresh_thread = QThread(self)
        self.refresh_worker = _CatalogRefreshWorker(self.download_facade, vip_code=vip_code)
        self.refresh_worker.moveToThread(self.refresh_thread)
        self.refresh_thread.started.connect(self.refresh_worker.run)
        self.refresh_worker.finished.connect(self._refresh_finished)
        self.refresh_worker.failed.connect(self._refresh_failed)
        self.refresh_worker.finished.connect(self.refresh_thread.quit)
        self.refresh_worker.failed.connect(self.refresh_thread.quit)
        self.refresh_thread.finished.connect(self._cleanup_refresh_thread)
        self.refresh_thread.start()

    def _start_download(self) -> None:
        if self.download_thread is not None or self.item_list.currentItem() is None:
            return

        self.progress_bar.setValue(0)
        selection = self.item_list.currentItem().text()
        model_type = self.model_type_combo.currentText()
        vip_code = self.vip_code_field.text().strip()
        self._set_status(f"Downloading {selection}")
        self._append_log(f"Queued download: {selection}")
        self._set_busy(True)

        self.download_thread = QThread(self)
        self.download_worker = _DownloadWorker(
            self.download_facade,
            request=DownloadRequest(
                model_type=model_type,
                selection=selection,
                vip_code=vip_code,
                refresh_model_settings=True,
            ),
        )
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.progress_emitted.connect(self._set_progress)
        self.download_worker.status_emitted.connect(self._set_status)
        self.download_worker.log_emitted.connect(self._append_log)
        self.download_worker.finished.connect(self._download_finished)
        self.download_worker.failed.connect(self._download_failed)
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.failed.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self._cleanup_download_thread)
        self.download_thread.start()

    def _set_progress(self, value: int) -> None:
        self.progress_bar.setValue(value)

    def _refresh_finished(self, result: CatalogRefreshResult) -> None:
        self.current_downloads = result.available_downloads
        self.bulletin_field.setPlainText(result.available_downloads.bulletin or "")
        self._refresh_list()
        self._set_status("Catalog refreshed")
        self._append_log("Catalog refresh completed.")
        self.progress_bar.setValue(100)
        self._set_busy(False)

    def _refresh_failed(self, message: str) -> None:
        self._set_status("Catalog refresh failed")
        self._append_log(message)
        self._set_busy(False)

    def _download_finished(self, result: DownloadJobResult) -> None:
        self.progress_bar.setValue(100)
        self._set_status(f"Downloaded {len(result.completed_files)} file(s)")
        for path in result.completed_files:
            self._append_log(f"Downloaded: {path}")
        for path in result.skipped_existing:
            self._append_log(f"Skipped existing: {path}")
        self._set_busy(False)

    def _download_failed(self, message: str) -> None:
        self._set_status("Download failed")
        self._append_log(message)
        self._set_busy(False)

    def _cleanup_refresh_thread(self) -> None:
        if self.refresh_worker is not None:
            self.refresh_worker.deleteLater()
        if self.refresh_thread is not None:
            self.refresh_thread.deleteLater()
        self.refresh_worker = None
        self.refresh_thread = None
        self._set_busy(False)

    def _cleanup_download_thread(self) -> None:
        if self.download_worker is not None:
            self.download_worker.deleteLater()
        if self.download_thread is not None:
            self.download_thread.deleteLater()
        self.download_worker = None
        self.download_thread = None
        self._set_busy(False)


class _CatalogRefreshWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, facade: DownloadFacade, *, vip_code: str) -> None:
        super().__init__()
        self.facade = facade
        self.vip_code = vip_code

    def run(self) -> None:
        try:
            result = self.facade.refresh_catalog(vip_code=self.vip_code)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)


class _DownloadWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    log_emitted = Signal(str)
    progress_emitted = Signal(int)
    status_emitted = Signal(str)

    def __init__(self, facade: DownloadFacade, *, request: DownloadRequest) -> None:
        super().__init__()
        self.facade = facade
        self.request = request

    def run(self) -> None:
        try:
            result = self.facade.download(
                self.request,
                log=self.log_emitted.emit,
                progress=lambda value: self.progress_emitted.emit(int(max(0, min(value, 100)))),
                status=self.status_emitted.emit,
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(result)
