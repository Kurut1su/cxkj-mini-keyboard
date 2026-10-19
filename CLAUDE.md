# cxkj-mini-keyboard

A replacement configurator for the **CXKJ MINI_KEYBOARD**, an AliExpress Bluetooth macropad with
12 keys and 3 knobs with push buttons (USB `514C:8842`). It replaces the vendor app
(`MINI_KEYBOARD.exe`).

## Status

- **v0.1**, tested with the real keyboard. It identifies the keyboard, reads the 3 layers, shows
  them in a GUI and saves a JSON backup.
- **Writing works** (`03 FD …` + `03 FD FE FF`), tested with a single-key record and persistent
  across unplugging. `Macropad.write_record` and `Macropad.commit` in `device.py`.
- **GUI editing** implemented on 2026-10-19: per-slot editor, pending changes, "Write to keyboard" (auto
  backup to `%LOCALAPPDATA%\cxkj-mini-keyboard\backups`, one commit per layer, read back to
  verify) and "Restore backup…". Tested on the keyboard: single keys, a macro,
  media, mouse wheel and restoring a backup.

## Stack and environment

- Python ≥ 3.10 + **PySide6-Essentials** (not the full PySide6) + **hidapi**.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.txt
.venv\Scripts\python -m cxkj_mini_keyboard      # starts the GUI (blocks until closed)
```

- Configuration is **only possible over USB cable**: the vendor channel does not exist over
  Bluetooth.

## Layout

| Path | Contents |
|---|---|
| `cxkj_mini_keyboard/device.py` | HID transport: `find_devices` and `Macropad` (`identify`, `read_layer`, `write_record`, `commit`) |
| `cxkj_mini_keyboard/actions.py` | `decode` / `encode` between a 50-byte record and `KeyAction`, `MediaAction`, `MouseAction`, … |
| `cxkj_mini_keyboard/hid_names.py` | Names for HID keys, modifiers and media codes |
| `cxkj_mini_keyboard/scancodes.py` | Windows scan code → HID keycode, for capturing key combos |
| `cxkj_mini_keyboard/layout.py` | Key placement and physical knob mapping |
| `cxkj_mini_keyboard/config.py` | `Config` (JSON save/load, diff), `read_config`, `write_changes` (write + commit + verify) |
| `cxkj_mini_keyboard/editor.py` | Dialog to edit one action: keys/macro (with capture), media, mouse |
| `cxkj_mini_keyboard/gui.py` | Main window (Qt): pending changes, write with auto-backup, restore a backup |
| `tests/` | `unittest` tests (no hardware): `.venv\Scripts\python -m unittest discover -s tests` |

## Protocol in brief

HID interface 0 (usage page `0xFF00`). Output reports of 65 bytes (`03` + 64 bytes) are sent and
64-byte replies are read.
- `03 FB FB FB`: identifies the keyboard.
- `03 FA <keys> <knobs> <layer>`: reads a layer (one packet per key or knob action).
- `03 FD <record>`: writes a key.
- `03 FD FE FF`: commits and saves.

## Hardware safety rules

- **Never send** `03 FC …` (changes the model) or `03 EF EF` (bootloader). They can brick the
  keyboard.
- **Never write** to the `AE*` GATT characteristics over Bluetooth: they may be OTA.
- Keys are 3 rows × 4 columns, row-major (1–4 / 5–8 / 9–12), with the knobs on the right and the
  large one at the bottom. Confirmed on the keyboard.
- **Writing:** test on a layer that is not in use first. Back up before and read back afterwards
  to compare.
- Before sending an untested command to the keyboard, explain what it does and ask the user to
  confirm.
- Map physical actions by **position** in a layer's read order, not by ID (record byte 1): keys
  are positions 1–12, then left / press / right of each knob from top to bottom. The ID only says
  which record a write overwrites, in place. The knob IDs come in a different order in each
  layer, so there is no fixed ID → direction table.

## Conventions

- **Code, user interface and documentation** (identifiers, UI text, comments, docstrings,
  commits, `.md` files) in **English**.
- **Dependencies:** venv + pip, not uv. `requirements.txt` with exact versions and SHA-256 hashes.
  `pyproject.toml` uses flexible ranges.
- Do not pin versions published less than two weeks ago.
- Running the GUI to test blocks. Use test scripts that do not open it, or close it afterwards,
  and do not leave processes holding the HID device.

## Open questions

- LEDs: 7 colours and modes 0–5 (0 = off), always off over Bluetooth. Reading returns no LED
  record, and `03 FE B0 …` is untested.
- Layers are switched with a push button on the side edge (from the product listing).
- Chip: JieLi (AC63xx) hypothesis, unconfirmed because the marking is scratched off.
