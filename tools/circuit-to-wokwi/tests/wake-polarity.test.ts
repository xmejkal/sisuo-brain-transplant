/**
 * The one disagreement no firmware test can see.
 *
 * Every armed deep-sleep pin on this chip shares a single trigger level, so the direction is one
 * decision written in two independent places: `config.WAKE_ON_HIGH`, and which rail the OPEN
 * button's far side is tied to on the board.
 *
 * Flip the constant alone and the entire firmware flips with it — the pin's pull, the button's
 * pressed level, the sensor's interrupt polarity, every assertion that derives from any of them.
 * 113 tests stay green. The bin still never wakes, because the copper did not move.
 *
 * That is not hypothetical: it is what the mutation run showed on 2026-09-25, immediately after
 * the board was rewired to 3V3. This check is the only thing standing between that mutation and
 * a battery that goes flat with the lid shut.
 */

import { describe, expect, test } from "bun:test";

import { checkWakePolarity, railBehind, readWakeOnHigh } from "../lib/checks/wake-polarity";
import type { Netlist } from "../lib/types";

/** A board with the OPEN button's far side tied to the given rail. */
function board(rail: string): Netlist {
  return {
    components: [
      { id: "c_btn", name: "BtnOpen", type: "simple_chip",
        pins: [{ name: "A", portId: "p_a" }, { name: "B", portId: "p_b" }] },
      { id: "c_mcu", name: "Mcu", type: "simple_chip", pins: [{ name: "D11", portId: "p_d11" }] },
    ],
    nets: [
      { id: "n_rail", name: rail, members: [{ componentId: "c_btn", pinName: "B" }] },
      { id: "n_sig", name: "SIG", members: [
        { componentId: "c_btn", pinName: "A" }, { componentId: "c_mcu", pinName: "D11" }] },
    ],
  };
}

const HIGH = "WAKE_ON_HIGH = True\n";
const LOW = "WAKE_ON_HIGH = False\n";

describe("reading the firmware's armed level", () => {
  test("True and False are both read", () => {
    expect(readWakeOnHigh(HIGH)).toBe(true);
    expect(readWakeOnHigh(LOW)).toBe(false);
  });

  test("a commented-out line is not the setting", () => {
    // config.py carries a long comment block about this very constant, and several lines in it
    // contain the word. Matching one of those would report the opposite of the truth.
    expect(readWakeOnHigh("# WAKE_ON_HIGH = False is what it used to be\nWAKE_ON_HIGH = True\n"))
      .toBe(true);
  });

  test("absent is undefined, not a guess", () => {
    expect(readWakeOnHigh("SOMETHING_ELSE = 1\n")).toBeUndefined();
  });
});

describe("reading the board's asserted level", () => {
  test("a button tied to 3V3 is found on V33", () => {
    expect(railBehind(board("V33"), "BtnOpen")).toBe("V33");
  });

  test("a button tied to ground is found on GND", () => {
    expect(railBehind(board("GND"), "BtnOpen")).toBe("GND");
  });

  test("a button on neither rail is undefined", () => {
    expect(railBehind(board("MOTOR6V"), "BtnOpen")).toBeUndefined();
  });

  test("a button that is not on the board at all is undefined", () => {
    expect(railBehind(board("V33"), "BtnNotHere")).toBeUndefined();
  });
});

describe("the two against each other", () => {
  test("3V3 and WAKE_ON_HIGH=True agree", () => {
    const { problems, compared } = checkWakePolarity(HIGH, board("V33"));
    expect(problems).toEqual([]);
    expect(compared).toEqual({ button: "BtnOpen", tiedTo: "V33", assertsHigh: true, wakeOnHigh: true });
  });

  test("GND and WAKE_ON_HIGH=False agree", () => {
    expect(checkWakePolarity(LOW, board("GND")).problems).toEqual([]);
  });

  test("THE MUTATION: 3V3 board, firmware armed for LOW, is caught", () => {
    // The exact defect. Reverting the constant after the board moved to 3V3 left every firmware
    // test green.
    const { problems } = checkWakePolarity(LOW, board("V33"));
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("tied to V33");
    expect(problems[0]!.message).toContain("WAKE_ON_HIGH = False");
  });

  test("the opposite mistake is caught too", () => {
    const { problems } = checkWakePolarity(HIGH, board("GND"));
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("tied to GND");
  });

  test("it does not guess WHICH symptom, because that depends on the pulls", () => {
    // Whether a mismatch shows as "never wakes" or "wakes constantly" turns on whether the
    // internal pull or the board's resistor wins, which the netlist does not say. An earlier
    // version picked one from WAKE_ON_HIGH alone and was wrong in both directions.
    for (const { config, rail } of [{ config: LOW, rail: "V33" }, { config: HIGH, rail: "GND" }]) {
      const message = checkWakePolarity(config, board(rail)).problems[0]!.message;
      expect(message).toContain("either never wake or wake constantly");
    }
  });

  test("a board that states neither is could-not-check, not a pass", () => {
    const { problems, compared } = checkWakePolarity(HIGH, board("MOTOR6V"));
    expect(compared).toBeUndefined();
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("cannot be checked");
  });

  test("a config that states nothing is could-not-check, not a pass", () => {
    expect(checkWakePolarity("", board("V33")).problems).toHaveLength(1);
  });
});
