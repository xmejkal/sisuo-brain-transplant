#!/usr/bin/env python3
"""
Which board this project is built around — resolved in one place, and checked against a contract.

    python3 tools/boards.py --path        the active board's definition file
    python3 tools/boards.py --id          the active board's id
    python3 tools/boards.py --list        every board available to switch to
    python3 tools/boards.py --paths       their file paths, for tools that take a list
    python3 tools/boards.py --get chip    one field, by dotted path
    python3 tools/boards.py --validate    check every board file against the contract
    python3 tools/boards.py --validate --for-fab
                                          also require what the PCB needs, not just the firmware

Boards are drop-in: add `boards/<id>.json`, put that id in `boards/active.json`, run `make`.
Nothing else names a board. This file is both the library the Python tools import and the command
the Makefile and `make check` call, because a second copy of "where is the board file" would be
the exact duplication that boards/ exists to remove.

The contract is enforced rather than documented. A board definition that a person merely
*described* correctly is how the C6 pin map nearly shipped with D3 read as GPIO3; a definition
that a program refuses to load cannot fail that way. Structural validity and fab-readiness are
separate on purpose — the firmware can be built and simulated against a board whose footprint
nobody has verified, and it is better to say so than to either block that work or let an
unverified footprint reach a gerber.
"""

import json
import sys
from pathlib import Path

#: Where the board files live, and the file that says which one is active.
REPO = Path(__file__).resolve().parent.parent
BOARDS_DIR = REPO / "boards"
SELECTION_FILE = BOARDS_DIR / "active.json"
DEFINITION_SUFFIX = ".json"

#: Files in boards/ that are not board definitions.
NOT_A_BOARD = frozenset({SELECTION_FILE.name})

#: The only schema version this code understands. A board file claiming a different one is
#: refused rather than read optimistically: the failure mode of guessing is a wrong pin map,
#: which is silent until the hardware is built.
SUPPORTED_SCHEMA = 1

#: What every board definition must carry for the firmware and the simulator to be generated.
REQUIRED_KEYS = ("schema", "id", "name", "chip", "wokwi_part_type",
                 "pins", "wake_capable_gpio", "adc_gpio", "physical")

#: What a board must additionally carry before it can be laid out and fabricated. Kept apart
#: from REQUIRED_KEYS because these are the fields that, if wrong, cost money.
REQUIRED_FOR_FAB = ("footprint_module", "footprint_export")

#: Keys a board file may NOT contain, because they are decisions rather than facts about the
#: hardware. boards/README.md states the rule; this enforces it. `wake_on_high` is the named
#: example and is exactly what went wrong: it was removed from one board file when the rule was
#: written and left in the other, and --validate said "ok" for a day.
#:
#: A fact is true of the board whatever you build with it. A decision is a choice you made, and
#: a board file that accumulates choices stops being swappable, which is the point of boards/.
FORBIDDEN_KEYS = {
    "wake_on_high": "follows from how the buttons are wired; belongs in config.WAKE_ON_HIGH",
    "i2c_freq": "a firmware setting, not a property of the board",
    "i2c_freq_hz": "a firmware setting, not a property of the board",
    "pin_assignments": "which function sits on which pin is the design; see mcu-pins.ts",
    "signals": "which function sits on which pin is the design; see mcu-pins.ts",
}

#: Ranges a GPIO number must fall in to be a number at all. Deliberately generous — this catches
#: a typo or a silkscreen label parsed as a pin, not a chip-specific mistake.
GPIO_MIN, GPIO_MAX = 0, 63

EXIT_OK, EXIT_INVALID = 0, 1


class BoardError(Exception):
    """A board definition that cannot be used, with the reason a person needs to fix it."""


def _read_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise BoardError(f"no {what} at {path.relative_to(REPO)}")
    try:
        return json.loads(path.read_text())
    except ValueError as broken:
        raise BoardError(f"{path.relative_to(REPO)} is not valid JSON: {broken}") from broken


def active_id() -> str:
    """The id of the board the project is currently built around."""
    selection = _read_json(SELECTION_FILE, "board selection")
    board_id = selection.get("board")
    if not board_id:
        raise BoardError(f"{SELECTION_FILE.relative_to(REPO)} names no board "
                         f'(expected a "board" key holding a board id)')
    return board_id


def definition_path(board_id: str = None) -> Path:
    """Where a board's definition lives. Defaults to the active board."""
    board_id = board_id or active_id()
    path = BOARDS_DIR / f"{board_id}{DEFINITION_SUFFIX}"
    if not path.is_file():
        raise BoardError(f"no board definition for {board_id!r}.\n"
                         f"  available: {', '.join(available()) or '(none)'}")
    return path


def available() -> list:
    """Every board that could be switched to."""
    return sorted(path.stem for path in BOARDS_DIR.glob(f"*{DEFINITION_SUFFIX}")
                  if path.name not in NOT_A_BOARD)


def load(board_id: str = None) -> dict:
    """A board definition, validated. Defaults to the active board."""
    path = definition_path(board_id)
    board = _read_json(path, "board definition")
    problems = validate(board, path)
    if problems:
        raise BoardError(f"{path.relative_to(REPO)} does not meet the board contract:\n" +
                         "\n".join(f"  - {problem}" for problem in problems))
    return board


def validate(board: dict, path: Path, for_fab: bool = False) -> list:
    """
    Every way this board definition breaks the contract. Empty means it holds.

    Returns a list rather than raising on the first fault so that a person fixing a new board
    file sees all of it at once.
    """
    problems = []

    schema = board.get("schema")
    if schema != SUPPORTED_SCHEMA:
        problems.append(f"schema is {schema!r}, but this code understands only {SUPPORTED_SCHEMA}")

    for key in REQUIRED_KEYS:
        if key not in board:
            problems.append(f"missing required key {key!r}")

    if board.get("id") != path.stem:
        problems.append(f"id is {board.get('id')!r} but the file is named {path.stem!r}; "
                        f"the two must match, because active.json selects by filename")

    pins = board.get("pins")
    if isinstance(pins, dict):
        if not pins:
            problems.append("pins is empty: a board with no pins cannot be wired to anything")
        for label, gpio in pins.items():
            # Two labels sharing one GPIO is legal and common — on the FireBeetle 2 S3 both A4
            # and SS are GPIO10 — so duplicates are not an error. A non-integer is.
            if not isinstance(gpio, int) or isinstance(gpio, bool):
                problems.append(f"pin {label!r} maps to {gpio!r}, which is not a GPIO number")
            elif not GPIO_MIN <= gpio <= GPIO_MAX:
                problems.append(f"pin {label!r} maps to GPIO{gpio}, outside {GPIO_MIN}-{GPIO_MAX}")
    elif pins is not None:
        problems.append("pins must be an object of silkscreen label -> GPIO number")

    for key in ("wake_capable_gpio", "adc_gpio"):
        value = board.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(
                isinstance(gpio, int) and not isinstance(gpio, bool) for gpio in value):
            problems.append(f"{key} must be a list of GPIO numbers")

    for role_name, role in (board.get("pin_roles") or {}).items():
        if not isinstance(role, dict) or "gpio" not in role or "note" not in role:
            problems.append(f"pin_roles.{role_name} needs both a 'gpio' list and a 'note'")
            continue
        if not role["note"].strip():
            # The note is the whole value of a role: "GPIO0 is special" helps nobody, whereas
            # "held low at reset it enters the bootloader" decides whether a button can go there.
            problems.append(f"pin_roles.{role_name} has an empty note; say what the caveat is")

    # Decisions must not leak into a facts file, at any depth.
    def forbidden(node, path=""):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                where = "%s.%s" % (path, key) if path else key
                problems.append(
                    "%s is a DECISION, not a fact about this board: %s. See boards/README.md"
                    % (where, FORBIDDEN_KEYS[key]))
            forbidden(value, "%s.%s" % (path, key) if path else key)

    forbidden(board)

    physical = board.get("physical")
    if for_fab:
        if not isinstance(physical, dict):
            problems.append("physical is missing, so the board cannot be laid out")
        else:
            for key in REQUIRED_FOR_FAB:
                if not physical.get(key):
                    problems.append(
                        f"physical.{key} is not set: no verified footprint for this board, "
                        f"so it is not ready to be laid out or fabricated")

    return problems


#: Separates the levels of a key path given to --get, e.g. `physical.width_mm`.
KEY_PATH_SEPARATOR = "."


def get(key_path: str, board_id: str = None):
    """
    One field out of a board definition, addressed by dotted path.

    A generic accessor rather than a flag per field, because the Makefile and any future consumer
    should be able to reach a new board fact without this file growing a new option for it.
    """
    value = load(board_id)
    for step in key_path.split(KEY_PATH_SEPARATOR):
        if not isinstance(value, dict) or step not in value:
            raise BoardError(f"no {key_path!r} in this board definition "
                             f"(stopped at {step!r})")
        value = value[step]
    return value


def _validate_all(for_fab: bool) -> int:
    """Check every board file, not just the active one, and say what is wrong with each."""
    failed = False
    for board_id in available():
        path = BOARDS_DIR / f"{board_id}{DEFINITION_SUFFIX}"
        try:
            board = _read_json(path, "board definition")
        except BoardError as broken:
            print(f"  {board_id}: {broken}")
            failed = True
            continue
        problems = validate(board, path, for_fab=for_fab)
        marker = "active" if board_id == active_id() else "     "
        if problems:
            print(f"  {marker}  {board_id}: {len(problems)} problem(s)")
            for problem in problems:
                print(f"           - {problem}")
            failed = True
        else:
            print(f"  {marker}  {board_id}: ok")
    return EXIT_INVALID if failed else EXIT_OK


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="boards.py", description="Resolve and check the project's board definitions.")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--path", action="store_true", help="the active board's definition file")
    what.add_argument("--id", action="store_true", help="the active board's id")
    what.add_argument("--list", action="store_true", help="every board available to switch to")
    what.add_argument("--paths", action="store_true",
                      help="every board definition file, for tools that take a list")
    what.add_argument("--validate", action="store_true", help="check every board file")
    what.add_argument("--get", metavar="KEY.PATH",
                      help="one field from the active board, e.g. chip or physical.width_mm")
    parser.add_argument("--for-fab", action="store_true",
                        help="with --validate, also require what the PCB needs")
    args = parser.parse_args(argv)

    try:
        if args.path:
            print(definition_path().relative_to(REPO))
        elif args.id:
            print(active_id())
        elif args.paths:
            # Deliberately not `boards/*.json`: that glob also matches active.json, which is a
            # selection rather than a board. Everything that needs the list should ask here.
            print(" ".join(str(definition_path(b).relative_to(REPO)) for b in available()))
        elif args.get:
            print(get(args.get))
        elif args.list:
            current = active_id()
            for board_id in available():
                print(f"  {'*' if board_id == current else ' '} {board_id}")
        else:
            return _validate_all(for_fab=args.for_fab)
    except BoardError as broken:
        print(f"boards.py: {broken}", file=sys.stderr)
        return EXIT_INVALID
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
