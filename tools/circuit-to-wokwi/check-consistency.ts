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

import { readdirSync } from "node:fs";

import { board, canWake, hasAdc, labelForGpio } from "./lib/board";
import { checkScenarioPins, findScenarios } from "./lib/checks/scenario-pins";
import { checkBringUpPins } from "./lib/checks/bringup-pins";
import { checkFirmwarePins } from "./lib/checks/firmware-pins";
import { checkWakePolarity } from "./lib/checks/wake-polarity";
import { buildNetlist } from "./lib/netlist";

const CIRCUIT = "../../dist/board/circuit.json";
const CONFIG = "../../firmware/micropython/config.py";
const BRINGUP = "../../firmware/micropython/bringup";

const circuitJson = await Bun.file(CIRCUIT).json();
const { netlist } = buildNetlist(circuitJson);
const configPython = await Bun.file(CONFIG).text();

const { problems, compared } = checkFirmwarePins(configPython, netlist);

// The bench scripts repeat their pin numbers on purpose (they run before the firmware is
// installed), so they are the one place the pin map can rot unnoticed.
const bringUpScripts = readdirSync(BRINGUP)
  .filter((name) => name.endsWith(".py"))
  .sort()
  .map((name) => ({ name: `bringup/${name}`, source: Bun.file(`${BRINGUP}/${name}`) }));
const bringUp = checkBringUpPins(
  configPython,
  await Promise.all(
    bringUpScripts.map(async (script) => ({ name: script.name, source: await script.source.text() })),
  ),
);

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

// The scenarios are the only part of the simulation that asserts anything, and they are
// hand-written while the diagram is generated — so they are exactly where a board change rots.
const DIAGRAM = `${import.meta.dir}/../../firmware/micropython/sim/diagram.json`;
const SCENARIOS = `${import.meta.dir}/../../firmware/micropython/sim`;
const scenarios = checkScenarioPins(await Bun.file(DIAGRAM).json(), findScenarios(SCENARIOS));

// One trigger level covers every armed wake pin, so which direction the board asserts in and
// which the firmware arms for are two statements that must agree — and no firmware test can
// compare them, because they all derive from the same constant.
const wake = checkWakePolarity(configPython, netlist);
if (wake.compared) {
  console.log(
    `wake polarity: ${wake.compared.button} tied to ${wake.compared.tiedTo}, asserts ` +
      `${wake.compared.assertsHigh ? "HIGH" : "LOW"}, firmware arms for ` +
      `${wake.compared.wakeOnHigh ? "HIGH" : "LOW"}`,
  );
}

const designErrors = circuitJson.filter((element: any) => String(element.type).includes("error"));
if (designErrors.length) {
  console.error(`\nthe board design has ${designErrors.length} error(s):`);
  for (const error of designErrors.slice(0, 5)) console.error(`  ${error.message}`);
}

if (problems.length || capabilityProblems.length || bringUp.problems.length ||
    scenarios.problems.length || wake.problems.length) {
  console.error("\nout of step:");
  for (const problem of problems) console.error(`  - ${problem.message}`);
  for (const problem of capabilityProblems) console.error(`  - ${problem}`);
  for (const problem of bringUp.problems) console.error(`  - ${problem.message}`);
  for (const problem of scenarios.problems) console.error(`  - ${problem.message}`);
  for (const problem of wake.problems) console.error(`  - ${problem.message}`);
}

if (problems.length || capabilityProblems.length || bringUp.problems.length ||
    scenarios.problems.length || wake.problems.length || designErrors.length) {
  process.exit(1);
}
console.log(`bench scripts <-> firmware: ${bringUp.compared.length} pins compared`);
console.log(`simulation scenarios: ${scenarios.compared} assertion(s) over ${scenarios.files.length} file(s)`);
console.log("\nfirmware, board, bench scripts and simulation all describe the same bin");
