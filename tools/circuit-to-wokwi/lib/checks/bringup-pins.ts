/**
 * Do the bench scripts agree with the firmware about where everything is wired?
 *
 * `firmware/micropython/bringup/*.py` deliberately repeat their pin numbers instead of importing
 * config.py: their whole job is to run on a board where the firmware is not yet installed, or is
 * the thing under suspicion, so they must depend on as little as possible.
 *
 * That independence is worth having and it is exactly what rots. A pin map that moves — as this
 * one did when deep sleep forced the sensor and the OPEN button onto D0/D1/D2 — leaves the bench
 * scripts pointing at the old pins, and the failure arrives as "step 5 does not turn the motor"
 * on an evening when everything else is also new. This makes that a build error instead.
 *
 * The rule is: a `PIN_*` in a bench script either matches config.py's constant of the same name,
 * or is a documented fact about the board itself (the on-board user LED, which no config.py
 * setting names). Anything else is drift or a typo.
 */

import { board, labelForGpio } from "../board";
import type { Problem } from "../types";

export interface BringUpPinCheck {
  problems: Problem[];
  compared: { script: string; setting: string; gpio: number }[];
}

/**
 * Roles that identify one specific pin on the module, as opposed to describing a caveat that
 * happens to apply to many. A bench script may name one of these without config.py knowing it.
 */
const FIXED_FUNCTION_ROLES = new Set(["onboard_led", "onboard_button", "boot_log_tx", "strapping"]);

export function checkBringUpPins(
  configPython: string,
  scripts: { name: string; source: string }[],
): BringUpPinCheck {
  const problems: Problem[] = [];
  const compared: BringUpPinCheck["compared"] = [];

  const firmware = readPinAssignments(configPython);
  // Only roles that name a FIXED on-board function count as "the board documents this pin".
  // Taking every role let GPIO15 through as an on-board LED, because it appears in this board's
  // "adc2_unusable_with_wifi" list — a caveat covering ten pins, which was accidentally acting
  // as a whitelist. Bring-up step 1 then blinked a bare header pin and the guard said fine.
  const documented = new Set(
    Object.entries(board.pin_roles ?? {})
      .filter(([role]) => FIXED_FUNCTION_ROLES.has(role))
      .flatMap(([, role]) => role.gpio),
  );

  for (const script of scripts) {
    for (const [setting, gpio] of readPinAssignments(script.source)) {
      const inFirmware = firmware.get(setting);

      if (inFirmware === undefined) {
        // No constant of that name in config.py. Allowed only for a pin the board definition
        // itself documents — otherwise it is a name nothing else knows, which is how a typo
        // survives.
        if (!documented.has(gpio)) {
          problems.push({
            message:
              `${script.name} sets ${setting} = GPIO${gpio}, which is neither a config.py ` +
              `setting nor a documented pin of the ${board.name}`,
          });
        }
        continue;
      }

      if (inFirmware !== gpio) {
        problems.push({
          message:
            `${script.name} sets ${setting} = GPIO${gpio} (${labelForGpio(gpio) ?? "not on the header"}), ` +
            `but the firmware uses GPIO${inFirmware} (${labelForGpio(inFirmware) ?? "?"}). ` +
            `The bench script would test the wrong pin`,
        });
        continue;
      }

      compared.push({ script: script.name, setting, gpio });
    }
  }

  return { problems, compared };
}

/** `PIN_MOTOR_IA = 21  # D3` -> ["PIN_MOTOR_IA", 21]. Comments and other settings are ignored. */
function readPinAssignments(python: string): Map<string, number> {
  const assignments = new Map<string, number>();
  for (const line of python.split("\n")) {
    const match = /^(PIN_[A-Z0-9_]+)\s*=\s*(\d+)/.exec(line.trim());
    if (match) assignments.set(match[1]!, Number(match[2]));
  }
  return assignments;
}
