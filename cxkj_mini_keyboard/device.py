"""HID transport for the macropad's configuration interface.

Commands:
    03 FB FB FB              -> identify, reply 03 FB <keys> <knobs>
    03 FA <keys> <knobs> <L> -> read layer L, one reply per key / knob action
    03 <record>              -> write one key / knob action (record[0] is FD)
    03 FD FE FF              -> commit: save the written records to the keyboard's storage

Never send 03 FC (changes the model) or 03 EF (bootloader).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import hid

from .actions import RECORD_MARKER, RECORD_SIZE

VENDOR_IDS = (0x514C, 0x1189)
PRODUCT_IDS = (0x8842, 0x8840, 0x8830, 0x8831, 0x8832, 0x8833, 0x8850)
CONFIG_USAGE_PAGE = 0xFF00
REPORT_ID = 0x03
PACKET_SIZE = 65  # report id + 64 bytes
LAYERS = (1, 2, 3)
FIRST_KNOB_ID = 16
COMMIT = (0xFD, 0xFE, 0xFF)
COMMIT_DELAY_S = 0.2  # the vendor app waits 200 ms after each commit
REPLY_WAIT_MS = 50


class MacropadError(Exception):
    pass


@dataclass
class DeviceInfo:
    path: bytes
    vendor_id: int
    product_id: int
    serial: str


def find_devices() -> list[DeviceInfo]:
    """Return the configuration interface of every connected macropad."""
    found = []
    for d in hid.enumerate():
        if d["vendor_id"] not in VENDOR_IDS or d["product_id"] not in PRODUCT_IDS:
            continue
        if d["usage_page"] == CONFIG_USAGE_PAGE or (d["usage_page"] == 0 and d["interface_number"] == 0):
            found.append(DeviceInfo(d["path"], d["vendor_id"], d["product_id"], d["serial_number"] or ""))
    return found


class Macropad:
    def __init__(self, info: DeviceInfo):
        self.info = info
        self._dev = hid.device()
        self._dev.open_path(info.path)

    def close(self) -> None:
        self._dev.close()

    def __enter__(self) -> Macropad:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _send(self, *payload: int) -> None:
        packet = bytes((REPORT_ID, *payload)).ljust(PACKET_SIZE, b"\0")
        if self._dev.write(packet) != PACKET_SIZE:
            raise MacropadError("could not write to the keyboard")

    def _read(self, timeout_ms: int = 1000) -> bytes:
        return bytes(self._dev.read(64, timeout_ms))

    def _drain(self) -> list[bytes]:
        """Discard pending input. Returns what was discarded, for diagnostics."""
        replies = []
        while reply := self._read(REPLY_WAIT_MS):
            replies.append(reply)
        return replies

    def identify(self) -> tuple[int, int]:
        """Return (number of keys, number of knobs)."""
        self._drain()
        self._send(0xFB, 0xFB, 0xFB)
        reply = self._read()
        if len(reply) < 4 or reply[:2] != bytes((REPORT_ID, 0xFB)):
            raise MacropadError(f"unexpected reply to identify: {reply.hex(' ')}")
        return reply[2], reply[3]

    def read_layer(self, layer: int, keys: int, knobs: int) -> dict[int, bytes]:
        """Read one layer. Returns {key id: 50-byte record}."""
        expected = keys + 3 * knobs
        self._drain()
        self._send(0xFA, keys, knobs, layer)
        records = {}
        while len(records) < expected:
            reply = self._read()
            if not reply:
                raise MacropadError(f"layer {layer}: received {len(records)} of {expected} records")
            if reply[:2] != bytes((REPORT_ID, 0xFA)):
                continue
            # reply = 03 FA record[1..]; record[0] is always FD for keys.
            record = (b"\xfd" + reply[2:2 + RECORD_SIZE - 1]).ljust(RECORD_SIZE, b"\0")
            records[record[1]] = record
        return records

    def write_record(self, record: bytes, keys: int, knobs: int) -> list[bytes]:
        """Send one key / knob record. It is not saved until commit().

        Returns any replies the keyboard sent (none are expected).
        """
        valid_ids = set(range(1, keys + 1)) | set(range(FIRST_KNOB_ID, FIRST_KNOB_ID + 3 * knobs))
        if len(record) != RECORD_SIZE:
            raise ValueError(f"record must be {RECORD_SIZE} bytes, got {len(record)}")
        # These checks also keep a record from ever looking like the commit packet.
        if record[0] != RECORD_MARKER or record[1] not in valid_ids or record[2] not in LAYERS:
            raise ValueError(f"refusing to write a malformed record: {record[:4].hex(' ')}")
        self._drain()
        self._send(*record)
        return self._drain()

    def commit(self) -> list[bytes]:
        """Save the records written since the last commit. Returns any replies."""
        self._send(*COMMIT)
        time.sleep(COMMIT_DELAY_S)
        return self._drain()
