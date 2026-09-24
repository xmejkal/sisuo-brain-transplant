/**
 * Which board this project is built around.
 *
 * One file describes it (`boards/<id>.json`) and everything here derives from that, so the
 * silkscreen-to-GPIO map exists once rather than in the firmware, the PCB design, the simulator
 * project and two checkers.
 *
 * Which board that is comes from `boards/active.json`, the single place it is chosen — the same
 * file the Makefile and the firmware's spec generator read. Switching board is editing that one
 * line; nothing here names a board. See `boards/README.md`.
 */

import { readFileSync } from "node:fs";

/** Relative to this file (lib/), so: tools/circuit-to-wokwi/lib -> repo root -> boards/. */
const BOARDS_DIR = "../../../boards/";
const SELECTION_FILE = "active.json";
const DEFINITION_SUFFIX = ".json";

/** The only board-file schema this code understands; see tools/boards.py for the contract. */
const SUPPORTED_SCHEMA = 1;

function readBoardsFile<T>(name: string): T {
  return JSON.parse(readFileSync(new URL(BOARDS_DIR + name, import.meta.url), "utf8")) as T;
}

const selection = readBoardsFile<{ board: string }>(SELECTION_FILE);
if (!selection.board) {
  throw new Error(`${BOARDS_DIR}${SELECTION_FILE} names no board (expected a "board" key)`);
}

/** The active board's definition file, for error messages that have to name it. */
export const BOARD_DEFINITION = `${BOARDS_DIR}${selection.board}${DEFINITION_SUFFIX}`;

export interface BoardDefinition {
  schema: number;
  id: string;
  name: string;
  chip: string;
  micropython_port: string;
  wokwi_part_type: string;
  /** True when Wokwi has no model of this exact board and the part above stands in for it. */
  wokwi_is_stand_in?: boolean;
  /** How the Wokwi part names its pins: by raw GPIO number, or by this board's silkscreen. */
  wokwi_pin_naming: "gpio" | "silkscreen";
  /** Power pins, which no naming rule covers - the S3 devkit calls them 3V3.1 and GND.1. */
  wokwi_power_pins?: Record<string, string>;
  /** Silkscreen label -> the GPIO it actually is. On the FireBeetle 2 S3, D9 is GPIO0. */
  pins: Record<string, number>;
  wake_capable_gpio: number[];
  adc_gpio: number[];
  /** What a pin is beyond its number: typed for checks, with a note for people. */
  pin_roles?: Record<string, { gpio: number[]; note: string }>;
  /** What the board is physically. The footprint fields are null until one is verified. */
  physical: {
    footprint_module: string | null;
    footprint_export: string | null;
    width_mm: number;
    height_mm: number;
    wokwi_size_px: { width: number; height: number };
  };
  deep_sleep?: {
    wake_api: string;
    single_polarity_for_all_pins: boolean;
    simulated_by_wokwi: boolean;
  };
}

export const board: BoardDefinition = readBoardsFile<BoardDefinition>(
  selection.board + DEFINITION_SUFFIX,
);

if (board.schema !== SUPPORTED_SCHEMA) {
  throw new Error(
    `${BOARD_DEFINITION} declares schema ${board.schema}, but this code understands only ` +
      `${SUPPORTED_SCHEMA}. Reading it anyway risks a wrong pin map, which is silent until the ` +
      `hardware is built.`,
  );
}
if (board.id !== selection.board) {
  throw new Error(
    `${BOARD_DEFINITION} has id "${board.id}" but is selected as "${selection.board}"`,
  );
}

/** The label a person reads on the silkscreen, for a GPIO number. */
export function labelForGpio(gpio: number): string | undefined {
  return Object.entries(board.pins).find(([, number]) => number === gpio)?.[0];
}

export function gpioForLabel(label: string): number | undefined {
  return board.pins[label];
}

export function canWake(gpio: number): boolean {
  return board.wake_capable_gpio.includes(gpio);
}

export function hasAdc(gpio: number): boolean {
  return board.adc_gpio.includes(gpio);
}
