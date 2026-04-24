"""Manage Profiles dialog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import DEFAULT_DATA
from uvr.config.models import AppSettings
from uvr.config.profiles import ProfileError, SettingsProfileStore
from uvr_qt.state import AppState


class ProfilesDialog(QDialog):
    """Non-modal dialog for managing saved settings profiles."""

    def __init__(
        self,
        profile_store: SettingsProfileStore,
        state: AppState,
        on_state_changed: Callable[[AppState], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Profiles")
        self.setModal(False)
        self.resize(480, 200)
        self._profile_store = profile_store
        self._state = state
        self._on_state_changed = on_state_changed
        self._build_ui()
        self._refresh_controls()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Profile"), 0, 0)
        self._combo = QComboBox(self)
        self._combo.currentTextChanged.connect(lambda _: self._refresh_controls())
        grid.addWidget(self._combo, 0, 1)

        btn_row = QWidget(self)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self._save_btn = QPushButton("Save Current", self)
        self._save_btn.clicked.connect(self._save_profile)
        self._load_btn = QPushButton("Load Selected", self)
        self._load_btn.clicked.connect(self._load_profile)
        self._delete_btn = QPushButton("Delete Selected", self)
        self._delete_btn.clicked.connect(self._delete_profile)
        self._refresh_btn = QPushButton("Refresh", self)
        self._refresh_btn.clicked.connect(self._refresh_controls)

        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._load_btn)
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addWidget(self._refresh_btn)
        btn_layout.addStretch(1)

        self._status_label = QLabel(self)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #5f6b7a;")

        grid.addWidget(btn_row, 1, 0, 1, 2)
        grid.addWidget(self._status_label, 2, 0, 1, 2)
        root.addLayout(grid)
        root.addStretch(1)

    def update_from_state(self, state: AppState) -> None:
        self._state = state
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        selected = self._combo.currentText()
        profiles = self._profile_store.list_profiles()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(list(profiles))
        if selected in profiles:
            self._combo.setCurrentText(selected)
        self._combo.blockSignals(False)
        is_processing = self._state.runtime.is_processing
        has_selection = bool(self._combo.currentText())
        self._save_btn.setEnabled(not is_processing)
        self._load_btn.setEnabled(not is_processing and has_selection)
        self._delete_btn.setEnabled(not is_processing and has_selection)
        self._status_label.setText(
            f"{len(profiles)} saved profile(s) available." if profiles else "No saved profiles yet."
        )

    def _save_profile(self) -> None:
        if self._state.runtime.is_processing:
            return
        name, accepted = QInputDialog.getText(
            self, "Save Profile", "Profile name:", text=self._combo.currentText()
        )
        if not accepted:
            return
        try:
            saved = self._profile_store.save_profile(name, self._state.to_legacy_dict())
        except (OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return
        self._refresh_controls()
        self._combo.setCurrentText(saved)
        self._status_label.setText(f'Saved: "{saved}"')

    def _load_profile(self) -> None:
        if self._state.runtime.is_processing:
            return
        name = self._combo.currentText().strip()
        if not name:
            return
        try:
            payload = self._profile_store.load_profile(name)
        except (FileNotFoundError, OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Load Profile Failed", str(exc))
            self._refresh_controls()
            return
        loaded = AppState.from_settings(AppSettings.from_legacy_dict(payload, DEFAULT_DATA))
        new_runtime = replace(
            self._state.runtime,
            status_text=f'Profile loaded: "{name}"',
            last_error=None,
        )
        new_state = replace(loaded, paths=self._state.paths, runtime=new_runtime)
        self._state = new_state
        self._on_state_changed(new_state)
        self._status_label.setText(f'Loaded: "{name}"')

    def _delete_profile(self) -> None:
        if self._state.runtime.is_processing:
            return
        name = self._combo.currentText().strip()
        if not name:
            return
        confirm = QMessageBox.question(self, "Delete Profile", f'Delete profile "{name}"?')
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._profile_store.delete_profile(name)
        except (FileNotFoundError, OSError, ProfileError) as exc:
            QMessageBox.warning(self, "Delete Profile Failed", str(exc))
            self._refresh_controls()
            return
        self._status_label.setText(f'Deleted: "{name}"')
        self._refresh_controls()
