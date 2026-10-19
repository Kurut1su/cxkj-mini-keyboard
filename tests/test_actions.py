"""Record decoding and encoding, checked against records read from the real keyboard."""

import unittest

from cxkj_mini_keyboard.actions import (
    MAX_STEPS, KeyAction, MediaAction, MouseAction, decode, encode,
)

# (id, layer, record bytes up to the last non-zero one), from the 2026-10-18 backup.
REAL_RECORDS = [
    (1, 1, "fd 01 01 02 00 00 00 00 00 01 b6"),        # media: previous track
    (5, 1, "fd 05 01 01 00 00 00 00 00 01 04 43"),     # Alt+F10
    (20, 1, "fd 14 01 01 00 00 00 00 00 01 03 10"),    # Ctrl+Shift+M
    (7, 2, "fd 07 02 01 00 00 00 00 00 02 00 0a 03 06"),  # macro: G, Ctrl+Shift+C
    (22, 1, "fd 16 01 03 00 00 00 00 00 04 00 00 00 00 ff"),  # mouse: wheel down
    (23, 1, "fd 17 01 03 00 00 00 00 00 04 00 04"),    # mouse: middle click
    (24, 2, "fd 18 02 03 00 00 00 00 00 04 01 00 00 00 01"),  # mouse: Ctrl+wheel up
]


def _record(hex_prefix: str) -> bytes:
    return bytes.fromhex(hex_prefix).ljust(50, b"\0")


class RoundTripTest(unittest.TestCase):
    def test_real_records_round_trip(self):
        for key_id, layer, raw in REAL_RECORDS:
            with self.subTest(raw=raw):
                record = _record(raw)
                self.assertEqual(encode(decode(record), key_id, layer), record)

    def test_decoded_values(self):
        self.assertEqual(decode(_record(REAL_RECORDS[0][2])).usage, 0xB6)
        self.assertEqual(decode(_record(REAL_RECORDS[3][2])).steps, [(0x00, 0x0A), (0x03, 0x06)])
        self.assertEqual(decode(_record(REAL_RECORDS[4][2])).wheel, -1)


class EncodeTest(unittest.TestCase):
    def test_media_count_is_one(self):
        record = encode(MediaAction(b"", 0x0192), 3, 1)
        self.assertEqual(record[9], 1)
        self.assertEqual(record[10:12], b"\x92\x01")

    def test_mouse_count_is_four(self):
        record = encode(MouseAction(b"", 0, 1, 0, 0, 0), 23, 3)
        self.assertEqual(record[9], 4)

    def test_step_limit(self):
        encode(KeyAction(b"", [(0, 0x04)] * MAX_STEPS), 1, 3)
        with self.assertRaises(ValueError):
            encode(KeyAction(b"", [(0, 0x04)] * (MAX_STEPS + 1)), 1, 3)
        with self.assertRaises(ValueError):
            encode(KeyAction(b"", []), 1, 3)

    def test_mouse_range(self):
        with self.assertRaises(ValueError):
            encode(MouseAction(b"", 0, 0, 200, 0, 0), 23, 3)


if __name__ == "__main__":
    unittest.main()
