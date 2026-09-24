/**
 * Which board this project is built around.
 *
 * One file describes it (`boards/<id>.json`) and everything here derives from that, so the
 * silkscreen-to-GPIO map exists once rather than in the firmware, the PCB design, the simulator
 * project and two checkers.
 *
 * Changing board starts by pointing `BOARD_DEFINITION` at a different file; `boards/README.md`
 * says what else it takes.
 */

import { readFileSync } from "node:fs";

// Relative to this file (lib/), so: tools/circuit-to-wokwi/lib -> repo root -> boards/.
export const BOARD_DEFINITION = "../../../boards/xiao-esp32-c6.json";

export interface BoardDefinition {
  id: string;
  name: string;
  chip: string;
  wokwi_part_type: string;
  /** Silkscreen label -> the GPIO it actually is. D3 is GPIO21 on this board, not GPIO3. */
  pins: Record<string, number>;
  wake_capable_gpio: number[];
  adc_gpio: number[];
  /** What a pin is beyond its number: typed for checks, with a note for people. */
  pin_roles?: Record<string, { gpio: number[]; note: string }>;
  /** What the board is physically: its footprint in the PCB design, and its size. */
  physical: {
    footprint_module: string;
    footprint_export: string;
    width_mm: number;
    height_mm: number;
    wokwi_size_px: { width: number; height: number };
  };
  deep_sleep?: { wake_api: string; single_polarity_for_all_pins: boolean; simulated_by_wokwi: boolean };
}

export const board: BoardDefinition = JSON.parse(
  readFileSync(new URL(BOARD_DEFINITION, import.meta.url), "utf8"),
);

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
