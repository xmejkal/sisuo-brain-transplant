/**
 * Do the simulation's scenarios address parts and pins that actually exist in the diagram?
 *
 * The scenario files are the only part of the simulation that ASSERTS anything. Everything else
 * is the firmware's own account of itself; an `expect-pin` is an independent observation of a
 * wire. That makes them the highest-value assertions in the repo — and the easiest to lose,
 * because a scenario that names a part the diagram no longer contains does not fail loudly. It
 * is simply never matched.
 *
 * This exists because that happened. The board changed from a XIAO to a FireBeetle; the diagram
 * is generated, so it followed; the scenarios are hand-written, so they did not. Every
 * `expect-pin` in the suite went on addressing `part-id: xiao, name: D10` on a diagram whose
 * board is now `mcu` with pins named by GPIO number. `make check` reported that the simulation
 * matched the board, and it was telling the truth about the diagram and nothing about the
 * assertions over it.
 *
 * `make simulate` needs a Wokwi token and a network, so it is not part of `make check`. This is,
 * and it costs nothing: it is a string comparison against the generated diagram.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import type { Problem } from "../types";

/**
 * Every `part-id:`, whatever the step — a scenario driving a part that does not exist is always
 * wrong.
 */
const PART_ID = /part-id:\s*([A-Za-z0-9_.-]+)/g;

/**
 * Only `expect-pin` names a WIRED pin. `set-control` also carries a `name:`, but that names a
 * control on a custom chip — "distance" on the rangefinder, "pressed" on a button — which is a
 * knob the chip exposes, not a net. Checking those against the diagram's connections reports
 * every working scenario as broken, which is how this check was wrong on its first run.
 */
const EXPECT_PIN_INLINE = /expect-pin:\s*\{[^}]*?part-id:\s*([A-Za-z0-9_.-]+)[^}]*?name:\s*([A-Za-z0-9_.-]+)/g;
const EXPECT_PIN_BLOCK = /expect-pin:\s*\n\s*part-id:\s*([A-Za-z0-9_.-]+)\s*\n\s*name:\s*([A-Za-z0-9_.-]+)/g;

const SCENARIO_SUFFIX = ".scenario.yaml";

export interface ScenarioCheck {
  problems: Problem[];
  /** How many (part, pin) pairs were checked — so a silent zero is visible. */
  compared: number;
  files: string[];
}

/** Every scenario file under a directory, including one level of subdirectory. */
export function findScenarios(root: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(root)) {
    const path = join(root, entry);
    if (entry.endsWith(SCENARIO_SUFFIX)) found.push(path);
    else if (statSync(path).isDirectory()) {
      for (const nested of readdirSync(path)) {
        if (nested.endsWith(SCENARIO_SUFFIX)) found.push(join(path, nested));
      }
    }
  }
  return found.sort();
}

/**
 * `diagram` is the generated Wokwi project. Pins are taken from its connections rather than from
 * a part library, because that is what the scenario can actually observe.
 */
export function checkScenarioPins(diagram: any, scenarioPaths: string[]): ScenarioCheck {
  const partIds = new Set<string>((diagram.parts ?? []).map((part: any) => part.id));
  const pinsByPart = new Map<string, Set<string>>();
  for (const [from, to] of diagram.connections ?? []) {
    for (const endpoint of [from, to]) {
      const [part, pin] = String(endpoint).split(":");
      if (!part || !pin) continue;
      if (!pinsByPart.has(part)) pinsByPart.set(part, new Set());
      pinsByPart.get(part)!.add(pin);
    }
  }

  const problems: Problem[] = [];
  let compared = 0;

  for (const path of scenarioPaths) {
    const name = path.split("/").slice(-2).join("/");
    const source = readFileSync(path, "utf8");

    for (const [, partId] of source.matchAll(PART_ID)) {
      if (!partIds.has(partId)) {
        problems.push({
          message:
            `${name} drives part "${partId}", which is not in the generated diagram. ` +
            `Parts present: ${[...partIds].join(", ")}`,
        });
      }
    }

    for (const pattern of [EXPECT_PIN_INLINE, EXPECT_PIN_BLOCK]) {
      for (const [, partId, pin] of source.matchAll(pattern)) {
        if (!partIds.has(partId)) continue; // already reported above
        compared += 1;
        const pins = pinsByPart.get(partId);
        if (!pins?.has(pin)) {
          problems.push({
            message:
              `${name} asserts on ${partId}:${pin}, but nothing in the diagram is wired to ` +
              `that pin. Wired pins of ${partId}: ${[...(pins ?? [])].sort().join(", ") || "none"}`,
          });
        }
      }
    }
  }

  // A suite whose every `expect-pin` was silently deleted would otherwise pass this check.
  if (scenarioPaths.length && compared === 0) {
    problems.push({
      message:
        `found ${scenarioPaths.length} scenario file(s) but not one expect-pin among them — ` +
        `the simulation would run without observing a single wire`,
    });
  }

  return { problems, compared, files: scenarioPaths };
}
