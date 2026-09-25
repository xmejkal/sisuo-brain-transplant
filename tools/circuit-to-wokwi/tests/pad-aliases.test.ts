/**
 * A pin's name and the label on its pad are not always the same word.
 *
 * The FireBeetle brings SPI out on pads silkscreened `MI`, `MO` and `SCK`, while the board file
 * keys those GPIOs by the names the vendor's own Arduino header uses — `MISO`, `MOSI`. Both are
 * correct. They are not the same string.
 *
 * `labelForGpio` answered with the vendor's name, and the firmware-pins check compares that
 * answer against `mcu-pins.ts`, which has to name the pad because that is what `board.tsx`
 * writes a trace to. So the moment a signal landed on GPIO15 the check would report `MOSI` and
 * `MO` as a mismatch: a disagreement between two correct statements, which is the kind of false
 * alarm that gets a check switched off rather than fixed.
 *
 * Found while moving the audio to I2S, which is the first design to use those three pads.
 */

import { describe, expect, test } from "bun:test";

import { board, labelForGpio } from "../lib/board";

describe("a pin's name versus the label on its pad", () => {
  test("a GPIO whose name is abbreviated on the silkscreen answers with the pad", () => {
    // Guard the premise first: if the board file stops keying these by the vendor's name, this
    // test would pass for the wrong reason and prove nothing.
    expect(board.pins.MOSI).toBe(15);
    expect(board.physical.pad_aliases?.MOSI).toBe("MO");

    expect(labelForGpio(15)).toBe("MO");
    expect(labelForGpio(16)).toBe("MI");
  });

  test("a GPIO whose name IS its pad label is returned unchanged", () => {
    // The common case, and the one an over-eager alias table would break.
    expect(labelForGpio(17)).toBe("SCK");
    expect(labelForGpio(board.pins.D3!)).toBe("D3");
  });

  test("a GPIO this board does not bring out is still undefined", () => {
    // Aliasing must not invent a pad for a pin that has none.
    expect(labelForGpio(99)).toBeUndefined();
  });

  test("every alias points at a pad the footprint actually has", () => {
    // An alias to a pad that does not exist relocates a signal to nowhere, silently.
    const order = (board.physical as { header_order?: Record<string, string[]> }).header_order;
    if (!order) return; // older board files do not record it; nothing to check against
    const pads = new Set(
      Object.entries(order)
        .filter(([key]) => !key.startsWith("//"))
        .flatMap(([, labels]) => labels),
    );
    for (const [name, pad] of Object.entries(board.physical.pad_aliases ?? {})) {
      expect(pads.has(pad), `${name} is aliased to ${pad}, which is on no row`).toBe(true);
    }
  });
});
