"""Whole-device configuration: read it from the macropad and save it as JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .actions import Action, decode
from .device import LAYERS, Macropad

FORMAT_VERSION = 1


@dataclass
class Config:
    vendor_id: int
    product_id: int
    keys: int
    knobs: int
    layers: dict[int, dict[int, bytes]] = field(default_factory=dict)  # layer -> id -> record

    def action(self, layer: int, key_id: int) -> Action | None:
        record = self.layers.get(layer, {}).get(key_id)
        return decode(record) if record else None

    def to_json(self) -> dict:
        return {
            "format": FORMAT_VERSION,
            "saved": datetime.now().isoformat(timespec="seconds"),
            "device": {"vendor_id": f"0x{self.vendor_id:04x}", "product_id": f"0x{self.product_id:04x}",
                       "keys": self.keys, "knobs": self.knobs},
            "layers": {
                str(layer): {
                    str(key_id): {"raw": record.hex(" "), "action": decode(record).to_dict()}
                    for key_id, record in sorted(records.items())
                }
                for layer, records in self.layers.items()
            },
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")


def read_config(pad: Macropad) -> Config:
    keys, knobs = pad.identify()
    config = Config(pad.info.vendor_id, pad.info.product_id, keys, knobs)
    for layer in LAYERS:
        config.layers[layer] = pad.read_layer(layer, keys, knobs)
    return config
