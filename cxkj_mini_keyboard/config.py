"""Whole-device configuration: read it from the macropad, write changes back, save it as JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .actions import RECORD_SIZE, Action, decode
from .device import LAYERS, Macropad

FORMAT_VERSION = 1

# layer -> id -> record. In Config.layers the dicts keep the keyboard's read order, which is
# what maps records to physical actions (see layout.py).
Records = dict[int, dict[int, bytes]]


@dataclass
class Config:
    vendor_id: int
    product_id: int
    keys: int
    knobs: int
    layers: Records = field(default_factory=dict)

    def action(self, layer: int, key_id: int) -> Action | None:
        record = self.layers.get(layer, {}).get(key_id)
        return decode(record) if record else None

    def id_at(self, layer: int, position: int) -> int | None:
        """Id of the record at a physical position (see layout.py) in a layer."""
        ids = list(self.layers.get(layer, {}))
        return ids[position] if position < len(ids) else None

    def to_json(self) -> dict:
        return {
            "format": FORMAT_VERSION,
            "saved": datetime.now().isoformat(timespec="seconds"),
            "device": {"vendor_id": f"0x{self.vendor_id:04x}", "product_id": f"0x{self.product_id:04x}",
                       "keys": self.keys, "knobs": self.knobs},
            # Records in the keyboard's read order; "position" is informative.
            "layers": {
                str(layer): {
                    str(key_id): {"position": position, "raw": record.hex(" "),
                                  "action": decode(record).to_dict()}
                    for position, (key_id, record) in enumerate(records.items())
                }
                for layer, records in self.layers.items()
            },
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Config:
        """Load a backup saved by save(). Only the raw records are used; "action" is informative.

        Backups saved before 2026-10-19 are sorted by id instead of in read order. That is fine
        for restoring, which writes by id, but not for showing knob directions.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != FORMAT_VERSION:
            raise ValueError(f"unsupported backup format: {data.get('format')}")
        dev = data["device"]
        config = cls(int(dev["vendor_id"], 16), int(dev["product_id"], 16), dev["keys"], dev["knobs"])
        for layer, records in data["layers"].items():
            config.layers[int(layer)] = {}
            for key_id, entry in records.items():
                record = bytes.fromhex(entry["raw"])
                if len(record) != RECORD_SIZE or record[1] != int(key_id) or record[2] != int(layer):
                    raise ValueError(f"invalid record in layer {layer}, id {key_id}")
                config.layers[int(layer)][int(key_id)] = record
        return config

    def differences(self, other: Config) -> Records:
        """Records of `other` that differ from this configuration."""
        diff: Records = {}
        for layer, records in other.layers.items():
            for key_id, record in records.items():
                if self.layers.get(layer, {}).get(key_id) != record:
                    diff.setdefault(layer, {})[key_id] = record
        return diff


def read_config(pad: Macropad) -> Config:
    keys, knobs = pad.identify()
    config = Config(pad.info.vendor_id, pad.info.product_id, keys, knobs)
    for layer in LAYERS:
        config.layers[layer] = pad.read_layer(layer, keys, knobs)
    return config


def write_changes(pad: Macropad, changes: Records) -> tuple[Config, Records]:
    """Write the changed records, one commit per layer, then read everything back.

    Returns (configuration read back, records that did not read back as written).
    """
    keys, knobs = pad.identify()
    for layer in LAYERS:
        records = changes.get(layer)
        if not records:
            continue
        for record in records.values():
            pad.write_record(record, keys, knobs)
        pad.commit()
    after = read_config(pad)
    failed: Records = {}
    for layer, records in changes.items():
        for key_id, record in records.items():
            if after.layers.get(layer, {}).get(key_id) != record:
                failed.setdefault(layer, {})[key_id] = record
    return after, failed


def backup_path(folder: Path) -> Path:
    return folder / f"backup-{datetime.now():%Y%m%d-%H%M%S}.json"
