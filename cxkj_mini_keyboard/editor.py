"""Dialog to edit the action of one key or knob action."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from .actions import MAX_STEPS, Action, KeyAction, MediaAction, MouseAction
from .hid_names import CONSUMER, KEYCODES, MODIFIERS, combo_name
from .scancodes import MODIFIER_SCANCODES, SCANCODE_TO_HID

# Left-hand modifiers offered as checkboxes; right-hand ones can still be captured.
BASIC_MODIFIERS = MODIFIERS[:4]
MOUSE_BUTTONS = [(0x01, "Left"), (0x02, "Right"), (0x04, "Middle")]
WHEEL_CHOICES = [(0, "No wheel"), (1, "Wheel up"), (-1, "Wheel down")]


class CaptureButton(QPushButton):
    """Click it, then press a key combination: emits (modifier bits, HID keycode).

    Releasing the modifiers without pressing another key captures the modifiers alone.
    Clicking elsewhere cancels.
    """

    captured = Signal(int, int)
    IDLE_TEXT = "Capture combination"

    def __init__(self) -> None:
        super().__init__(self.IDLE_TEXT)
        self.setAutoDefault(False)
        self.capturing = False
        self.mods = 0
        self.clicked.connect(self.start)

    def start(self) -> None:
        self.capturing = True
        self.mods = 0
        self.setText("Press the combination…")
        self.setFocus()

    def stop(self) -> None:
        self.capturing = False
        self.setText(self.IDLE_TEXT)

    def focusOutEvent(self, e) -> None:
        self.stop()
        super().focusOutEvent(e)

    def event(self, e) -> bool:
        if not self.capturing or e.type() not in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride):
            return super().event(e)
        # Swallow everything while capturing: Tab, Enter, Esc and shortcuts are keys to capture too.
        if e.type() == QEvent.ShortcutOverride or e.isAutoRepeat():
            e.accept()
            return True
        scancode = e.nativeScanCode()
        if e.type() == QEvent.KeyPress:
            if scancode in MODIFIER_SCANCODES:
                self.mods |= MODIFIER_SCANCODES[scancode]
                self.setText(combo_name(self.mods, 0) + "+…")
            elif scancode in SCANCODE_TO_HID:
                self.stop()
                self.captured.emit(self.mods, SCANCODE_TO_HID[scancode])
            else:
                self.setText(f"Unrecognized key (0x{scancode:X}); use the list")
        elif scancode in MODIFIER_SCANCODES and self.mods:
            self.stop()
            self.captured.emit(self.mods, 0)
        return True


class ModifierChecks(QWidget):
    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.boxes = []
        for bit, name in BASIC_MODIFIERS:
            box = QCheckBox(name)
            self.boxes.append((bit, box))
            row.addWidget(box)

    def value(self) -> int:
        return sum(bit for bit, box in self.boxes if box.isChecked())

    def set_value(self, mods: int) -> None:
        for bit, box in self.boxes:
            box.setChecked(bool(mods & bit))


class KeysTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.steps = QListWidget()

        capture = CaptureButton()
        capture.captured.connect(self.add_step)
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda: self._take(self.steps.currentRow()))
        up = QPushButton("Move up")
        up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("Move down")
        down.clicked.connect(lambda: self._move(1))
        clear = QPushButton("Clear")
        clear.clicked.connect(self.steps.clear)
        buttons = QHBoxLayout()
        for btn in (capture, remove, up, down, clear):
            btn.setAutoDefault(False)
            buttons.addWidget(btn)

        self.mods = ModifierChecks()
        self.key = QComboBox()
        self.key.addItem("(modifiers only)", 0)
        for code, name in sorted(KEYCODES.items()):
            self.key.addItem(name, code)
        add = QPushButton("Add")
        add.setAutoDefault(False)
        add.clicked.connect(lambda: self.add_step(self.mods.value(), self.key.currentData()))
        manual = QHBoxLayout()
        manual.addWidget(self.mods)
        manual.addWidget(self.key, 1)
        manual.addWidget(add)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Each step is one key combination. Several steps make a macro, "
                                f"sent in order (up to {MAX_STEPS})."))
        layout.addWidget(self.steps, 1)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Or pick the key from the list (for keys that Windows does not let you capture):"))
        layout.addLayout(manual)

    def add_step(self, mods: int, code: int) -> None:
        if not mods and not code:
            return
        if self.steps.count() >= MAX_STEPS:
            QMessageBox.warning(self, "Macro", f"Up to {MAX_STEPS} steps.")
            return
        item = QListWidgetItem(combo_name(mods, code))
        item.setData(Qt.UserRole, (mods, code))
        self.steps.addItem(item)
        self.steps.setCurrentItem(item)

    def _take(self, row: int) -> QListWidgetItem | None:
        return self.steps.takeItem(row) if row >= 0 else None

    def _move(self, delta: int) -> None:
        row = self.steps.currentRow()
        if row < 0 or not 0 <= row + delta < self.steps.count():
            return
        item = self._take(row)
        self.steps.insertItem(row + delta, item)
        self.steps.setCurrentItem(item)

    def set_action(self, action: KeyAction) -> None:
        for mods, code in action.steps:
            self.add_step(mods, code)

    def action(self) -> Action | None:
        steps = [self.steps.item(i).data(Qt.UserRole) for i in range(self.steps.count())]
        return KeyAction(b"", steps) if steps else None


class MediaTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.list = QListWidget()
        for usage, name in CONSUMER.items():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, usage)
            self.list.addItem(item)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)

    def set_action(self, action: MediaAction) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == action.usage:
                self.list.setCurrentRow(i)
                return
        # A code the list doesn't know: keep it selectable.
        item = QListWidgetItem(f"Media 0x{action.usage:04X}")
        item.setData(Qt.UserRole, action.usage)
        self.list.addItem(item)
        self.list.setCurrentItem(item)

    def action(self) -> Action | None:
        item = self.list.currentItem()
        return MediaAction(b"", item.data(Qt.UserRole)) if item else None


class MouseTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.mods = ModifierChecks()
        self.buttons = [(bit, QCheckBox(name)) for bit, name in MOUSE_BUTTONS]
        self.wheel = QComboBox()
        for value, name in WHEEL_CHOICES:
            self.wheel.addItem(name, value)
        self.x = self.y = 0  # pointer movement: kept from the original action, not editable

        buttons_row = QHBoxLayout()
        for _, box in self.buttons:
            buttons_row.addWidget(box)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Buttons:"))
        layout.addLayout(buttons_row)
        layout.addWidget(QLabel("Wheel:"))
        layout.addWidget(self.wheel)
        layout.addWidget(QLabel("Modifiers (for example, Ctrl + wheel = zoom):"))
        layout.addWidget(self.mods)
        layout.addStretch()

    def set_action(self, action: MouseAction) -> None:
        self.mods.set_value(action.modifiers)
        for bit, box in self.buttons:
            box.setChecked(bool(action.buttons & bit))
        self.wheel.setCurrentIndex(max(0, self.wheel.findData(max(-1, min(1, action.wheel)))))
        self.x, self.y = action.x, action.y

    def action(self) -> Action | None:
        buttons = sum(bit for bit, box in self.buttons if box.isChecked())
        wheel = self.wheel.currentData()
        if not (buttons or wheel or self.x or self.y):
            return None
        return MouseAction(b"", self.mods.value(), buttons, self.x, self.y, wheel)


class ActionDialog(QDialog):
    def __init__(self, title: str, action: Action | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.keys, self.media, self.mouse = KeysTab(), MediaTab(), MouseTab()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.keys, "Keys")
        self.tabs.addTab(self.media, "Media")
        self.tabs.addTab(self.mouse, "Mouse")
        for tab, action_class in ((self.keys, KeyAction), (self.media, MediaAction), (self.mouse, MouseAction)):
            if isinstance(action, action_class):
                tab.set_action(action)
                self.tabs.setCurrentWidget(tab)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self.resize(560, 420)
        self.result_action: Action | None = None

    def accept(self) -> None:
        action = self.tabs.currentWidget().action()
        if action is None:
            QMessageBox.warning(self, self.windowTitle(), "The action is empty.")
            return
        self.result_action = action
        super().accept()
