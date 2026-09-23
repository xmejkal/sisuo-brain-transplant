#!/usr/bin/env bun
/**
 * Generate the Wokwi project from the board design.
 *
 *   bun run cli.ts                       write the diagram, reporting what it did
 *   bun run cli.ts --check               fail if the committed diagram is out of date (CI)
 *   bun run cli.ts --circuit x --out y   somewhere other than the defaults
 *
 * `--check` is the point of the whole tool: it turns "the simulation matches the board" from a
 * hope into something that fails a build.
 */

import { emitWokwiDiagram } from "./lib/emitters/wokwi";
import { mergeWithExisting } from "./lib/merge";
import { buildNetlist } from "./lib/netlist";
import { ConversionFailed } from "./lib/types";
import { validate } from "./lib/validate";

const DEFAULT_CIRCUIT = "../../dist/board/circuit.json";
const DEFAULT_OUT = "../../firmware/micropython/sim/diagram.generated.json";
const DEFAULT_CHIPS = "../../firmware/micropython/sim/chips";

interface Options {
  circuit: string;
  out: string;
  check: boolean;
}

function parseArguments(argv: string[]): Options {
  const options: Options = { circuit: DEFAULT_CIRCUIT, out: DEFAULT_OUT, check: false };
  for (let index = 0; index < argv.length; index++) {
    const argument = argv[index];
    if (argument === "--check") options.check = true;
    else if (argument === "--circuit") options.circuit = argv[++index] ?? options.circuit;
    else if (argument === "--out") options.out = argv[++index] ?? options.out;
    else if (argument === "--help") {
      console.log(__doc__());
      process.exit(0);
    }
  }
  return options;
}

function __doc__() {
  return `Usage: bun run cli.ts [--circuit <circuit.json>] [--out <diagram.json>] [--check]`;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));

  const circuitJson = await Bun.file(options.circuit).json();
  const { netlist, problems: designProblems } = buildNetlist(circuitJson);
  const emitted = emitWokwiDiagram(netlist, { chipsDirectory: DEFAULT_CHIPS });
  const existing = await readExisting(options.out);
  const { diagram, summary } = mergeWithExisting(emitted.diagram, existing);
  const validation = validate({ ...emitted, diagram });

  report({ netlist, emitted, summary, validation, designProblems });

  const blocking = [...emitted.problems, ...validation.problems];
  if (blocking.length) throw new ConversionFailed(blocking);

  const serialised = JSON.stringify(diagram, null, 2) + "\n";

  if (options.check) {
    const committed = (await Bun.file(options.out).text().catch(() => "")) || "";
    if (committed !== serialised) {
      console.error(
        `\n${options.out} is out of date.\n` +
          `The board design has changed since the diagram was generated. Run:\n` +
          `  bun run tools/circuit-to-wokwi/cli.ts\n`,
      );
      process.exit(1);
    }
    console.log("\nup to date: the simulation matches the board");
    return;
  }

  await Bun.write(options.out, serialised);
  console.log(`\nwrote ${options.out}`);
}

async function readExisting(path: string) {
  try {
    return await Bun.file(path).json();
  } catch {
    return undefined; // first run
  }
}

function report({ netlist, emitted, summary, validation, designProblems }: any) {
  console.log(
    `board: ${netlist.components.length} components, ${netlist.nets.length} nets\n` +
      `diagram: ${emitted.diagram.parts.length} parts, ` +
      `${emitted.diagram.connections.length} wires, ` +
      `${validation.wiredNets}/${validation.checkedNets} nets wired`,
  );

  if (emitted.skipped.length) {
    console.log("\nnot simulated, on purpose:");
    for (const { component, reason } of emitted.skipped) {
      console.log(`  ${component}: ${reason}`);
    }
  }

  if (summary.keptPositions || summary.keptHandAddedParts.length || summary.keptRoutes) {
    console.log(
      `\nkept from the existing diagram: ${summary.keptPositions} positions, ` +
        `${summary.keptRoutes} wire routes` +
        (summary.keptHandAddedParts.length
          ? `, hand-added parts: ${summary.keptHandAddedParts.join(", ")}`
          : ""),
    );
  }

  if (designProblems.length) {
    console.log("\nthe board design itself reports:");
    for (const problem of designProblems) console.log(`  ${problem.message}`);
  }
}

main().catch((error) => {
  console.error(`\n${error.message}`);
  process.exit(1);
});
