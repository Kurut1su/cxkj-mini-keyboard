"""Physical layout of the 12-key + 3-knob model.

Knob action ids were measured on the real device: the top knob's encoder is reversed,
so its "turn right" is the first id of its group while the other two knobs start with "left".
"""

from dataclasses import dataclass

KEY_COLUMNS = 4
KEY_IDS = list(range(1, 13))


@dataclass(frozen=True)
class Knob:
    name: str
    left: int
    press: int
    right: int


KNOBS = [
    Knob("Rueda de arriba", left=18, press=17, right=16),
    Knob("Rueda del medio", left=19, press=20, right=21),
    Knob("Rueda grande", left=22, press=23, right=24),
]
