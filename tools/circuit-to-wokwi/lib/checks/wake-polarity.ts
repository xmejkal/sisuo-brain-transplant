/**
 * Does the firmware wake on the level the board actually asserts?
 *
 * This chip applies ONE trigger level to every armed deep-sleep pin — the S3 has no per-pin
 * setting — so the direction is a single decision, and it is recorded in two independent places:
 *
 *   1. `config.WAKE_ON_HIGH`  - the level the firmware arms for
 *   2. `board.tsx`            - which rail the OPEN button's far side goes to
 *
 * A button to 3V3 asserts HIGH; a button to GND asserts LOW. Get the pair wrong and the bin
 * either never wakes or wakes constantly, and NEITHER shows up in a unit test: everything in the
 * firmware derives from `WAKE_ON_HIGH`, so flipping it flips the whole firmware consistently and
 * every test still passes. It is only wrong relative to the copper.
 *
 * That is exactly what happened on 2026-09-25. The board was rewired to 3V3 and the constant set
 * to True, and reverting the constant alone left 113 tests green — a silent, battery-only
 * failure. This check is the thing that catches it, and it is the same shape as `firmware-pins`:
 * two statements nobody derives from the other.
 */

import type { Netlist, Problem } from "../types";

/** Rails a button's far side can go to, and what that means for the level it asserts. */
const ASSERTS_HIGH_WHEN_TIED_TO = "V33";
const ASSERTS_LOW_WHEN_TIED_TO = "GND";

export interface WakePolarityCheck {
  problems: Problem[];
  /** What was compared, so a passing run still shows its working. */
  compared?: { button: string; tiedTo: string; assertsHigh: boolean; wakeOnHigh: boolean };
}

/** `WAKE_ON_HIGH = True` -> true. Absent or unparseable -> undefined. */
export function readWakeOnHigh(configPython: string): boolean | undefined {
  for (const line of configPython.split("\n")) {
    const match = /^WAKE_ON_HIGH\s*=\s*(True|False)\b/.exec(line.trim());
    if (match) return match[1] === "True";
  }
  return undefined;
}

/**
 * The rail the named button's far side is tied to, or undefined if it is on neither.
 *
 * "Far side" means the pin that is NOT the one going to the microcontroller. A button has two,
 * and only one of them decides the asserted level.
 */
export function railBehind(netlist: Netlist, buttonName: string): string | undefined {
  const button = netlist.components.find((component) => component.name === buttonName);
  if (!button) return undefined;
  for (const net of netlist.nets) {
    if (net.name !== ASSERTS_HIGH_WHEN_TIED_TO && net.name !== ASSERTS_LOW_WHEN_TIED_TO) continue;
    if (net.members.some((member) => member.componentId === button.id)) return net.name;
  }
  return undefined;
}

export function checkWakePolarity(
  configPython: string,
  netlist: Netlist,
  buttonName = "BtnOpen",
): WakePolarityCheck {
  const wakeOnHigh = readWakeOnHigh(configPython);
  if (wakeOnHigh === undefined) {
    return { problems: [{ message: "config.py does not set WAKE_ON_HIGH, so nothing says which level deep sleep arms for" }] };
  }

  const rail = railBehind(netlist, buttonName);
  if (rail === undefined) {
    // Not a pass. The board may be mid-edit, and saying so beats assuming agreement.
    return {
      problems: [{
        message:
          `${buttonName} is tied to neither ${ASSERTS_HIGH_WHEN_TIED_TO} nor ` +
          `${ASSERTS_LOW_WHEN_TIED_TO}, so the level it asserts cannot be read from the board ` +
          `and the firmware's WAKE_ON_HIGH cannot be checked against anything`,
        context: { component: buttonName },
      }],
    };
  }

  const assertsHigh = rail === ASSERTS_HIGH_WHEN_TIED_TO;
  if (assertsHigh !== wakeOnHigh) {
    return {
      problems: [{
        message:
          `${buttonName} is tied to ${rail}, so it asserts ` +
          `${assertsHigh ? "HIGH" : "LOW"}, but config.py sets WAKE_ON_HIGH = ` +
          `${wakeOnHigh ? "True" : "False"}, arming deep sleep for ` +
          `${wakeOnHigh ? "HIGH" : "LOW"}. The bin will either never wake or wake constantly — ` +
          `which of the two depends on whether the internal pull or the board's resistor wins, ` +
          `so this does not guess. Neither is visible to any firmware test: they all derive ` +
          `from that same constant, so flipping it flips them with it`,
        context: { component: buttonName, net: rail },
      }],
    };
  }

  return { problems: [], compared: { button: buttonName, tiedTo: rail, assertsHigh, wakeOnHigh } };
}
