/**
 * How big Wokwi's parts are, and which pin names they really have.
 *
 * Pin names come from `@wokwi/diagram-lint`, which bundles Wokwi's own registry of 137 parts —
 * so an emitted `"u1:SDA"` is checked against the real part offline, before anything is written.
 *
 * Sizes are a small local table. Wokwi publishes geometry in `@wokwi/elements` and
 * `wokwi-boards`, but only placement needs it, placement is deliberately coarse, and a handful
 * of approximate boxes beats a dependency that must be scraped.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { PartRegistry } from "@wokwi/diagram-lint";

import { board } from "./board";

/** Wokwi's grid: 0.1 inch at 96 dpi. Parts snapped to it line up with the editor's own. */
export const GRID_PX = 9.6;

/**
 * Approximate part sizes in pixels, for stacking. Refine only if the layout gets cramped.
 *
 * The board's own size comes from the board definition rather than this table, so a different
 * board brings its own dimensions with it.
 */
const SIZES: Record<string, { width: number; height: number }> = {
  [board.wokwi_part_type]: board.physical.wokwi_size_px,
  "wokwi-pushbutton": { width: 70, height: 40 },
  "board-ssd1306": { width: 150, height: 120 },
  "wokwi-led": { width: 20, height: 40 },
  "wokwi-resistor": { width: 60, height: 20 },
  "chip-vl6180x": { width: 80, height: 60 },
  "chip-l9110s": { width: 80, height: 60 },
};

const DEFAULT_SIZE = { width: 80, height: 60 };

export function sizeOf(wokwiType: string) {
  return SIZES[wokwiType] ?? DEFAULT_SIZE;
}

export function snapToGrid(value: number): number {
  return Math.round(value / GRID_PX) * GRID_PX;
}

/**
 * The pin-name oracle: does this part really have this pin?
 *
 * Two sources, because there are two kinds of part. Wokwi's own parts come from the registry
 * bundled with `@wokwi/diagram-lint` — 137 of them, offline. Our custom chips come from their
 * `chip.json` files, which is the same place the simulator reads them from.
 *
 * Covering custom chips matters more than it sounds: they are the parts we invented, so they are
 * the ones whose pin names nobody else will catch. `wokwi-cli lint` does not resolve them.
 */
export class PinOracle {
  private registry = new PartRegistry();
  private chipPins = new Map<string, string[]>();

  /** @param chipsDirectory where our own `*.chip.json` files live. */
  constructor(chipsDirectory?: string) {
    if (chipsDirectory) this.loadChips(chipsDirectory);
  }

  private loadChips(directory: string) {
    let entries: string[];
    try {
      entries = readdirSync(directory);
    } catch {
      return; // no custom chips in this project
    }

    for (const entry of entries) {
      if (!entry.endsWith(".chip.json")) continue;
      try {
        const definition = JSON.parse(readFileSync(join(directory, entry), "utf8"));
        const chipName = entry.replace(/\.chip\.json$/, "");
        // A chip.json pin list may contain "" to leave a physical pin position unused.
        const pins = (definition.pins ?? []).filter((pin: string) => pin !== "");
        this.chipPins.set(`chip-${chipName}`, pins);
      } catch {
        // A malformed chip.json is the chip author's problem; the simulator will say so.
      }
    }
  }

  knowsPart(wokwiType: string): boolean {
    return this.pinsOf(wokwiType).length > 0;
  }

  pinsOf(wokwiType: string): string[] {
    const chip = this.chipPins.get(wokwiType);
    if (chip) return chip;
    try {
      return this.registry.getPins(wokwiType) ?? [];
    } catch {
      return [];
    }
  }

  isValidPin(wokwiType: string, pin: string): boolean {
    if (!this.knowsPart(wokwiType)) return true; // nothing to check it against
    return this.pinsOf(wokwiType).includes(pin);
  }
}
