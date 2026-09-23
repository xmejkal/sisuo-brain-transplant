/**
 * Netlist -> Wokwi diagram.json.
 *
 * The one job with real thought in it is the last one: **Wokwi has no concept of a net**. It
 * knows only pin-to-pin wires, so every net has to be expanded. Where a net touches the board
 * (almost all of them do) the board's pin is the hub and every other member is wired to it,
 * which keeps wires short and readable. Otherwise the members are chained.
 */

import { PinOracle } from "../geometry";
import { BOARD, findMapping, findSkipRule, type PartMapping, wokwiPinName } from "../mapping";
import { ColumnPlacer, type PlacedPart, type Placer } from "../placement";
import type { Netlist, Problem } from "../types";

export interface WokwiPart {
  type: string;
  id: string;
  top: number;
  left: number;
  /** Degrees. Only ever set by a human, via merge.ts. */
  rotate?: number;
  attrs: Record<string, string>;
}

export type WokwiConnection = [string, string, string, string[]];

export interface WokwiDiagram {
  version: 1;
  author: string;
  editor: string;
  parts: WokwiPart[];
  connections: WokwiConnection[];
}

export interface EmitResult {
  diagram: WokwiDiagram;
  problems: Problem[];
  /** What was left out and why, so the report reads as decisions rather than omissions. */
  skipped: { component: string; reason: string }[];
  /**
   * What became of every net. The emitter is the only thing that knows why a net produced no
   * wire — a skipped part, a bad pin — so it says so rather than leaving validation to guess.
   */
  netOutcomes: NetOutcome[];
}

export interface NetOutcome {
  netId: string;
  name?: string;
  /** Endpoints on parts that exist in the diagram. */
  simulatedEndpoints: number;
  /** Endpoints dropped because their part is deliberately not simulated. */
  skippedEndpoints: number;
  /** Wires emitted for this net. */
  wires: number;
}

const GROUND_WIRE = "black";
const POWER_WIRE = "red";
const SIGNAL_WIRE = "green";

export function emitWokwiDiagram(
  netlist: Netlist,
  options: { author?: string; placer?: Placer; chipsDirectory?: string } = {},
): EmitResult {
  const problems: Problem[] = [];
  const skipped: { component: string; reason: string }[] = [];
  const oracle = new PinOracle(options.chipsDirectory);

  const mapped = mapComponents(netlist, problems, skipped);
  const placer = options.placer ?? new ColumnPlacer();
  const placements = placer.place(mapped.parts);

  const diagram: WokwiDiagram = {
    version: 1,
    author: options.author ?? "generated from board.tsx",
    editor: "wokwi",
    parts: mapped.parts.map((part) => ({
      type: part.wokwiType,
      id: part.id,
      top: placements.get(part.id)?.top ?? 0,
      left: placements.get(part.id)?.left ?? 0,
      attrs: mapped.mappingByPartId.get(part.id)?.attrs ?? {},
    })),
    connections: [],
  };

  const netOutcomes: NetOutcome[] = [];
  diagram.connections = wireNets(netlist, mapped, oracle, problems, netOutcomes);

  return { diagram, problems, skipped, netOutcomes };
}

interface MappedComponents {
  parts: PlacedPart[];
  partIdByComponent: Map<string, string>;
  mappingByComponent: Map<string, PartMapping>;
  mappingByPartId: Map<string, PartMapping>;
}

function mapComponents(
  netlist: Netlist,
  problems: Problem[],
  skipped: { component: string; reason: string }[],
): MappedComponents {
  const parts: PlacedPart[] = [];
  const partIdByComponent = new Map<string, string>();
  const mappingByComponent = new Map<string, PartMapping>();
  const mappingByPartId = new Map<string, PartMapping>();

  for (const component of netlist.components) {
    const skipRule = findSkipRule(component.name);
    if (skipRule) {
      skipped.push({ component: component.name, reason: skipRule.reason });
      continue;
    }

    const mapping = findMapping(component.name);
    if (!mapping) {
      problems.push({
        message:
          "no Wokwi part is mapped to this component. Add it to lib/mapping.ts, " +
          "or add a skip rule saying why the simulation does without it",
        context: { component: component.name },
      });
      continue;
    }

    // Wokwi ids must be unique, and are what a person reads in the editor, so the design's own
    // name is used, lowercased.
    const partId = component.name.toLowerCase();
    parts.push({ id: partId, wokwiType: mapping.wokwiType, side: mapping.side ?? "right" });
    partIdByComponent.set(component.id, partId);
    mappingByComponent.set(component.id, mapping);
    mappingByPartId.set(partId, mapping);
  }

  return { parts, partIdByComponent, mappingByComponent, mappingByPartId };
}

interface Endpoint {
  partId: string;
  pin: string;
  isBoard: boolean;
}

function wireNets(
  netlist: Netlist,
  mapped: MappedComponents,
  oracle: PinOracle,
  problems: Problem[],
  netOutcomes: NetOutcome[],
): WokwiConnection[] {
  const connections: WokwiConnection[] = [];

  for (const net of netlist.nets) {
    const endpoints: Endpoint[] = [];
    let skippedEndpoints = 0;

    for (const member of net.members) {
      const partId = mapped.partIdByComponent.get(member.componentId);
      const mapping = mapped.mappingByComponent.get(member.componentId);
      if (!partId || !mapping) {
        skippedEndpoints += 1; // a part we deliberately do not simulate
        continue;
      }

      const pin = wokwiPinName(mapping, member.pinName);
      if (pin === null) {
        skippedEndpoints += 1; // the stand-in part has no such pin, and the mapping says so
        continue;
      }
      if (!oracle.isValidPin(mapping.wokwiType, pin)) {
        problems.push({
          message:
            `"${pin}" is not a pin of ${mapping.wokwiType}. Valid pins: ` +
            oracle.pinsOf(mapping.wokwiType).join(", "),
          context: { component: partId, pin: member.pinName, net: net.name ?? net.id },
        });
        continue;
      }
      endpoints.push({ partId, pin, isBoard: mapping.wokwiType === BOARD.wokwiType });
    }

    const outcome: NetOutcome = {
      netId: net.id,
      name: net.name,
      simulatedEndpoints: endpoints.length,
      skippedEndpoints,
      wires: 0,
    };
    netOutcomes.push(outcome);

    if (endpoints.length < 2) continue; // the rest of this net went to parts we do not simulate

    const colour = wireColour(net.name);
    const hub = endpoints.find((endpoint) => endpoint.isBoard) ?? endpoints[0]!;
    for (const endpoint of endpoints) {
      if (endpoint === hub) continue;
      connections.push([
        `${hub.partId}:${hub.pin}`,
        `${endpoint.partId}:${endpoint.pin}`,
        colour,
        [],
      ]);
      outcome.wires += 1;
    }
  }

  return connections;
}

/** Wokwi's own convention: black for ground, red for power, green for everything else. */
function wireColour(netName?: string): string {
  if (!netName) return SIGNAL_WIRE;
  if (/gnd|ground/i.test(netName)) return GROUND_WIRE;
  if (/^v|power|vcc|vbat|3v3|5v/i.test(netName)) return POWER_WIRE;
  return SIGNAL_WIRE;
}
