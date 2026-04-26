"""Dialog for saving or resetting per-model default parameters."""

from __future__ import annotations

import traceback
from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_data.constants import MDX_ARCH_TYPE, NO_MODEL, VR_ARCH_PM
from uvr_qt.services.processing_facade import ProcessingFacade
from uvr_qt.state import AppState


class ModelDefaultsDialog(QDialog):
    """Non-modal dialog for saving/deleting per-model default parameters.

    The "current settings" that get saved are taken from the AppState provided
    via update_from_state() — i.e. whatever the user has configured in the main
    window and the Advanced Settings panel at the time they click Apply.
    """

    def __init__(
        self,
        state: AppState,
        facade: ProcessingFacade,
        on_state_changed: Callable[[AppState], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Defaults")
        self.setModal(False)
        self.resize(500, 300)
        self._state = state
        self._facade = facade
        self._on_state_changed = on_state_changed

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self._build_info_group())
        layout.addWidget(self._build_model_group())
        layout.addWidget(self._build_action_group())

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.close)
        layout.addWidget(close_box)

        self.update_from_state(state)

    # ── UI builders ───────────────────────────────────────────────────────────

    def _build_info_group(self) -> QGroupBox:
        group = QGroupBox("About Model Defaults")
        layout = QVBoxLayout(group)
        info = QLabel(
            "UVR stores per-model parameter presets in a small JSON file alongside each model.\n"
            "Select a VR or MDX model and click <b>Apply Current Settings</b> to save the\n"
            "values you have configured in the Advanced Settings panel as that model's defaults.\n\n"
            "<b>Delete Saved Defaults</b> restores the built-in settings for the selected model.",
            group,
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _build_model_group(self) -> QGroupBox:
        group = QGroupBox("Model Selection")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Architecture"))
        self.arch_combo = QComboBox(group)
        self.arch_combo.addItems([VR_ARCH_PM, MDX_ARCH_TYPE])
        self.arch_combo.currentTextChanged.connect(self._repopulate_models)
        layout.addWidget(self.arch_combo)

        layout.addWidget(QLabel("Model"))
        self.model_combo = QComboBox(group)
        self.model_combo.setMinimumWidth(200)
        layout.addWidget(self.model_combo)
        layout.addStretch(1)
        return group

    def _build_action_group(self) -> QGroupBox:
        group = QGroupBox("Actions")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        self.apply_btn = QPushButton("Apply Current Settings as Defaults", group)
        self.apply_btn.clicked.connect(self._apply_defaults)
        layout.addWidget(self.apply_btn)

        self.delete_btn = QPushButton("Delete Saved Defaults", group)
        self.delete_btn.clicked.connect(self._delete_defaults)
        layout.addWidget(self.delete_btn)

        layout.addStretch(1)
        self.status_label = QLabel("", group)
        layout.addWidget(self.status_label)
        return group

    # ── Public API ────────────────────────────────────────────────────────────

    def update_from_state(self, state: AppState) -> None:
        self._state = state
        self._repopulate_models(self.arch_combo.currentText())

    # ── Internal ──────────────────────────────────────────────────────────────

    def _repopulate_models(self, arch: str) -> None:
        process_method = VR_ARCH_PM if arch == VR_ARCH_PM else MDX_ARCH_TYPE
        try:
            models = self._facade.available_models_for_method(process_method)
        except Exception:
            models = ()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if models:
            self.model_combo.addItems(list(models))
        else:
            self.model_combo.addItem(NO_MODEL)
        self.model_combo.blockSignals(False)
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        ok = self.model_combo.currentText() not in ("", NO_MODEL)
        self.apply_btn.setEnabled(ok)
        self.delete_btn.setEnabled(ok)

    def _state_for_selected(self) -> AppState:
        """Return a copy of the current state with the selected model active."""
        from dataclasses import replace

        arch = self.arch_combo.currentText()
        model_name = self.model_combo.currentText()
        if arch == VR_ARCH_PM:
            return replace(
                self._state,
                models=replace(self._state.models, vr_model=model_name),
                processing=replace(self._state.processing, process_method=VR_ARCH_PM),
            )
        return replace(
            self._state,
            models=replace(self._state.models, mdx_net_model=model_name),
            processing=replace(self._state.processing, process_method=MDX_ARCH_TYPE),
        )

    def _apply_defaults(self) -> None:
        self.status_label.setText("")
        state = self._state_for_selected()
        try:
            name = self._facade.save_model_defaults(state)
            self.status_label.setText(f'Saved defaults for "{name}".')
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Could not save model defaults:\n\n{exc}",
            )

    def _delete_defaults(self) -> None:
        self.status_label.setText("")
        state = self._state_for_selected()
        model_name = self.model_combo.currentText()
        reply = QMessageBox.question(
            self,
            "Delete Defaults",
            f'Delete saved default parameters for "{model_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            name = self._facade.delete_model_defaults(state)
            self.status_label.setText(f'Defaults deleted for "{name}".')
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Delete Failed",
                f"Could not delete model defaults:\n\n{exc}",
            )
