"""Decoding of the 50-byte key records stored in the macropad.

Record layout:
    [0] 0xFD   [1] key id   [2] layer (1-3)   [3] type   [4..5] delay (LE, unverified)
    [9] entry count   [10..] type-specific data
"""

from __future__ import annotations

from dataclasses import dataclass

from .hid_names import combo_name, consumer_name, modifier_names

RECORD_SIZE = 50

TYPE_KEYS = 1
TYPE_MEDIA = 2
TYPE_MOUSE = 3


@dataclass
class Action:
    """Base class: an action whose type we can't decode yet."""

    raw: bytes

    def describe(self) -> str:
        return f"Tipo {self.raw[3]} (desconocido)"

    def to_dict(self) -> dict:
        return {"type": "unknown", "record_type": self.raw[3]}


@dataclass
class EmptyAction(Action):
    def describe(self) -> str:
        return "Sin asignar"

    def to_dict(self) -> dict:
        return {"type": "empty"}


@dataclass
class KeyAction(Action):
    """One key combination, or a sequence of them (macro)."""

    steps: list[tuple[int, int]]  # (modifier bits, HID keycode)

    def describe(self) -> str:
        return ", ".join(combo_name(m, k) for m, k in self.steps)

    def to_dict(self) -> dict:
        return {
            "type": "keys",
            "steps": [{"modifiers": modifier_names(m), "keycode": k, "name": combo_name(m, k)}
                      for m, k in self.steps],
        }


@dataclass
class MediaAction(Action):
    usage: int  # consumer page usage

    def describe(self) -> str:
        return consumer_name(self.usage)

    def to_dict(self) -> dict:
        return {"type": "media", "usage": self.usage, "name": consumer_name(self.usage)}


@dataclass
class MouseAction(Action):
    modifiers: int
    buttons: int  # bit 0 left, bit 1 right, bit 2 middle
    x: int
    y: int
    wheel: int

    def describe(self) -> str:
        parts = modifier_names(self.modifiers)
        for bit, name in ((1, "Clic izquierdo"), (2, "Clic derecho"), (4, "Clic central")):
            if self.buttons & bit:
                parts.append(name)
        if self.wheel:
            parts.append("Rueda arriba" if self.wheel > 0 else "Rueda abajo")
        if self.x or self.y:
            parts.append(f"Mover ({self.x:+d}, {self.y:+d})")
        return "+".join(parts) or "Ratón (nada)"

    def to_dict(self) -> dict:
        return {"type": "mouse", "modifiers": modifier_names(self.modifiers),
                "buttons": self.buttons, "x": self.x, "y": self.y, "wheel": self.wheel}


def _signed(b: int) -> int:
    return b - 256 if b > 127 else b


def decode(record: bytes) -> Action:
    if len(record) != RECORD_SIZE:
        raise ValueError(f"record must be {RECORD_SIZE} bytes, got {len(record)}")
    rtype, count, data = record[3], record[9], record[10:]
    if count == 0:
        return EmptyAction(record)
    if rtype == TYPE_KEYS:
        steps = [(data[2 * i], data[2 * i + 1]) for i in range(min(count, len(data) // 2))]
        return KeyAction(record, steps)
    if rtype == TYPE_MEDIA:
        return MediaAction(record, data[0] | data[1] << 8)
    if rtype == TYPE_MOUSE:
        return MouseAction(record, data[0], data[1], _signed(data[2]), _signed(data[3]), _signed(data[4]))
    return Action(record)
