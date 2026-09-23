/**
 * The bench-script pin check, checked.
 *
 * A guard that cannot fail is worse than none, because it is believed. These cases are the two
 * ways the bench scripts can rot: a pin that moved in config.py and not here, and a name that
 * exists nowhere else.
 */

import { describe, expect, test } from "bun:test";

import { checkBringUpPins } from "../lib/checks/bringup-pins";

const CONFIG = `
PIN_MOTOR_IA = 21           # D3
PIN_BUTTON_OPEN = 1         # D1
`;

const script = (source: string) => [{ name: "bringup/xx_test.py", source }];

describe("bench scripts against the firmware", () => {
  test("agreeing pins are compared, not complained about", () => {
    const { problems, compared } = checkBringUpPins(CONFIG, script("PIN_MOTOR_IA = 21"));
    expect(problems).toEqual([]);
    expect(compared).toHaveLength(1);
  });

  test("a pin that moved in the firmware is caught", () => {
    const { problems } = checkBringUpPins(CONFIG, script("PIN_MOTOR_IA = 3"));
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("would test the wrong pin");
  });

  test("a pin the board documents needs no config.py setting", () => {
    // GPIO15 is the on-board user LED: a fact about the board, named in boards/*.json.
    const { problems } = checkBringUpPins(CONFIG, script("PIN_USER_LED = 15"));
    expect(problems).toEqual([]);
  });

  test("a name nothing else knows is caught", () => {
    const { problems } = checkBringUpPins(CONFIG, script("PIN_INVENTED = 14"));
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("neither a config.py setting");
  });
});
