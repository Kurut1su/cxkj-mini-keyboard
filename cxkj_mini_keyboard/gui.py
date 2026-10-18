"""Main window: shows the configuration read from the macropad (read-only for now)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import APP_NAME
from .config import Config, read_config
from .device import LAYERS, Macropad, MacropadError, find_devices
from .layout import KEY_COLUMNS, KEY_IDS, KNOBS

MAX_LABEL = 24


def _short(text: str) -> str:
    return text if len(text) <= MAX_LABEL else text[:MAX_LABEL - 1] + "…"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.config: Config | None = None
        self.layer = LAYERS[0]
        self.slot_titles: dict[int, str] = {}

        read_btn = QPushButton("Leer del teclado")
        read_btn.clicked.connect(lambda: self.read_device())
        self.save_btn = QPushButton("Guardar copia…")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_backup)
        self.status = QLabel()

        top = QHBoxLayout()
        top.addWidget(read_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.status, 1)

        self.layer_group = QButtonGroup(self)
        layers_row = QHBoxLayout()
        for layer in LAYERS:
            btn = QPushButton(f"Capa {layer}")
            btn.setCheckable(True)
            btn.setChecked(layer == self.layer)
            self.layer_group.addButton(btn, layer)
            layers_row.addWidget(btn)
        layers_row.addStretch()
        self.layer_group.idClicked.connect(self.set_layer)

        # Every key and knob action is a checkable button; its group id is the record id.
        self.slots = QButtonGroup(self)
        self.slots.idClicked.connect(lambda _: self.show_detail())

        keys_box = QGroupBox("Teclas")
        keys_grid = QGridLayout(keys_box)
        for i, key_id in enumerate(KEY_IDS):
            self.slot_titles[key_id] = f"Tecla {key_id}"
            btn = self._slot_button(key_id, min_height=70)
            keys_grid.addWidget(btn, i // KEY_COLUMNS, i % KEY_COLUMNS)
        for col in range(KEY_COLUMNS):
            keys_grid.setColumnStretch(col, 1)

        knobs_col = QVBoxLayout()
        for knob in KNOBS:
            box = QGroupBox(knob.name)
            row = QHBoxLayout(box)
            for key_id, label in ((knob.left, "⟲ Izquierda"), (knob.press, "Pulsar"), (knob.right, "Derecha ⟳")):
                self.slot_titles[key_id] = f"{knob.name}: {label}"
                row.addWidget(self._slot_button(key_id, min_height=50), 1)
            knobs_col.addWidget(box)

        body = QHBoxLayout()
        body.addWidget(keys_box, 3)
        body.addLayout(knobs_col, 2)

        self.detail = QLabel("Selecciona una tecla o una acción de rueda.")
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail.setWordWrap(True)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(layers_row)
        root.addLayout(body, 1)
        root.addWidget(self.detail)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.resize(1000, 560)

        self.refresh()
        QTimer.singleShot(0, lambda: self.read_device(quiet=True))

    def _slot_button(self, key_id: int, min_height: int) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setMinimumHeight(min_height)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.slots.addButton(btn, key_id)
        return btn

    def read_device(self, quiet: bool = False) -> None:
        devices = find_devices()
        if not devices:
            self.status.setText("Teclado no encontrado. ¿Está conectado por cable?")
            if not quiet:
                QMessageBox.warning(self, APP_NAME, "No se encuentra el teclado.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with Macropad(devices[0]) as pad:
                self.config = read_config(pad)
        except (MacropadError, OSError) as e:
            self.status.setText("Error al leer el teclado.")
            QMessageBox.critical(self, APP_NAME, f"Error al leer el teclado:\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        c = self.config
        self.status.setText(f"Leído: {c.keys} teclas, {c.knobs} ruedas "
                            f"(VID {c.vendor_id:04X}, PID {c.product_id:04X})")
        self.save_btn.setEnabled(True)
        self.refresh()

    def set_layer(self, layer: int) -> None:
        self.layer = layer
        self.refresh()

    def refresh(self) -> None:
        for key_id, title in self.slot_titles.items():
            btn = self.slots.button(key_id)
            action = self.config.action(self.layer, key_id) if self.config else None
            text = action.describe() if action else "—"
            short_title = f"Tecla {key_id}" if key_id in KEY_IDS else title.split(": ")[1]
            btn.setText(f"{short_title}\n{_short(text)}")
            btn.setToolTip(text)
        self.show_detail()

    def show_detail(self) -> None:
        key_id = self.slots.checkedId()
        if key_id < 0:
            return
        record = self.config.layers.get(self.layer, {}).get(key_id) if self.config else None
        if record is None:
            self.detail.setText(f"{self.slot_titles[key_id]} · capa {self.layer}: sin datos")
            return
        action = self.config.action(self.layer, key_id)
        self.detail.setText(f"<b>{self.slot_titles[key_id]}</b> · capa {self.layer} · "
                            f"{action.describe()}<br><tt>{record.hex(' ')}</tt>")

    def save_backup(self) -> None:
        if not self.config:
            return
        default = f"backup-{datetime.now():%Y%m%d-%H%M%S}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar copia", default, "JSON (*.json)")
        if path:
            self.config.save(Path(path))
            self.status.setText(f"Copia guardada en {path}")


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
