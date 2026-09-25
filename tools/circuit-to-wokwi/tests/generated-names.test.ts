/**
 * A component's INSTANCE name is the board's business; what it IS decides how it simulates.
 *
 * These rules matched `"MotorDriver"` by string equality and `SensorHeader` by a pattern listing
 * this board's names for the thing. That is fine for a board somebody typed, and wrong for one
 * generated from a module list — spark names its components after the PART, so the same physical
 * L9110S arrived as `L9110sModule` and did not map. The converter read the board, placed the
 * microcontroller, and then reported three real components as unknown.
 *
 * Reproduced on 2026-09-25 against a spark-generated design: 4 components, 8 nets, 1 part
 * emitted. After matching on the part instead: 3 parts, 10 wires, 7 of 8 nets. The eighth is the
 * motor supply, which correctly has nothing to wire to — Wokwi does not simulate a 6 V pack.
 *
 * So these tests are not about spark. They are about a rule that mistook a name for an identity,
 * and they would have failed the same way for anyone who called their driver `M1`.
 */

import { describe, expect, test } from "bun:test";

import { findMapping, findSkipRule, wokwiPinName } from "../lib/mapping";

describe("the same part under different instance names", () => {
  test("a motor driver maps whether it is called MotorDriver or L9110sModule", () => {
    for (const name of ["MotorDriver", "L9110sModule", "L9110S", "l9110s-module"]) {
      expect(findMapping(name)?.wokwiType, name).toBe("chip-l9110s");
    }
  });

  test("a rangefinder maps under this board's name and under its part's", () => {
    for (const name of ["SensorHeader", "Vl6180xBreakout", "vl6180x-breakout", "TofSensor"]) {
      expect(findMapping(name)?.wokwiType, name).toBe("chip-vl6180x");
    }
  });

  test("a connector is skipped whatever it is called", () => {
    // A power inlet is wiring. The bin's is `BinConnector`; a generated one is named after the
    // part it came from.
    for (const name of ["BinConnector", "JstPh2PowerInlet", "PowerInlet"]) {
      expect(findSkipRule(name), name).toBeDefined();
    }
  });

  test("something genuinely unknown is still unknown", () => {
    // The rules were widened, not loosened. A component nothing knows about must still be
    // reported rather than quietly matched by a pattern that grew too generous.
    expect(findMapping("Ssd1306Display")).toBeUndefined();
    expect(findSkipRule("Ssd1306Display")).toBeUndefined();
  });

  test("widening did not make the motor rule swallow the rangefinder", () => {
    // Two unanchored patterns in one list is how a rule starts matching its neighbour's parts.
    expect(findMapping("Vl6180xBreakout")?.wokwiType).not.toBe("chip-l9110s");
    expect(findMapping("L9110sModule")?.wokwiType).not.toBe("chip-vl6180x");
  });
});

describe("the same pad under different silkscreens", () => {
  test("every name a VL6180X carrier gives its interrupt reaches INT", () => {
    // Pololu's #2489 prints GPIO1, the IR receiver it replaces prints OUT, this board's header
    // prints INT. A breakout's silkscreen is not negotiable, so the aliases live in the mapping.
    const sensor = findMapping("SensorHeader")!;
    for (const pad of ["INT", "OUT", "GPIO1"]) {
      expect(wokwiPinName(sensor, pad), pad).toBe("INT");
    }
  });

  test("a pad with no alias keeps its own name", () => {
    const sensor = findMapping("SensorHeader")!;
    expect(wokwiPinName(sensor, "SDA")).toBe("SDA");
  });
});
