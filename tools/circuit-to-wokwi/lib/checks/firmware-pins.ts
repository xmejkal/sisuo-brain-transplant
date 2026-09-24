/**
 * Does the firmware think the board is wired the way the board is wired?
 *
 * The converter proves the *simulation* matches the board. This proves the *firmware* does —
 * the third side of the triangle, and the one that would otherwise be checked by a person
 * remembering to, which is to say not checked.
 *
 * Three independent statements have to agree, and this compares them:
 *   1. `config.py`          - this signal is on GPIO n
 *   2. `boards/<id>.json`   - GPIO n is the pin silkscreened X
 *   3. `mcu-pins.ts`        - the signal is wired to the pin silkscreened X
 *
 * None is derived from another, which is what gives the check teeth. A mismatch here is the bug
 * that wastes a bench evening: the firmware drives one pin while the board wired the motor to
 * another, and nothing complains until the lid does not move.
 */

import { board, labelForGpio } from "../board";
import { BOARD } from "../mapping";
import { MCU } from "../../../../mcu-pins";
import type { Netlist, Problem } from "../types";

/**
 * Which firmware setting corresponds to which label in the board design.
 *
 * Only the pins that must agree. The IR fallback reuses the I2C pins by design, and the limit
 * switch shares the sense pin, so those are listed as alternates rather than conflicts.
 */
const CORRESPONDENCE: Record<string, string> = {
  PIN_TOF_INTERRUPT: "TOF_INT",
  PIN_BUTTON_OPEN: "BTN_OPEN",
  PIN_SHUNT_ADC: "MOTOR_SENSE",
  PIN_LIMIT_SWITCH: "MOTOR_SENSE",
  PIN_MOTOR_IA: "MOTOR_IA",
  PIN_I2C_SDA: "SDA",
  PIN_I2C_SCL: "SCL",
  PIN_IR_EMITTER: "SDA", // the fallback build reuses the bus pins
  PIN_IR_RECEIVER: "SCL",
  PIN_BUTTON_MODE: "BTN_MODE",
  PIN_LED_RED: "LED_RED",
  PIN_MOTOR_IB: "MOTOR_IB",
  PIN_MP3_TX: "MP3_TX",
  PIN_LED_GREEN: "LED_GREEN",
};

export interface FirmwarePinCheck {
  problems: Problem[];
  compared: { setting: string; gpio: number; dpin: string; boardLabel: string }[];
}

export function checkFirmwarePins(configPython: string, netlist: Netlist): FirmwarePinCheck {
  const problems: Problem[] = [];
  const compared: FirmwarePinCheck["compared"] = [];

  const firmwarePins = readPinAssignments(configPython);
  const boardLabels = boardPinLabels(netlist);

  for (const [setting, gpio] of firmwarePins) {
    const boardLabel = CORRESPONDENCE[setting];
    if (!boardLabel) continue; // a setting with no counterpart on the board

    const dpin = labelForGpio(gpio);
    if (!dpin) {
      problems.push({
        message: `${setting} = GPIO${gpio}, which ${board.name} does not bring out`,
      });
      continue;
    }

    const boardDpin = (MCU as Record<string, string>)[boardLabel];
    if (boardDpin === undefined) {
      problems.push({
        message:
          `the firmware sets ${setting}, but mcu-pins.ts does not say which pin carries ` +
          `${boardLabel}. Either that table or config.py is out of date`,
      });
      continue;
    }
    if (!boardLabels.has(boardDpin)) {
      problems.push({
        message:
          `mcu-pins.ts puts ${boardLabel} on ${boardDpin}, but the board design has no such ` +
          `pin on the module. Either the footprint or that table is wrong`,
      });
      continue;
    }

    if (boardDpin !== dpin) {
      problems.push({
        message:
          `${setting} = GPIO${gpio} (${dpin}), but the board wires ${boardLabel} to ${boardDpin}. ` +
          `The firmware would drive the wrong pin`,
      });
      continue;
    }

    compared.push({ setting, gpio, dpin, boardLabel });
  }

  return { problems, compared };
}

/** `PIN_MOTOR_IA = 21` -> ["PIN_MOTOR_IA", 21]. Comments and other settings are ignored. */
function readPinAssignments(configPython: string): [string, number][] {
  const assignments: [string, number][] = [];
  for (const line of configPython.split("\n")) {
    const match = /^(PIN_[A-Z0-9_]+)\s*=\s*(\d+)/.exec(line.trim());
    if (match) assignments.push([match[1]!, Number(match[2])]);
  }
  return assignments;
}

/** The labels the design gives the board's own pins. */
function boardPinLabels(netlist: Netlist): Set<string> {
  const board = netlist.components.find((component) => component.name === BOARD.match);
  return new Set(board?.pins.map((pin) => pin.name) ?? []);
}

