/**
 * The bench-script pin check, checked.
 *
 * A guard that cannot fail is worse than none, because it is believed. These cases are the two
 * ways the bench scripts can rot: a pin that moved in config.py and not here, and a name that
 * exists nowhere else.
 */

import { describe, expect, test } from "bun:test";

import { board } from "../lib/board";
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
    // A pin with a role in boards/*.json - the on-board LED, a strapping pin - is a fact about
    // the board, so a bench script may name it without config.py having a setting for it.
    // Taken from the board definition rather than written here, because which pins those are
    // changes with the board: on the ESP32-C6 the user LED was GPIO15, on the S3 it is GPIO21.
    const documented = Object.values(board.pin_roles ?? {}).flatMap((role) => role.gpio)[0];
    expect(documented).toBeDefined();
    const { problems } = checkBringUpPins(CONFIG, script(`PIN_USER_LED = ${documented}`));
    expect(problems).toEqual([]);
  });

  test("a caveat that covers many pins is not a whitelist", () => {
    // GPIO15 sits in this board's "adc2_unusable_with_wifi" role, which describes ten pins.
    // Taking every role as documentation let bring-up step 1 blink GPIO15 as if it were the
    // on-board LED, on a board whose LED is GPIO21 and whose GPIO15 is MOSI.
    const caveat = board.pin_roles?.adc2_unusable_with_wifi?.gpio?.[0];
    if (caveat === undefined) return; // a board without that caveat has nothing to prove here
    const { problems } = checkBringUpPins(CONFIG, script(`PIN_USER_LED = ${caveat}`));
    expect(problems).toHaveLength(1);
  });

  test("a name nothing else knows is caught", () => {
    // A GPIO this board brings out but gives no role to, and which config.py does not set: the
    // bench script is the only thing that has ever heard of it, which is the bug.
    const documented = new Set(Object.values(board.pin_roles ?? {}).flatMap((role) => role.gpio));
    const inConfig = new Set(
      [...CONFIG.matchAll(/^PIN_[A-Z0-9_]+\s*=\s*(\d+)/gm)].map((match) => Number(match[1])),
    );
    const unknown = Object.values(board.pins).find(
      (gpio) => !documented.has(gpio) && !inConfig.has(gpio),
    );
    expect(unknown).toBeDefined();

    const { problems } = checkBringUpPins(CONFIG, script(`PIN_INVENTED = ${unknown}`));
    expect(problems).toHaveLength(1);
    expect(problems[0]!.message).toContain("neither a config.py setting");
  });
});
