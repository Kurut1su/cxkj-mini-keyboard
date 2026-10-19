"""Main window: shows the configuration read from the macropad, edits it and writes it back."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import APP_NAME
from .actions import decode, encode
from .config import Config, Records, backup_path, read_config, write_changes
from .device import LAYERS, Macropad, MacropadError, find_devices
from .editor import ActionDialog
from .layout import KEY_COLUMNS, KEY_POSITIONS, KNOBS

MAX_LABEL = 24
PENDING_STYLE = "font-weight: bold; color: #c05800;"


def _short(text: str) -> str:
    return text if len(text) <= MAX_LABEL else text[:MAX_LABEL - 1] + "…"


def _count(records: Records) -> int:
    return sum(len(r) for r in records.values())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.config: Config | None = None
        self.pending: Records = {}  # edited records not yet written: layer -> id -> record
        self.layer = LAYERS[0]
        self.slot_titles: dict[int, str] = {}  # position -> title
        self.backup_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "backups"

        read_btn = QPushButton("Read from keyboard")
        read_btn.clicked.connect(lambda: self.read_device())
        self.write_btn = QPushButton()
        self.write_btn.clicked.connect(self.write_device)
        self.save_btn = QPushButton("Save backup…")
        self.save_btn.clicked.connect(self.save_backup)
        self.restore_btn = QPushButton("Restore backup…")
        self.restore_btn.clicked.connect(self.restore_backup)
        self.status = QLabel()

        top = QHBoxLayout()
        for btn in (read_btn, self.write_btn, self.save_btn, self.restore_btn):
            top.addWidget(btn)
        top.addWidget(self.status, 1)

        self.layer_group = QButtonGroup(self)
        layers_row = QHBoxLayout()
        for layer in LAYERS:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(layer == self.layer)
            self.layer_group.addButton(btn, layer)
            layers_row.addWidget(btn)
        layers_row.addStretch()
        self.layer_group.idClicked.connect(self.set_layer)

        # Every key and knob action is a checkable button; its group id is the physical position.
        # The record id at that position depends on the layer (see layout.py).
        self.slots = QButtonGroup(self)
        self.slots.idClicked.connect(lambda _: self.show_detail())

        keys_box = QGroupBox("Keys")
        keys_grid = QGridLayout(keys_box)
        for position in KEY_POSITIONS:
            self.slot_titles[position] = f"Key {position + 1}"
            btn = self._slot_button(position, min_height=70)
            keys_grid.addWidget(btn, position // KEY_COLUMNS, position % KEY_COLUMNS)
        for col in range(KEY_COLUMNS):
            keys_grid.setColumnStretch(col, 1)

        knobs_col = QVBoxLayout()
        for knob in KNOBS:
            box = QGroupBox(knob.name)
            row = QHBoxLayout(box)
            for position, label in ((knob.left, "⟲ Left"), (knob.press, "Press"), (knob.right, "Right ⟳")):
                self.slot_titles[position] = f"{knob.name}: {label}"
                row.addWidget(self._slot_button(position, min_height=50), 1)
            knobs_col.addWidget(box)

        body = QHBoxLayout()
        body.addWidget(keys_box, 3)
        body.addLayout(knobs_col, 2)

        self.detail = QLabel("Select a key or a knob action.")
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail.setWordWrap(True)
        self.edit_btn = QPushButton("Edit…")
        self.edit_btn.clicked.connect(self.edit_slot)
        self.revert_btn = QPushButton("Discard change")
        self.revert_btn.clicked.connect(self.revert_slot)
        detail_row = QHBoxLayout()
        detail_row.addWidget(self.detail, 1)
        detail_row.addWidget(self.edit_btn)
        detail_row.addWidget(self.revert_btn)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(layers_row)
        root.addLayout(body, 1)
        root.addLayout(detail_row)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.resize(1100, 600)

        self.refresh()
        QTimer.singleShot(0, lambda: self.read_device(quiet=True))

    def _slot_button(self, position: int, min_height: int) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setMinimumHeight(min_height)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.slots.addButton(btn, position)
        return btn

    # --- state -------------------------------------------------------------------------------

    def id_at(self, position: int) -> int | None:
        """Record id of a physical position in the current layer."""
        return self.config.id_at(self.layer, position) if self.config else None

    def title(self, layer: int, key_id: int) -> str:
        ids = list(self.config.layers.get(layer, {})) if self.config else []
        return self.slot_titles[ids.index(key_id)] if key_id in ids else f"ID {key_id}"

    def record(self, layer: int, key_id: int) -> bytes | None:
        """The record shown for a slot: the pending edit if there is one, else the keyboard's."""
        if key_id in self.pending.get(layer, {}):
            return self.pending[layer][key_id]
        return self.config.layers.get(layer, {}).get(key_id) if self.config else None

    def is_pending(self, layer: int, key_id: int) -> bool:
        return key_id in self.pending.get(layer, {})

    def set_pending(self, layer: int, key_id: int, record: bytes | None) -> None:
        """Set or (with None) drop the pending edit of a slot."""
        layer_pending = self.pending.setdefault(layer, {})
        original = self.config.layers.get(layer, {}).get(key_id)
        if record is None or record == original:
            layer_pending.pop(key_id, None)
        else:
            layer_pending[key_id] = record
        if not layer_pending:
            del self.pending[layer]
        self.refresh()

    def confirm_discard(self, what: str) -> bool:
        if not self.pending:
            return True
        answer = QMessageBox.question(
            self, APP_NAME, f"There are {_count(self.pending)} changes not written to the keyboard. "
                            f"{what} will discard them. Continue?")
        return answer == QMessageBox.Yes

    # --- device ------------------------------------------------------------------------------

    def open_device(self, quiet: bool = False) -> Macropad | None:
        devices = find_devices()
        if not devices:
            self.status.setText("Keyboard not found. Is it connected with a USB cable?")
            if not quiet:
                QMessageBox.warning(self, APP_NAME, "Keyboard not found. Connect it with a USB cable.")
            return None
        return Macropad(devices[0])

    def read_device(self, quiet: bool = False) -> None:
        if not self.confirm_discard("Reading the keyboard"):
            return
        pad = self.open_device(quiet)
        if not pad:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with pad:
                self.config = read_config(pad)
        except (MacropadError, OSError) as e:
            self.status.setText("Error reading the keyboard.")
            QMessageBox.critical(self, APP_NAME, f"Error reading the keyboard:\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.pending = {}
        c = self.config
        self.status.setText(f"Read: {c.keys} keys, {c.knobs} knobs "
                            f"(VID {c.vendor_id:04X}, PID {c.product_id:04X})")
        self.refresh()

    def write_device(self) -> None:
        if not self.pending or not self.config:
            return
        layers = ", ".join(str(layer) for layer in sorted(self.pending))
        answer = QMessageBox.question(
            self, APP_NAME, f"{_count(self.pending)} changes will be written to the keyboard (layers {layers}).\n"
                            f"An automatic backup is saved first, to:\n{self.backup_dir}\n\nContinue?")
        if answer != QMessageBox.Yes:
            return
        pad = self.open_device()
        if not pad:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with pad:
                current = read_config(pad)
                if (current.keys, current.knobs) != (self.config.keys, self.config.knobs):
                    raise MacropadError("the connected keyboard is not the one that was read")
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_path(self.backup_dir)
                current.save(backup)
                after, failed = write_changes(pad, self.pending)
        except (MacropadError, OSError, ValueError) as e:
            self.status.setText("Error writing to the keyboard.")
            QMessageBox.critical(self, APP_NAME, f"Error writing to the keyboard:\n{e}\n\n"
                                                 f"The changes are still pending. Read the keyboard again "
                                                 f"to see its actual state.")
            return
        finally:
            QApplication.restoreOverrideCursor()
        written = _count(self.pending)
        self.config = after
        self.pending = failed
        self.refresh()
        if failed:
            slots = ", ".join(f"layer {layer} {self.title(layer, key_id)}"
                              for layer, records in sorted(failed.items()) for key_id in sorted(records))
            self.status.setText("Write incomplete.")
            QMessageBox.critical(self, APP_NAME, f"Reading back, these changes do not match what was written "
                                                 f"and are still pending:\n{slots}\n\nPrevious backup: {backup}")
        else:
            self.status.setText(f"Wrote and verified {written} changes. Previous backup: {backup.name}")

    # --- view --------------------------------------------------------------------------------

    def set_layer(self, layer: int) -> None:
        self.layer = layer
        self.refresh()

    def refresh(self) -> None:
        for layer in LAYERS:
            mark = " •" if layer in self.pending else ""
            self.layer_group.button(layer).setText(f"Layer {layer}{mark}")
        for position, title in self.slot_titles.items():
            btn = self.slots.button(position)
            key_id = self.id_at(position)
            record = self.record(self.layer, key_id) if key_id is not None else None
            text = decode(record).describe() if record else "—"
            short_title = title.split(": ")[-1]
            btn.setText(f"{short_title}\n{_short(text)}")
            btn.setToolTip(text)
            btn.setStyleSheet(PENDING_STYLE if self.is_pending(self.layer, key_id) else "")
        n = _count(self.pending)
        self.write_btn.setText(f"Write to keyboard ({n})" if n else "Write to keyboard")
        self.write_btn.setEnabled(bool(n))
        self.save_btn.setEnabled(self.config is not None)
        self.restore_btn.setEnabled(self.config is not None)
        self.show_detail()

    def show_detail(self) -> None:
        position = self.slots.checkedId()
        key_id = self.id_at(position) if position >= 0 else None
        self.edit_btn.setEnabled(key_id is not None)
        self.revert_btn.setEnabled(key_id is not None and self.is_pending(self.layer, key_id))
        if position < 0:
            return
        record = self.record(self.layer, key_id) if key_id is not None else None
        if record is None:
            self.detail.setText(f"{self.slot_titles[position]} · layer {self.layer}: no data")
            return
        state = " · <b>pending write</b>" if self.is_pending(self.layer, key_id) else ""
        self.detail.setText(f"<b>{self.slot_titles[position]}</b> · layer {self.layer} · ID {key_id} · "
                            f"{decode(record).describe()}{state}<br><tt>{record.hex(' ')}</tt>")

    # --- editing -----------------------------------------------------------------------------

    def edit_slot(self) -> None:
        position = self.slots.checkedId()
        key_id = self.id_at(position) if position >= 0 else None
        if key_id is None:
            return
        record = self.record(self.layer, key_id)
        title = f"{self.slot_titles[position]} · layer {self.layer}"
        dialog = ActionDialog(title, decode(record) if record else None, self)
        if dialog.exec() != ActionDialog.Accepted:
            return
        try:
            new = encode(dialog.result_action, key_id, self.layer)
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, f"This action cannot be saved:\n{e}")
            return
        self.set_pending(self.layer, key_id, new)

    def revert_slot(self) -> None:
        position = self.slots.checkedId()
        key_id = self.id_at(position) if position >= 0 else None
        if key_id is not None:
            self.set_pending(self.layer, key_id, None)

    # --- backups -----------------------------------------------------------------------------

    def save_backup(self) -> None:
        if not self.config:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save backup (what was read from the keyboard)",
                                              backup_path(Path()).name, "JSON (*.json)")
        if path:
            self.config.save(Path(path))
            self.status.setText(f"Backup saved to {path}")

    def restore_backup(self) -> None:
        if not self.config or not self.confirm_discard("Restoring a backup"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Restore backup", str(self.backup_dir), "JSON (*.json)")
        if not path:
            return
        try:
            backup = Config.load(Path(path))
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.critical(self, APP_NAME, f"Cannot read the backup:\n{e}")
            return
        if (backup.keys, backup.knobs) != (self.config.keys, self.config.knobs):
            QMessageBox.critical(self, APP_NAME, f"The backup is from a different model "
                                                 f"({backup.keys} keys, {backup.knobs} knobs).")
            return
        self.pending = self.config.differences(backup)
        self.refresh()
        n = _count(self.pending)
        self.status.setText(f"Backup loaded: {n} pending changes. Review them and click “Write to keyboard”."
                            if n else "The backup matches what is on the keyboard.")

    def closeEvent(self, e) -> None:
        if self.confirm_discard("Closing"):
            e.accept()
        else:
            e.ignore()


def main() -> int:
    app = QApplication([])
    app.setApplicationName("cxkj-mini-keyboard")
    window = MainWindow()
    window.show()
    return app.exec()
