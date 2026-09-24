#!/usr/bin/env python3
"""
Generate the firmware's copy of the board facts from boards/<id>.json.

The firmware cannot read that file at runtime — it is not on the device — so it gets a generated
module instead. Generated rather than hand-written because the alternative is two copies of the
silkscreen-to-GPIO map, and the whole point of boards/ is that there is one.

    python3 tools/generate-board-spec.py [--check]

`--check` writes nothing and fails if the committed module is out of date, which is what `make
check` uses.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFINITION = REPO / "boards" / "xiao-esp32-c6.json"
OUTPUT = REPO / "firmware" / "micropython" / "smartbin" / "board_spec.py"


def render(board: dict) -> str:
    pins = board["pins"]
    pin_lines = "\n".join(
        f'    "{label}": {gpio},' for label, gpio in sorted(pins.items(), key=lambda p: p[1])
    )
    special = "\n".join(
        f"#   GPIO{gpio}: {role['note']}"
        for role in board.get("pin_roles", {}).values()
        for gpio in role["gpio"]
    )

    return f'''"""
{board["name"]} — the facts, generated from boards/{board["id"]}.json.

DO NOT EDIT. Run `make` after changing the board definition; `make check` fails if this is stale.

The silkscreen label is not the GPIO number on this board — D3 is GPIO{pins["D3"]} — which is the
single easiest mistake to make here, and the reason this table exists in exactly one place.
{chr(10) + "# Pins with a second job:" + chr(10) + special if special else ""}
"""

NAME = "{board["name"]}"
CHIP = "{board["chip"]}"

#: Silkscreen label -> GPIO number.
PINS = {{
{pin_lines}
}}

#: GPIOs that can wake the chip from deep sleep. On this board that is {", ".join(
    label for label, gpio in sorted(pins.items(), key=lambda p: p[1])
    if gpio in board["wake_capable_gpio"]
)} and nothing else.
WAKE_CAPABLE_GPIO = {tuple(board["wake_capable_gpio"])}

#: GPIOs with an analogue input.
ADC_GPIO = {tuple(board["adc_gpio"])}


def label_for(gpio):
    """The silkscreen label for a GPIO, for log messages a person has to read."""
    for label, number in PINS.items():
        if number == gpio:
            return label
    return "GPIO%d" % gpio
'''


def main() -> int:
    board = json.loads(DEFINITION.read_text())
    generated = render(board)

    if "--check" in sys.argv:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != generated:
            print(f"{OUTPUT.relative_to(REPO)} is out of date; run: make")
            return 1
        print(f"   {OUTPUT.name} matches {DEFINITION.name}")
        return 0

    OUTPUT.write_text(generated)
    print(f"   wrote {OUTPUT.relative_to(REPO)} from {DEFINITION.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
