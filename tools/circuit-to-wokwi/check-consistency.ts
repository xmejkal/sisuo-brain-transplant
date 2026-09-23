#!/usr/bin/env bun
/**
 * One command that answers "is everything still describing the same bin?".
 *
 *   bun run check-consistency.ts
 *
 * Three things have to agree, and each is checked against the board design rather than against
 * each other, so there is one source of truth and no circular reasoning:
 *
 *   board.tsx  ->  the simulation   (the generated diagram is up to date)
 *   board.tsx  ->  the firmware     (config.py's GPIO numbers are the board's pins)
 *   board.tsx  ->  itself           (the design builds and routes without errors)
 */

import { board, canWake, hasAdc, labelForGpio } from "./lib/board";
import { checkFirmwarePins } from "./lib/checks/firmware-pins";
import { buildNetlist } from "./lib/netlist";

const CIRCUIT = "../../dist/board/circuit.json";
const CONFIG = "../../firmware/micropython/config.py";

const circuitJson = await Bun.file(CIRCUIT).json();
const { netlist } = buildNetlist(circuitJson);
const configPython = await Bun.file(CONFIG).text();

const { problems, compared } = checkFirmwarePins(configPython, netlist);

// The board definition also says what each pin *can do*, so a setting on an impossible pin is
// caught here rather than on a bench: a wake source that cannot wake, an ADC that is not one.
const capabilityProblems: string[] = [];
for (const assignment of configPython.matchAll(/^(PIN_[A-Z0-9_]+)\s*=\s*(\d+)/gm)) {
  const [, setting, gpioText] = assignment;
  const gpio = Number(gpioText);
  const label = labelForGpio(gpio);

  if (label === undefined) {
    // checkFirmwarePins already reports pins the board does not have, for the settings it knows
    // about. Only add the ones it does not cover, so a single mistake is reported once.
    if (!compared.some((pin) => pin.setting === setting)) {
      capabilityProblems.push(`${setting} = GPIO${gpio}, which ${board.name} does not bring out`);
    }
    continue;
  }
  if (/INTERRUPT|BUTTON_OPEN/.test(setting!) && !canWake(gpio)) {
    capabilityProblems.push(
      `${setting} is on ${label} (GPIO${gpio}), which cannot wake this chip — deep sleep would ` +
        `never come back`,
    );
  }
  if (/ADC|SHUNT/.test(setting!) && !hasAdc(gpio)) {
    capabilityProblems.push(`${setting} is on ${label} (GPIO${gpio}), which has no ADC`);
  }
}

console.log(`board: ${board.name} (${board.id})`);
console.log(`firmware <-> board: ${compared.length} pins compared`);
for (const pin of compared) {
  console.log(`  ${pin.setting.padEnd(20)} GPIO${String(pin.gpio).padStart(2)} = ${pin.dpin.padEnd(3)} = ${pin.boardLabel}`);
}

const designErrors = circuitJson.filter((element: any) => String(element.type).includes("error"));
if (designErrors.length) {
  console.error(`\nthe board design has ${designErrors.length} error(s):`);
  for (const error of designErrors.slice(0, 5)) console.error(`  ${error.message}`);
}

if (problems.length || capabilityProblems.length) {
  console.error("\nout of step:");
  for (const problem of problems) console.error(`  - ${problem.message}`);
  for (const problem of capabilityProblems) console.error(`  - ${problem}`);
}

if (problems.length || capabilityProblems.length || designErrors.length) process.exit(1);
console.log("\nfirmware, board and simulation all describe the same bin");
