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

import sys
from pathlib import Path

import boards

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "firmware" / "micropython" / "smartbin" / "board_spec.py"

#: Above this fraction of the header able to wake the chip, the short thing to say is which pins
#: CANNOT. On the C6 three pins of eleven could wake it; on the S3 it is nearly all of them, and
#: "and nothing else" after a list of twenty is not a sentence anyone reads.
MOSTLY_WAKE_CAPABLE = 0.5


def pin_names(pins: dict, gpios) -> list:
    """Silkscreen labels for a set of GPIOs, so a note names what is printed on the board."""
    names = []
    for gpio in gpios:
        labels = [label for label, number in pins.items() if number == gpio]
        names.append("/".join(labels) if labels else f"GPIO{gpio}")
    return names


def describe_wake(pins: dict, wake_capable: list) -> str:
    """One sentence saying which header pins can wake the chip, from whichever side is shorter."""
    by_gpio = sorted(pins.items(), key=lambda pin: pin[1])
    can = [label for label, gpio in by_gpio if gpio in wake_capable]
    cannot = [label for label, gpio in by_gpio if gpio not in wake_capable]
    if not cannot:
        return "every pin"
    if len(can) / len(by_gpio) > MOSTLY_WAKE_CAPABLE:
        return f"every pin except {', '.join(cannot)}"
    return f"{', '.join(can)} and nothing else"


def render(board: dict) -> str:
    pins = board["pins"]
    pin_lines = "\n".join(
        f'    "{label}": {gpio},' for label, gpio in sorted(pins.items(), key=lambda p: p[1])
    )
    example_label, example_gpio = min(
        ((label, gpio) for label, gpio in pins.items() if label != f"D{gpio}"),
        default=(None, None), key=lambda pin: pin[1])
    mislabelled = (f"{example_label} is GPIO{example_gpio}" if example_label
                   else "the labels are not the GPIO numbers")
    # One line per role, naming every pin that has it. Emitting a line per GPIO instead
    # reprints the whole note ten times for a role like "on ADC2", which is unreadable.
    special = "\n".join(
        f"#   {', '.join(pin_names(pins, role['gpio']))}: {role['note']}"
        for role in board.get("pin_roles", {}).values()
        if role["gpio"]
    )

    return f'''"""
{board["name"]} — the facts, generated from boards/{board["id"]}.json.

DO NOT EDIT. Run `make` after changing the board definition; `make check` fails if this is stale.

The silkscreen label is not the GPIO number on this board — {mislabelled} — which is the
single easiest mistake to make here, and the reason this table exists in exactly one place.
{chr(10) + "# Pins with a second job:" + chr(10) + special if special else ""}
"""

NAME = "{board["name"]}"
CHIP = "{board["chip"]}"

#: Silkscreen label -> GPIO number.
PINS = {{
{pin_lines}
}}

#: GPIOs that can wake the chip from deep sleep. On this board that is {describe_wake(
    pins, board["wake_capable_gpio"])}.
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
    try:
        board = boards.load()
        definition = boards.definition_path()
    except boards.BoardError as broken:
        print(f"cannot generate the board facts: {broken}", file=sys.stderr)
        return 1
    generated = render(board)

    if "--check" in sys.argv:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != generated:
            print(f"{OUTPUT.relative_to(REPO)} is out of date; run: make")
            return 1
        print(f"   {OUTPUT.name} matches {definition.name}")
        return 0

    OUTPUT.write_text(generated)
    print(f"   wrote {OUTPUT.relative_to(REPO)} from {definition.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
