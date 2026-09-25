/**
 * Which board this project is built around.
 *
 * Read from `.spark/board.json` — the active board, already found and validated by spark's
 * `boards.py`. This file used to do that work itself: read `boards/active.json`, look up the
 * definition, check the schema version, check the id. All of that was a second implementation
 * of a resolver that already existed in Python, and it would have needed a third change the
 * moment board definitions could also come from the plugin's shared library.
 *
 * So the search lives in one place and the answer lands in one file. Switching board is still
 * one line in `boards/active.json`; `make` regenerates this.
 */

import { readFileSync } from "node:fs";

/** Relative to this file (lib/): tools/circuit-to-wokwi/lib -> repo root -> .spark/. */
const RESOLVED_BOARD = "../../../.spark/board.json";

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
    /**
     * Where a pin's NAME differs from the label silkscreened on its PAD.
     *
     * The FireBeetle brings SPI out on pads printed `MI`, `MO` and `SCK`, while the board file
     * keys them by the names the vendor's own header uses - `MISO`, `MOSI`. Both are correct
     * and they are not the same string, so anything comparing a GPIO's name against a footprint
     * pad has to go through here or it finds a disagreement that does not exist.
     */
    pad_aliases?: Record<string, string>;
  };
  deep_sleep?: {
    wake_api: string;
    single_polarity_for_all_pins: boolean;
    simulated_by_wokwi: boolean;
  };
}

export const board: BoardDefinition = JSON.parse(
  readFileSync(new URL(RESOLVED_BOARD, import.meta.url), "utf8"),
);

/** The active board's definition file, for error messages that have to name it. */
export const BOARD_DEFINITION = RESOLVED_BOARD;

/** The label a person reads on the silkscreen, for a GPIO number. */
export function labelForGpio(gpio: number): string | undefined {
  const name = Object.entries(board.pins).find(([, number]) => number === gpio)?.[0];
  if (name === undefined) return undefined;
  // Answer in the pad's own silkscreen, because that is what a footprint and `mcu-pins.ts`
  // both speak. Returning the vendor's name made GPIO15 come back as `MOSI` while the pad it
  // lands on reads `MO`, so the firmware-pins check reported the two as a mismatch - a
  // disagreement between two correct statements, which is the kind of false alarm that gets a
  // check switched off.
  return board.physical?.pad_aliases?.[name] ?? name;
}

export function gpioForLabel(label: string): number | undefined {
  const direct = board.pins[label];
  if (direct !== undefined) return direct;
  // The other direction of the same bridge `labelForGpio` crosses. A footprint pad reads `MI`
  // while the board file keys that GPIO as `MISO`, so a lookup by the pad's own label finds
  // nothing — and the Wokwi emitter, which converts silkscreen to raw GPIO, then reports the
  // pad as not existing on the part.
  const aliases = board.physical?.pad_aliases ?? {};
  const name = Object.keys(aliases).find((key) => aliases[key] === label);
  return name === undefined ? undefined : board.pins[name];
}

export function canWake(gpio: number): boolean {
  return board.wake_capable_gpio.includes(gpio);
}

export function hasAdc(gpio: number): boolean {
  return board.adc_gpio.includes(gpio);
}
