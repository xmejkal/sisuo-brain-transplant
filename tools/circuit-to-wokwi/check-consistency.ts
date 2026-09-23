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

import { checkFirmwarePins } from "./lib/checks/firmware-pins";
import { buildNetlist } from "./lib/netlist";

const CIRCUIT = "../../dist/board/circuit.json";
const CONFIG = "../../firmware/micropython/config.py";

const circuitJson = await Bun.file(CIRCUIT).json();
const { netlist } = buildNetlist(circuitJson);
const configPython = await Bun.file(CONFIG).text();

const { problems, compared } = checkFirmwarePins(configPython, netlist);

console.log(`firmware <-> board: ${compared.length} pins compared`);
for (const pin of compared) {
  console.log(`  ${pin.setting.padEnd(20)} GPIO${String(pin.gpio).padStart(2)} = ${pin.dpin.padEnd(3)} = ${pin.boardLabel}`);
}

const designErrors = circuitJson.filter((element: any) => String(element.type).includes("error"));
if (designErrors.length) {
  console.error(`\nthe board design has ${designErrors.length} error(s):`);
  for (const error of designErrors.slice(0, 5)) console.error(`  ${error.message}`);
}

if (problems.length) {
  console.error("\nout of step:");
  for (const problem of problems) console.error(`  - ${problem.message}`);
}

if (problems.length || designErrors.length) process.exit(1);
console.log("\nfirmware, board and simulation all describe the same bin");
