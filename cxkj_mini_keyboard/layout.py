"""Physical layout of the 12-key + 3-knob model.

A physical action is identified by its **position** in the list of records a layer read
returns, not by the record id (byte 1). The id only says which stored record a write
overwrites, in place. The ids of the knob actions come in a different order in each layer
(for example 18, 17, 16 or 16, 17, 18 for the top knob), so a fixed id -> direction table
is wrong. Tested on 2026-10-19 on layers 1 and 3.

Positions: keys 0..11 (row-major, 4 columns), then for each knob, top to bottom:
turn left, press, turn right.
"""

from dataclasses import dataclass

KEY_COLUMNS = 4
KEY_POSITIONS = list(range(12))


@dataclass(frozen=True)
class Knob:
    name: str
    left: int  # positions
    press: int
    right: int


KNOBS = [
    Knob(name, left=12 + 3 * i, press=13 + 3 * i, right=14 + 3 * i)
    for i, name in enumerate(("Top knob", "Middle knob", "Large knob"))
]
