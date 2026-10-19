# cxkj-mini-keyboard

An open-source configurator for the **CXKJ MINI_KEYBOARD**, a 12-key + 3-knob Bluetooth macropad
sold on AliExpress (USB ID `514C:8842`). It replaces the vendor's `MINI_KEYBOARD.exe`.

It reads the three layers of the keyboard, lets you change what each key and knob does, and
writes the changes back:
- **Keys:** a key combination, or a macro of up to 18 steps.
- **Media:** volume, playback, brightness, calculator, browser keys and more.
- **Mouse:** clicks and the scroll wheel, with modifiers (for example, Ctrl + wheel to zoom).

## Requirements

- **Windows.** It has only been tested on Windows 11. Capturing key combinations relies on
  Windows scan codes.
- **Python 3.10 or newer.**
- **The keyboard connected with a USB cable.** It cannot be configured over Bluetooth: the
  configuration channel only exists over USB.

## Installation

```powershell
git clone https://github.com/Kurut1su/cxkj-mini-keyboard.git
cd cxkj-mini-keyboard
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.txt
```

`requirements.txt` pins exact versions with their SHA-256 hashes, so pip refuses any package
that does not match.

## Running

```powershell
.venv\Scripts\python -m cxkj_mini_keyboard
```

The app reads the keyboard when it starts.

## Usage

1. **Choose a layer** (*Layer 1–3*). The keyboard's side button switches between the same layers.
2. **Select a key or knob action**, then click **Edit…**. Each knob has three actions: turn
   left, press and turn right.
3. **Choose the new action:**
   - **Keys:** click *Capture combination* and press the keys. Capture several times to build a
     macro. Keys that Windows keeps for itself (such as Win or Print Screen) can be picked from
     the list instead.
   - **Media:** pick a media key.
   - **Mouse:** pick mouse buttons and the wheel direction.
4. Edited actions are highlighted and **nothing is sent yet**. Click **Write to keyboard** to
   write them. The app reads the keyboard back afterwards to check that every change was saved.

### Backups

- **Before every write**, the app saves the current configuration to
  `%LOCALAPPDATA%\cxkj-mini-keyboard\backups`.
- **Save backup…** saves a backup wherever you choose.
- **Restore backup…** loads a backup and marks its differences as pending changes. Review them,
  then click *Write to keyboard*.

Save a backup before your first change, so you can always get the original configuration back.

## Safety

The app only uses the commands needed to read and write keys. It never sends the vendor
protocol's commands that change the keyboard model or start a firmware update, which could leave
the keyboard unusable. Even so, this is an unofficial tool for an undocumented device: use it at
your own risk.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

The tests do not need the keyboard.
