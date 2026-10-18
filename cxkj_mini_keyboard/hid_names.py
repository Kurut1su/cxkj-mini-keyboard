"""Human-readable names for HID keyboard usages, modifiers and consumer (media) usages."""

# Modifier byte bits (HID boot keyboard report).
MODIFIERS = [
    (0x01, "Ctrl"),
    (0x02, "Shift"),
    (0x04, "Alt"),
    (0x08, "Win"),
    (0x10, "RCtrl"),
    (0x20, "RShift"),
    (0x40, "RAlt"),
    (0x80, "RWin"),
]

# Keyboard/Keypad page (0x07) usages.
KEYCODES: dict[int, str] = {}
KEYCODES.update({0x04 + i: chr(ord("A") + i) for i in range(26)})
KEYCODES.update({0x1E + i: str((i + 1) % 10) for i in range(10)})
KEYCODES.update({
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab", 0x2C: "Space",
    0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]", 0x31: "\\", 0x32: "#",
    0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",", 0x37: ".", 0x38: "/",
    0x39: "CapsLock",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause", 0x49: "Insert",
    0x4A: "Home", 0x4B: "PageUp", 0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock", 0x54: "Num/", 0x55: "Num*", 0x56: "Num-", 0x57: "Num+",
    0x58: "NumEnter", 0x62: "Num0", 0x63: "Num.", 0x64: "<>", 0x65: "Menu",
})
KEYCODES.update({0x3A + i: f"F{i + 1}" for i in range(12)})
KEYCODES.update({0x68 + i: f"F{i + 13}" for i in range(12)})
KEYCODES.update({0x59 + i: f"Num{i + 1}" for i in range(9)})

# Consumer page (0x0C) usages offered by the vendor app.
CONSUMER: dict[int, str] = {
    0x00CD: "Play/Pausa",
    0x00B7: "Stop",
    0x00B6: "Pista anterior",
    0x00B5: "Pista siguiente",
    0x00E2: "Silencio",
    0x00E9: "Volumen +",
    0x00EA: "Volumen −",
    0x006F: "Brillo +",
    0x0070: "Brillo −",
    0x0152: "Graves +",
    0x0153: "Graves −",
    0x0154: "Agudos +",
    0x0155: "Agudos −",
    0x0183: "Reproductor multimedia",
    0x018A: "Correo",
    0x0192: "Calculadora",
    0x0194: "Mi PC",
    0x0223: "Navegador: inicio",
    0x0224: "Navegador: atrás",
    0x0225: "Navegador: adelante",
    0x0227: "Navegador: recargar",
}


def modifier_names(mods: int) -> list[str]:
    return [name for bit, name in MODIFIERS if mods & bit]


def key_name(code: int) -> str:
    return KEYCODES.get(code, f"0x{code:02X}")


def combo_name(mods: int, code: int) -> str:
    parts = modifier_names(mods)
    if code:
        parts.append(key_name(code))
    return "+".join(parts) or "(nada)"


def consumer_name(usage: int) -> str:
    return CONSUMER.get(usage, f"Multimedia 0x{usage:04X}")
